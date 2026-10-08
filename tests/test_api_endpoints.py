import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_agents():
    response = client.get("/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) >= 3
    ids = [a["agent_id"] for a in agents]
    assert "customer_research_agent" in ids

def test_get_agent_config():
    response = client.get("/agents/customer_research_agent/config")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "customer_research_agent"
    assert "CRM.get_customer" in data["allowed_tools"]
    assert "Analytics.get_customer_metrics" in data["allowed_tools"]

def test_list_executions():
    response = client.get("/executions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_agent_config():
    # Update temperature
    response = client.put(
        "/agents/customer_research_agent/config",
        json={"temperature": 0.25}
    )
    assert response.status_code == 200
    assert response.json()["temperature"] == 0.25

def test_mcp_endpoints():
    # Servers
    res_servers = client.get("/mcp/servers")
    assert res_servers.status_code == 200
    assert len(res_servers.json()) >= 2

    # Tools
    res_tools = client.get("/mcp/tools")
    assert res_tools.status_code == 200
    tool_names = [t["tool_name"] for t in res_tools.json()]
    assert "CRM.get_customer" in tool_names

def test_run_agent_api():
    response = client.post(
        "/agents/customer_research_agent/run",
        json={
            "query": "Give me a complete summary of customer ABC including recent activity and internal documentation.",
            "conversation_id": "api_test_conv"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "execution_id" in data
    assert len(data["answer"]) > 50

    # Test trace retrieval
    exec_id = data["execution_id"]
    trace_res = client.get(f"/executions/{exec_id}/trace")
    assert trace_res.status_code == 200
    assert len(trace_res.json()["trace"]) >= 5

    # Test prompt retrieval
    prompt_res = client.get(f"/executions/{exec_id}/prompt")
    assert prompt_res.status_code == 200
    assert "ORCHESTRATED MULTI-MCP AGENT EXECUTION AUDIT LOG" in prompt_res.text


def test_stream_agent_api():
    import json
    response = client.post(
        "/agents/customer_research_agent/stream",
        json={
            "query": "Give me a summary of ABC",
            "conversation_id": "test_stream_conv"
        },
        headers={"Accept": "text/event-stream"}
    )
    assert response.status_code == 200
    lines = response.text.split("\n")
    tokens = []
    complete = None
    for line in lines:
        if line.startswith("data: "):
            d = json.loads(line[6:])
            if d.get("type") == "token":
                tokens.append(d.get("delta", ""))
            elif d.get("type") == "complete":
                complete = d
    assert len(tokens) > 0
    assert complete is not None
    assert complete["status"] == "completed"


def test_multi_chat_session_lifecycle():
    import uuid
    cid = f"test_multi_chat_{uuid.uuid4().hex[:8]}"
    sid = f"sess_{uuid.uuid4().hex[:8]}"

    # 1. Create a conversation with session_id
    create_res = client.post(
        "/memory/conversations",
        json={
            "conversation_id": cid,
            "agent_id": "luna",
            "title": "Account Review Session",
            "session_id": sid
        }
    )
    assert create_res.status_code == 201
    assert create_res.json()["conversation_id"] == cid
    assert create_res.json()["session_id"] == sid

    # 2. List conversations by session_id
    list_res = client.get(f"/memory/conversations?session_id={sid}")
    assert list_res.status_code == 200
    convs = list_res.json()
    assert len(convs) >= 1
    assert convs[0]["conversation_id"] == cid
    assert convs[0]["title"] == "Account Review Session"

    # 3. Rename conversation title
    patch_res = client.patch(
        f"/memory/conversations/{cid}",
        json={"title": "Renamed Operations Chat"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Renamed Operations Chat"

    # 4. Run agent query inside this conversation session
    run_res = client.post(
        "/agents/luna/run",
        json={
            "query": "Lookup customer NovaHealth details",
            "conversation_id": cid,
            "session_id": sid
        }
    )
    assert run_res.status_code == 200
    assert run_res.json()["status"] == "completed"

    # 5. Get full conversation history
    detail_res = client.get(f"/memory/conversations/{cid}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["messages"]) >= 2
    assert detail["title"] == "Renamed Operations Chat"

    # 6. Delete conversation
    del_res = client.delete(f"/memory/conversations/{cid}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
