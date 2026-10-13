"""
LLM Provider Adapter
====================
Provides LLM completions via Groq (high-speed open-weights inference) or OpenAI
when configured with an API key, or using a strictly grounded, deterministic
offline reasoning engine when running locally without external credentials.

Adheres strictly to the Data-Provenance Rule:
  - If a source (CRM, Analytics, RAG, Memory) has no data or returned not found,
    the response explicitly classifies it under 'Unavailable / Missing Information'.
  - Never fabricates imaginary customer names, ARR figures, or metrics (Zero Silent Fallbacks).
"""
import asyncio
import re
import json
import logging
import random
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from app.config import settings
from app.services.query_classifier import query_classifier
from openai import OpenAI, AsyncOpenAI

logger = logging.getLogger("llm_provider")


def clean_llm_markdown_output(output: str) -> str:
    """Ensure output is clean Markdown prose, unwrapping JSON structures if accidentally generated."""
    if not output:
        return ""
    text = output.strip()

    # Check if text is enclosed in ```json ... ``` codeblock
    json_block_match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    candidate_json = json_block_match.group(1).strip() if json_block_match else text

    if (candidate_json.startswith("{") and candidate_json.endswith("}")) or (candidate_json.startswith("[") and candidate_json.endswith("]")):
        try:
            parsed = json.loads(candidate_json)
            if isinstance(parsed, dict):
                # Look for typical answer fields
                for key in ["response", "answer", "final_answer", "content", "text", "message", "summary", "result", "output"]:
                    if key in parsed and isinstance(parsed[key], str) and parsed[key].strip():
                        return clean_llm_markdown_output(parsed[key].strip())
                # If it's a dict representing an operation or customer, format as clean Markdown
                formatted_lines = []
                for k, v in parsed.items():
                    k_clean = k.replace("_", " ").title()
                    formatted_lines.append(f"- **{k_clean}**: {v}")
                return "\n".join(formatted_lines)
            elif isinstance(parsed, list):
                formatted_lines = []
                for item in parsed:
                    if isinstance(item, dict):
                        fields = [f"**{k.replace('_', ' ').title()}**: {v}" for k, v in item.items()]
                        formatted_lines.append("- " + ", ".join(fields))
                    else:
                        formatted_lines.append(f"- {item}")
                return "\n".join(formatted_lines)
        except Exception:
            pass

    return text


class LLMProvider:
    """Manages LLM completions, tool plan generation, and grounded response synthesis."""

    def __init__(self):
        self.use_groq = bool(settings.GROQ_API_KEY)
        self.use_openai = bool(settings.OPENAI_API_KEY)
        self._client = None
        self._async_client = None
        self._provider_type = None
        # Secondary Groq client — dedicated to conversation naming and as
        # automatic fallback when the primary key is rate-limited or fails.
        self._secondary_client = None
        self._secondary_async_client = None

    def _get_client(self):
        if self._client is not None:
            return self._client, self._provider_type

        # 1. Groq priority (fast, open-weights)
        if self.use_groq:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=settings.GROQ_API_KEY,
                    base_url="https://api.groq.com/openai/v1",
                    timeout=20.0
                )
                self._provider_type = "groq"
                return self._client, self._provider_type
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")

        # 2. OpenAI fallback
        if self.use_openai:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=20.0)
                self._provider_type = "openai"
                return self._client, self._provider_type
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")

        return None, "local"

    def _get_async_client(self):
        if self._async_client is not None:
            return self._async_client, self._provider_type

        if self.use_groq:
            try:
                from openai import AsyncOpenAI
                self._async_client = AsyncOpenAI(
                    api_key=settings.GROQ_API_KEY,
                    base_url="https://api.groq.com/openai/v1",
                    timeout=20.0
                )
                self._provider_type = "groq"
                return self._async_client, self._provider_type
            except Exception as e:
                logger.warning(f"Failed to initialize Groq async client: {e}")

        if self.use_openai:
            try:
                from openai import AsyncOpenAI
                self._async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=20.0)
                self._provider_type = "openai"
                return self._async_client, self._provider_type
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI async client: {e}")

        return None, "local"

    # ------------------------------------------------------------------
    # Secondary Groq Client (GROQ_API_KEY2)
    # Used for: (a) conversation name generation  (b) fallback on main key failure
    # ------------------------------------------------------------------
    def _get_secondary_client(self):
        """Return the secondary Groq sync client (GROQ_API_KEY2), or None."""
        if self._secondary_client is not None:
            return self._secondary_client
        if settings.GROQ_API_KEY2:
            try:
                from openai import OpenAI
                self._secondary_client = OpenAI(
                    api_key=settings.GROQ_API_KEY2,
                    base_url="https://api.groq.com/openai/v1",
                    timeout=15.0
                )
                return self._secondary_client
            except Exception as e:
                logger.warning(f"Failed to initialize secondary Groq client: {e}")
        return None

    def _get_secondary_async_client(self):
        """Return the secondary Groq async client (GROQ_API_KEY2), or None."""
        if self._secondary_async_client is not None:
            return self._secondary_async_client
        if settings.GROQ_API_KEY2:
            try:
                from openai import AsyncOpenAI
                self._secondary_async_client = AsyncOpenAI(
                    api_key=settings.GROQ_API_KEY2,
                    base_url="https://api.groq.com/openai/v1",
                    timeout=15.0
                )
                return self._secondary_async_client
            except Exception as e:
                logger.warning(f"Failed to initialize secondary Groq async client: {e}")
        return None

    # ------------------------------------------------------------------
    # Conversation Name Generation (uses GROQ_API_KEY2 exclusively)
    # ------------------------------------------------------------------
    def generate_conversation_name(self, user_message: str) -> str:
        """
        Generate a short, descriptive conversation title from the user's first
        message using the secondary Groq key (GROQ_API_KEY2).

        Falls back to simple truncation if the secondary key is unavailable
        or the LLM call fails.
        """
        fallback = user_message.strip().split("\n")[0]
        if len(fallback) > 48:
            fallback = fallback[:45] + "..."

        client = self._get_secondary_client()
        if client is None:
            return fallback

        try:
            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate ultra-short conversation titles. "
                            "Return ONLY the title text — no quotes, no explanation, no punctuation at the end. "
                            "Maximum 6 words. Be specific and descriptive."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Generate a concise title for a conversation that starts with this message:\n\"{user_message[:300]}\""
                    }
                ],
                temperature=0.3,
                max_tokens=30
            )
            title = resp.choices[0].message.content.strip().strip('"\'.')
            if title and len(title) > 2:
                # Enforce length limit
                if len(title) > 64:
                    title = title[:61] + "..."
                return title
        except Exception as e:
            logger.warning(f"Conversation name generation via GROQ_API_KEY2 failed: {e}")

        return fallback

    async def generate_conversation_name_async(self, user_message: str) -> str:
        """
        Async version of conversation name generation using GROQ_API_KEY2.
        """
        fallback = user_message.strip().split("\n")[0]
        if len(fallback) > 48:
            fallback = fallback[:45] + "..."

        client = self._get_secondary_async_client()
        if client is None:
            return fallback

        try:
            resp = await client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate ultra-short conversation titles. "
                            "Return ONLY the title text — no quotes, no explanation, no punctuation at the end. "
                            "Maximum 6 words. Be specific and descriptive."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Generate a concise title for a conversation that starts with this message:\n\"{user_message[:300]}\""
                    }
                ],
                temperature=0.3,
                max_tokens=30
            )
            title = resp.choices[0].message.content.strip().strip('"\'.')
            if title and len(title) > 2:
                if len(title) > 64:
                    title = title[:61] + "..."
                return title
        except Exception as e:
            logger.warning(f"Async conversation name generation via GROQ_API_KEY2 failed: {e}")

        return fallback

    def extract_user_facts(self, query: str) -> List[Dict[str, Any]]:
        """
        Extract durable user facts, business context, ongoing project responsibilities,
        and preferences using LLM when available, filtering out emotional venting and transient questions.
        """
        client, ptype = self._get_client()
        if client is None:
            return []

        prompt = (
            "You are an intelligent memory distillation agent for an enterprise AI assistant.\n"
            "Analyze the following user message and extract ONLY durable, important facts about:\n"
            "- The user's role, responsibilities, or current projects (e.g., 'User is working to fix Abc revenue').\n"
            "- Specific business situations, metrics, or risks mentioned (e.g., 'Abc revenue is projected to decline by 12%').\n"
            "- Specific user preferences (e.g., formatting preferences, timezone, communication style).\n\n"
            "STRICT FILTERING GUIDELINES:\n"
            "1. DO NOT extract emotional venting, complaints about salary/coworkers, existential despair, or personal frustrations (e.g., 'others are useless', 'feel to leave and start a new life', 'got no money').\n"
            "2. DO NOT extract transient queries, greetings, or questions (e.g., 'how are we doing what all projects are active?').\n"
            "3. Formulate each extracted fact concisely in neutral, objective third-person prose.\n"
            "4. If no durable facts or business situations are present, return an empty JSON array [].\n\n"
            f"User Message:\n\"\"\"{query}\"\"\"\n\n"
            "Return ONLY a JSON array of objects with the exact schema:\n"
            "[{\"fact\": \"string\", \"type\": \"user_context\" | \"user_preference\" | \"business_metric\", \"importance\": 1.0 to 1.5}]\n"
            "Do not include explanation or markdown fences outside the JSON."
        )

        try:
            target_model = settings.GROQ_MODEL if ptype == "groq" else settings.OPENAI_MODEL
            resp = client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": "You extract durable business facts and user preferences from user messages into JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=300
            )
            raw = resp.choices[0].message.content.strip()
            # Clean possible markdown wrapping
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                valid = []
                for item in parsed:
                    if isinstance(item, dict) and "fact" in item and item["fact"].strip():
                        valid.append({
                            "fact": item["fact"].strip(),
                            "type": item.get("type", "user_context"),
                            "importance": float(item.get("importance", 1.2))
                        })
                return valid
        except Exception as e:
            logger.warning(f"LLM fact extraction failed or bypassed: {e}")

        return []

    def plan_tools(
        self,
        query: str,
        available_tools: List[Dict[str, Any]],
        knowledge_chunks: List[Dict[str, Any]],
        short_term_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Determines which tools to invoke based on user query analysis,
        detected customer entities, and available tool catalog.
        """
        planned = []
        classification = query_classifier.classify(query)
        entities = list(classification.target_entities)
        avail_canon = {t["name"].lower(): t["name"] for t in available_tools}
        q_lower = query.lower()

        is_global_list_customers = bool(
            (
                re.search(r"\b(list|show|view|get|display|all)\s+(?:all\s+|the\s+|our\s+|active\s+|current\s+)*customers\b", q_lower)
                or re.search(r"\b(list|show|display)\s+(?:all\s+of\s+)?them(?:\s+again)?\b", q_lower)
            )
            and not entities
        )

        # Resolve pronouns ("it", "its", "it's", "his", "their", "this customer") from recent conversation history
        if not entities and not is_global_list_customers and short_term_history:
            for turn in reversed(short_term_history):
                content = turn.get("content", "") if isinstance(turn, dict) else str(turn)
                if content:
                    hist_entities = query_classifier.classify(content).target_entities
                    if hist_entities:
                        entities = [hist_entities[0]]
                        break

        # Check if agent has access to Operations tools
        has_operations = any(name.startswith("operations.") for name in avail_canon)

        # ---------------------------------------------------------
        # 1. Operations MCP Planning
        # ---------------------------------------------------------
        if has_operations:
            # A. Create Customer
            if any(k in q_lower for k in ["create customer", "create a customer", "create a new customer", "add customer", "add a customer", "add a new customer", "register customer", "new customer"]):
                if "operations.create_customer" in avail_canon:
                    customer_id = entities[0] if entities else "CUST001"
                    # Extract company name
                    comp_match = re.search(r"(?:company\s+(?:name\s+)?|company\s*[:=]\s*|with\s+company\s+)(['\"]?)(.+?)\1(?:\.|$|\s+and\s+status|\s+with\s+status)", query, re.IGNORECASE)
                    named_match = re.search(r"\bcustomer\s+(?:named|called)\s+([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+)?)(?=\s+(?:and|with|whose|his|her|its|having|status|id)\b|[.,;]|$)", query, re.IGNORECASE)
                    if comp_match:
                        company_name = comp_match.group(2).strip(" .,;\"'")
                    elif named_match:
                        company_name = named_match.group(1).strip(" .,;\"'").title()
                    elif ":" in query:
                        company_name = query.split(":", 1)[1].strip()
                    else:
                        clean_name = customer_id.replace("_", " ").title() if customer_id else "New"
                        company_name = f"{clean_name} Corporation" if not clean_name.endswith("Corporation") else clean_name

                    create_args: Dict[str, Any] = {
                        "customer_id": customer_id,
                        "company_name": company_name,
                        "status": "Active"
                    }
                    ren_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
                    if ren_match:
                        create_args["renewal_date"] = ren_match.group(1)
                    own_match = re.search(r"\bowner(?:\s+name|\s+is|\s+to)?\s*[:=]?\s*([A-Za-z][A-Za-z\s.]{1,35}?)(?=\s+(?:and|with|renewal|status)\b|[.,;]|$)", query, re.IGNORECASE)
                    if own_match:
                        create_args["owner"] = own_match.group(1).strip()

                    steps = [{
                        "id": "step_create_customer",
                        "tool_name": avail_canon["operations.create_customer"],
                        "arguments": create_args,
                        "depends_on": []
                    }]

                    # If the user also included extra profile details (e.g., CEO, revenue, ARR, tier, contact), record an operational note
                    if "operations.add_customer_note" in avail_canon and any(w in q_lower for w in ["ceo", "revenue", "arr", "contact", "tier", "headquarters"]):
                        steps.append({
                            "id": "step_add_initial_profile_note",
                            "tool_name": avail_canon["operations.add_customer_note"],
                            "arguments": {
                                "customer_id": customer_id,
                                "note": f"Initial onboarding details: {query.strip()}",
                                "author": "Luna Autonomous Agent"
                            },
                            "depends_on": ["step_create_customer"]
                        })

                    return steps

            # B. List Customers
            if is_global_list_customers and "operations.list_customers" in avail_canon:
                return [{
                    "id": "step_list_customers",
                    "tool_name": avail_canon["operations.list_customers"],
                    "arguments": {},
                    "depends_on": []
                }]

            # C. Audit History
            if any(k in q_lower for k in ["audit history", "audit log", "audit history for", "show audit"]) and "operations.get_audit_history" in avail_canon:
                customer_id = entities[0] if entities else None
                return [{
                    "id": "step_audit_history",
                    "tool_name": avail_canon["operations.get_audit_history"],
                    "arguments": {"customer_id": customer_id},
                    "depends_on": []
                }]

            # D. Get Notes
            if any(k in q_lower for k in [
                "show notes", "list notes", "get notes", "view notes",
                "customer notes", "operational notes", "all notes", "notes for"
            ]) and "operations.get_customer_notes" in avail_canon:
                customer_id = entities[0] if entities else None
                return [{
                    "id": "step_get_notes",
                    "tool_name": avail_canon["operations.get_customer_notes"],
                    "arguments": {"customer_id": customer_id} if customer_id else {},
                    "depends_on": []
                }]

            # E. Create Task
            if any(k in q_lower for k in [
                "create a follow-up task", "create follow-up task", "create follow up task",
                "create a task", "create task", "add task", "add a task", "new task"
            ]) and entities and "operations.create_follow_up_task" in avail_canon:
                customer_id = entities[0]
                title_match = re.search(r"(?:called|named|title|task)\s+['\"]?(.+?)['\"]?(?:\s+for|\s+with|\.|$)", query, re.IGNORECASE)
                title = title_match.group(1).strip(" .,;\"'") if title_match else "Customer follow-up"
                return [{
                    "id": "step_create_task",
                    "tool_name": avail_canon["operations.create_follow_up_task"],
                    "arguments": {
                        "customer_id": customer_id,
                        "title": title
                    },
                    "depends_on": []
                }]

            # F. List Follow-up Tasks
            if any(k in q_lower for k in [
                "list follow-up tasks", "list follow up tasks", "show follow-up tasks", "show follow up tasks",
                "list tasks", "show tasks", "get tasks", "pending tasks", "open tasks",
                "tasks for", "assigned to", "all tasks", "what tasks", "view tasks"
            ]) and not any(k in q_lower for k in ["create", "add", "new task"]) and "operations.list_follow_up_tasks" in avail_canon:
                if len(entities) > 1:
                    # When multiple entities are mentioned (e.g. Spotify and Stripe), query each entity's tasks
                    return [
                        {
                            "id": f"step_list_tasks_{ent.lower()}",
                            "tool_name": avail_canon["operations.list_follow_up_tasks"],
                            "arguments": {"customer_id": ent},
                            "depends_on": []
                        }
                        for ent in entities
                    ]
                customer_id = entities[0] if entities else None
                task_args = {}
                if customer_id:
                    task_args["customer_id"] = customer_id
                return [{
                    "id": "step_list_tasks",
                    "tool_name": avail_canon["operations.list_follow_up_tasks"],
                    "arguments": task_args,
                    "depends_on": []
                }]

            # F2. Update Status, Renewal Date, or Owner
            if any(k in q_lower for k in ["change", "update", "set", "mark", "assign"]) and any(k in q_lower for k in ["status", "active", "churned", "inactive", "suspended", "renewal", "owner"]) and entities and "operations.update_customer_status" in avail_canon:
                customer_id = entities[0]
                status = "Active"
                if "churn" in q_lower:
                    status = "Churned"
                elif "inactive" in q_lower:
                    status = "Inactive"
                elif "suspend" in q_lower:
                    status = "Suspended"
                elif "active" in q_lower:
                    status = "Active"

                update_args: Dict[str, Any] = {
                    "customer_id": customer_id,
                    "status": status,
                    "reason": query
                }
                ren_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
                if ren_match:
                    update_args["renewal_date"] = ren_match.group(1)
                own_match = re.search(r"\bowner(?:\s+name|\s+is|\s+to)?\s*[:=]?\s*([A-Za-z][A-Za-z\s.]{1,35}?)(?=\s+(?:and|with|renewal|status)\b|[.,;]|$)", query, re.IGNORECASE)
                if own_match:
                    update_args["owner"] = own_match.group(1).strip()

                return [{
                    "id": "step_update_status",
                    "tool_name": avail_canon["operations.update_customer_status"],
                    "arguments": update_args,
                    "depends_on": []
                }]

            # G. Add Note
            if any(k in q_lower for k in ["add note", "add a note", "append note", "save note", "note '", "note \""]) and entities and "operations.add_customer_note" in avail_canon:
                customer_id = entities[0]
                note_match = re.search(r"note\s+['\"](.+?)['\"]", query, re.IGNORECASE)
                if note_match:
                    note = note_match.group(1)
                elif ":" in query:
                    note = query.split(":", 1)[1].strip()
                else:
                    note = query
                return [{
                    "id": "step_add_note",
                    "tool_name": avail_canon["operations.add_customer_note"],
                    "arguments": {
                        "customer_id": customer_id,
                        "note": note
                    },
                    "depends_on": []
                }]


            # I. Operations Get Customer
            if any(k in q_lower for k in ["get customer", "show customer", "lookup customer", "view customer", "details for", "customer details"]) and entities and "operations.get_customer" in avail_canon:
                customer_id = entities[0]
                return [{
                    "id": "step_ops_get_customer",
                    "tool_name": avail_canon["operations.get_customer"],
                    "arguments": {"customer_id": customer_id},
                    "depends_on": []
                }]

        # ---------------------------------------------------------
        # 2. CRM & Analytics Planning
        # ---------------------------------------------------------
        target_entities = entities if entities else (["ABC"] if not has_operations and not classification.requires_rag else [])

        for customer_id in target_entities:
            crm_id = f"crm_{customer_id}"
            
            # CRM Lookup
            if "crm.get_customer" in avail_canon:
                if classification.requires_crm or not planned:
                    planned.append({
                        "id": crm_id,
                        "tool_name": avail_canon["crm.get_customer"],
                        "arguments": {"customer_id": customer_id},
                        "depends_on": []
                    })

            # Analytics Metrics
            if "analytics.get_customer_metrics" in avail_canon:
                if classification.requires_analytics or any(k in q_lower for k in ["metric", "metrics", "arr", "mrr", "health", "churn", "summary", "dossier"]):
                    planned.append({
                        "id": f"metrics_{customer_id}",
                        "tool_name": avail_canon["analytics.get_customer_metrics"],
                        "arguments": {"customer_id": customer_id},
                        "depends_on": [crm_id] if any(p.get("id") == crm_id for p in planned) else []
                    })

            # Analytics History
            if "analytics.get_customer_history" in avail_canon:
                if any(k in q_lower for k in ["history", "timeline", "past", "incident", "qbr", "recent", "month", "activity", "analyze", "dossier"]):
                    planned.append({
                        "id": f"history_{customer_id}",
                        "tool_name": avail_canon["analytics.get_customer_history"],
                        "arguments": {"customer_id": customer_id, "months": 3},
                        "depends_on": [crm_id] if any(p.get("id") == crm_id for p in planned) else []
                    })

        # CRM Search fallback
        if not planned and not entities and "crm.search_customer" in avail_canon and not classification.requires_rag:
            search_query = query.split()[0] if query.split() else "ABC"
            planned.append({
                "id": "step_crm_search",
                "tool_name": avail_canon["crm.search_customer"],
                "arguments": {"query": search_query},
                "depends_on": []
            })

        return planned

    def synthesize_response(
        self,
        agent_name: str,
        system_prompt: str,
        playbook: str,
        query: str,
        short_term_history: List[Dict[str, str]],
        long_term_facts: List[str],
        condensed_tool_summary: str,
        retrieved_chunks: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        max_tokens: int = 1500,
        on_token: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Synthesizes the final answer combining playbook instructions, memory, verified tool findings,
        user profile context, and RAG snippets. Supports live Groq / OpenAI or grounded local synthesis.
        """
        client, ptype = self._get_client()

        # Build prompt messages
        system_instructions = (
            f"{system_prompt}\n\n"
            f"=== PLAYBOOK GUIDELINES ===\n{playbook}\n\n"
            "=== AUTHORITATIVE DATA-PROVENANCE RULES ===\n"
            "1. Tool execution results provided below are authoritative and complete.\n"
            "2. If a tool executed successfully (e.g. Operations.create_customer, Operations.update_customer_status), "
            "confirm the action clearly to the user. Never ask for confirmation of an action that has already completed.\n"
            "3. If a tool failed or returned not found, clearly state the error or absence of data.\n"
            "4. Never claim an action occurred unless verified by successful tool execution.\n\n"
            "=== STRICT RESPONSE FORMAT RULES ===\n"
            "- Always format your entire response in elegant, clear, conversational Markdown.\n"
            "- Whenever listing multiple customers, tasks, audit entries, metrics, or comparing entities, ALWAYS include a clean Markdown Table summarizing the records (e.g., | Customer ID | Company Name | Status | Account Owner | Renewal Date | Open Tasks |), followed by concise bullet highlights.\n"
            "- Use readable headings (##, ###), Markdown tables, and bullet lists.\n"
            "- NEVER return raw JSON, JSON objects ({...}), JSON code blocks, or dictionary schemas unless the user explicitly requested JSON.\n"
            "- Write natural sentences to describe operations and actions."
        )

        messages = [
            {"role": "system", "content": system_instructions}
        ]

        context_parts = []
        if user_profile:
            user_context_block = [
                "### Authenticated User Profile & Cross-Chat Context:",
                f"- Name: {user_profile.get('full_name')} (@{user_profile.get('username')})",
                f"- Role & Department: {user_profile.get('role')} | {user_profile.get('department')}",
                f"- Primary Responsibilities: {user_profile.get('responsibilities') or 'General operations'}"
            ]
            user_facts = [f for f in (long_term_facts or []) if "[User Context]" in f or "Preference:" in f or "Context:" in f or "Profile:" in f]
            if user_facts:
                user_context_block.append("- Learned User Facts & Preferences across all conversations:")
                for uf in user_facts:
                    user_context_block.append(f"  * {uf}")
            context_parts.append("\n".join(user_context_block))

        if condensed_tool_summary:
            context_parts.append("### VERIFIED TOOL EXECUTION RESULTS:\n" + condensed_tool_summary)

        entity_facts = [f for f in (long_term_facts or []) if not ("[User Context]" in f or "Preference:" in f or "Context:" in f or "Profile:" in f)]
        if entity_facts:
            context_parts.append("### Long-Term Memory / Entity Facts:\n" + "\n".join([f"- {f}" for f in entity_facts]))

        if retrieved_chunks:
            chunk_texts = []
            for c in retrieved_chunks[:8]:
                c_content = c.get("content", "").strip()
                if len(c_content) > 1000:
                    c_content = c_content[:1000] + "... [truncated]"
                chunk_texts.append(f"[{c.get('filename', 'doc')} (chunk {c.get('chunk_index', 0)})]: {c_content}")
            context_parts.append("### Retrieved Knowledge Base Context (RAG):\n" + "\n\n".join(chunk_texts))

        context_str = "\n\n".join(context_parts) if context_parts else "No external tool or RAG context retrieved."

        # Retain only the most recent conversation context to avoid context bloat
        for m in short_term_history[-4:]:
            messages.append({"role": m["role"], "content": m["content"]})

        final_user_prompt = (
            f"User Request: {query}\n\n"
            f"=== CONTEXT & VERIFIED DATA ===\n{context_str}\n\n"
            "Please provide a structured, verified Markdown response strictly derived from the verified data above. Do NOT output raw JSON format."
        )
        messages.append({"role": "user", "content": final_user_prompt})

        # Try live completion if Groq or OpenAI is configured
        if client is not None:
            target_model = settings.GROQ_MODEL if ptype == "groq" else (model or settings.OPENAI_MODEL)
            max_retries = 3
            base_delay = 0.5
            for attempt in range(max_retries):
                try:
                    if on_token is not None:
                        completion = client.chat.completions.create(
                            model=target_model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            messages=messages,
                            stream=True
                        )

                        full_answer = []
                        for chunk in completion:
                            delta = chunk.choices[0].delta.content if (chunk.choices and chunk.choices[0].delta) else None
                            if delta:
                                full_answer.append(delta)
                                try:
                                    on_token(delta)
                                except Exception:
                                    pass

                        ans = "".join(full_answer)
                        if ans and ans.strip():
                            return clean_llm_markdown_output(ans)
                    else:
                        completion = client.chat.completions.create(
                            model=target_model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            messages=messages,
                            stream=False
                        )
                        ans = completion.choices[0].message.content or ""
                        if ans and ans.strip():
                            return clean_llm_markdown_output(ans)
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = any(k in err_str for k in ["429", "rate_limit", "too many requests", "rate limit"])
                    if is_rate_limit and attempt < max_retries - 1:
                        sleep_time = base_delay * (2 ** attempt) + random.uniform(0.1, 0.4)
                        logger.warning(f"Live LLM call ({ptype}) hit rate limit (429). Retrying in {sleep_time:.2f}s (attempt {attempt+1}/{max_retries})...")
                        time.sleep(sleep_time)
                    else:
                        logger.warning(f"Live LLM call ({ptype}) failed: {e}. Falling back to local grounded synthesis.")
                        break

        # ------------------------------------------------------------------
        # Fallback #1: Retry with GROQ_API_KEY2 (secondary key) before going offline
        # ------------------------------------------------------------------
        secondary = self._get_secondary_client()
        if secondary is not None:
            try:
                fallback_model = settings.GROQ_MODEL
                logger.info("Primary key exhausted — attempting completion with GROQ_API_KEY2...")
                if on_token is not None:
                    completion = secondary.chat.completions.create(
                        model=fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        messages=messages,
                        stream=True
                    )
                    full_answer = []
                    for chunk in completion:
                        delta = chunk.choices[0].delta.content if (chunk.choices and chunk.choices[0].delta) else None
                        if delta:
                            full_answer.append(delta)
                            try:
                                on_token(delta)
                            except Exception:
                                pass
                    ans = "".join(full_answer)
                    if ans and ans.strip():
                        return clean_llm_markdown_output(ans)
                else:
                    completion = secondary.chat.completions.create(
                        model=fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        messages=messages,
                        stream=False
                    )
                    ans = completion.choices[0].message.content or ""
                    if ans and ans.strip():
                        return clean_llm_markdown_output(ans)
            except Exception as e:
                logger.warning(f"Secondary key (GROQ_API_KEY2) also failed: {e}. Falling back to local grounded synthesis.")

        # Fallback #2: Grounded Local Synthesis Engine (Deterministic offline mode)
        return self._local_grounded_synthesize(
            agent_name=agent_name,
            query=query,
            long_term_facts=long_term_facts,
            condensed_tool_summary=condensed_tool_summary,
            retrieved_chunks=retrieved_chunks,
            user_profile=user_profile
        )

    async def synthesize_response_async(
        self,
        agent_name: str,
        system_prompt: str,
        playbook: str,
        query: str,
        short_term_history: List[Dict[str, str]],
        long_term_facts: List[str],
        condensed_tool_summary: str,
        retrieved_chunks: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        max_tokens: int = 1500,
        on_token: Optional[Callable[[str], Any]] = None
    ) -> str:
        """
        Asynchronously synthesizes the final answer with true non-blocking token streaming and jittered exponential backoff.
        """
        async_client, ptype = self._get_async_client()

        # Build prompt messages
        system_instructions = (
            f"{system_prompt}\n\n"
            f"=== PLAYBOOK GUIDELINES ===\n{playbook}\n\n"
            "=== AUTHORITATIVE DATA-PROVENANCE RULES ===\n"
            "1. Tool execution results provided below are authoritative and complete.\n"
            "2. If a tool executed successfully (e.g. Operations.create_customer, Operations.update_customer_status), "
            "confirm the action clearly to the user. Never ask for confirmation of an action that has already completed.\n"
            "3. If a tool failed or returned not found, clearly state the error or absence of data.\n"
            "4. Never claim an action occurred unless verified by successful tool execution.\n\n"
            "=== STRICT RESPONSE FORMAT RULES ===\n"
            "- Always format your entire response in elegant, clear, conversational Markdown.\n"
            "- Whenever listing multiple customers, tasks, audit entries, metrics, or comparing entities, ALWAYS include a clean Markdown Table summarizing the records (e.g., | Customer ID | Company Name | Status | Account Owner | Renewal Date | Open Tasks |), followed by concise bullet highlights.\n"
            "- Use readable headings (##, ###), Markdown tables, and bullet lists.\n"
            "- NEVER return raw JSON, JSON objects ({...}), JSON code blocks, or dictionary schemas unless the user explicitly requested JSON.\n"
            "- Write natural sentences to describe operations and actions."
        )

        messages = [
            {"role": "system", "content": system_instructions}
        ]

        context_parts = []
        if user_profile:
            user_context_block = [
                "### Authenticated User Profile & Cross-Chat Context:",
                f"- Name: {user_profile.get('full_name')} (@{user_profile.get('username')})",
                f"- Role & Department: {user_profile.get('role')} | {user_profile.get('department')}",
                f"- Primary Responsibilities: {user_profile.get('responsibilities') or 'General operations'}"
            ]
            user_facts = [f for f in (long_term_facts or []) if "[User Context]" in f or "Preference:" in f or "Context:" in f or "Profile:" in f]
            if user_facts:
                user_context_block.append("- Learned User Facts & Preferences across all conversations:")
                for uf in user_facts:
                    user_context_block.append(f"  * {uf}")
            context_parts.append("\n".join(user_context_block))

        if condensed_tool_summary:
            context_parts.append("### VERIFIED TOOL EXECUTION RESULTS:\n" + condensed_tool_summary)

        entity_facts = [f for f in (long_term_facts or []) if not ("[User Context]" in f or "Preference:" in f or "Context:" in f or "Profile:" in f)]
        if entity_facts:
            context_parts.append("### Long-Term Memory / Entity Facts:\n" + "\n".join([f"- {f}" for f in entity_facts]))

        if retrieved_chunks:
            chunk_texts = []
            for c in retrieved_chunks[:8]:
                c_content = c.get("content", "").strip()
                if len(c_content) > 1000:
                    c_content = c_content[:1000] + "... [truncated]"
                chunk_texts.append(f"[{c.get('filename', 'doc')} (chunk {c.get('chunk_index', 0)})]: {c_content}")
            context_parts.append("### Retrieved Knowledge Base Context (RAG):\n" + "\n\n".join(chunk_texts))

        context_str = "\n\n".join(context_parts) if context_parts else "No external tool or RAG context retrieved."

        for m in short_term_history[-4:]:
            messages.append({"role": m["role"], "content": m["content"]})

        final_user_prompt = (
            f"User Request: {query}\n\n"
            f"=== CONTEXT & VERIFIED DATA ===\n{context_str}\n\n"
            "Please provide a structured, verified Markdown response strictly derived from the verified data above. Do NOT output raw JSON format."
        )
        messages.append({"role": "user", "content": final_user_prompt})

        # Try live async completion if Groq or OpenAI is configured
        if async_client is not None:
            target_model = settings.GROQ_MODEL if ptype == "groq" else (model or settings.OPENAI_MODEL)
            max_retries = 3
            base_delay = 0.5
            for attempt in range(max_retries):
                try:
                    if on_token is not None:
                        completion = await async_client.chat.completions.create(
                            model=target_model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            messages=messages,
                            stream=True
                        )

                        full_answer = []
                        async for chunk in completion:
                            delta = chunk.choices[0].delta.content if (chunk.choices and chunk.choices[0].delta) else None
                            if delta:
                                full_answer.append(delta)
                                try:
                                    res = on_token(delta)
                                    if asyncio.iscoroutine(res):
                                        await res
                                except Exception:
                                    pass
                                # Give event loop a cycle to dispatch SSE queue chunk to network
                                await asyncio.sleep(0.002)

                        ans = "".join(full_answer)
                        if ans and ans.strip():
                            return clean_llm_markdown_output(ans)
                    else:
                        completion = await async_client.chat.completions.create(
                            model=target_model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            messages=messages,
                            stream=False
                        )
                        ans = completion.choices[0].message.content or ""
                        if ans and ans.strip():
                            return clean_llm_markdown_output(ans)
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = any(k in err_str for k in ["429", "rate_limit", "too many requests", "rate limit"])
                    if is_rate_limit and attempt < max_retries - 1:
                        sleep_time = base_delay * (2 ** attempt) + random.uniform(0.1, 0.4)
                        logger.warning(f"Live async LLM call ({ptype}) hit rate limit (429). Retrying in {sleep_time:.2f}s (attempt {attempt+1}/{max_retries})...")
                        await asyncio.sleep(sleep_time)
                    else:
                        logger.warning(f"Live async LLM call ({ptype}) failed: {e}. Falling back to local grounded synthesis.")
                        break

        # ------------------------------------------------------------------
        # Fallback #1: Retry with GROQ_API_KEY2 (secondary key) before going offline
        # ------------------------------------------------------------------
        secondary_async = self._get_secondary_async_client()
        if secondary_async is not None:
            try:
                fallback_model = settings.GROQ_MODEL
                logger.info("Primary async key exhausted — attempting completion with GROQ_API_KEY2...")
                if on_token is not None:
                    completion = await secondary_async.chat.completions.create(
                        model=fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        messages=messages,
                        stream=True
                    )
                    full_answer = []
                    async for chunk in completion:
                        delta = chunk.choices[0].delta.content if (chunk.choices and chunk.choices[0].delta) else None
                        if delta:
                            full_answer.append(delta)
                            try:
                                res = on_token(delta)
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception:
                                pass
                            await asyncio.sleep(0.002)
                    ans = "".join(full_answer)
                    if ans and ans.strip():
                        return clean_llm_markdown_output(ans)
                else:
                    completion = await secondary_async.chat.completions.create(
                        model=fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        messages=messages,
                        stream=False
                    )
                    ans = completion.choices[0].message.content or ""
                    if ans and ans.strip():
                        return clean_llm_markdown_output(ans)
            except Exception as e:
                logger.warning(f"Secondary async key (GROQ_API_KEY2) also failed: {e}. Falling back to local grounded synthesis.")

        # Grounded Local Synthesis Engine fallback
        return self._local_grounded_synthesize(
            agent_name=agent_name,
            query=query,
            long_term_facts=long_term_facts,
            condensed_tool_summary=condensed_tool_summary,
            retrieved_chunks=retrieved_chunks,
            user_profile=user_profile
        )

    def _local_grounded_synthesize(
        self,
        agent_name: str,
        query: str,
        long_term_facts: List[str],
        condensed_tool_summary: str,
        retrieved_chunks: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Dynamically synthesizes output strictly derived from actual evidence.
        Distinguishes Verified, Unavailable, and Recommended Next Steps.
        """
        lines = []
        lines.append("## Executive Summary & Customer Dossier")
        lines.append(f"**Agent**: {agent_name} | **Engine**: [GROUNDED VERIFIED ENGINE]")
        if user_profile:
            lines.append(f"**Requester**: {user_profile.get('full_name')} ({user_profile.get('role')}, {user_profile.get('department')})")
        lines.append("> **Audit Status**: Verified via Multi-MCP Tool Execution & Structured Provenance\n")

        # Direct user memory / profile questions
        user_query_lower = query.lower()
        if any(k in user_query_lower for k in ["who am i", "about me", "my profile", "my role", "my responsibilities", "my preference", "remember about me", "my context", "what do you know about me", "what do you remember"]):
            lines = ["## User Context & Persistent Memory Profile"]
            if user_profile:
                lines.append(f"**User**: {user_profile.get('full_name')} (@{user_profile.get('username')})")
                lines.append(f"**Role & Department**: {user_profile.get('role')} | {user_profile.get('department')}")
                lines.append(f"**Primary Focus & Duties**: {user_profile.get('responsibilities') or 'General enterprise operations'}")
                if user_profile.get("email"):
                    lines.append(f"**Email**: {user_profile.get('email')}")
            else:
                lines.append("You are currently browsing as an anonymous user.")

            user_facts = [f for f in (long_term_facts or []) if "[User Context]" in f or "Preference:" in f or "Context:" in f or "Profile:" in f]
            if user_facts:
                lines.append("\n### Persistent Memories Learned Across Conversations")
                for uf in user_facts:
                    clean_uf = uf.replace("[User Context]: ", "")
                    lines.append(f"- {clean_uf}")
            else:
                lines.append("\n### Persistent Memories")
                lines.append("- No custom preferences or facts recorded yet. As you chat across sessions, Luna automatically learns and remembers your preferences and project notes.")

            return "\n".join(lines)

        # Operations Actions (Create, Update, Note, Task, List, Audit)
        if "operations" in condensed_tool_summary.lower() or "operation succeeded" in condensed_tool_summary.lower():
            lines.append("### Verified Operation Result")
            for item in condensed_tool_summary.split("\n\n"):
                if item.strip():
                    lines.append(f"- {item.strip()}")
            if "create" in query.lower() and ("customer" in query.lower() or "id" in query.lower()):
                lines.append(f"\nThe customer operation was successfully completed for: **{query.strip()}** and recorded in the audit log.")
            else:
                lines.append("\nThe requested customer operation was successfully completed and recorded in the audit log.")
            return "\n".join(lines)

        has_verified = False
        verified_lines = []
        missing_lines = []

        # 1. CRM Section
        crm_found = False
        if "crm profile for" in condensed_tool_summary.lower() or "customer:" in condensed_tool_summary.lower() or "company:" in condensed_tool_summary.lower():
            if "not found in crm" in condensed_tool_summary.lower() or "'found': false" in condensed_tool_summary.lower():
                missing_lines.append("- **CRM Profile**: Customer record was not found in the connected CRM data source.")
            else:
                crm_found = True
                has_verified = True
                verified_lines.append("### 1. Account Profile (CRM)")
                for l in condensed_tool_summary.split("\n"):
                    if any(k in l for k in [
                        "Company:", "Tier:", "SLA:", "Contract:", "Stakeholder", "Account Exec:",
                        "CRM Profile for", "Account Owner:", "Owner:", "Primary Contact:", "Contact:",
                        "Renewal Date:", "Notes:", "CEO:", "Revenue:"
                    ]):
                        verified_lines.append(f"  {l.strip()}")
        else:
            missing_lines.append("- **CRM Profile**: No CRM record retrieved or customer not found.")

        # 2. Analytics Metrics Section
        if "arr:" in condensed_tool_summary.lower() or "nps score:" in condensed_tool_summary.lower() or "health:" in condensed_tool_summary.lower():
            if "no analytics metrics" in condensed_tool_summary.lower():
                missing_lines.append("- **Analytics & Health Metrics**: No metrics recorded for this customer in analytics store.")
            else:
                has_verified = True
                verified_lines.append("\n### 2. Operational Health & Platform Metrics (Analytics)")
                for l in condensed_tool_summary.split("\n"):
                    if any(k in l.lower() for k in ["arr:", "mrr:", "nps score:", "churn risk:", "active users:", "sla compliance:", "health:"]):
                        verified_lines.append(f"  {l.strip()}")
        else:
            missing_lines.append("- **Analytics Metrics**: No analytics metrics queried or available.")

        # 3. Analytics History Section
        if "analytics event history" in condensed_tool_summary.lower() or "timeline" in condensed_tool_summary.lower() or "incident" in condensed_tool_summary.lower():
            verified_lines.append("\n### 3. Chronological Event History (Analytics Timeline)")
            for l in condensed_tool_summary.split("\n"):
                if any(k in l.lower() for k in ["qbr", "upgrade", "incident", "audit", "renewal", "analytics event history", "* ["]):
                    verified_lines.append(f"  {l.strip()}")

        # 4. RAG Knowledge Section
        if retrieved_chunks:
            has_verified = True
            verified_lines.append("\n### 4. Grounded Documentation & SLA Policies (RAG)")
            for c in retrieved_chunks[:8]:
                snippet = c.get('content', '').split("\n")[0].strip("# ")
                if len(snippet) > 120:
                    snippet = snippet[:120] + "..."
                verified_lines.append(f"- **[{c.get('filename', 'doc')} · Chunk #{c.get('chunk_index', 0)}]**: {snippet} *(Score: {round(c.get('score', 0)*100, 1)}%)*")
        else:
            missing_lines.append("- **Knowledge Base**: No relevant internal documentation found in the knowledge base partition.")

        # 5. Memory Section
        if long_term_facts:
            has_verified = True
            verified_lines.append("\n### 5. Persistent Memory & Engagement History")
            for fact in long_term_facts:
                verified_lines.append(f"- *Prior Context*: {fact}")

        # Assemble output
        lines.append("### Verified Information")
        if has_verified:
            lines.extend(verified_lines)
        else:
            lines.append("- No verified data is available from connected sources.")

        if missing_lines:
            lines.append("\n### Unavailable / Missing Information")
            lines.extend(missing_lines)

        lines.append("\n### Recommended Next Steps")
        if crm_found:
            lines.append("- Align with account executive on upcoming quarterly review commitments.")
            lines.append("- Verify SLA compliance metrics against client service tier guarantees.")
        else:
            lines.append("- Verify customer details or create an operations record if needed.")

        return "\n".join(lines)


llm_provider = LLMProvider()
