"""
Agent Management & Execution API Endpoints
"""

from typing import List, Optional, Dict, Any
import asyncio
import json
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import Agent, AgentTool
from app.models.user import User
from app.services.auth_service import get_current_user_optional
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentConfigResponse,
)
from app.schemas.execution import (
    RunAgentRequest,
    RunAgentResponse,
)
from app.workflow.agent_workflow import create_agent_workflow
from app.mcp.client_manager import mcp_client_manager
from app.services.progress import progress_bus


router = APIRouter(
    prefix="/agents",
    tags=["Agents"]
)


# ============================================================
# LIST AGENTS
# ============================================================

@router.get(
    "",
    response_model=List[AgentResponse],
    summary="List all configured agents"
)
def list_agents(
    db: Session = Depends(get_db)
):
    agents = db.query(Agent).all()

    results = []

    for a in agents:

        allowed = [
            t.tool_name
            for t in a.tools
            if t.enabled
        ]

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


# ============================================================
# CREATE AGENT
# ============================================================

@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new dynamic agent"
)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db)
):

    existing = (
        db.query(Agent)
        .filter(
            Agent.agent_id == payload.agent_id
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Agent '{payload.agent_id}' "
                f"already exists."
            )
        )

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

        server_id = (
            mcp_client_manager.get_tool_server_id(
                tool_name
            )
            or "unknown"
        )

        at = AgentTool(
            agent_id=agent.agent_id,
            tool_name=tool_name,
            server_id=server_id
        )

        db.add(at)

    db.commit()
    db.refresh(agent)

    allowed = [
        t.tool_name
        for t in agent.tools
        if t.enabled
    ]

    return AgentResponse(
        agent_id=agent.agent_id,
        agent_name=agent.agent_name,
        category=getattr(
            agent,
            "category",
            "General"
        ),
        description=agent.description,
        system_prompt=agent.system_prompt,
        playbook=agent.playbook,
        model=agent.model,
        temperature=agent.temperature,
        memory_configuration=(
            agent.memory_configuration or {}
        ),
        workflow_configuration=(
            agent.workflow_configuration or {}
        ),
        allowed_tools=allowed,
        enabled=agent.enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at
    )


# ============================================================
# GET AGENT
# ============================================================

@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent details"
)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db)
):

    agent = (
        db.query(Agent)
        .filter(
            Agent.agent_id == agent_id
        )
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Agent '{agent_id}' "
                f"not found."
            )
        )

    allowed = [
        t.tool_name
        for t in agent.tools
        if t.enabled
    ]

    return AgentResponse(
        agent_id=agent.agent_id,
        agent_name=agent.agent_name,
        category=getattr(
            agent,
            "category",
            "General"
        ),
        description=agent.description,
        system_prompt=agent.system_prompt,
        playbook=agent.playbook,
        model=agent.model,
        temperature=agent.temperature,
        memory_configuration=(
            agent.memory_configuration or {}
        ),
        workflow_configuration=(
            agent.workflow_configuration or {}
        ),
        allowed_tools=allowed,
        enabled=agent.enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at
    )


# ============================================================
# GET AGENT CONFIG
# ============================================================

@router.get(
    "/{agent_id}/config",
    response_model=AgentConfigResponse,
    summary="Get agent configuration"
)
def get_agent_config(
    agent_id: str,
    db: Session = Depends(get_db)
):

    agent = (
        db.query(Agent)
        .filter(
            Agent.agent_id == agent_id
        )
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Agent '{agent_id}' "
                f"not found."
            )
        )

    allowed = [
        t.tool_name
        for t in agent.tools
        if t.enabled
    ]

    wf = agent.workflow_configuration or {}

    return AgentConfigResponse(
        agent_id=agent.agent_id,
        category=getattr(
            agent,
            "category",
            "General"
        ),
        model=agent.model,
        temperature=agent.temperature,
        memory=(
            agent.memory_configuration or {}
        ),
        rag={
            "enabled": wf.get(
                "rag_enabled",
                True
            ),
            "knowledge_base": wf.get(
                "knowledge_base",
                "customer_docs"
            )
        },
        workflow={
            "max_iterations": wf.get(
                "max_iterations",
                10
            ),
            "enable_subagents": wf.get(
                "enable_subagents",
                True
            )
        },
        allowed_tools=allowed
    )


# ============================================================
# UPDATE AGENT CONFIG
# ============================================================

@router.put(
    "/{agent_id}/config",
    response_model=AgentConfigResponse,
    summary="Update agent configuration dynamically"
)
def update_agent_config(
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db)
):

    agent = (
        db.query(Agent)
        .filter(
            Agent.agent_id == agent_id
        )
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Agent '{agent_id}' "
                f"not found."
            )
        )

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
        agent.memory_configuration = (
            payload.memory_configuration
        )

    if payload.workflow_configuration is not None:
        agent.workflow_configuration = (
            payload.workflow_configuration
        )

    if payload.enabled is not None:
        agent.enabled = payload.enabled

    if payload.allowed_tools is not None:

        db.query(AgentTool).filter(
            AgentTool.agent_id == agent.agent_id
        ).delete()

        for tool_name in payload.allowed_tools:

            server_id = (
                mcp_client_manager.get_tool_server_id(
                    tool_name
                )
                or "unknown"
            )

            at = AgentTool(
                agent_id=agent.agent_id,
                tool_name=tool_name,
                server_id=server_id
            )

            db.add(at)

    db.commit()
    db.refresh(agent)

    allowed = [
        t.tool_name
        for t in agent.tools
        if t.enabled
    ]

    wf = agent.workflow_configuration or {}

    return AgentConfigResponse(
        agent_id=agent.agent_id,
        category=getattr(
            agent,
            "category",
            "General"
        ),
        model=agent.model,
        temperature=agent.temperature,
        memory=(
            agent.memory_configuration or {}
        ),
        rag={
            "enabled": wf.get(
                "rag_enabled",
                True
            ),
            "knowledge_base": wf.get(
                "knowledge_base",
                "customer_docs"
            )
        },
        workflow={
            "max_iterations": wf.get(
                "max_iterations",
                10
            ),
            "enable_subagents": wf.get(
                "enable_subagents",
                True
            )
        },
        allowed_tools=allowed
    )


# ============================================================
# NORMAL AGENT EXECUTION
# ============================================================

@router.post(
    "/{agent_id}/run",
    response_model=RunAgentResponse,
    summary="Execute agent workflow on query"
)
async def run_agent(
    agent_id: str = Path(
        ...,
        description="Unique Agent identifier",
        examples=["customer_research_agent"]
    ),
    payload: RunAgentRequest = ...,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):

    agent = (
        db.query(Agent)
        .filter(
            Agent.agent_id == agent_id,
            Agent.enabled == True
        )
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Active agent '{agent_id}' "
                f"not found. Available agents: "
                f"customer_research_agent, "
                f"financial_analyst_agent, "
                f"support_compliance_agent."
            )
        )

    workflow = create_agent_workflow()

    effective_user_id = getattr(payload, "user_id", None) or (current_user.user_id if current_user else None)
    user_profile_data = current_user.to_dict() if current_user else None

    result = await workflow.run(
        agent_id=agent_id,
        query=payload.query,
        conversation_id=payload.conversation_id,
        session_id=payload.session_id,
        user_id=effective_user_id,
        user_profile=user_profile_data
    )

    return RunAgentResponse(
        execution_id=result["execution_id"],
        agent_id=result["agent_id"],
        conversation_id=result.get("conversation_id"),
        session_id=result.get("session_id"),
        answer=result["answer"],
        sources=result.get("sources", []),
        tools_used=result.get("tools_used", []),
        query_classification=result.get("query_classification"),
        status=result["status"],
        duration_ms=result["duration_ms"],
        prompt_file=result.get("prompt_file")
    )


# ============================================================
# STREAMING AGENT EXECUTION
# ============================================================

@router.post(
    "/{agent_id}/stream",
    summary="Execute an agent and stream safe progress events"
)
async def stream_agent(
    agent_id: str = Path(...),
    payload: RunAgentRequest = ...,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # 1. Validate agent
    # --------------------------------------------------------

    agent = (
        db.query(Agent)
        .filter(
            Agent.agent_id == agent_id,
            Agent.enabled == True
        )
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Active agent '{agent_id}' "
                f"not found."
            )
        )

    # --------------------------------------------------------
    # 2. Create unique execution ID
    # --------------------------------------------------------

    execution_id = (
        f"exec_{uuid.uuid4().hex[:12]}"
    )

    # --------------------------------------------------------
    # 3. Subscribe BEFORE starting workflow
    # --------------------------------------------------------

    queue = progress_bus.subscribe(
        execution_id
    )

    # --------------------------------------------------------
    # 4. SSE event generator
    # --------------------------------------------------------

    effective_user_id = getattr(payload, "user_id", None) or (current_user.user_id if current_user else None)
    user_profile_data = current_user.to_dict() if current_user else None

    async def events():

        workflow = create_agent_workflow()

        # Start workflow in background.
        # This is important because the SSE generator
        # must remain free to consume ProgressBus events.
        task = asyncio.ensure_future(
            workflow.run(
                agent_id=agent_id,
                query=payload.query,
                conversation_id=payload.conversation_id,
                session_id=payload.session_id,
                user_id=effective_user_id,
                user_profile=user_profile_data,
                execution_id=execution_id
            )
        )

        try:

            # ------------------------------------------------
            # Keep listening until workflow finishes
            # ------------------------------------------------

            while True:

                try:

                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=0.05
                    )

                    event_type = event.get(
                        "type",
                        "progress"
                    )

                    yield (
                        f"event: {event_type}\n"
                        f"data: "
                        f"{json.dumps(event)}\n\n"
                    )

                except asyncio.TimeoutError:

                    if task.done():
                        # Drain any remaining queued events before breaking
                        while not queue.empty():
                            try:
                                rem_event = queue.get_nowait()
                                rem_type = rem_event.get("type", "progress")
                                yield (
                                    f"event: {rem_type}\n"
                                    f"data: "
                                    f"{json.dumps(rem_event)}\n\n"
                                )
                            except asyncio.QueueEmpty:
                                break
                        break

                    continue

            # ------------------------------------------------
            # Workflow completed
            # ------------------------------------------------

            result = await task

            result_payload = {
                "type": "complete",
                **result
            }

            yield (
                "event: complete\n"
                f"data: "
                f"{json.dumps(result_payload)}\n\n"
            )

        # ----------------------------------------------------
        # Client disconnected
        # ----------------------------------------------------

        except asyncio.CancelledError:

            if not task.done():

                task.cancel()

                try:
                    await task

                except asyncio.CancelledError:
                    pass

            raise

        # ----------------------------------------------------
        # Workflow / streaming error
        # ----------------------------------------------------

        except Exception as exc:

            if not task.done():

                task.cancel()

                try:
                    await task

                except asyncio.CancelledError:
                    pass

            error_payload = {
                "type": "error",
                "message": str(exc)
            }

            yield (
                "event: error\n"
                f"data: "
                f"{json.dumps(error_payload)}\n\n"
            )

        # ----------------------------------------------------
        # Always clean up subscription
        # ----------------------------------------------------

        finally:

            progress_bus.unsubscribe(
                execution_id
            )

    # --------------------------------------------------------
    # 5. Return SSE response
    # --------------------------------------------------------

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )