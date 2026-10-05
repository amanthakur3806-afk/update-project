"""
Agent Management & Execution API Endpoints
"""
from typing import List
import asyncio
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import Agent, AgentTool
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentConfigResponse
from app.schemas.execution import RunAgentRequest, RunAgentResponse
from app.workflow.agent_workflow import create_agent_workflow
from app.mcp.client_manager import mcp_client_manager
from app.services.progress import progress_bus

router = APIRouter(prefix="/agents", tags=["Agents"])

@router.get("", response_model=List[AgentResponse], summary="List all configured agents")
def list_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).all()
    results = []
    for a in agents:
        allowed = [t.tool_name for t in a.tools if t.enabled]
        resp = AgentResponse(
            agent_id=a.agent_id,
            agent_name=a.agent_name,
            category=getattr(a, "category", "General"),
            description=a.description,
            system_prompt=a.system_prompt,
            playbook=a.playbook,
            model=a.model,
            temperature=a.temperature,
            memory_configuration=a.memory_configuration or {},
            workflow_configuration=a.workflow_configuration or {},
            allowed_tools=allowed,
            enabled=a.enabled,
            created_at=a.created_at,
            updated_at=a.updated_at
        )
        results.append(resp)
    return results

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, summary="Create a new dynamic agent")
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    existing = db.query(Agent).filter(Agent.agent_id == payload.agent_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Agent '{payload.agent_id}' already exists.")

    agent = Agent(
        agent_id=payload.agent_id,
        agent_name=payload.agent_name,
        category=payload.category,
        description=payload.description,
        system_prompt=payload.system_prompt,
        playbook=payload.playbook,
        model=payload.model,
        temperature=payload.temperature,
        memory_configuration=payload.memory_configuration,
        workflow_configuration=payload.workflow_configuration,
        enabled=payload.enabled
    )
    db.add(agent)
    db.flush()

    for tool_name in payload.allowed_tools:
        server_id = mcp_client_manager.get_tool_server_id(tool_name) or "unknown"
        at = AgentTool(agent_id=agent.agent_id, tool_name=tool_name, server_id=server_id)
        db.add(at)

    db.commit()
    db.refresh(agent)

    allowed = [t.tool_name for t in agent.tools if t.enabled]
    return AgentResponse(
        agent_id=agent.agent_id,
        agent_name=agent.agent_name,
        category=getattr(agent, "category", "General"),
        description=agent.description,
        system_prompt=agent.system_prompt,
        playbook=agent.playbook,
        model=agent.model,
        temperature=agent.temperature,
        memory_configuration=agent.memory_configuration or {},
        workflow_configuration=agent.workflow_configuration or {},
        allowed_tools=allowed,
        enabled=agent.enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at
    )

@router.get("/{agent_id}", response_model=AgentResponse, summary="Get agent details")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    
    allowed = [t.tool_name for t in agent.tools if t.enabled]
    return AgentResponse(
        agent_id=agent.agent_id,
        agent_name=agent.agent_name,
        category=getattr(agent, "category", "General"),
        description=agent.description,
        system_prompt=agent.system_prompt,
        playbook=agent.playbook,
        model=agent.model,
        temperature=agent.temperature,
        memory_configuration=agent.memory_configuration or {},
        workflow_configuration=agent.workflow_configuration or {},
        allowed_tools=allowed,
        enabled=agent.enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at
    )

@router.get("/{agent_id}/config", response_model=AgentConfigResponse, summary="Get agent configuration")
def get_agent_config(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")

    allowed = [t.tool_name for t in agent.tools if t.enabled]
    wf = agent.workflow_configuration or {}
    return AgentConfigResponse(
        agent_id=agent.agent_id,
        category=getattr(agent, "category", "General"),
        model=agent.model,
        temperature=agent.temperature,
        memory=agent.memory_configuration or {},
        rag={"enabled": wf.get("rag_enabled", True), "knowledge_base": wf.get("knowledge_base", "customer_docs")},
        workflow={"max_iterations": wf.get("max_iterations", 10), "enable_subagents": wf.get("enable_subagents", True)},
        allowed_tools=allowed
    )

@router.put("/{agent_id}/config", response_model=AgentConfigResponse, summary="Update agent configuration dynamically")
def update_agent_config(agent_id: str, payload: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")

    if payload.agent_name is not None:
        agent.agent_name = payload.agent_name
    if payload.category is not None:
        agent.category = payload.category
    if payload.description is not None:
        agent.description = payload.description
    if payload.system_prompt is not None:
        agent.system_prompt = payload.system_prompt
    if payload.playbook is not None:
        agent.playbook = payload.playbook
    if payload.model is not None:
        agent.model = payload.model
    if payload.temperature is not None:
        agent.temperature = payload.temperature
    if payload.memory_configuration is not None:
        agent.memory_configuration = payload.memory_configuration
    if payload.workflow_configuration is not None:
        agent.workflow_configuration = payload.workflow_configuration
    if payload.enabled is not None:
        agent.enabled = payload.enabled

    if payload.allowed_tools is not None:
        # Replace existing tools
        db.query(AgentTool).filter(AgentTool.agent_id == agent.agent_id).delete()
        for tool_name in payload.allowed_tools:
            server_id = mcp_client_manager.get_tool_server_id(tool_name) or "unknown"
            at = AgentTool(agent_id=agent.agent_id, tool_name=tool_name, server_id=server_id)
            db.add(at)

    db.commit()
    db.refresh(agent)

    allowed = [t.tool_name for t in agent.tools if t.enabled]
    wf = agent.workflow_configuration or {}
    return AgentConfigResponse(
        agent_id=agent.agent_id,
        category=getattr(agent, "category", "General"),
        model=agent.model,
        temperature=agent.temperature,
        memory=agent.memory_configuration or {},
        rag={"enabled": wf.get("rag_enabled", True), "knowledge_base": wf.get("knowledge_base", "customer_docs")},
        workflow={"max_iterations": wf.get("max_iterations", 10), "enable_subagents": wf.get("enable_subagents", True)},
        allowed_tools=allowed
    )

@router.post("/{agent_id}/run", response_model=RunAgentResponse, summary="Execute agent workflow on query")
async def run_agent(
    agent_id: str = Path(..., description="Unique Agent identifier", examples=["customer_research_agent"]),

    payload: RunAgentRequest = ...,
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id, Agent.enabled == True).first()
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Active agent '{agent_id}' not found. Available agents: customer_research_agent, financial_analyst_agent, support_compliance_agent."
        )

    workflow = create_agent_workflow()
    result = await workflow.run(
        agent_id=agent_id,
        query=payload.query,
        conversation_id=payload.conversation_id
    )

    return RunAgentResponse(
        execution_id=result["execution_id"],
        agent_id=result["agent_id"],
        conversation_id=result.get("conversation_id"),
        answer=result["answer"],
        sources=result.get("sources", []),
        tools_used=result.get("tools_used", []),
        query_classification=result.get("query_classification"),
        status=result["status"],
        duration_ms=result["duration_ms"],
        prompt_file=result.get("prompt_file")
    )


@router.post("/{agent_id}/stream", summary="Execute an agent and stream safe progress events")
async def stream_agent(
    agent_id: str = Path(...),
    payload: RunAgentRequest = ...,
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id, Agent.enabled == True).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Active agent '{agent_id}' not found.")

    execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    queue = progress_bus.subscribe(execution_id)

    async def events():
        workflow = create_agent_workflow()
        task = asyncio.ensure_future(workflow.run(
            agent_id=agent_id,
            query=payload.query,
            conversation_id=payload.conversation_id,
            execution_id=execution_id
        ))
        try:
            while not task.done() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield f"event: progress\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    continue
            result = await task
            result_payload = {"type": "complete", **result}
            yield f"event: complete\ndata: {json.dumps(result_payload)}\n\n"
        except Exception as exc:
            if not task.done():
                task.cancel()
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        finally:
            progress_bus.unsubscribe(execution_id)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
