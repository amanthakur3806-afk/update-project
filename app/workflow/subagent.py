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
                    sla_val = cust.get("sla") or cust.get("sla_tier", "N/A")
                    owner_val = cust.get("account_owner") or cust.get("account_executive", "N/A")
                    contact_val = cust.get("primary_stakeholder") or cust.get("technical_contact", "N/A")
                    renewal_val = cust.get("renewal_date") or cust.get("contract_renewal", "N/A")
                    notes_val = cust.get("notes", [])
                    notes_str = ("\n  - Notes: " + " | ".join(notes_val[-3:])) if notes_val else ""
                    summary = (
                        f"CRM Profile for {cust.get('company_name', 'Unknown')} (ID: {cust.get('customer_id', '')}):\n"
                        f"  - Tier: {cust.get('tier', 'N/A')} | Status: {cust.get('status', 'Active')}\n"
                        f"  - SLA: {sla_val}\n"
                        f"  - Account Owner: {owner_val} | Primary Contact: {contact_val}\n"
                        f"  - Contract Value: {cust.get('contract_value', 'N/A')} (Renewal Date: {renewal_val})"
                        f"{notes_str}"
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
                        mrr_val = metrics.get('mrr', metrics.get('monthly_recurring_revenue', 0))
                        nps_val = metrics.get('nps', metrics.get('nps_score', 'N/A'))
                        churn_val = metrics.get('churn_risk', metrics.get('churn_risk_score', 'N/A'))
                        if isinstance(churn_val, (int, float)):
                            churn_str = f"{churn_val * 100:.1f}%" if churn_val <= 1.0 else f"{churn_val}%"
                        else:
                            churn_str = str(churn_val)
                        api_calls = metrics.get('api_calls_monthly', metrics.get('api_calls_last_30d', 0))
                        sla_rate = metrics.get('sla_compliance', metrics.get('sla_compliance_rate', 'N/A'))
                        if isinstance(sla_rate, (int, float)) and sla_rate <= 1.0:
                            sla_str = f"{sla_rate * 100:.3f}%"
                        else:
                            sla_str = str(sla_rate)
                        avg_latency = metrics.get('avg_latency_ms', 'N/A')
                        latency_str = f"{avg_latency}ms" if isinstance(avg_latency, (int, float)) else str(avg_latency)

                        summary = (
                            f"Analytics Metrics for {res.get('customer_id', '')}:\n"
                            f"  - ARR: ${arr_val:,} | MRR: ${mrr_val:,}\n"
                            f"  - NPS Score: {nps_val} | Churn Risk: {churn_str}\n"
                            f"  - API Volume: {api_calls:,} calls/month | Avg Latency: {latency_str}\n"
                            f"  - SLA Compliance: {sla_str} | Health: {metrics.get('health_status', 'Healthy')}"
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
                    err_text = res.get("error") or res.get("message") or "Operation failed."
                    extracted_facts.append(f"Operations {tool_name} FAILED: {err_text}")
                elif "create_customer" in tool_name.lower():
                    cust = res.get("customer", {})
                    extracted_facts.append(
                        f"Operations Created Customer: ID '{cust.get('customer_id')}', Company: '{cust.get('company_name')}', Status: '{cust.get('status')}', Owner: '{cust.get('owner') or 'Unassigned'}', Renewal Date: '{cust.get('renewal_date') or 'Not set'}'"
                    )
                elif "update_customer_status" in tool_name.lower():
                    new_st = res.get("status") or res.get("new_status")
                    extracted_facts.append(
                        f"Operations Updated Customer Record: Customer '{res.get('customer_id')}' ({res.get('company_name', '')}) -> Status: '{new_st}' (was '{res.get('old_status')}'), Owner: '{res.get('owner') or 'Unchanged'}', Renewal Date: '{res.get('renewal_date') or 'Unchanged'}'"
                    )
                elif "add_customer_note" in tool_name.lower():
                    extracted_facts.append(
                        f"Operations Added Note: Customer '{res.get('customer_id')}', Note: '{res.get('note')}'"
                    )
                elif "create_follow_up_task" in tool_name.lower():
                    task = res.get("task", {})
                    extracted_facts.append(
                        f"Operations Created Follow-up Task: Customer '{res.get('customer_id')}', Title: '{task.get('title')}', Task ID: {task.get('task_id')}"
                    )
                elif "list_customers" in tool_name.lower():
                    cust_list = res.get("customers", [])
                    if cust_list:
                        table_rows = [
                            "| Customer ID | Company Name | Status | Account Owner | Renewal Date | Open Tasks |",
                            "| :--- | :--- | :--- | :--- | :--- | :---: |"
                        ]
                        for c in cust_list:
                            table_rows.append(
                                f"| `{c.get('customer_id')}` | {c.get('company_name')} | {c.get('status')} | {c.get('owner') or 'Unassigned'} | {c.get('renewal_date') or 'Not set'} | {c.get('open_tasks', 0)} |"
                            )
                        extracted_facts.append(f"Operations Customer Accounts ({len(cust_list)} found):\n\n" + "\n".join(table_rows))
                    else:
                        extracted_facts.append("Operations Customer Accounts: No customer records found.")
                elif "get_customer_notes" in tool_name.lower():
                    notes = res.get("notes", [])
                    if notes:
                        items = [f"[{n.get('created_at', '')}] {n.get('note')}" for n in notes]
                        extracted_facts.append(f"Operations Notes for Customer '{res.get('customer_id')}' ({len(notes)} note(s)):\n  - " + "\n  - ".join(items))
                    else:
                        extracted_facts.append(f"Operations Notes for Customer '{res.get('customer_id')}': No notes recorded.")
                elif "list_follow_up_tasks" in tool_name.lower():
                    tasks = res.get("tasks", [])
                    cid = res.get("customer_id") or "All Customers"
                    if tasks:
                        items = [
                            f"Task #{t.get('id') or t.get('task_id')}: {t.get('title')} [{t.get('status')}] (Customer: {t.get('customer_id') or cid}, Due: {t.get('due_date') or 'No date'})"
                            for t in tasks
                        ]
                        extracted_facts.append(f"Operations Follow-up Tasks for Customer '{cid}' ({len(tasks)} task(s)):\n  - " + "\n  - ".join(items))
                    else:
                        extracted_facts.append(f"Operations Follow-up Tasks for Customer '{cid}': No open tasks.")
                elif "get_audit_history" in tool_name.lower():
                    history = res.get("audit_history") or res.get("history") or []
                    if history:
                        items = [f"[{h.get('created_at', '')}] {h.get('action')}: {h.get('details', '') or h.get('new_value', '')}" for h in history[:6]]
                        extracted_facts.append(f"Operations Audit History ({len(history)} entries):\n  - " + "\n  - ".join(items))
                    else:
                        extracted_facts.append("Operations Audit History: No audit records found.")
                elif "get_customer" in tool_name.lower():
                    cust = res.get("customer", {})
                    extracted_facts.append(
                        f"Operations Customer Record: ID '{cust.get('customer_id')}', Company: '{cust.get('company_name')}', Status: '{cust.get('status')}', Open Tasks: {res.get('open_tasks_count', 0)}"
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
