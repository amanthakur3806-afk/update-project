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
    requires_rag: bool = False
    requires_calculation: bool = False
    suggested_tools: List[str] = Field(default_factory=list)
    intent_summary: str = ""


class QueryClassifier:
    """
    Lightweight rule-based query classifier that produces structured classification.
    """

    KNOWN_ENTITIES = ["ABC", "XYZ", "ACME", "NOVA", "FINTECH", "CLOUD"]

    def classify(self, query: str) -> QueryClassification:
        q_lower = query.lower()

        # 1. Extract target entities
        entities = []
        for ent in self.KNOWN_ENTITIES:
            pattern = rf"\b{ent}\b"
            if re.search(pattern, query, re.IGNORECASE):
                entities.append(ent)

        if not entities:
            match = re.search(r"\bcustomer\s+([A-Z0-9]+)\b", query, re.IGNORECASE)
            if match:
                entities.append(match.group(1).upper())

        # 2. Heuristics for capabilities
        has_policy_intent = any(w in q_lower for w in [
            "policy", "policies", "compliance", "agreement", "guideline",
            "sop", "terms", "rules"
        ])

        has_crm_intent = any(w in q_lower for w in [
            "crm", "customer", "account", "profile", "contact", "stakeholder",
            "tier", "contract", "company", "who is", "address", "notes"
        ])

        has_analytics_intent = any(w in q_lower for w in [
            "analytics", "telemetry", "arr", "mrr", "metric", "metrics", "nps", "churn", "usage",
            "api call", "error rate", "resolution", "ticket", "history",
            "timeline", "qbr", "upgrade", "incident", "health", "financial", "revenue"
        ])

        has_rag_intent = has_policy_intent or any(w in q_lower for w in [
            "rag", "doc", "docs", "document", "documentation", "architecture", "integration", "overview", "internal", "kb"
        ])

        is_comparison = any(w in q_lower for w in [
            "compare", "difference", "versus", "vs", "between", "both"
        ]) or len(entities) > 1

        is_calculation = any(w in q_lower for w in [
            "calculate", "growth", "percentage", "total", "average", "ratio", "sum"
        ])

        # 3. Determine query_type
        if is_comparison:
            query_type = "Comparison"
            intent = f"Comparing entities: {', '.join(entities) if entities else 'multiple targets'}"
        elif has_policy_intent:
            query_type = "Policy & Compliance Check"
            intent = "Searching internal corporate policies, agreements, and standard procedures"
            has_rag_intent = True
        elif "history" in q_lower or "incident" in q_lower or "timeline" in q_lower:
            query_type = "Event History & Incident Review"
            intent = "Retrieving chronological events, incident logs, or review records"
        elif any(w in q_lower for w in ["arr", "mrr", "churn", "nps", "financial", "revenue"]):
            query_type = "Financial & Health Analytics"
            intent = "Auditing financial figures, ARR/MRR, churn risk, and operational scores"
        elif has_crm_intent and has_analytics_intent:
            query_type = "Multi-Step Research Dossier"
            intent = "Generating 360-degree customer research dossier combining CRM, metrics, and documentation"
        elif has_crm_intent:
            query_type = "Customer Account Lookup"
            intent = "Looking up customer profile, contacts, and account tier in CRM"
        elif has_rag_intent:
            query_type = "Document Q&A"
            intent = "Querying internal documentation knowledge bases"
        else:
            query_type = "General Inquiry"
            intent = "General assistant request"

        # 4. Suggest tools
        suggested_tools = []
        if has_crm_intent or is_comparison:
            suggested_tools.append("CRM.get_customer")
        if has_analytics_intent or is_comparison:
            suggested_tools.append("Analytics.get_customer_metrics")
            if any(w in q_lower for w in ["history", "timeline", "past", "recent", "incident"]):
                suggested_tools.append("Analytics.get_customer_history")

        return QueryClassification(
            query=query,
            query_type=query_type,
            target_entities=entities,
            requires_crm=has_crm_intent or is_comparison,
            requires_analytics=has_analytics_intent or is_comparison,
            requires_rag=has_rag_intent or has_policy_intent,
            requires_calculation=is_calculation,
            suggested_tools=suggested_tools,
            intent_summary=intent
        )


query_classifier = QueryClassifier()
