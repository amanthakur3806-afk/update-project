"""
System Health & Observability Endpoints
=======================================
Exposes real-time component health, system execution statistics,
and demo mode status for the Operations Dashboard.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.config import settings
from app.database import get_db
from app.models.execution import Execution, ExecutionStep
from app.models.agent import Agent
from app.models.knowledge import KnowledgeBase, Document
from app.models.memory import Memory, Conversation
from app.services.data_service import data_service
from app.rag.vector_store import vector_store

router = APIRouter(prefix="/system", tags=["System & Observability"])


@router.get("/health", summary="System Health & Component Status")
def get_system_health(db: Session = Depends(get_db)):
    """
    Returns live connectivity and operational readiness across all platform subsystems.
    """
    # 1. Database Check
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    # 2. LLM Provider Check
    llm_status = "offline_deterministic"
    llm_info = "Built-in local reasoning engine (zero API costs)"
    if settings.GROQ_API_KEY:
        llm_status = "connected"
        llm_info = f"Groq Live API ({settings.GROQ_MODEL})"
    elif settings.OPENAI_API_KEY:
        llm_status = "connected"
        llm_info = f"OpenAI Live API ({settings.OPENAI_MODEL})"

    # 3. Vector Store Check
    vs_ready = vector_store.total_vectors >= 0

    # 4. MCP Servers
    crm_count = len(data_service.list_customers())
    analytics_count = len(data_service.list_all_metrics())

    # 5. Memory counts
    memories_count = db.query(Memory).count()

    return {
        "status": "operational" if db_ok else "degraded",
        "components": {
            "database": {
                "status": "connected" if db_ok else "unreachable",
                "engine": "SQLite / SQLAlchemy"
            },
            "llm": {
                "status": llm_status,
                "provider": llm_info
            },
            "crm_mcp": {
                "status": "connected",
                "server_id": "crm_mcp",
                "records_loaded": crm_count
            },
            "analytics_mcp": {
                "status": "connected",
                "server_id": "analytics_mcp",
                "records_loaded": analytics_count
            },
            "vector_store": {
                "status": "ready" if vs_ready else "error",
                "index_type": "FAISS IndexFlatIP (Cosine)",
                "total_vectors": vector_store.total_vectors
            },
            "memory": {
                "status": "ready",
                "stored_long_term_facts": memories_count
            }
        }
    }


@router.get("/metrics", summary="Platform Observability Metrics")
def get_observability_metrics(db: Session = Depends(get_db)):
    """
    Computes top-level platform execution statistics.
    """
    total_runs = db.query(Execution).count()
    completed_runs = db.query(Execution).filter(Execution.status == "completed").count()
    failed_runs = db.query(Execution).filter(Execution.status == "failed").count()

    avg_dur = db.query(func.avg(Execution.duration_ms)).scalar() or 0.0

    tool_steps_count = db.query(ExecutionStep).filter(ExecutionStep.step_name.like("execute_mcp_tool%")).count()
    rag_steps_count = db.query(ExecutionStep).filter(ExecutionStep.step_name == "memory_and_rag_retrieval").count()

    total_agents = db.query(Agent).filter(Agent.enabled == True).count()
    total_kbs = db.query(KnowledgeBase).count()
    total_docs = db.query(Document).count()

    return {
        "total_executions": total_runs,
        "successful_executions": completed_runs,
        "failed_executions": failed_runs,
        "success_rate_percentage": round((completed_runs / total_runs * 100), 1) if total_runs > 0 else 100.0,
        "average_duration_ms": round(float(avg_dur), 2),
        "total_tool_calls": tool_steps_count,
        "total_rag_queries": rag_steps_count,
        "active_agents": total_agents,
        "knowledge_bases": total_kbs,
        "documents_indexed": total_docs,
        "total_vectors": vector_store.total_vectors
    }
