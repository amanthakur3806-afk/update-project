# Nexus AI - Detailed Technical Project Report

## 1. Executive summary

Nexus AI is a chatbot-oriented agent platform built with FastAPI, LlamaIndex
Workflows, SQLAlchemy/SQLite, FAISS vector search, and a browser chat
interface. A user selects an agent, submits a prompt, watches live execution
progress, and receives a grounded answer or a confirmed customer operation.

The platform uses one shared orchestration workflow instead of separate
hard-coded chatbots. Each agent is database-configured with its own prompt,
playbook, model settings, memory settings, workflow settings, and allowed
tools. This makes agent behavior configurable without changing the central
workflow.

The repository has been cleaned to focus on the chatbot. The legacy dashboard,
duplicate chat clients, demo controls, migration scripts, and fake demo data
were removed.

## 2. Main capabilities

- Browser chatbot with selectable agents.
- Streaming Live Activity events during each run.
- A Minimize/Show control for Live Activity so final answers remain visible.
- Database-driven agent prompts, playbooks, settings, and tool permissions.
- Query classification and customer/entity extraction.
- Conversation memory and long-term memory facts.
- RAG retrieval from indexed knowledge documents using FAISS.
- MCP tool discovery, permission checks, routing, retries, and timeouts.
- Customer research using CRM and analytics tools.
- Customer status, note, and follow-up task operations.
- Dependency-aware execution for read-before-write operations.
- Execution history, execution steps, prompt audit logs, and operations audits.

## 3. Technology stack

| Layer | Technology |
|---|---|
| HTTP application | FastAPI |
| Workflow engine | LlamaIndex Workflows |
| Database layer | SQLAlchemy with SQLite by default |
| Semantic search | FAISS |
| LLM providers | Groq or OpenAI, with deterministic local grounding fallback |
| Frontend | HTML, CSS, and vanilla JavaScript |
| Tool layer | In-process MCP-style servers |

Run the application with:

~~~
python run.py
~~~

Open http://127.0.0.1:8080/ for the chatbot and
http://127.0.0.1:8080/docs for Swagger API documentation.

## 4. Architecture

~~~
Browser Chat UI
    |
    | POST /agents/{agent_id}/stream
    v
FastAPI
    |
    v
AgentOrchestratorWorkflow
    |
    +-- Agent configuration and permissions (SQLite)
    +-- Query classification
    +-- Conversation memory and long-term facts
    +-- RAG retrieval (FAISS and knowledge documents)
    +-- MCP tool planning and execution
    |     +-- CRM MCP server
    |     +-- Analytics MCP server
    |     +-- Customer Operations MCP server
    +-- Tool-result condensation
    +-- LLM or local grounded response synthesis
    |
    +-- Execution records, step records, memory turns, audit logs
~~~

## 5. User interface

The active UI is in app/static/chat.html. It loads the enabled agents from the
API, opens a stream for each prompt, and renders each progress event in Live
Activity. When an execution completes, it renders the final assistant answer.

### 5.1 Live Activity panel

The Live Activity panel records workflow progress such as:

- Loading the selected agent.
- Classifying the prompt.
- Retrieving memory and knowledge.
- Planning tools.
- Calling MCP tools.
- Combining context.
- Synthesizing the final response.

The panel includes a Minimize button. When minimized, events remain available
in the browser but the event list is hidden. The button changes to Show.

### 5.2 UI files

| File | Role |
|---|---|
| app/static/chat.html | Chat layout and controls |
| app/static/chat-rich.js | Streaming, messages, agent loading, Live Activity toggle |
| app/static/chat.css | Main responsive chat styling |
| app/static/chat-live.css | Live Activity and minimize-button styling |
| app/static/chat-format.css | Assistant answer formatting |
| app/static/chat-polish.css | UI polish |
| app/static/chat-scroll.css | Scroll styling |

## 6. Agents

### 6.1 Customer Research Specialist

Purpose: builds a customer/account summary from CRM records, analytics,
knowledge documents, and memory.

Typical tools:

- CRM.get_customer
- CRM.search_customer
- Analytics.get_customer_metrics
- Analytics.get_customer_history

Example prompts:

- Give me a complete profile for customer ACME.
- Summarize this customer's health and recent activity.
- Compare two customer accounts.

### 6.2 Financial and Metrics Analyst

Purpose: focuses on financial and customer-health data, including ARR, MRR,
NPS, churn risk, usage, errors, tickets, and customer history.

Typical tools:

- Analytics.get_customer_metrics
- Analytics.get_customer_history

### 6.3 Support and SLA Compliance Agent

Purpose: reviews customer information against policy and support context. It
can add CRM notes when its permissions allow it.

Typical tools:

- CRM.get_customer
- CRM.update_notes

### 6.4 Customer Operations Agent

Purpose: performs customer operations and produces a persistent audit trail.

Typical tools:

- Operations.get_customer
- Operations.update_customer_status
- Operations.add_customer_note
- Operations.create_follow_up_task
- Operations.get_audit_history

Example prompts:

- Update customer ACME status to At Risk.
- Add a note to customer ACME: Renewal discussion requested.
- Create a follow-up task for ACME: Schedule renewal meeting.
- Show the audit history for customer ACME.

## 7. Agent workflow

The primary workflow is implemented in app/workflow/agent_workflow.py.

### Stage 1 - Load agent and classify query

The workflow receives the selected agent ID, prompt, optional conversation ID,
and execution ID. It loads the enabled agent and its allowed tools from the
database. The query classifier identifies likely intent, target customer
entities, resource needs, and query type.

An executions record is created with status running. The first
execution_steps row stores details such as selected agent, allowed tools,
detected entities, and query classification.

### Stage 2 - Retrieve memory and knowledge

The workflow retrieves:

- Recent turns from the current conversation.
- Long-term memory facts related to the target entity.
- Relevant knowledge chunks from the agent's configured knowledge base.

RAG is only used when the configured workflow enables it.

### Stage 3 - Plan tools

The planner receives the query, agent-permitted tools, and retrieved knowledge.
It returns an ordered plan. Each step can include a tool name, arguments, an
identifier, and dependencies.

### Stage 4 - Permission check and execution

Before every call, the MCP manager checks whether the selected agent has
permission to run that tool. It then selects the appropriate server, applies a
timeout/retry policy, and records the result.

Each tool call is persisted in execution_steps with input arguments, result or
error, duration, and completion state.

### Stage 5 - Dependency handling

Tool steps can declare prerequisites. If a prerequisite fails, the dependent
step is recorded as skipped and does not run.

The Customer Operations Agent uses a read-before-write pattern:

~~~
Operations.get_customer
  -> Operations.update_customer_status
  -> Operations.add_customer_note
  -> Operations.create_follow_up_task
~~~

If the customer lookup fails, an operations write is blocked.

### Stage 6 - Condense results

The TemporaryResearchSubAgent converts raw results from CRM, Analytics, and
Operations tools into compact grounded context. It also preserves tool errors
and not-found results.

### Stage 7 - Synthesize and save

The final response has access to agent instructions, the user prompt, memory,
RAG context, and condensed tool outcomes. Groq or OpenAI is used when
configured; otherwise the application generates a deterministic grounded
answer.

After synthesis, the workflow:

1. Writes a sanitized prompt audit log under logs/executions.
2. Updates the execution record with final status, answer, and duration.
3. Saves a conversation turn when a conversation ID was supplied.
4. Returns the execution ID, answer, source list, tools used, and status.

## 8. MCP servers and tools

MCP routing and permission enforcement are implemented by
app/mcp/client_manager.py.

### 8.1 CRM MCP server

Implemented in app/mcp/servers/crm_server.py.

| Tool | Role |
|---|---|
| CRM.get_customer | Retrieve one customer record |
| CRM.search_customer | Search customer records |
| CRM.update_notes | Append a timestamped CRM note |

### 8.2 Analytics MCP server

Implemented in app/mcp/servers/analytics_server.py.

| Tool | Role |
|---|---|
| Analytics.get_customer_metrics | Return customer financial, usage, health, and SLA metrics |
| Analytics.get_customer_history | Return customer event history |

### 8.3 Customer Operations MCP server

Implemented in app/mcp/servers/operations_server.py.

| Tool | Role |
|---|---|
| Operations.get_customer | Confirm a customer is available for operations |
| Operations.update_customer_status | Update status and log an audit entry |
| Operations.add_customer_note | Create a persistent operations note and audit entry |
| Operations.create_follow_up_task | Create a task and audit entry |
| Operations.get_audit_history | List operation audit events |

## 9. Customer operations behavior

### 9.1 Customer status update

A status update validates that the customer exists, updates its live CRM
status, updates the matching customer_accounts record, and inserts an
operation_audit_logs record.

### 9.2 Customer note

An add-note operation validates the customer, appends a timestamped note to
the live CRM record, inserts a customer_operation_notes record, and inserts an
operation_audit_logs record.

### 9.3 Follow-up task

A task operation validates the customer, ensures an operational customer
account exists, inserts a follow_up_tasks record, and inserts an
operation_audit_logs record.

## 10. Database design

### 10.1 Agent configuration tables

| Table | Role |
|---|---|
| agents | Agent ID, name, prompt, playbook, model, memory/workflow settings, enabled state |
| agent_tools | Allowed tools assigned to each agent |
| mcp_servers | Registered MCP server configuration |

### 10.2 Execution and audit tables

| Table | Role |
|---|---|
| executions | One agent run, its answer, state, duration, and audit-log path |
| execution_steps | Each workflow stage and MCP call from an execution |
| operation_audit_logs | Auditable customer write events |

### 10.3 Customer operations tables

| Table | Role |
|---|---|
| customer_accounts | Operational customer records |
| customer_operation_notes | Notes created by the Operations Agent |
| follow_up_tasks | Persistent follow-up tasks |

### 10.4 Memory tables

| Table | Role |
|---|---|
| conversations | Conversation session metadata |
| messages | Individual user and assistant messages |
| memories | Long-term reusable facts |

### 10.5 Knowledge tables

| Table | Role |
|---|---|
| knowledge_bases | Knowledge-base registrations |
| documents | Document metadata |
| document_chunks | Chunked searchable document content |

## 11. Knowledge retrieval and memory

Knowledge files live in the knowledge directory. They are registered in
SQLite, split into chunks, embedded, and indexed in FAISS. During a run, the
workflow searches the knowledge-base partition configured for the selected
agent.

The Knowledge API supports listing knowledge bases/documents, inspecting
chunks, uploading and ingesting documents, deleting a document with its
vectors, reindexing, and rebuilding vector indexes.

Memory has two levels:

- Short-term memory contains recent turns from the active conversation.
- Long-term memory stores persistent facts which may be retrieved for an
  entity.

## 12. API reference

### Agents

| Endpoint | Method | Purpose |
|---|---|---|
| /agents | GET | List configured agents |
| /agents | POST | Create an agent |
| /agents/{agent_id} | GET | Read agent details |
| /agents/{agent_id}/config | GET | Read agent configuration |
| /agents/{agent_id}/config | PUT | Update agent configuration and allowed tools |
| /agents/{agent_id}/run | POST | Run an agent and return a final result |
| /agents/{agent_id}/stream | POST | Run an agent with streamed progress |

### Executions

| Endpoint | Method | Purpose |
|---|---|---|
| /executions | GET | List execution history |
| /executions/{execution_id} | GET | Read execution details |
| /executions/{execution_id}/trace | GET | Read the concise workflow trace |
| /executions/{execution_id}/prompt | GET | Read the sanitized prompt audit log |

### Knowledge

| Endpoint | Method | Purpose |
|---|---|---|
| /knowledge/bases | GET/POST | List or register knowledge bases |
| /knowledge/documents | GET | List indexed documents |
| /knowledge/documents/{document_id}/chunks | GET | Inspect document chunks |
| /knowledge/documents/{document_id} | DELETE | Delete document and purge vectors |
| /knowledge/upload | POST | Upload and ingest a document |
| /knowledge/reindex | POST | Reindex a knowledge-base directory |
| /knowledge/rebuild | POST | Rebuild vector indexes |

### Other routes

| Route | Purpose |
|---|---|
| /memory | Conversation and long-term memory management |
| /mcp | MCP server registration and tool discovery |
| /system/health | Component health |
| /system/metrics | Execution and platform metrics |

## 13. Security, audit, and reliability

### Tool permissions

Every MCP call is checked against the selected agent's allowed tool list.
Unauthorized tools are blocked before execution.

### Secret redaction

Before writing a prompt audit log, the workflow redacts values that resemble
API keys, bearer tokens, passwords, and secrets.

### Operation auditing

Each customer mutation stores the agent ID, tool name, customer ID, action,
old/new values where applicable, success state, and timestamp in
operation_audit_logs.

### Explicit missing-data behavior

The application does not invent customer records, metrics, or tool results. A
missing customer results in an explicit not-found response.

## 14. Current data limitation

Fake customer fixtures were removed during project cleanup. The CRM and
Analytics data service therefore starts empty until it is populated by a real
integration or data-loading mechanism.

As a result, a prompt for a customer such as ABC will produce a not-found
result unless that customer is available in the live data service. The
Operations Agent also requires a successful customer lookup before it can
write a status, note, or task.

## 15. Repository layout

~~~
app/
  api/                 FastAPI routers
  mcp/                 MCP client manager and server implementations
  memory/              Conversation and long-term memory logic
  models/              SQLAlchemy database models
  rag/                 Embeddings, ingestion, and FAISS vector store
  schemas/             API request/response schemas
  services/            Data service, progress events, query classifier
  static/              Active chatbot UI
  workflow/            Agent workflow, events, synthesis, condensation
knowledge/             RAG source documents
logs/executions/       Sanitized execution audit logs
tests/                 Chatbot, API, workflow, and RAG tests
run.py                 Application startup
~~~

## 16. Verification

After the chatbot-focused cleanup, the remaining project test suite completed
successfully:

~~~
11 passed
~~~

The verified coverage includes the API, agent workflow, execution persistence,
and RAG retrieval.

## 17. Recommended next steps

1. Connect CRM and Analytics tools to persistent real data sources.
2. Add authenticated user identity and authorization for customer writes.
3. Add an explicit confirmation/approval mechanism for write operations.
4. Add dedicated API endpoints for operation notes and follow-up tasks.
5. Add production database migrations.
6. Add isolated integration-test data instead of restored fake fixtures.
