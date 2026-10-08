"""
Test Cross-Chat User Memory & Context Retention
Verifies that:
1. User preferences, projects, and context are automatically extracted and persisted.
2. When starting a NEW conversation with a DIFFERENT conversation_id, the user's learned memory is remembered.
3. User memory is isolated between different accounts.
4. User memory endpoints allow inspecting and managing persistent memories.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.seed_data import seed_default_users
from app.memory.memory_manager import memory_manager
from app.memory.store import MemoryStore
from app.models.memory import Memory

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db = SessionLocal()
    try:
        seed_default_users(db)
    finally:
        db.close()


def test_automatic_user_fact_extraction_and_persistence():
    """Verify memory_manager extracts stated user facts and preferences."""
    db = SessionLocal()
    try:
        test_uid = "usr_mem_test_01"
        
        # Simulate user stating a preference and project in chat 1
        query_1 = "Please remember that I prefer concise bullet points and my primary project is Cloud Migration 2026."
        memory_manager.save_turn(
            db=db,
            conversation_id="conv_session_1",
            agent_id="luna",
            user_query=query_1,
            assistant_response="Got it! I will remember your preference for concise bullet points and your focus on Cloud Migration 2026.",
            user_id=test_uid
        )

        # Query user memories
        user_mems = MemoryStore.search_user_memories(db, user_id=test_uid)
        assert len(user_mems) >= 1
        contents = " ".join([m.content for m in user_mems]).lower()
        assert "concise bullet points" in contents or "cloud migration 2026" in contents

        # In a completely DIFFERENT conversation (conv_session_2), load memory context
        loaded = memory_manager.load_memory_context(
            db=db,
            conversation_id="conv_session_2",  # Different chat
            query="Can you summarize our plan?",
            user_id=test_uid
        )

        assert len(loaded["user_facts"]) >= 1
        combined_facts_str = " ".join(loaded["long_term_facts"]).lower()
        assert "concise" in combined_facts_str or "migration" in combined_facts_str

    finally:
        db.query(Memory).filter(Memory.user_id == test_uid).delete()
        db.commit()
        db.close()


def test_user_memory_api_endpoints():
    """Verify GET, POST, DELETE /memory/user endpoints with JWT auth."""
    # 1. Login Sarah
    login_res = client.post("/auth/login", json={
        "username_or_email": "sarah",
        "password": "LunaDemo2026!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Add manual preference via API
    add_res = client.post("/memory/user", json={
        "content": "Prefers revenue metrics formatted with quarterly run-rate",
        "memory_type": "user_preference",
        "importance": 1.5
    }, headers=headers)
    assert add_res.status_code == 201
    mem_id = add_res.json()["memory"]["id"]

    # 3. List user memories
    list_res = client.get("/memory/user", headers=headers)
    assert list_res.status_code == 200
    mems = list_res.json()
    assert any(m["id"] == mem_id for m in mems)

    # 4. Delete user memory
    del_res = client.delete(f"/memory/user/{mem_id}", headers=headers)
    assert del_res.status_code == 200

    # 5. Verify deleted
    list_after = client.get("/memory/user", headers=headers).json()
    assert not any(m["id"] == mem_id for m in list_after)


def test_user_memory_isolation_between_accounts():
    """Verify Sarah cannot see or access Alex's learned memories."""
    sarah_token = client.post("/auth/login", json={
        "username_or_email": "sarah",
        "password": "LunaDemo2026!"
    }).json()["access_token"]
    alex_token = client.post("/auth/login", json={
        "username_or_email": "alex",
        "password": "LunaDemo2026!"
    }).json()["access_token"]

    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    # Alex adds memory
    add_res = client.post("/memory/user", json={
        "content": "Alex confidential infrastructure runbook preference",
        "memory_type": "user_context"
    }, headers=alex_headers)
    alex_mem_id = add_res.json()["memory"]["id"]

    # Sarah gets user memories -> should NOT contain Alex's memory
    sarah_mems = client.get("/memory/user", headers=sarah_headers).json()
    assert not any(m["id"] == alex_mem_id for m in sarah_mems)

    # Sarah cannot delete Alex's memory -> 403 Forbidden
    del_res = client.delete(f"/memory/user/{alex_mem_id}", headers=sarah_headers)
    assert del_res.status_code == 403

    # Clean up Alex memory
    client.delete(f"/memory/user/{alex_mem_id}", headers=alex_headers)


def test_complex_user_message_with_noise_and_metrics_memory_extraction():
    """Verify memory manager extracts critical business metrics & goals from messages with venting/noise."""
    db = SessionLocal()
    test_uid = "usr_complex_test_02"
    try:
        query = (
            "Abc revenue will go down by 12% so i need to fix it as other are useless but get more "
            "money then me sometimes i feel to leave and start a new life in some new state and "
            "let this company get distroyed but i got no money anyway give how are we doing what all projects are active?"
        )
        memory_manager.save_turn(
            db=db,
            conversation_id="conv_session_complex_1",
            agent_id="luna",
            user_query=query,
            assistant_response="I understand that Abc revenue is projected to decrease by 12% and you are working to address it.",
            user_id=test_uid
        )

        user_mems = MemoryStore.search_user_memories(db, user_id=test_uid)
        assert len(user_mems) >= 1

        contents = " ".join([m.content for m in user_mems]).lower()
        # Should extract the business context / metrics or responsibility
        assert "abc revenue" in contents or "12%" in contents or "fix" in contents
        # Should NOT store the personal venting / complaints
        assert "start a new life" not in contents
        assert "let this company get distroyed" not in contents
        assert "other are useless" not in contents
    finally:
        db.query(Memory).filter(Memory.user_id == test_uid).delete()
        db.commit()
        db.close()

