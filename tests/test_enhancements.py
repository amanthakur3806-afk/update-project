"""
Enhancement & Zero-Silent-Fallback Verification Tests
=====================================================
Validates all enhancement requirements from the Product Design Addendum:
  1. Zero hardcoded business data: Deleting customer ABC makes it unavailable.
  2. Zero silent fallback: No imaginary customers or metrics fabricated.
  3. Anti-stale cache: Deleting a knowledge document synchronously purges its vectors from FAISS.
  4. Dynamic Memory: Deleting a long-term memory fact removes it from retrieval.
  5. Dynamic RAG Rebuild: Clearing FAISS allows complete rebuild from source documents.
  6. Smart Query Classification: Queries correctly classified and entities extracted.
  7. Agent Classification: Agents have categories (Research, Finance, Compliance).
  8. System Health: Live component diagnostics report operational status.
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.database import SessionLocal
from app.models.agent import Agent
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.models.memory import Memory
from app.services.data_service import data_service
from app.services.query_classifier import query_classifier
from app.rag.vector_store import vector_store
from app.rag.ingest import delete_document, ingest_knowledge_base, rebuild_all_knowledge_bases
from app.rag.embeddings import embeddings_provider

client = TestClient(app)


def test_zero_silent_fallback_on_missing_crm_customer():
    """
    Test 1: If customer is not in CRM, CRM.get_customer must return found: False
    and NEVER silently fallback to an imaginary customer.
    """
    res = client.get("/data/crm/customers/NON_EXISTENT_CORP_999")
    assert res.status_code == 404

    from app.mcp.servers.crm_server import crm_server_instance
    import asyncio
    result = asyncio.run(crm_server_instance.call_tool("CRM.get_customer", {"customer_id": "IMAGINARY_CORP"}))
    assert result["found"] is False
    assert "not found" in result["message"].lower()


def test_delete_crm_customer_makes_it_unavailable():
    """
    Test 2: Deleting customer ABC causes CRM lookup to immediately fail (Zero Stale Data).
    """
    data_service.load_demo_data()
    assert data_service.get_customer("ABC") is not None

    del_res = client.delete("/data/crm/customers/ABC")
    assert del_res.status_code == 200

    get_res = client.get("/data/crm/customers/ABC")
    assert get_res.status_code == 404

    from app.mcp.servers.crm_server import crm_server_instance
    import asyncio
    mcp_res = asyncio.run(crm_server_instance.call_tool("CRM.get_customer", {"customer_id": "ABC"}))
    assert mcp_res["found"] is False

    # Restore demo data
    data_service.load_demo_data()


def test_delete_analytics_metrics_makes_them_unavailable():
    """
    Test 3: Deleting customer XYZ metrics causes Analytics tool to report not found.
    """
    data_service.load_demo_data()
    assert data_service.get_metrics("XYZ") is not None

    del_res = client.delete("/data/analytics/metrics/XYZ")
    assert del_res.status_code == 200

    from app.mcp.servers.analytics_server import analytics_server_instance
    import asyncio
    mcp_res = asyncio.run(analytics_server_instance.call_tool("Analytics.get_customer_metrics", {"customer_id": "XYZ"}))
    assert mcp_res["found"] is False

    data_service.load_demo_data()


def test_delete_document_purges_vectors_from_faiss():
    """
    Test 4: When a document is deleted, all its vectors are purged from FAISS so
    stale citations can NEVER be retrieved again (Anti-Stale Cache rule).
    """
    db = SessionLocal()
    try:
        # Create a dedicated temporary document for the test
        temp_file = settings.KNOWLEDGE_BASE_DIR / "customer_docs" / "temp_ephemeral_test_doc.md"
        temp_file.write_text("# Ephemeral Test Document\nUnique phrase: EPHEMERAL_TOKEN_XYZ_9981.", encoding="utf-8")

        # Ingest it
        ingest_knowledge_base("customer_docs", str(settings.KNOWLEDGE_BASE_DIR / "customer_docs"), db)

        doc = db.query(Document).filter(Document.filename == "temp_ephemeral_test_doc.md").first()
        assert doc is not None

        doc_id = doc.id
        initial_vectors = vector_store.total_vectors

        # Verify it is searchable
        q_vec = embeddings_provider.get_embedding("EPHEMERAL_TOKEN_XYZ_9981")
        search_res = vector_store.search(q_vec, top_k=5, kb_id="customer_docs")
        assert any(r["document_id"] == doc_id for r in search_res)

        # Delete document via API
        res = client.delete(f"/knowledge/documents/{doc_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["vectors_purged"] > 0

        # Verify vectors count decreased
        assert vector_store.total_vectors < initial_vectors

        # Verify document chunk is gone from vector store metadata
        remaining_chunks = vector_store.inspect_chunks(document_id=doc_id)
        assert len(remaining_chunks) == 0

        # Verify search for document content no longer returns this doc_id
        search_results_after = vector_store.search(q_vec, top_k=5, kb_id="customer_docs")
        assert not any(r["document_id"] == doc_id for r in search_results_after)

    finally:
        db.close()


def test_delete_long_term_memory():
    """
    Test 5: Deleting a long-term memory fact removes it so it no longer influences responses.
    """
    db = SessionLocal()
    try:
        # Clear any prior test entries
        db.query(Memory).filter(Memory.entity_key == "customer:TEST_CO").delete()
        db.commit()

        mem = Memory(
            entity_key="customer:TEST_CO",
            content="Customer TEST_CO exclusively uses encrypted satellite telemetry.",
            importance_score=2.0
        )
        db.add(mem)
        db.commit()
        mem_id = mem.id

        get_res = client.get(f"/memory/items?entity_key=customer:TEST_CO")
        assert get_res.status_code == 200
        assert len(get_res.json()) >= 1

        del_res = client.delete(f"/memory/items/{mem_id}")
        assert del_res.status_code == 200

        get_res_after = client.get(f"/memory/items?entity_key=customer:TEST_CO")
        assert len(get_res_after.json()) == 0

    finally:
        db.close()


def test_faiss_rebuild_from_scratch():
    """
    Test 6: Clearing FAISS index allows rebuilding completely from registered knowledge base directories.
    """
    vector_store.clear()
    assert vector_store.total_vectors == 0

    res = client.post("/knowledge/rebuild")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_vectors"] > 0
    assert vector_store.total_vectors > 0


def test_smart_query_classifier():
    """
    Test 7: Query classifier accurately detects intent, entities, and required tools.
    """
    c1 = query_classifier.classify("Compare customer ABC and customer XYZ on SLA tier and revenue.")
    assert c1.query_type == "Comparison"
    assert "ABC" in c1.target_entities
    assert "XYZ" in c1.target_entities
    assert c1.requires_crm is True
    assert c1.requires_analytics is True

    c2 = query_classifier.classify("What is the ARR, MRR, and churn risk for ACME?")
    assert c2.requires_analytics is True
    assert "ACME" in c2.target_entities

    c3 = query_classifier.classify("What are our standard corporate SLA resolution policies?")
    assert c3.requires_rag is True


def test_agent_category_classification():
    """
    Test 8: Agents include category classifications (Research, Finance, Compliance).
    """
    res = client.get("/agents")
    assert res.status_code == 200
    agents = res.json()

    research_agent = next((a for a in agents if a["agent_id"] == "customer_research_agent"), None)
    assert research_agent is not None
    assert research_agent["category"] == "Research"

    finance_agent = next((a for a in agents if a["agent_id"] == "financial_analyst_agent"), None)
    assert finance_agent is not None
    assert finance_agent["category"] == "Finance"

    compliance_agent = next((a for a in agents if a["agent_id"] == "support_compliance_agent"), None)
    assert compliance_agent is not None
    assert compliance_agent["category"] == "Compliance"


def test_system_health_and_observability():
    """
    Test 9: System health and observability endpoints report operational status.
    """
    health_res = client.get("/system/health")
    assert health_res.status_code == 200
    h_data = health_res.json()
    assert h_data["status"] == "operational"
    assert "components" in h_data
    assert h_data["components"]["database"]["status"] == "connected"
    assert h_data["components"]["crm_mcp"]["status"] == "connected"

    metrics_res = client.get("/system/metrics")
    assert metrics_res.status_code == 200
    m_data = metrics_res.json()
    assert m_data["active_agents"] >= 3
    assert m_data["knowledge_bases"] >= 3


def test_llm_provider_error_handling_and_offline_grounding():
    """
    Test 10: Validates that LLM failure raises explicit error without silent fake fallback,
    and offline mode is explicitly labeled without hallucinated data.
    """
    from unittest.mock import MagicMock
    from app.workflow.llm_provider import LLMProvider

    provider = LLMProvider()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Groq API rate limit or network timeout")
    provider._client = mock_client
    provider._provider_type = "groq"

    # Should raise RuntimeError explicitly
    with pytest.raises(RuntimeError) as exc_info:
        provider.synthesize_response(
            agent_name="Test Agent",
            system_prompt="Test",
            playbook="Test",
            query="Test query",
            short_term_history=[],
            long_term_facts=[],
            condensed_tool_summary="",
            retrieved_chunks=[]
        )
    assert "Groq/LLM API call failed" in str(exc_info.value)

    # Offline mode test: reset client and disable external flags
    offline_provider = LLMProvider()
    offline_provider.use_groq = False
    offline_provider.use_openai = False
    offline_provider._client = None
    offline_provider._provider_type = "local"
    offline_res = offline_provider.synthesize_response(
        agent_name="Test Agent",
        system_prompt="Test",
        playbook="Test",
        query="Test query",
        short_term_history=[],
        long_term_facts=[],
        condensed_tool_summary="",
        retrieved_chunks=[]
    )
    assert "[OFFLINE GROUNDED ENGINE - NO API KEY CONFIGURED]" in offline_res
    assert "No verified data is available" in offline_res

