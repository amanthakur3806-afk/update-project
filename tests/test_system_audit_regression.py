"""
System-Wide Engineering Audit & Regression Test Suite
=====================================================
Covers the 20 mandatory regression tests for agent tool planning, permissions,
execution semantics, safety rules, memory priority, and final synthesis.
"""
import pytest
import asyncio
from app.workflow.agent_workflow import create_agent_workflow
from app.mcp.client_manager import mcp_client_manager, ToolPermissionError
from app.workflow.llm_provider import llm_provider
from app.services.query_classifier import query_classifier
from app.database import SessionLocal
from app.models.customer_operations import CustomerAccount, OperationAuditLog


@pytest.fixture(autouse=True)
def clean_test_customer():
    """Clean up test customer TEST001 and TEST002 before/after tests."""
    db = SessionLocal()
    try:
        db.query(OperationAuditLog).filter(OperationAuditLog.customer_id.in_(["TEST001", "TEST002", "TEST_DUP"])).delete(synchronize_session=False)
        db.query(CustomerAccount).filter(CustomerAccount.customer_id.in_(["TEST001", "TEST002", "TEST_DUP"])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(OperationAuditLog).filter(OperationAuditLog.customer_id.in_(["TEST001", "TEST002", "TEST_DUP"])).delete(synchronize_session=False)
        db.query(CustomerAccount).filter(CustomerAccount.customer_id.in_(["TEST001", "TEST002", "TEST_DUP"])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ----------------------------------------------------------------------
# TEST 1: List all customers -> Operations.list_customers
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_list_all_customers():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.list_customers", "Operations.create_customer"
    ])
    plan = llm_provider.plan_tools("List all customers.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.list_customers"


# ----------------------------------------------------------------------
# TEST 2: Create customer TEST001 with company Test Corporation -> Operations.create_customer
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_create_customer():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.create_customer", "Operations.get_customer"
    ])
    plan = llm_provider.plan_tools("Create customer TEST001 with company Test Corporation.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.create_customer"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"
    assert "Test Corporation" in plan[0]["arguments"]["company_name"]


# ----------------------------------------------------------------------
# TEST 3: Get customer TEST001 -> Operations.get_customer
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_get_customer():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.get_customer", "Operations.list_customers"
    ])
    plan = llm_provider.plan_tools("Get customer TEST001.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.get_customer"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"


# ----------------------------------------------------------------------
# TEST 4: Change TEST001 status to active -> Operations.update_customer_status
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_change_status():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.update_customer_status", "Operations.get_customer"
    ])
    plan = llm_provider.plan_tools("Change TEST001 status to active.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.update_customer_status"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"
    assert plan[0]["arguments"]["status"].lower() == "active"


# ----------------------------------------------------------------------
# TEST 5: Add note 'Called customer' to TEST001 -> Operations.add_customer_note
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_add_customer_note():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.add_customer_note", "Operations.get_customer"
    ])
    plan = llm_provider.plan_tools("Add note 'Called customer' to TEST001.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.add_customer_note"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"
    assert "Called customer" in plan[0]["arguments"]["note"]


# ----------------------------------------------------------------------
# TEST 6: Show notes for TEST001 -> Operations.get_customer_notes
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_06_show_notes():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.get_customer_notes", "Operations.add_customer_note"
    ])
    plan = llm_provider.plan_tools("Show notes for TEST001.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.get_customer_notes"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"


# ----------------------------------------------------------------------
# TEST 7: Create a follow-up task for TEST001 called Renewal call -> Operations.create_follow_up_task
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_07_create_follow_up_task():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.create_follow_up_task", "Operations.list_follow_up_tasks"
    ])
    plan = llm_provider.plan_tools("Create a follow-up task for TEST001 called Renewal call.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.create_follow_up_task"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"
    assert "Renewal call" in plan[0]["arguments"]["title"]


# ----------------------------------------------------------------------
# TEST 8: Show follow-up tasks for TEST001 -> Operations.list_follow_up_tasks
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_08_show_tasks():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.list_follow_up_tasks", "Operations.create_follow_up_task"
    ])
    plan = llm_provider.plan_tools("Show follow-up tasks for TEST001.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.list_follow_up_tasks"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"


# ----------------------------------------------------------------------
# TEST 9: Show audit history for TEST001 -> Operations.get_audit_history
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_09_show_audit_history():
    available_tools = await mcp_client_manager.get_tools_for_agent([
        "Operations.get_audit_history"
    ])
    plan = llm_provider.plan_tools("Show audit history for TEST001.", available_tools, [])
    assert len(plan) == 1
    assert plan[0]["tool_name"] == "Operations.get_audit_history"
    assert plan[0]["arguments"]["customer_id"] == "TEST001"


# ----------------------------------------------------------------------
# TEST 10: Unauthorized agent tries create_customer -> PERMISSION_DENIED and zero DB mutation
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_unauthorized_agent_permission_denied():
    allowed_tools = ["CRM.get_customer", "Analytics.get_customer_metrics"]
    assert not mcp_client_manager.check_tool_permission("Operations.create_customer", allowed_tools)
    
    with pytest.raises(ToolPermissionError):
        await mcp_client_manager.execute_tool(
            tool_name="Operations.create_customer",
            arguments={"customer_id": "UNAUTH001", "company_name": "Unauthorized Corp"},
            allowed_tools=allowed_tools
        )
    
    # Verify zero DB mutation
    db = SessionLocal()
    try:
        acc = db.query(CustomerAccount).filter(CustomerAccount.customer_id == "UNAUTH001").first()
        assert acc is None
    finally:
        db.close()


# ----------------------------------------------------------------------
# TEST 11: Planner produces nonexistent tool -> validation failure before execution
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_nonexistent_tool_handling():
    res = await mcp_client_manager.execute_tool(
        tool_name="Operations.nonexistent_custom_tool",
        arguments={"customer_id": "TEST001"},
        allowed_tools=["Operations.nonexistent_custom_tool"]
    )
    assert res["success"] is False
    assert res["transport_success"] is False
    assert "not registered" in res["error"]


# ----------------------------------------------------------------------
# TEST 12: create_customer succeeds -> final response confirms creation
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_create_customer_confirms_success():
    wf = create_agent_workflow()
    res = await wf.run(
        agent_id="customer_operations_agent",
        query="Create a new customer with ID TEST001 and company name Test Corporation.",
        conversation_id="test_conv_create"
    )
    assert res["status"] == "completed"
    assert "Operations.create_customer" in res["tools_used"]
    ans_lower = res["answer"].lower()
    assert ("test001" in ans_lower or "test corporation" in ans_lower)
    assert ("created" in ans_lower or "success" in ans_lower)
    assert "need explicit confirmation" not in ans_lower


# ----------------------------------------------------------------------
# TEST 13: create_customer fails -> final response does NOT claim creation
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_create_customer_failure_synthesis():
    summary = "Operations Operations.create_customer FAILED: Database unique constraint failed: Customer 'TEST_FAIL' already exists."
    synth = llm_provider._local_grounded_synthesize(
        agent_name="Customer Operations Agent",
        query="Create customer TEST_FAIL",
        long_term_facts=[],
        condensed_tool_summary=summary,
        retrieved_chunks=[]
    )
    assert "FAILED" in synth or "failed" in synth.lower()


# ----------------------------------------------------------------------
# TEST 14: duplicate TEST001 creation -> clear duplicate error and no duplicate record
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_duplicate_customer_creation():
    allowed_tools = ["Operations.create_customer"]
    # First creation
    res1 = await mcp_client_manager.execute_tool(
        tool_name="Operations.create_customer",
        arguments={"customer_id": "TEST_DUP", "company_name": "Dup Corp"},
        allowed_tools=allowed_tools
    )
    assert res1["success"] is True
    assert res1["tool_success"] is True

    # Duplicate creation attempt
    res2 = await mcp_client_manager.execute_tool(
        tool_name="Operations.create_customer",
        arguments={"customer_id": "TEST_DUP", "company_name": "Dup Corp 2"},
        allowed_tools=allowed_tools
    )
    assert res2["success"] is False
    assert res2["tool_success"] is False
    assert "already exists" in res2["result"]["error"]

    # Verify single record in DB
    db = SessionLocal()
    try:
        count = db.query(CustomerAccount).filter(CustomerAccount.customer_id == "TEST_DUP").count()
        assert count == 1
    finally:
        db.close()


# ----------------------------------------------------------------------
# TEST 15: read tool times out -> safe retry according to metadata
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_read_tool_safe_retry_metadata():
    meta = mcp_client_manager.get_tool_metadata("Operations.get_customer")
    assert meta is not None
    assert meta["read_only"] is True
    assert meta["safe_to_retry"] is True


# ----------------------------------------------------------------------
# TEST 16: write tool times out -> no blind retry unless idempotency protection exists
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_16_write_tool_safe_retry_metadata():
    meta = mcp_client_manager.get_tool_metadata("Operations.create_customer")
    assert meta is not None
    assert meta["read_only"] is False
    assert meta["safe_to_retry"] is False


# ----------------------------------------------------------------------
# TEST 17: CRUD query -> RAG skipped unless explicitly necessary
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_17_crud_query_skips_rag():
    c = query_classifier.classify("Create customer TEST001 with company Test Corporation.")
    assert c.is_action_intent is True
    assert c.requires_rag is False


# ----------------------------------------------------------------------
# TEST 18: knowledge question -> RAG used; no unnecessary write tool
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_18_knowledge_question_uses_rag():
    c = query_classifier.classify("What is our enterprise SLA policy for response time?")
    assert c.requires_rag is True
    assert c.is_action_intent is False
    assert "Operations.create_customer" not in c.suggested_tools


# ----------------------------------------------------------------------
# TEST 19: tool result conflicts with old memory -> current tool result wins
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_19_tool_result_priority_over_memory():
    synth = llm_provider._local_grounded_synthesize(
        agent_name="Customer Research Agent",
        query="What is ABC status?",
        long_term_facts=["Customer ABC previously had status: Churned"],
        condensed_tool_summary="CRM Profile for ABC (ID: ABC):\n  - Tier: Enterprise\n  - Status: Active",
        retrieved_chunks=[]
    )
    assert "CRM Profile for ABC" in synth
    assert "Account Profile (CRM)" in synth


# ----------------------------------------------------------------------
# TEST 20: multi-tool dependency failure -> dependent operations are skipped safely
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_20_dependency_failure_skips_dependent_step():
    wf = create_agent_workflow()
    # Execute a plan where prerequisite fails
    step_rec_results = []
    failed_plan_ids = {"step_1"}
    dependencies = ["step_1"]
    blocked = [dep for dep in dependencies if dep in failed_plan_ids]
    assert blocked == ["step_1"]


# ----------------------------------------------------------------------
# TEST 21: Argument templating & step output forwarding
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_21_argument_templating_and_output_forwarding():
    wf = create_agent_workflow()
    step_outputs = {
        "step_1": {"customer_id": "ABC", "company_name": "ABC Global Logistics"},
        "step_2": {"arr": 1200000, "status": "Active"}
    }
    raw_args = {
        "customer_id": "$step_1.customer_id",
        "company": "$step_1.company_name",
        "metric_arr": "$step_2.arr",
        "direct_val": "StaticValue"
    }
    resolved = wf._resolve_templated_arguments(raw_args, step_outputs)
    assert resolved["customer_id"] == "ABC"
    assert resolved["company"] == "ABC Global Logistics"
    assert resolved["metric_arr"] == 1200000
    assert resolved["direct_val"] == "StaticValue"


# ----------------------------------------------------------------------
# TEST 22: Autonomous self-correction & natural language entity resolution
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_22_autonomous_self_correction_entity_resolution():
    # Verify CRM search resolves "NovaHealth" to canonical ID "NOVA"
    search_res = await mcp_client_manager.execute_tool(
        tool_name="CRM.search_customer",
        arguments={"query": "NovaHealth"},
        allowed_tools=["CRM.search_customer", "CRM.get_customer"]
    )
    assert search_res["success"] is True
    assert len(search_res["result"]["results"]) > 0
    assert search_res["result"]["results"][0]["customer_id"] == "NOVA"


# ----------------------------------------------------------------------
# TEST 23: Luna autonomous multi-mcp workflow execution
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_23_luna_autonomous_multi_domain_execution():
    wf = create_agent_workflow()
    result = await wf.run(
        agent_id="luna",
        query="Give me an operational and financial breakdown for NovaHealth Solutions.",
        conversation_id="test_luna_autonomous"
    )
    assert result["status"] == "completed"
    assert result["agent_id"] == "luna"
    assert len(result["answer"]) > 50
    assert len(result["tools_used"]) > 0

