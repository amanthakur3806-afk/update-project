"""
Smart Query Classifier
======================
Lightweight, deterministic query analysis and intent categorization.

Analyzes user requests before workflow execution to:
  1. Determine task category (e.g. comparison, lookup, analytics, policy).
  2. Extract target customer entities.
  3. Predict required resources (CRM, Analytics, RAG, Memory, Calculations).
  4. Suggest optimal MCP tools.
"""
import re
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class QueryClassification(BaseModel):
    query: str
    query_type: str = Field(..., description="Classification category")
    target_entities: List[str] = Field(default_factory=list)
    requires_crm: bool = False
    requires_analytics: bool = False
    requires_operations: bool = False
    requires_rag: bool = False
    requires_calculation: bool = False
    is_action_intent: bool = False
    suggested_tools: List[str] = Field(default_factory=list)
    intent_summary: str = ""


class QueryClassifier:
    """
    Lightweight rule-based query classifier that produces structured classification.
    """

    KNOWN_ENTITIES = ["ABC", "XYZ", "ACME", "NOVA", "FINTECH", "CLOUD"]
    STOP_WORDS = {
        "WITH", "THE", "FOR", "AND", "NEW", "NAME", "FROM", "COMPANY", "A", "AN",
        "CUSTOMER", "CUSTOMERS", "ID", "STATUS", "NOTE", "NOTES", "TASK", "TASKS",
        "ALL", "IS", "IN", "TO", "OF", "ON", "AT", "BY", "THIS", "THAT", "IT"
    }

    def classify(self, query: str) -> QueryClassification:
        q_lower = query.lower().strip()

        # 1. Extract target entities
        entities: List[str] = []
        for ent in self.KNOWN_ENTITIES:
            pattern = rf"\b{ent}\b"
            if re.search(pattern, query, re.IGNORECASE) and ent not in entities:
                entities.append(ent)

        # Regex for explicit IDs like "ID TEST001", "id: TEST001", "customer TEST001", "for TEST001"
        id_patterns = [
            r"\b(?:id|customer_id)\s*[:=]?\s*([A-Za-z0-9_-]{2,32})\b",
            r"\bcustomer\s+([A-Za-z0-9_-]{2,32})\b",
            r"\bfor\s+([A-Z0-9_-]{3,32})\b",
            r"\b([A-Z]{2,10}\d{1,6})\b",  # e.g. TEST001, CUST123
        ]
        for pat in id_patterns:
            for match in re.finditer(pat, query, re.IGNORECASE):
                candidate = match.group(1).strip().upper()
                if candidate not in self.STOP_WORDS and candidate not in entities and len(candidate) >= 2:
                    entities.append(candidate)

        # 2. Action / Operations intent detection
        is_create_intent = bool(re.search(r"\b(create|add|register|provision|new)\s+(?:a\s+)?(?:new\s+)?customer\b", q_lower))
        is_status_intent = bool(re.search(r"\b(update|change|set|mark)\b.*\b(status|active|inactive|churned|suspended)\b", q_lower))
        is_note_intent = bool(re.search(r"\b(add|create|insert|save|append|show|list)\b.*\b(note|notes)\b", q_lower))
        is_task_intent = bool(re.search(r"\b(create|add|assign|follow-up|follow up|task|tasks|list tasks|show tasks)\b", q_lower))
        is_list_customers_intent = bool(re.search(r"\b(list|show|all)\s+customers\b", q_lower) and not entities)
        is_audit_intent = bool(re.search(r"\b(audit|history|logs|changes)\b", q_lower) and "operations" in q_lower or "audit history" in q_lower)

        is_action_intent = is_create_intent or is_status_intent or (is_note_intent and ("add" in q_lower or "create" in q_lower)) or (is_task_intent and ("create" in q_lower or "add" in q_lower)) or is_list_customers_intent or is_audit_intent

        # 3. Heuristics for capabilities
        has_policy_intent = any(w in q_lower for w in [
            "policy", "policies", "compliance", "agreement", "guideline",
            "sop", "terms", "rules"
        ])

        has_crm_intent = any(w in q_lower for w in [
            "crm", "customer", "account", "profile", "contact", "stakeholder",
            "tier", "contract", "company", "who is", "address"
        ])

        has_analytics_intent = any(w in q_lower for w in [
            "analytics", "telemetry", "arr", "mrr", "metric", "metrics", "nps", "churn", "usage",
            "api call", "error rate", "resolution", "ticket",
            "timeline", "qbr", "upgrade", "incident", "health", "financial", "revenue"
        ])

        has_rag_intent = has_policy_intent or any(w in q_lower for w in [
            "policy", "policies", "agreement", "guideline", "sop", "knowledge base", "internal documentation", "architecture document"
        ])

        is_comparison = any(w in q_lower for w in [
            "compare", "difference", "versus", "vs", "between", "both"
        ]) or len(entities) > 1

        is_calculation = any(w in q_lower for w in [
            "calculate", "growth", "percentage", "total revenue", "average", "ratio", "sum"
        ])

        # 4. Determine query_type
        suggested_tools: List[str] = []

        if is_create_intent:
            query_type = "Customer Operations - Create"
            intent = "Creating a new persistent customer record"
            suggested_tools.append("Operations.create_customer")
        elif is_status_intent:
            query_type = "Customer Operations - Status Update"
            intent = "Updating customer lifecycle status in operations database"
            suggested_tools.append("Operations.update_customer_status")
        elif is_note_intent:
            query_type = "Customer Operations - Notes"
            intent = "Managing operational notes for customer"
            if "add" in q_lower or "create" in q_lower:
                suggested_tools.append("Operations.add_customer_note")
            else:
                suggested_tools.append("Operations.get_customer_notes")
        elif is_task_intent:
            query_type = "Customer Operations - Tasks"
            intent = "Managing customer follow-up tasks"
            if "create" in q_lower or "add" in q_lower:
                suggested_tools.append("Operations.create_follow_up_task")
            else:
                suggested_tools.append("Operations.list_follow_up_tasks")
        elif is_list_customers_intent:
            query_type = "Customer Operations - List"
            intent = "Listing all persistent operations customer accounts"
            suggested_tools.append("Operations.list_customers")
        elif is_audit_intent:
            query_type = "Customer Operations - Audit History"
            intent = "Retrieving operations audit history log"
            suggested_tools.append("Operations.get_audit_history")
        elif is_comparison:
            query_type = "Comparison"
            intent = f"Comparing entities: {', '.join(entities) if entities else 'multiple targets'}"
            suggested_tools.extend(["CRM.get_customer", "Analytics.get_customer_metrics"])
        elif has_policy_intent:
            query_type = "Policy & Compliance Check"
            intent = "Searching internal corporate policies, agreements, and standard procedures"
            has_rag_intent = True
        elif "history" in q_lower or "incident" in q_lower or "timeline" in q_lower:
            query_type = "Event History & Incident Review"
            intent = "Retrieving chronological events, incident logs, or review records"
            suggested_tools.append("Analytics.get_customer_history")
        elif any(w in q_lower for w in ["arr", "mrr", "churn", "nps", "financial", "revenue"]):
            query_type = "Financial & Health Analytics"
            intent = "Auditing financial figures, ARR/MRR, churn risk, and operational scores"
            suggested_tools.append("Analytics.get_customer_metrics")
        elif has_crm_intent and has_analytics_intent:
            query_type = "Multi-Step Research Dossier"
            intent = "Generating 360-degree customer research dossier combining CRM, metrics, and documentation"
            suggested_tools.extend(["CRM.get_customer", "Analytics.get_customer_metrics"])
        elif has_crm_intent:
            query_type = "Customer Account Lookup"
            intent = "Looking up customer profile, contacts, and account tier in CRM"
            suggested_tools.append("CRM.get_customer")
        elif has_rag_intent:
            query_type = "Document Q&A"
            intent = "Querying internal documentation knowledge bases"
        else:
            query_type = "General Inquiry"
            intent = "General assistant request"

        return QueryClassification(
            query=query,
            query_type=query_type,
            target_entities=entities,
            requires_crm=(has_crm_intent or is_comparison) and not is_action_intent,
            requires_analytics=(has_analytics_intent or is_comparison) and not is_action_intent,
            requires_operations=is_action_intent or "operations" in q_lower,
            requires_rag=has_rag_intent and not is_action_intent,
            requires_calculation=is_calculation,
            is_action_intent=is_action_intent,
            suggested_tools=suggested_tools,
            intent_summary=intent
        )


query_classifier = QueryClassifier()
