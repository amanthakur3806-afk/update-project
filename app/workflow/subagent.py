"""
Temporary Sub-Agent
Handles focused sub-tasks like tool result condensation, metric analysis,
and intermediate synthesis without polluting the main agent's context budget.
"""
from typing import List, Dict, Any


class TemporaryResearchSubAgent:
    """Ephemeral sub-agent spawned for tool result condensation and anomaly analysis."""

    def __init__(self, subagent_id: str = "temp_research_subagent"):
        self.subagent_id = subagent_id

    async def condense_results(
        self,
        query: str,
        tool_results: List[Dict[str, Any]],
        knowledge_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Condenses raw JSON tool outputs and knowledge snippets into a high-signal brief.
        Explicitly records negative results (e.g. customer not found) for provenance.
        """
        extracted_facts = []

        for item in tool_results:
            tool_name = item.get("tool_name", "")
            res = item.get("result", {})
            error = item.get("error")

            if error:
                extracted_facts.append(f"Tool {tool_name} Error: {error}")
                continue

            if "crm" in tool_name.lower():
                if res.get("found"):
                    cust = res.get("customer", {})
                    summary = (
                        f"CRM Profile for {cust.get('company_name', 'Unknown')} (ID: {cust.get('customer_id', '')}):\n"
                        f"  - Tier: {cust.get('tier', 'N/A')}\n"
                        f"  - SLA: {cust.get('sla_tier', 'N/A')} ({cust.get('sla_response_time', 'N/A')})\n"
                        f"  - Account Exec: {cust.get('account_executive', 'N/A')} | Contact: {cust.get('technical_contact', 'N/A')}\n"
                        f"  - Contract Value: {cust.get('contract_value', 'N/A')} (Renewal: {cust.get('contract_renewal', 'N/A')})"
                    )
                    extracted_facts.append(summary)
                else:
                    cid = res.get("customer_id", "Unknown")
                    msg = res.get("message", f"Customer {cid} not found in CRM.")
                    extracted_facts.append(f"CRM Lookup: {msg}")

            elif "analytics" in tool_name.lower():
                if "metrics" in tool_name.lower():
                    if res.get("found"):
                        metrics = res.get("metrics", {})
                        arr_val = metrics.get('arr', 0)
                        mrr_val = metrics.get('monthly_recurring_revenue', 0)
                        summary = (
                            f"Analytics Metrics for {res.get('customer_id')}:\n"
                            f"  - ARR: ${arr_val:,} | MRR: ${mrr_val:,}\n"
                            f"  - NPS Score: {metrics.get('nps_score')} | Churn Risk: {metrics.get('churn_risk_score')}\n"
                            f"  - Active Users: {metrics.get('active_users', 0):,} | API Calls (30d): {metrics.get('api_calls_last_30d', 0):,}\n"
                            f"  - SLA Compliance: {metrics.get('sla_compliance_rate', 'N/A')} | Health: {metrics.get('health_status', 'N/A')}"
                        )
                        extracted_facts.append(summary)
                    else:
                        cid = res.get("customer_id", "Unknown")
                        msg = res.get("message", f"No analytics metrics for customer {cid}.")
                        extracted_facts.append(f"Analytics Metrics: {msg}")

                elif "history" in tool_name.lower():
                    timeline = res.get("timeline", [])
                    if timeline:
                        events_str = "\n".join([
                            f"    * [{e.get('date')}] {e.get('event_type')}: {e.get('details', '')}"
                            for e in timeline[:4]
                        ])
                        extracted_facts.append(f"Analytics Event History for {res.get('customer_id')}:\n{events_str}")
                    else:
                        extracted_facts.append(f"Analytics History: No historical events recorded.")

            elif "operations" in tool_name.lower():
                if res.get("found") is False or res.get("success") is False:
                    extracted_facts.append(
                        f"Operations {tool_name}: {res.get('error') or res.get('message', 'Customer was not found.') }"
                    )
                elif tool_name.lower().endswith("get_customer"):
                    customer = res.get("customer", {})
                    extracted_facts.append(
                        f"Operations Customer Lookup: verified {customer.get('company_name', customer.get('customer_id', 'customer'))} "
                        f"(ID: {customer.get('customer_id', 'unknown')})."
                    )
                else:
                    details = ", ".join(f"{key}={value}" for key, value in res.items() if key not in {"success", "customer_id"})
                    extracted_facts.append(f"Operation succeeded ({tool_name}) for customer {res.get('customer_id', 'unknown')}: {details}")

        condensed_text = "\n\n".join(extracted_facts) if extracted_facts else "No active tool data returned."

        return {
            "subagent": self.subagent_id,
            "status": "condensed",
            "extracted_facts_count": len(extracted_facts),
            "condensed_summary": condensed_text
        }
