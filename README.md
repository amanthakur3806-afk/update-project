# Nexus AI: Orchestrated Multi-MCP AI Agent Operations Platform

Production-grade AI agent operations platform coordinating multiple **Model Context Protocol (MCP)** servers, **LlamaIndex Workflows**, dynamic database-driven agent playbooks, **FAISS vector search (RAG)** with anti-stale cache invalidation, and dual-tier memory.

Built with **FastAPI**, **LlamaIndex Workflows**, **FAISS**, **SQLite / SQLAlchemy**, and **Vanilla JavaScript** (Zero Gradients, Zero Emojis, Dark Slate-Zinc Console theme).

---

## 1. What is this? (5-Minute Mental Model)

Modern enterprise AI applications require coordinating tools and data across fragmented sources:
- **CRM Systems**: Who is this customer? What is their SLA and contract tier?
- **Analytics Platforms**: What is their ARR, monthly API usage, and churn risk?
- **Knowledge Bases**: What are our architecture specifications and corporate SLA policies?
- **Conversation Memory**: What was discussed earlier? What are their communication preferences?
- **Temporary Sub-Agents**: How do we condense raw tool outputs before LLM synthesis?

The platform maps to a clear mental model:

```
USER
  │
  ▼
FASTAPI REST API
  │
  ▼
AGENT (Loaded from SQL: category, system prompt, playbook, permissions)
  │
  ▼
LLAMAINDEX WORKFLOW
  ├── 1. QUERY CLASSIFICATION (Intent, entities, required resources)
  ├── 2. SHORT-TERM & LONG-TERM MEMORY (Recent dialogue + persistent facts)
  ├── 3. RAG RETRIEVAL (FAISS vector search across isolated partitions)
  ├── 4. DUAL MCP TOOL CALLS (CRM.get_customer + Analytics.get_metrics)
  └── 5. TEMPORARY SUB-AGENT (Condenses raw JSON payloads)
  │
  ▼
LLM SYNTHESIS (Groq, OpenAI, or Grounded Offline Engine)
  │
  ▼
STRUCTURED OUTPUT + SANITIZED AUDIT LOG (final_prompt.txt)
  │
  ▼
NEXUS AI CONSOLE (Simple View & Technical View)
```

---

## 2. Architecture Diagram

```
                           USER / BROWSER / SWAGGER
                                      │
                                      ▼
                      NEXUS AI OPERATIONS CONSOLE
                         (http://localhost:8080/)
                                      │
                                      ▼
                               FASTAPI API
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
             /agents & /executions             /system & /knowledge
                    │
                    ▼
           AgentOrchestratorWorkflow (LlamaIndex)
                    │
       ┌────────────┼───────────────────┐
       ▼            ▼                   ▼
    Memory         RAG                 MCP
       │            │                   │
       ▼            ▼            ┌──────┴──────┐
     SQLite       FAISS          ▼             ▼
    (Session) (IndexFlatIP)   CRM MCP    Analytics MCP
                    │            │             │
                Knowledge        └──────┬──────┘
                  Files                 │
                                        ▼
                                   DataService
                                        │
                                   demo_data/
                               (External Fixtures)
                                        │
                                        ▼
                                  LLM Provider
                               ┌────────┴────────┐
                               ▼                 ▼
                          Groq / OpenAI    Offline Grounded
                                               Engine
                                        │
                                        ▼
                                Execution Trace &
                                 final_prompt.txt
```

---

## 3. Quick Start

### Prerequisites
- Python 3.12 (`py -3.12` on Windows)
- Dependencies installed via `requirements.txt`:
  ```powershell
  pip install -r requirements.txt
  ```

### Run Server (Default Port: 8080)
```powershell
cd "c:\Users\91887\Downloads\main-project-main"
py -3.12 run.py
```

Open the interfaces:
- **Operations Console**: [http://localhost:8080/](http://localhost:8080/)
- **Swagger Interactive API**: [http://localhost:8080/docs](http://localhost:8080/docs)
- **Health Diagnostic**: [http://localhost:8080/system/health](http://localhost:8080/system/health)

---

## 4. Demo Mode & External Fixtures (Zero Hardcoded Data)

A key architectural principle of the platform:

```
SOURCE CODE  = logic + schemas + workflow + configuration
DATA         = external JSON / CSV / PDF / DOCX / database
```

**Zero business data is hardcoded in Python.**
- `crm_server.py` and `analytics_server.py` delegate 100% of data queries to `DataService`.
- External demo fixtures live strictly in `demo_data/`:
  - `demo_data/crm/customers.json`: 6 customer records (`ABC`, `XYZ`, `ACME`, `NOVA`, `FINTECH`, `CLOUD`)
  - `demo_data/analytics/metrics.json`: ARR, MRR, churn risk, NPS, SLA compliance
  - `demo_data/analytics/history.json`: QBRs, capacity upgrades, incident logs
  - `demo_data/knowledge/`: Source documents for RAG

### Zero Silent Fallbacks Rule
If customer `NON_EXISTENT` is queried, or if customer `ABC` is deleted via the API:
- The system returns an explicit `found: False` status: `"Customer not found in CRM data source."`
- The platform **never** silently fabricates an imaginary customer or metrics.

---

## 5. How RAG Works & Dynamic Lifecycle

- **Vector Store**: FAISS `IndexFlatIP` (cosine similarity on L2-normalised 384-dimensional embeddings).
- **Graceful Fallback**: If FAISS is ever unavailable in an environment, falls back transparently to NumPy inner-product cosine search.
- **Partition Isolation**: Every vector chunk is tagged with `kb_id` (`customer_docs`, `company_policies`, `technical_docs`). Agents can never retrieve unauthorized chunks from other partitions.
- **Anti-Stale Vector Invalidation**:
  When a document is deleted via `DELETE /knowledge/documents/{id}`, its vectors and metadata are **immediately purged from FAISS**. Stale citations can never survive document deletion.
- **Index Rebuild**:
  `POST /knowledge/rebuild` allows clearing the index and vectorizing all files from scratch at any time.

---

## 6. How MCP Works (Multiple Servers & Tool Calling)

The platform implements two in-process MCP servers conforming to the Model Context Protocol:

| Server ID | Server Name | Registered Tools | Description |
|-----------|-------------|------------------|-------------|
| `crm_mcp` | CRM MCP Server | `CRM.get_customer`<br>`CRM.search_customer`<br>`CRM.update_notes` | Customer profiles, SLA tier, stakeholders, contract terms |
| `analytics_mcp` | Analytics MCP Server | `Analytics.get_customer_metrics`<br>`Analytics.get_customer_history` | ARR, MRR, churn risk, NPS score, active users, incident timeline |

- **Dynamic Discovery**: Client manager inspects `list_tools()` on boot.
- **Agent Permission Guard**: The workflow enforces that an agent can only execute tools explicitly granted in SQL (`agent_tools` table). Unauthorized tool attempts are blocked with audit logs.
- **Tool Name Normalization**: Resolves aliases and case variations (e.g. `CRM.get_customer`, `crm.get_customer`, `get_customer`).

---

## 7. How Agents Work (Database-Driven Configuration & Categories)

Agent configurations are stored entirely in the SQLite database (`agents` table). Updating an agent's prompt, playbook, model, or allowed tools does **not** require modifying Python code.

### Pre-Configured Agents & Categories

1. **Customer Research Specialist (`customer_research_agent`)**
   - **Category**: `Research`
   - **Capabilities**: CRM MCP + Analytics MCP + RAG (`customer_docs`) + Memory
   - **Playbook**: Comprehensive executive dossiers, stakeholder mapping, SLA analysis.

2. **Financial & Metrics Analyst (`financial_analyst_agent`)**
   - **Category**: `Finance`
   - **Capabilities**: Analytics MCP + RAG (`technical_docs`)
   - **Playbook**: SaaS unit economics, ARR/MRR trends, churn risk mitigation.

3. **Support & SLA Compliance Agent (`support_compliance_agent`)**
   - **Category**: `Compliance`
   - **Capabilities**: CRM MCP + RAG (`company_policies`)
   - **Playbook**: SLA verification against enterprise escalation guidelines.

---

## 8. Memory Management (Dual-Tier)

- **Short-Term Memory**:
  Stored in `conversations` and `messages` tables. Maintains dialogue history per `conversation_id`, sliding window of recent user and assistant turns.
- **Long-Term Memory**:
  Stored in `memories` table. Persistent semantic facts (e.g. communication preferences, SLA guarantees) with importance scores. Loaded dynamically based on target entity (e.g. `customer:ABC`).
- **Memory Inspector**:
  The UI and API allow inspecting conversations, viewing turns, clearing conversations, and deleting specific semantic facts. Deleting a fact proves anti-stale memory behavior.

---

## 9. LlamaIndex Workflow (10 Steps)

The orchestrator executes an event-driven LlamaIndex Workflow:

```
[StartEvent]
     │
     ▼
Step 1: step_load_agent
        Load agent config from SQL + Smart Query Classification
     │
     ▼
Step 2: step_load_memory_and_rag
        Load short-term turns, long-term facts, and FAISS RAG chunks
     │
     ▼
Step 3: step_plan_tools
        Tool planning across CRM and Analytics MCP servers
     │
     ▼
Step 4: step_execute_tools (Permission Guard & Multi-MCP Execution)
        Strict SQL permission check followed by tool execution
     │
     ▼
Step 5: step_subagent_and_context
        Temporary research sub-agent condenses JSON outputs
     │
     ▼
Step 6: step_synthesize_and_save
        LLM synthesis, sanitized final_prompt.txt audit logging, SQL persistence
     │
     ▼
[StopEvent]
```

---

## 10. REST API Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/agents` | GET / POST | List or create agents |
| `/agents/{id}/config` | GET / PUT | Read or dynamically update agent configuration |
| `/agents/{id}/run` | POST | Trigger workflow execution with user query |
| `/executions` | GET | List execution history |
| `/executions/{id}/trace` | GET | Step-by-step trace with durations and payloads |
| `/executions/{id}/prompt` | GET | Sanitized prompt audit log (`final_prompt.txt`) |
| `/knowledge/bases` | GET / POST | Knowledge base partitions with chunk stats |
| `/knowledge/documents` | GET | List indexed documents |
| `/knowledge/documents/{id}/chunks` | GET | Inspect chunks for a document |
| `/knowledge/documents/{id}` | DELETE | Delete document and purge vectors from FAISS |
| `/knowledge/upload` | POST | Ingest document into FAISS + SQL |
| `/knowledge/rebuild` | POST | Clear and rebuild all FAISS indexes |
| `/mcp/servers` | GET | Registered MCP servers and status |
| `/mcp/tools` | GET | Discovered MCP tools catalog |
| `/data/crm/customers` | GET / POST | Dynamic CRM customer CRUD |
| `/data/crm/customers/{id}` | DELETE | Delete customer (Test Zero Silent Fallback) |
| `/data/analytics/metrics` | GET / POST | Dynamic Analytics metrics CRUD |
| `/data/demo/reload` | POST | Reload external demo fixtures |
| `/data/demo/clear` | POST | Clear business data (Test empty state) |
| `/memory/conversations` | GET | List conversation sessions |
| `/memory/items` | GET / POST | Long-term memory CRUD |
| `/system/health` | GET | Component diagnostics (DB, LLM, MCP, Vector Store) |
| `/system/metrics` | GET | Platform execution statistics |
| `/system/mode` | POST | Toggle Demo Mode vs Real Mode |

---

## 11. Security & Redaction

- **Secret Redaction**:
  All execution logs and `final_prompt.txt` files pass through regex redaction patterns that scrub API keys (`sk-...`, `gsk_...`), Bearer tokens, and password fields.
- **Agent Permission Sandboxing**:
  Agents are restricted to their assigned tools in SQL. An agent cannot invoke unauthorized tools from other MCP servers.

---

## 12. Testing

The platform includes 22 automated tests covering all functional and architectural requirements:

```powershell
py -3.12 -m pytest tests/ -v
```

### Test Suite Breakdown:
- **`tests/test_api_endpoints.py`** (6 tests): Health, agent list, config retrieval, config dynamic update, MCP tools discovery, agent run API.
- **`tests/test_enhancements.py`** (9 tests): Zero silent fallback on missing customer, delete CRM customer makes it unavailable, delete analytics metrics makes them unavailable, delete document purges FAISS vectors, delete memory fact, FAISS rebuild from scratch, smart query classification, agent category classification, system health diagnostics.
- **`tests/test_mcp_execution.py`** (3 tests): Tool discovery, multi-server tool execution (CRM + Analytics in single workflow), agent permission guard enforcement.
- **`tests/test_rag_retrieval.py`** (3 tests): Semantic chunking logic, embedding generation, FAISS search and knowledge base partition isolation.
- **`tests/test_workflow_run.py`** (1 test): End-to-end LlamaIndex workflow execution.

---

## 13. UI Design Principles

- **Developer Console Aesthetic**: Dark slate-zinc console (`#09090b` base, `#121215` surface, `#2a2a30` border).
- **Strictly Zero Gradients**: All surfaces and buttons use solid accents (`#2563eb`).
- **Strictly Zero Emojis**: Clean SVG icons and text badges only.
- **Simple View vs Technical View**:
  - *Simple View*: Executive grounded answer, source cards, and tools used.
  - *Technical View*: Step-by-step execution timeline with duration breakdown, sanitized prompt audit log, raw MCP JSON payloads, and memory context.
