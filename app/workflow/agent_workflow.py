"""
LlamaIndex Workflow Orchestrator
Coordinates multi-stage agent execution:
Start -> Load Agent & Query Classification -> Memory & RAG -> Tool Planning
-> Permission Guard -> Multi-MCP Tool Execution -> Sub-Agent Condensation
-> Context Management -> LLM Synthesis -> Final Prompt Audit Logging -> Save State -> Stop
"""
import os
import re
import time
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path

from llama_index.core.workflow import Workflow, step, StartEvent, StopEvent
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.agent import Agent, AgentTool
from app.models.execution import Execution, ExecutionStep
from app.mcp.client_manager import mcp_client_manager, ToolPermissionError
from app.rag.embeddings import embeddings_provider
from app.rag.vector_store import vector_store
from app.memory.memory_manager import memory_manager
from app.workflow.subagent import TemporaryResearchSubAgent
from app.workflow.llm_provider import llm_provider
from app.services.progress import progress_bus
from app.services.query_classifier import query_classifier
from app.workflow.events import (
    AgentLoadedEvent,
    MemoryAndRAGLoadedEvent,
    ToolPlanGeneratedEvent,
    ToolsExecutedEvent,
    ContextCondensedEvent
)


def redact_secrets(text: str) -> str:
    """Scrub sensitive credentials, passwords, or API keys from logs and prompt files."""
    patterns = [
        (r'sk-[a-zA-Z0-9_\-]{20,}', '[REDACTED_API_KEY]'),
        (r'gsk_[a-zA-Z0-9_\-]{20,}', '[REDACTED_GROQ_KEY]'),
        (r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer [REDACTED_TOKEN]'),
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password="[REDACTED]"'),
        (r'secret["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'secret="[REDACTED]"')
    ]
    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def _rag_query_variants(query: str) -> List[str]:
    """Build focused retrieval queries for multi-company/document questions."""
    variants = [query]
    years = re.findall(r"\b20\d{2}\b", query)
    stop_words = {
        "what", "was", "were", "the", "and", "or", "with", "compare",
        "between", "versus", "how", "much", "revenue", "total", "in",
        "for", "from", "this", "that", "year"
    }
    entities = []
    query_lower = query.lower()
    # Match terms against indexed filenames as well as title-cased words. This
    # keeps retrieval working when users type "apple" and "google" in lower case.
    indexed_terms = set()
    for metadata in vector_store.metadata_map.values():
        filename = metadata.get("filename", "")
        indexed_terms.update(re.findall(r"[A-Za-z][A-Za-z0-9&.-]{2,}", filename))

    candidates = re.findall(r"\b[A-Za-z][A-Za-z0-9&.-]{2,}\b", query)
    candidates.extend(indexed_terms)
    for token in candidates:
        normalized = token.strip(".,:;()[]")
        if (
            normalized.lower() in query_lower
            and normalized.lower() not in stop_words
            and normalized not in years
            and normalized.lower() not in {item.lower() for item in entities}
        ):
            entities.append(normalized)

    for entity in entities:
        year_text = " ".join(years)
        variants.append(f"{entity} total net sales revenue {year_text}".strip())

    return variants


def _retrieve_rag_chunks(query: str, kb_id: str, top_k: int = 8) -> List[Dict[str, Any]]:
    """Merge focused searches so comparisons include each source document."""
    merged: Dict[tuple, Dict[str, Any]] = {}
    variants = _rag_query_variants(query)
    entities = [variant.split(" ", 1)[0] for variant in variants[1:]]
    for variant in variants:
        query_vector = embeddings_provider.get_embedding(variant)
        for chunk in vector_store.search(query_vector=query_vector, top_k=4, kb_id=kb_id):
            key = (chunk.get("document_id"), chunk.get("chunk_index"))
            previous = merged.get(key)
            if previous is None or chunk.get("score", 0.0) > previous.get("score", 0.0):
                merged[key] = chunk

    ranked = sorted(merged.values(), key=lambda item: item.get("score", 0.0), reverse=True)

    # Reserve slots for each uploaded document explicitly named in the query.
    # This prevents a comparison from returning only the strongest side.
    selected = []
    selected_keys = set()
    for entity in entities:
        matching = [
            item for item in ranked
            if entity.lower() in item.get("filename", "").lower()
        ]
        for item in matching[:2]:
            key = (item.get("document_id"), item.get("chunk_index"))
            if key not in selected_keys:
                selected.append(item)
                selected_keys.add(key)

    for item in ranked:
        key = (item.get("document_id"), item.get("chunk_index"))
        if key not in selected_keys:
            selected.append(item)
            selected_keys.add(key)
        if len(selected) >= top_k:
            break

    return selected[:top_k]


class AgentOrchestratorWorkflow(Workflow):
    """
    Enterprise LlamaIndex Workflow orchestrating dynamic multi-MCP agents.
    """

    @step
    async def step_load_agent(self, ev: StartEvent) -> AgentLoadedEvent:
        """Step 1: Load agent configuration, permissions, and classify user query."""
        t0 = time.time()
        self._start_time = t0
        agent_id = ev.get("agent_id")
        query = ev.get("query")
        conversation_id = ev.get("conversation_id")
        execution_id = ev.get("execution_id", f"exec_{uuid.uuid4().hex[:12]}")
        await progress_bus.publish(execution_id, "Loading the selected agent and its permissions", "agent")

        # Run Smart Query Classification
        classification = query_classifier.classify(query)
        classification_dict = classification.model_dump()
        entity_text = ", ".join(classification.target_entities) or "no named entities"
        await progress_bus.publish(
            execution_id,
            f"Classified as {classification.query_type}; targets: {entity_text}",
            "classification"
        )

        db: Session = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.agent_id == agent_id, Agent.enabled == True).first()
            if not agent:
                raise ValueError(f"Agent with ID '{agent_id}' not found or disabled.")

            allowed_tools = [t.tool_name for t in agent.tools if t.enabled]

            agent_config = {
                "agent_id": agent.agent_id,
                "agent_name": agent.agent_name,
                "category": getattr(agent, "category", "General"),
                "description": agent.description,
                "system_prompt": agent.system_prompt,
                "playbook": agent.playbook,
                "model": agent.model,
                "temperature": agent.temperature,
                "memory_configuration": agent.memory_configuration or {},
                "workflow_configuration": agent.workflow_configuration or {},
                "allowed_tools": allowed_tools
            }

            # Create Execution record in DB
            execution_rec = Execution(
                execution_id=execution_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                query=query,
                status="running"
            )
            db.add(execution_rec)

            # Log Step 1 in trace (Agent Load & Query Classification)
            step_rec = ExecutionStep(
                execution_id=execution_id,
                step_number=1,
                step_name="load_agent_and_query_classification",
                input_payload={"agent_id": agent_id, "query": query},
                output_payload={
                    "agent_name": agent.agent_name,
                    "category": agent_config["category"],
                    "allowed_tools": allowed_tools,
                    "query_type": classification.query_type,
                    "target_entities": classification.target_entities,
                    "intent": classification.intent_summary
                },
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()

        finally:
            db.close()

        return AgentLoadedEvent(
            agent_id=agent_id,
            agent_config=agent_config,
            query=query,
            conversation_id=conversation_id,
            execution_id=execution_id,
            query_classification=classification_dict
        )

    @step
    async def step_load_memory_and_rag(self, ev: AgentLoadedEvent) -> MemoryAndRAGLoadedEvent:
        """Step 2: Retrieve short-term dialogue, semantic long-term memory, and FAISS RAG context."""
        await progress_bus.publish(ev.execution_id, "Retrieving conversation memory and relevant knowledge", "memory")
        t0 = time.time()
        agent_cfg = ev.agent_config
        db: Session = SessionLocal()
        retrieved_chunks = []
        short_term_history = []
        long_term_facts = []

        try:
            # 1. Memory loading
            mem_cfg = agent_cfg.get("memory_configuration", {})
            if mem_cfg.get("short_term", True) or mem_cfg.get("long_term", True):
                # Target entity from classification
                target_entity = None
                if ev.query_classification and ev.query_classification.get("target_entities"):
                    first_ent = ev.query_classification["target_entities"][0]
                    target_entity = f"customer:{first_ent}"

                mem_data = memory_manager.load_memory_context(
                    db=db,
                    conversation_id=ev.conversation_id,
                    query=ev.query,
                    entity_key=target_entity
                )
                if mem_cfg.get("short_term", True):
                    short_term_history = mem_data["short_term_history"]
                if mem_cfg.get("long_term", True):
                    long_term_facts = mem_data["long_term_facts"]

            # 2. Knowledge Base RAG via FAISS (Conditional Retrieval)
            wf_cfg = agent_cfg.get("workflow_configuration", {})
            target_kb = wf_cfg.get("knowledge_base", "customer_docs")
            is_action_intent = bool(ev.query_classification and ev.query_classification.get("is_action_intent"))
            
            # Skip RAG retrieval for pure CRUD/action requests to avoid context contamination
            if wf_cfg.get("rag_enabled", True) and not is_action_intent:
                retrieved_chunks = _retrieve_rag_chunks(
                    query=ev.query,
                    kb_id=target_kb,
                    top_k=8
                )

            await progress_bus.publish(
                ev.execution_id,
                f"Retrieved {len(retrieved_chunks)} knowledge chunks from {target_kb if not is_action_intent else 'N/A (action request)'}; "
                f"memory: {len(short_term_history)} recent turns and {len(long_term_facts)} long-term facts",
                "retrieval"
            )

            # Record step in trace
            step_rec = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=2,
                step_name="memory_and_rag_retrieval",
                input_payload={"query": ev.query, "kb_id": wf_cfg.get("knowledge_base"), "is_action_intent": is_action_intent},
                output_payload={
                    "short_term_turns": len(short_term_history),
                    "long_term_facts_count": len(long_term_facts),
                    "rag_chunks_retrieved": len(retrieved_chunks),
                    "sources": [c["filename"] for c in retrieved_chunks]
                },
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()

        finally:
            db.close()

        return MemoryAndRAGLoadedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=short_term_history,
            long_term_facts=long_term_facts,
            retrieved_chunks=retrieved_chunks,
            query_classification=ev.query_classification
        )

    @step
    async def step_plan_tools(self, ev: MemoryAndRAGLoadedEvent) -> ToolPlanGeneratedEvent:
        """Step 3: Tool Planning across registered MCP servers."""
        await progress_bus.publish(ev.execution_id, "Planning the next actions from the agent configuration", "planning")
        t0 = time.time()
        agent_cfg = ev.agent_config
        allowed_tools = agent_cfg.get("allowed_tools", [])

        # Get discovered tools permitted for this agent
        permitted_tools = await mcp_client_manager.get_tools_for_agent(allowed_tools)

        # Generate tool plan
        planned_tools = llm_provider.plan_tools(
            query=ev.query,
            available_tools=permitted_tools,
            knowledge_chunks=ev.retrieved_chunks
        )
        planned_names = ", ".join(tool["tool_name"] for tool in planned_tools) or "no MCP tools required"
        await progress_bus.publish(
            ev.execution_id,
            f"Planned {len(planned_tools)} tool call(s): {planned_names}",
            "planning"
        )

        db: Session = SessionLocal()
        try:
            step_rec = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=3,
                step_name="tool_planning",
                input_payload={"available_tools_count": len(permitted_tools)},
                output_payload={"planned_tools": planned_tools},
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()
        finally:
            db.close()

        return ToolPlanGeneratedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            retrieved_chunks=ev.retrieved_chunks,
            planned_tools=planned_tools,
            query_classification=ev.query_classification
        )

    @step
    async def step_execute_tools(self, ev: ToolPlanGeneratedEvent) -> ToolsExecutedEvent:
        """Step 4 & 5: Permission Check and Multi-MCP Tool Execution (CRM + Analytics)."""
        agent_cfg = ev.agent_config
        allowed_tools = agent_cfg.get("allowed_tools", [])
        tool_results = []
        completed_plan_ids = set()
        failed_plan_ids = set()
        db: Session = SessionLocal()

        current_step_num = 4
        try:
            for plan in ev.planned_tools:
                t0 = time.time()
                tool_name = plan["tool_name"]
                arguments = plan.get("arguments", {})
                plan_id = plan.get("id", f"step_{current_step_num}")
                dependencies = plan.get("depends_on", [])
                blocked_dependencies = [dep for dep in dependencies if dep in failed_plan_ids]
                if blocked_dependencies:
                    err_msg = f"Skipped {tool_name}: prerequisite step(s) failed: {blocked_dependencies}"
                    db.add(ExecutionStep(
                        execution_id=ev.execution_id, step_number=current_step_num,
                        step_name=f"dependency_blocked:{tool_name}", tool_name=tool_name,
                        input_payload=arguments, output_payload={"error": err_msg},
                        duration_ms=0, status="skipped", error_message=err_msg))
                    db.commit()
                    failed_plan_ids.add(plan_id)
                    current_step_num += 1
                    continue
                await progress_bus.publish(ev.execution_id, f"Calling MCP tool: {tool_name}", "mcp")

                # Permission Check
                is_permitted = mcp_client_manager.check_tool_permission(tool_name, allowed_tools)
                if not is_permitted:
                    err_msg = f"Permission Denied: Agent '{ev.agent_id}' is not authorized to execute tool '{tool_name}'."
                    step_rec = ExecutionStep(
                        execution_id=ev.execution_id,
                        step_number=current_step_num,
                        step_name=f"permission_check_failed:{tool_name}",
                        tool_name=tool_name,
                        input_payload=arguments,
                        output_payload={"error": err_msg},
                        duration_ms=round((time.time() - t0) * 1000, 2),
                        status="failed",
                        error_message=err_msg
                    )
                    db.add(step_rec)
                    db.commit()
                    await progress_bus.publish(
                        ev.execution_id,
                        f"Blocked unauthorized tool {tool_name}",
                        "permission"
                    )
                    current_step_num += 1
                    failed_plan_ids.add(plan_id)
                    continue

                # Multi-MCP Execution
                res = await mcp_client_manager.execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    allowed_tools=allowed_tools
                )
                tool_results.append(res)

                step_rec = ExecutionStep(
                    execution_id=ev.execution_id,
                    step_number=current_step_num,
                    step_name=f"execute_mcp_tool:{tool_name}",
                    tool_name=tool_name,
                    input_payload=arguments,
                    output_payload=res.get("result", {"error": res.get("error")}),
                    duration_ms=res.get("duration_ms", 0.0),
                    status="completed" if res.get("success") else "failed",
                    error_message=res.get("error")
                )
                db.add(step_rec)
                db.commit()
                result_state = "completed" if res.get("success") else "failed"
                if res.get("success"):
                    completed_plan_ids.add(plan_id)
                else:
                    failed_plan_ids.add(plan_id)
                detail = res.get("error") or "result received"
                await progress_bus.publish(
                    ev.execution_id,
                    f"{tool_name} {result_state} in {res.get('duration_ms', 0.0)} ms ({detail})",
                    "tool"
                )
                current_step_num += 1

        finally:
            db.close()

        return ToolsExecutedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            retrieved_chunks=ev.retrieved_chunks,
            tool_results=tool_results,
            query_classification=ev.query_classification
        )

    @step
    async def step_subagent_and_context(self, ev: ToolsExecutedEvent) -> ContextCondensedEvent:
        """Step 6: Temporary Sub-Agent Result Condensation & Context Management."""
        await progress_bus.publish(ev.execution_id, "Combining MCP results with retrieved context", "context")
        t0 = time.time()
        agent_cfg = ev.agent_config
        wf_cfg = agent_cfg.get("workflow_configuration", {})

        condensed_summary = ""
        if wf_cfg.get("enable_subagents", True):
            subagent = TemporaryResearchSubAgent()
            subagent_res = await subagent.condense_results(
                query=ev.query,
                tool_results=ev.tool_results,
                knowledge_chunks=ev.retrieved_chunks
            )
            condensed_summary = subagent_res["condensed_summary"]
        else:
            condensed_summary = "\n".join([f"Tool {r['tool_name']}: {r.get('result')}" for r in ev.tool_results])

        await progress_bus.publish(
            ev.execution_id,
            f"Context ready: {len(ev.tool_results)} tool result(s), "
            f"{len(ev.retrieved_chunks)} knowledge chunk(s), {len(condensed_summary)} summary characters",
            "context"
        )

        db: Session = SessionLocal()
        try:
            curr_count = db.query(ExecutionStep).filter(ExecutionStep.execution_id == ev.execution_id).count()
            step_rec = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=curr_count + 1,
                step_name="subagent_context_condensation",
                input_payload={"raw_tools_count": len(ev.tool_results)},
                output_payload={"summary_length": len(condensed_summary)},
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()
        finally:
            db.close()

        return ContextCondensedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            retrieved_chunks=ev.retrieved_chunks,
            condensed_tool_summary=condensed_summary,
            raw_tool_results=ev.tool_results,
            query_classification=ev.query_classification
        )

    @step
    async def step_synthesize_and_save(self, ev: ContextCondensedEvent) -> StopEvent:
        """Step 7: LLM Synthesis, final_prompt.txt Audit Logging, DB State Persistence, and StopEvent."""
        t0 = time.time()
        agent_cfg = ev.agent_config
        await progress_bus.publish(
            ev.execution_id,
            f"Synthesizing from {len(ev.raw_tool_results)} tool result(s) and "
            f"{len(ev.retrieved_chunks)} knowledge chunk(s)",
            "synthesis"
        )

        # 1. Synthesize final answer with streaming support
        tokens_streamed = False

        def handle_token(delta: str):
            nonlocal tokens_streamed
            tokens_streamed = True
            progress_bus.publish_token(ev.execution_id, delta)

        final_answer = await llm_provider.synthesize_response_async(
            agent_name=agent_cfg["agent_name"],
            system_prompt=agent_cfg["system_prompt"],
            playbook=agent_cfg["playbook"],
            query=ev.query,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            condensed_tool_summary=ev.condensed_tool_summary,
            retrieved_chunks=ev.retrieved_chunks,
            model=agent_cfg.get("model", "gpt-4o-mini"),
            temperature=agent_cfg.get("temperature", 0.2),
            on_token=handle_token
        )

        # If live LLM streaming was not active (e.g. deterministic local mode), stream tokens in chunks
        if not tokens_streamed and final_answer:
            words = re.findall(r"\S+\s*", final_answer)
            chunk_size = 4
            for i in range(0, len(words), chunk_size):
                chunk = "".join(words[i:i + chunk_size])
                progress_bus.publish_token(ev.execution_id, chunk)
                await asyncio.sleep(0.005)

        # 2. Build and write final_prompt.txt (sanitized audit log)
        prompt_log_file = settings.EXECUTIONS_LOG_DIR / f"{ev.execution_id}_prompt.txt"

        prompt_content = f"""================================================================================
ORCHESTRATED MULTI-MCP AGENT EXECUTION AUDIT LOG
Execution ID: {ev.execution_id}
Agent ID:     {ev.agent_id} ({agent_cfg['agent_name']})
Category:     {agent_cfg.get('category', 'General')}
Model:        {agent_cfg.get('model', 'gpt-4o-mini')} | Temperature: {agent_cfg.get('temperature', 0.2)}
Timestamp:    {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}
================================================================================

[QUERY CLASSIFICATION]
{json_dumps(ev.query_classification) if ev.query_classification else "None"}

[AGENT SYSTEM PROMPT]
{agent_cfg['system_prompt']}

[AGENT PLAYBOOK]
{agent_cfg['playbook']}

[ALLOWED MCP TOOLS]
{agent_cfg.get('allowed_tools', [])}

[USER QUERY]
{ev.query}

[SHORT-TERM CONVERSATION TURNS]
{ev.short_term_history}

[LONG-TERM RETRIEVED MEMORY FACTS]
{ev.long_term_facts}

[RAG KNOWLEDGE BASE CHUNKS]
{[f"File: {c['filename']} (score: {c['score']})" for c in ev.retrieved_chunks]}

[TOOL CALLS & RESULTS]
{ev.condensed_tool_summary}

[FINAL SYNTHESIZED ANSWER]
{final_answer}
================================================================================
"""
        sanitized_prompt_log = redact_secrets(prompt_content)
        with open(prompt_log_file, "w", encoding="utf-8") as f:
            f.write(sanitized_prompt_log)

        # 3. Update Database Records
        db: Session = SessionLocal()
        total_duration_ms = 0.0
        try:
            curr_count = db.query(ExecutionStep).filter(ExecutionStep.execution_id == ev.execution_id).count()
            synth_step = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=curr_count + 1,
                step_name="llm_final_synthesis",
                input_payload={"model": agent_cfg.get("model")},
                output_payload={"answer_preview": final_answer[:150] + "..."},
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(synth_step)

            exec_rec = db.query(Execution).filter(Execution.execution_id == ev.execution_id).first()
            if exec_rec:
                exec_rec.final_answer = final_answer
                exec_rec.status = "completed"
                exec_rec.prompt_file_path = str(prompt_log_file)
                total_duration_ms = round((time.time() - getattr(self, "_start_time", t0)) * 1000, 2)
                exec_rec.duration_ms = total_duration_ms

            if ev.conversation_id:
                memory_manager.save_turn(
                    db=db,
                    conversation_id=ev.conversation_id,
                    agent_id=ev.agent_id,
                    user_query=ev.query,
                    assistant_response=final_answer
                )

            db.commit()

        finally:
            db.close()

        sources = [
            {
                "document_name": c["filename"],
                "kb_id": c["kb_id"],
                "chunk_index": c["chunk_index"],
                "similarity_score": c["score"],
                "snippet": c["content"][:200] + "..."
            }
            for c in ev.retrieved_chunks
        ]

        tools_used = [r.get("tool_name") for r in ev.raw_tool_results if r.get("tool_name")]

        return StopEvent(
            result={
                "execution_id": ev.execution_id,
                "agent_id": ev.agent_id,
                "conversation_id": ev.conversation_id,
                "answer": final_answer,
                "sources": sources,
                "tools_used": tools_used,
                "query_classification": ev.query_classification,
                "status": "completed",
                "duration_ms": round(total_duration_ms, 2),
                "prompt_file": str(prompt_log_file)
            }
        )


def json_dumps(data: Any) -> str:
    import json
    try:
        return json.dumps(data, indent=2)
    except Exception:
        return str(data)


def create_agent_workflow() -> AgentOrchestratorWorkflow:
    return AgentOrchestratorWorkflow(timeout=60.0)
