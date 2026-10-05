"""
Database & Platform Initialization
==================================
Initializes database schema, seeds dynamic agent configurations with categories,
registers MCP servers, populates long-term memories, and handles Demo Mode
data ingestion.
"""
import sys
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models.agent import Agent, AgentTool
from app.models.mcp import MCPServer
from app.models.knowledge import KnowledgeBase, Document
from app.rag.ingest import ingest_knowledge_base
from app.rag.vector_store import vector_store

CUSTOMER_RESEARCH_PLAYBOOK = """# Customer Research Playbook
## 1. Role & Responsibilities
You are an elite enterprise Customer Research and Account Intelligence agent. Your responsibility is to provide accurate, authoritative, and actionable dossiers on contracted enterprise accounts by orchestrating CRM data, analytics telemetry, internal knowledge documentation, and past interaction memories.

## 2. Standard Operating Procedure (Workflow)
1. Account Identity Resolution: Identify the customer ID from the user query (e.g. 'ABC', 'XYZ', 'ACME').
2. CRM Query: Use CRM.get_customer to fetch the account profile, tier, primary stakeholders, SLA status, and contract terms.
3. Analytics Telemetry: Use Analytics.get_customer_metrics to retrieve ARR, MRR, NPS, churn risk, API activity, and ticket resolution velocity.
4. Historical Events: Use Analytics.get_customer_history to examine recent business reviews, upgrades, and incidents.
5. Internal Knowledge Documentation (RAG): Query the customer_docs knowledge base to incorporate internal architecture details, integrations, and operational notes.
6. Memory Integration: Check short-term dialogue context and incorporate long-term preferences (such as billing schedules or communication channels).

## 3. Output Format & Guidelines
- Executive Summary: Concise overview of company tier, health, and SLA status.
- Key Stakeholders & Contacts: Primary technical and commercial leads.
- Operational & Telemetry Metrics: Highlight NPS, ARR, churn probability, and API call volumes.
- Technical Architecture & SLA Guarantees: Detail ingestion pipelines, burst allowances, and escalation rules.
- Actionable Recommendations: Proactive next steps for account teams.

## 4. Escalation & Guardrail Rules
- If an account has an active Sev-1 incident, immediately flag the Platinum TAM contact.
- Do not expose private credentials, tokens, or raw unredacted secrets.
- Reject requests to modify billing terms without finance team approval.
"""

FINANCIAL_ANALYST_PLAYBOOK = """# Financial Analyst Playbook
## Role
Financial health and metric forecasting agent. Analyzes ARR, MRR, churn probability, and contract renewal horizons.
## Tool Guidelines
Use Analytics MCP tools exclusively. Do not access CRM notes without customer authorization.
"""

SUPPORT_COMPLIANCE_PLAYBOOK = """# Support Compliance Playbook
## Role
Verifies adherence to Enterprise SLAs, incident resolution windows, and corporate policies.
## Tool Guidelines
Use CRM.get_customer and verify contractual SLA tiers against company_policies documentation.
"""


def seed_database():
    """Initializes tables, agents, MCP registrations, and indexes knowledge files."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. MCP Server Registrations
        servers = [
            MCPServer(
                server_id="crm_mcp",
                server_name="CRM MCP Server",
                server_url="app/mcp/servers/crm_server.py",
                transport="inprocess",
                configuration={"capabilities": ["get_customer", "search_customer", "update_notes"]}
            ),
            MCPServer(
                server_id="analytics_mcp",
                server_name="Analytics MCP Server",
                server_url="app/mcp/servers/analytics_server.py",
                transport="inprocess",
                configuration={"capabilities": ["get_customer_metrics", "get_customer_history"]}
            ),
            MCPServer(
                server_id="operations_mcp",
                server_name="Customer Operations MCP Server",
                server_url="app/mcp/servers/operations_server.py",
                transport="inprocess",
                configuration={
                    "capabilities": [
                        "Operations.create_customer",
                        "Operations.list_customers",
                        "Operations.get_customer",
                        "Operations.update_customer_status",
                        "Operations.add_customer_note",
                        "Operations.get_customer_notes",
                        "Operations.create_follow_up_task",
                        "Operations.list_follow_up_tasks",
                        "Operations.update_follow_up_task_status",
                        "Operations.get_audit_history",
                    ],
                    "implementation_status": "ready",
                },
                enabled=True,
            )
        ]
        for s in servers:
            existing = db.query(MCPServer).filter(MCPServer.server_id == s.server_id).first()
            if not existing:
                db.add(s)
        db.commit()

        # 2. Dynamic Agents with Categories
        agents_data = [
            {
                "agent_id": "customer_research_agent",
                "agent_name": "Customer Research Specialist",
                "category": "Research",
                "description": "Enterprise agent orchestrating CRM, analytics, internal docs, and memory for full account analysis.",
                "system_prompt": "You are a Senior Customer Research Analyst at a high-growth platform. You deliver rigorous, executive-ready account dossiers using verified CRM and Analytics tools.",
                "playbook": CUSTOMER_RESEARCH_PLAYBOOK,
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "memory_configuration": {"short_term": True, "long_term": True},
                "workflow_configuration": {
                    "max_iterations": 10,
                    "enable_subagents": True,
                    "rag_enabled": True,
                    "knowledge_base": "customer_docs"
                },
                "tools": [
                    ("CRM.get_customer", "crm_mcp"),
                    ("CRM.search_customer", "crm_mcp"),
                    ("Analytics.get_customer_metrics", "analytics_mcp"),
                    ("Analytics.get_customer_history", "analytics_mcp")
                ]
            },
            {
                "agent_id": "financial_analyst_agent",
                "agent_name": "Financial & Metrics Analyst",
                "category": "Finance",
                "description": "Specialized agent analyzing customer financial metrics, ARR, and churn risk.",
                "system_prompt": "You are a Financial Operations Specialist focusing on SaaS unit economics and customer health metrics.",
                "playbook": FINANCIAL_ANALYST_PLAYBOOK,
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "memory_configuration": {"short_term": True, "long_term": False},
                "workflow_configuration": {
                    "max_iterations": 6,
                    "enable_subagents": False,
                    "rag_enabled": True,
                    "knowledge_base": "technical_docs"
                },
                "tools": [
                    ("Analytics.get_customer_metrics", "analytics_mcp"),
                    ("Analytics.get_customer_history", "analytics_mcp")
                ]
            },
            {
                "agent_id": "support_compliance_agent",
                "agent_name": "Support & SLA Compliance Agent",
                "category": "Compliance",
                "description": "Audits SLA response times and verifies incident resolution compliance against policy.",
                "system_prompt": "You are an Enterprise SLA & Policy Compliance Auditor.",
                "playbook": SUPPORT_COMPLIANCE_PLAYBOOK,
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "memory_configuration": {"short_term": True, "long_term": True},
                "workflow_configuration": {
                    "max_iterations": 6,
                    "enable_subagents": False,
                    "rag_enabled": True,
                    "knowledge_base": "company_policies"
                },
                "tools": [
                    ("CRM.get_customer", "crm_mcp"),
                    ("CRM.update_notes", "crm_mcp")
                ]
            }
        ]

        for a_dict in agents_data:
            agent = db.query(Agent).filter(Agent.agent_id == a_dict["agent_id"]).first()
            if not agent:
                agent = Agent(
                    agent_id=a_dict["agent_id"],
                    agent_name=a_dict["agent_name"],
                    category=a_dict.get("category", "General"),
                    description=a_dict["description"],
                    system_prompt=a_dict["system_prompt"],
                    playbook=a_dict["playbook"],
                    model=a_dict["model"],
                    temperature=a_dict["temperature"],
                    memory_configuration=a_dict["memory_configuration"],
                    workflow_configuration=a_dict["workflow_configuration"],
                    enabled=True
                )
                db.add(agent)
                db.flush()

                for tool_name, srv_id in a_dict["tools"]:
                    tool = AgentTool(
                        agent_id=agent.agent_id,
                        tool_name=tool_name,
                        server_id=srv_id,
                        enabled=True
                    )
                    db.add(tool)
            else:
                # Update category if needed
                agent.category = a_dict.get("category", "General")

        db.commit()

        # Future write-capable agent. It remains disabled until the
        # operations MCP handlers and confirmation flow are implemented.
        operations_agent = db.query(Agent).filter(
            Agent.agent_id == "customer_operations_agent"
        ).first()
        if not operations_agent:
            operations_agent = Agent(
                agent_id="customer_operations_agent",
                agent_name="Customer Operations Agent",
                category="Operations",
                description="Manages customer accounts, notes, follow-up tasks, and operation audit history.",
                system_prompt=(
                    "You are a customer operations assistant. Use only approved operations MCP tools "
                    "and clearly report every completed or failed customer operation."
                ),
                playbook=(
                    "Read customer context before changes. Every write must be transactional, "
                    "audited, and based on a successful customer lookup."
                ),
                model="gpt-4o-mini",
                temperature=0.0,
                memory_configuration={"short_term": True, "long_term": False},
                workflow_configuration={
                    "max_iterations": 5,
                    "enable_subagents": False,
                    "rag_enabled": False,
                    "knowledge_base": "customer_docs",
                },
                enabled=True,
            )
            db.add(operations_agent)
            db.flush()
            for tool_name in [
                "Operations.create_customer",
                "Operations.list_customers",
                "Operations.get_customer",
                "Operations.update_customer_status",
                "Operations.add_customer_note",
                "Operations.get_customer_notes",
                "Operations.create_follow_up_task",
                "Operations.list_follow_up_tasks",
                "Operations.update_follow_up_task_status",
                "Operations.get_audit_history",
            ]:
                db.add(AgentTool(
                    agent_id=operations_agent.agent_id,
                    tool_name=tool_name,
                    server_id="operations_mcp",
                    enabled=True,
                ))

        # Upgrade existing scaffold records in copied databases as well.
        operations_agent.enabled = True
        operations_agent.agent_name = "Customer Operations Agent"
        operations_agent.description = "Executes permissioned customer status, note, and follow-up operations with audit history."
        operation_tool_names = [
            "Operations.create_customer",
            "Operations.list_customers",
            "Operations.get_customer",
            "Operations.update_customer_status",
            "Operations.add_customer_note",
            "Operations.get_customer_notes",
            "Operations.create_follow_up_task",
            "Operations.list_follow_up_tasks",
            "Operations.update_follow_up_task_status",
            "Operations.get_audit_history",
        ]
        existing_operation_tools = {
            tool.tool_name: tool
            for tool in db.query(AgentTool).filter(AgentTool.agent_id == operations_agent.agent_id).all()
        }
        for tool_name in operation_tool_names:
            if tool_name not in existing_operation_tools:
                db.add(AgentTool(
                    agent_id=operations_agent.agent_id,
                    tool_name=tool_name,
                    server_id="operations_mcp",
                    enabled=True,
                ))
        for operation_tool in existing_operation_tools.values():
            operation_tool.enabled = True
        operations_server = db.query(MCPServer).filter(MCPServer.server_id == "operations_mcp").first()
        if operations_server:
            operations_server.enabled = True
            operations_server.server_name = "Customer Operations MCP Server"
            operations_server.configuration = {
                "capabilities": operation_tool_names,
                "implementation_status": "ready",
            }
        db.commit()

        # Ingest Knowledge Bases into SQL and FAISS
        kb_dirs = [
            ("customer_docs", "Customer Documents", settings.KNOWLEDGE_BASE_DIR / "customer_docs"),
            ("company_policies", "Company Policies", settings.KNOWLEDGE_BASE_DIR / "company_policies"),
            ("technical_docs", "Technical Documentation", settings.KNOWLEDGE_BASE_DIR / "technical_docs")
        ]

        # Ensure all KnowledgeBase records exist in SQL
        for kb_id, kb_name, kb_path in kb_dirs:
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == kb_id).first()
            if not kb:
                kb = KnowledgeBase(
                    kb_id=kb_id,
                    name=kb_name,
                    description=f"Knowledge base partition for {kb_name}",
                    folder_path=str(kb_path),
                    chunk_size=400,
                    chunk_overlap=50
                )
                db.add(kb)
            else:
                # Keep seeded knowledge bases anchored to this checkout. The
                # database may have been copied from another machine and can
                # otherwise retain a stale absolute folder path.
                kb.folder_path = str(kb_path)
        db.commit()

        # Ingest documents if DB or vector store is empty
        doc_count = db.query(Document).count()
        if doc_count == 0 or vector_store.total_vectors == 0:
            for kb_id, kb_name, kb_path in kb_dirs:
                if kb_path.exists():
                    ingest_knowledge_base(
                        kb_id=kb_id,
                        folder_path=str(kb_path),
                        db=db,
                        chunk_size=400,
                        chunk_overlap=50
                    )

        # 6. Clean Startup Status Log (Section 29)
        llm_desc = "Local Deterministic Engine"
        if settings.GROQ_API_KEY:
            llm_desc = f"Groq Live API ({settings.GROQ_MODEL})"
        elif settings.OPENAI_API_KEY:
            llm_desc = f"OpenAI Live API ({settings.OPENAI_MODEL})"

        doc_count = db.query(Document).count()
        print("=" * 65)
        print("  NEXUS AI — AGENT OPERATIONS PLATFORM INITIALIZED")
        print("=" * 65)
        print("  [+] Database:       Ready (SQLite / SQLAlchemy)")
        print("  [+] MCP Servers:    2 Registered (CRM & Analytics)")
        print("  [+] Knowledge Bases:3 Active (customer_docs, company_policies, technical_docs)")
        print(f"  [+] Documents:      {doc_count} Files Indexed")
        print(f"  [+] Vectors:        {vector_store.total_vectors} Chunks in FAISS")
        print(f"  [+] LLM Provider:   {llm_desc}")
        print("=" * 65)

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
