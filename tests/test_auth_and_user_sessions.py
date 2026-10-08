"""
Test Suite: Authentication, JWT Security, Multi-Chat Sessions, and User Profile Isolation
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, get_db, SessionLocal
from app.seed_data import seed_default_users

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_default_users(db)
    db.close()
    yield


def test_demo_accounts_endpoint():
    """Verify demo personas endpoint returns Sarah, Alex, and Admin."""
    response = client.get("/auth/demo-accounts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    usernames = [u["username"] for u in data]
    assert "sarah" in usernames
    assert "alex" in usernames
    assert "admin" in usernames


def test_seed_user_login():
    """Verify Sarah can log in with demo password and receive a valid JWT token."""
    response = client.post("/auth/login", json={
        "username_or_email": "sarah",
        "password": "LunaDemo2026!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "sarah"
    assert data["user"]["role"] == "Senior Enterprise Account Executive"
    assert "ABC" in data["user"]["responsibilities"]


def test_auth_me_with_token():
    """Verify /auth/me returns the authenticated user's profile."""
    login_res = client.post("/auth/login", json={
        "username_or_email": "alex",
        "password": "LunaDemo2026!"
    })
    token = login_res.json()["access_token"]

    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "alex"
    assert me_data["role"] == "Lead Support Operations Architect"


def test_user_registration():
    """Verify a new user can register, receive a JWT token, and login."""
    import uuid
    rand_suffix = uuid.uuid4().hex[:6]
    test_username = f"user_{rand_suffix}"
    test_email = f"user_{rand_suffix}@enterprise.com"

    reg_payload = {
        "full_name": "Marcus Vance",
        "username": test_username,
        "email": test_email,
        "password": "StrongPassword123!",
        "role": "Director of Customer Success",
        "department": "Customer Operations",
        "responsibilities": "Oversees enterprise retention and customer escalations"
    }
    reg_res = client.post("/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["username"] == test_username
    assert reg_data["user"]["role"] == "Director of Customer Success"

    # Test login with new credentials
    login_res = client.post("/auth/login", json={
        "username_or_email": test_username,
        "password": "StrongPassword123!"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


def test_duplicate_registration_fails():
    """Verify duplicate username or email is rejected with 400 Bad Request."""
    reg_payload = {
        "full_name": "Sarah Duplicate",
        "username": "sarah",
        "email": "sarah.jenkins@enterprise.com",
        "password": "Password123!"
    }
    res = client.post("/auth/register", json=reg_payload)
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_invalid_login_credentials():
    """Verify wrong password returns 401 Unauthorized."""
    res = client.post("/auth/login", json={
        "username_or_email": "sarah",
        "password": "WrongPassword123"
    })
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]


def test_multi_chat_sessions_and_isolation():
    """
    Verify multi-chat session isolation:
    1. Sarah creates a conversation 'sarah_deal_review'.
    2. Alex creates a conversation 'alex_infra_incident'.
    3. Sarah only sees her own conversations in /memory/conversations.
    4. Alex only sees his own conversations.
    5. Sarah cannot delete or access Alex's conversation.
    """
    # 1. Login Sarah
    sarah_token = client.post("/auth/login", json={
        "username_or_email": "sarah",
        "password": "LunaDemo2026!"
    }).json()["access_token"]
    sarah_headers = {"Authorization": f"Bearer {sarah_token}"}

    # 2. Login Alex
    alex_token = client.post("/auth/login", json={
        "username_or_email": "alex",
        "password": "LunaDemo2026!"
    }).json()["access_token"]
    alex_headers = {"Authorization": f"Bearer {alex_token}"}

    # Sarah creates conversation
    res_c1 = client.post("/memory/conversations", json={
        "conversation_id": "sarah_deal_review",
        "title": "Q4 Enterprise Deal Strategy"
    }, headers=sarah_headers)
    assert res_c1.status_code == 201

    # Alex creates conversation
    res_c2 = client.post("/memory/conversations", json={
        "conversation_id": "alex_infra_incident",
        "title": "NOVA Sev-1 Incident Postmortem"
    }, headers=alex_headers)
    assert res_c2.status_code == 201

    # Sarah lists conversations
    sarah_list = client.get("/memory/conversations", headers=sarah_headers).json()
    sarah_cids = [c["conversation_id"] for c in sarah_list]
    assert "sarah_deal_review" in sarah_cids
    assert "alex_infra_incident" not in sarah_cids

    # Alex lists conversations
    alex_list = client.get("/memory/conversations", headers=alex_headers).json()
    alex_cids = [c["conversation_id"] for c in alex_list]
    assert "alex_infra_incident" in alex_cids
    assert "sarah_deal_review" not in alex_cids

    # Sarah attempts to access Alex's conversation -> 403 Forbidden
    unauth_get = client.get("/memory/conversations/alex_infra_incident", headers=sarah_headers)
    assert unauth_get.status_code == 403

    # Sarah attempts to delete Alex's conversation -> 403 Forbidden
    unauth_del = client.delete("/memory/conversations/alex_infra_incident", headers=sarah_headers)
    assert unauth_del.status_code == 403

    # Sarah deletes her own conversation -> 200 OK
    auth_del = client.delete("/memory/conversations/sarah_deal_review", headers=sarah_headers)
    assert auth_del.status_code == 200

    # Alex's conversation is still intact
    alex_check = client.get("/memory/conversations/alex_infra_incident", headers=alex_headers)
    assert alex_check.status_code == 200
    assert alex_check.json()["title"] == "NOVA Sev-1 Incident Postmortem"
