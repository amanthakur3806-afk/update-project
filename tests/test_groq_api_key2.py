"""
Unit and Integration Tests for GROQ_API_KEY2 Feature
=====================================================
Validates:
1. GROQ_API_KEY2 configuration loading from settings/.env.
2. Conversation title generation using GROQ_API_KEY2 via llm_provider.
3. Fallback mechanism: when primary client fails, secondary client is invoked.
4. Auto-naming of conversations during save_turn when title is default/unset.
5. On-demand title generation endpoint: POST /memory/conversations/{cid}/generate-title.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.workflow.llm_provider import LLMProvider, llm_provider
from app.database import get_db, SessionLocal
from app.memory.memory_manager import memory_manager
from app.models.memory import Conversation, Message


@pytest.fixture
def client():
    return TestClient(app)


def test_groq_api_key2_config_loaded():
    """Verify GROQ_API_KEY2 is recognized in settings."""
    assert hasattr(settings, "GROQ_API_KEY2")
    # If set in .env, verify it is a non-empty string
    assert isinstance(settings.GROQ_API_KEY2, str)


def test_secondary_client_initialization():
    """Verify that _get_secondary_client creates an OpenAI client with GROQ_API_KEY2."""
    provider = LLMProvider()
    with patch("app.config.settings.GROQ_API_KEY2", "gsk_test_key_2"):
        client = provider._get_secondary_client()
        assert client is not None
        assert client.api_key == "gsk_test_key_2"
        assert "groq.com" in str(client.base_url)


def test_secondary_async_client_initialization():
    """Verify that _get_secondary_async_client creates an AsyncOpenAI client with GROQ_API_KEY2."""
    provider = LLMProvider()
    with patch("app.config.settings.GROQ_API_KEY2", "gsk_test_key_2"):
        client = provider._get_secondary_async_client()
        assert client is not None
        assert client.api_key == "gsk_test_key_2"
        assert "groq.com" in str(client.base_url)


def test_generate_conversation_name_with_mock_client():
    """Verify generate_conversation_name extracts and returns short descriptive title."""
    provider = LLMProvider()
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Acme Corporation Expansion"))]
    mock_client.chat.completions.create.return_value = mock_resp

    with patch.object(provider, "_get_secondary_client", return_value=mock_client):
        title = provider.generate_conversation_name("Can you give me an overview of Acme Corporation's expansion plan?")
        assert title == "Acme Corporation Expansion"
        mock_client.chat.completions.create.assert_called_once()


def test_generate_conversation_name_fallback_on_failure():
    """Verify that if LLM call fails, generate_conversation_name cleanly falls back to query truncation."""
    provider = LLMProvider()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API rate limited")

    with patch.object(provider, "_get_secondary_client", return_value=mock_client):
        title = provider.generate_conversation_name("Tell me about Spotify ARR and health metrics for Q3")
        assert "Tell me about Spotify" in title


def test_synthesize_response_fallback_to_secondary_key():
    """
    Verify fallback: when the primary client fails (e.g., auth failure or rate limit exhausted),
    synthesize_response attempts completion using GROQ_API_KEY2 (secondary client).
    """
    provider = LLMProvider()

    # Primary client that fails
    mock_primary = MagicMock()
    mock_primary.chat.completions.create.side_effect = Exception("Primary key quota exhausted (429)")

    # Secondary client that succeeds
    mock_secondary = MagicMock()
    mock_secondary_resp = MagicMock()
    mock_secondary_resp.choices = [MagicMock(message=MagicMock(content="### Verified Response via Backup Key"))]
    mock_secondary.chat.completions.create.return_value = mock_secondary_resp

    with patch.object(provider, "_get_client", return_value=(mock_primary, "groq")), \
         patch.object(provider, "_get_secondary_client", return_value=mock_secondary):
        
        result = provider.synthesize_response(
            agent_name="luna",
            system_prompt="You are Luna.",
            playbook="Standard Playbook",
            query="Status of Acme deal",
            short_term_history=[],
            long_term_facts=[],
            condensed_tool_summary="",
            retrieved_chunks=[]
        )

        assert "Backup Key" in result or "Verified Response" in result
        mock_secondary.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_synthesize_response_async_fallback_to_secondary_key():
    """
    Verify async fallback: when primary async client fails, secondary async client is invoked.
    """
    provider = LLMProvider()

    # Primary async client that fails
    mock_primary = MagicMock()
    mock_primary.chat.completions.create = MagicMock(side_effect=Exception("Primary quota exhausted"))

    # Secondary async client that succeeds
    mock_secondary = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="### Async Response via Backup Key"))]

    async def mock_async_create(*args, **kwargs):
        return mock_resp

    mock_secondary.chat.completions.create = mock_async_create

    with patch.object(provider, "_get_async_client", return_value=(mock_primary, "groq")), \
         patch.object(provider, "_get_secondary_async_client", return_value=mock_secondary):
        
        result = await provider.synthesize_response_async(
            agent_name="luna",
            system_prompt="You are Luna.",
            playbook="Standard Playbook",
            query="Async query status",
            short_term_history=[],
            long_term_facts=[],
            condensed_tool_summary="",
            retrieved_chunks=[]
        )

        assert "Backup Key" in result or "Async Response" in result


def test_endpoint_generate_conversation_title(client):
    """Test POST /memory/conversations/{cid}/generate-title endpoint."""
    import uuid
    cid = f"conv_gen_{uuid.uuid4().hex[:8]}"

    # Create conversation with default title
    c_res = client.post(
        "/memory/conversations",
        json={"conversation_id": cid, "agent_id": "luna", "title": "New Chat"}
    )
    assert c_res.status_code == 201

    # Add a user message to give context
    db = SessionLocal()
    try:
        msg = Message(conversation_id=cid, role="user", content="Analyze the churn risk for Stripe customer account")
        db.add(msg)
        db.commit()
    finally:
        db.close()

    # Call generate-title endpoint
    with patch("app.workflow.llm_provider.llm_provider.generate_conversation_name", return_value="Stripe Churn Analysis"):
        res = client.post(f"/memory/conversations/{cid}/generate-title")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["title"] == "Stripe Churn Analysis"

    # Verify persisted in database
    get_res = client.get(f"/memory/conversations/{cid}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Stripe Churn Analysis"

    # Clean up
    client.delete(f"/memory/conversations/{cid}")


def test_save_turn_auto_names_conversation():
    """Verify that memory_manager.save_turn calls generate_conversation_name when title is New Chat."""
    import uuid
    cid = f"conv_turn_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()

    try:
        with patch("app.workflow.llm_provider.llm_provider.generate_conversation_name", return_value="NovaHealth SLA Review") as mock_gen:
            memory_manager.save_turn(
                db=db,
                conversation_id=cid,
                agent_id="luna",
                user_query="Can you review NovaHealth SLA compliance?",
                assistant_response="NovaHealth SLA is at 99.8%."
            )
            mock_gen.assert_called_once()

        conv = db.query(Conversation).filter(Conversation.conversation_id == cid).first()
        assert conv is not None
        assert conv.title == "NovaHealth SLA Review"
    finally:
        db.query(Message).filter(Message.conversation_id == cid).delete()
        db.query(Conversation).filter(Conversation.conversation_id == cid).delete()
        db.commit()
        db.close()
