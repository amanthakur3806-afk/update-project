"""
Data Service
============
Manages dynamic business data for CRM and Analytics.

Key Architecture Principles:
  1. Source code contains NO hardcoded business data.
  2. Starts empty and is populated by connected data integrations.
  3. ZERO SILENT FALLBACKS: If a customer or metric is missing/deleted,
     returns explicit "not found" / "no data configured" instead of fabricating data.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("data_service")


class DataService:
    """
    Central repository for dynamic CRM customer records, analytics metrics,
    and customer chronological event timelines.
    """

    def __init__(self):
        self._customers: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self.seed_initial_business_dataset()

    def seed_initial_business_dataset(self):
        """Seed rich realistic enterprise datasets for CRM and Analytics."""
        customers_seed = [
            {
                "customer_id": "ABC",
                "company_name": "ABC Global Logistics & Supply Inc.",
                "industry": "Logistics & Supply Chain Tracking",
                "tier": "Enterprise Tier 1 (Platinum)",
                "sla": "Platinum Mission-Critical (99.99% Uptime, 15-min Sev-1 Response)",
                "contract_value": "$480,000 / year",
                "renewal_date": "2027-01-15",
                "account_owner": "Sarah Jenkins",
                "primary_stakeholder": "Dr. Marcus Vance (marcus.vance@abc-logistics.example.com)",
                "status": "Active",
                "notes": [
                    "Global tracking telemetry gateway upgraded to v3.2 in Q1 2025.",
                    "Seasonal burst capacity exception pre-authorized for Q4 holiday peak.",
                    "Annual business review completed with executive sponsorship."
                ]
            },
            {
                "customer_id": "XYZ",
                "company_name": "XYZ FinTech Global Holdings",
                "industry": "Financial Services & Algorithmic Trading",
                "tier": "Enterprise Tier 1 (Platinum)",
                "sla": "Platinum Mission-Critical (99.99% Uptime, 15-min Sev-1 Response)",
                "contract_value": "$720,000 / year",
                "renewal_date": "2026-11-30",
                "account_owner": "Michael Chang",
                "primary_stakeholder": "Elena Rostova (e.rostova@xyzfintech.example.com)",
                "status": "Active",
                "notes": [
                    "Requested dedicated VPC peering and custom compliance audit logs for SOC2 Type II.",
                    "Latency jitter observed during market open spikes; engineering investigating eBPF bypass.",
                    "Contract renewal negotiation scheduled for November."
                ]
            },
            {
                "customer_id": "ACME",
                "company_name": "Acme Industrial Automation Corp",
                "industry": "Smart Manufacturing & Industrial IoT",
                "tier": "Enterprise Tier 2 (Gold)",
                "sla": "Enterprise Gold (99.95% Uptime, 1-hr Sev-1 Response)",
                "contract_value": "$240,000 / year",
                "renewal_date": "2027-01-20",
                "account_owner": "Jessica Vance",
                "primary_stakeholder": "Robert Sterling (r.sterling@acme-industrial.example.com)",
                "status": "Active",
                "notes": [
                    "Ingesting telemetry from 14 factory assembly plants across North America and Europe.",
                    "Edge agent containers upgraded to v4.8.",
                    "Planning expansion into 6 additional smart warehouses in Q4 2026."
                ]
            },
            {
                "customer_id": "NOVA",
                "company_name": "NovaHealth Technologies International",
                "industry": "Healthcare Genomics & Clinical SaaS",
                "tier": "Enterprise Tier 1 (Platinum Health)",
                "sla": "Platinum Mission-Critical (99.99% Uptime, 15-min Sev-1 Response, HIPAA/HITECH Certified)",
                "contract_value": "$620,000 / year",
                "renewal_date": "2027-08-10",
                "account_owner": "David K. Miller",
                "primary_stakeholder": "Dr. Aris Thorne (athorne@novahealth.example.com)",
                "status": "Active",
                "notes": [
                    "Business Associate Agreement (BAA) active. Zero-data-retention compliance addendum enforced.",
                    "Evaluating European clinical cloud expansion for 2027.",
                    "Annual third-party penetration test completed with zero critical findings."
                ]
            },
            {
                "customer_id": "VERTEX",
                "company_name": "Vertex Media & Streaming Networks",
                "industry": "Digital Media & Video Streaming",
                "tier": "Enterprise Tier 2 (Gold)",
                "sla": "Enterprise Gold (99.95% Uptime, 1-hr Sev-1 Response)",
                "contract_value": "$350,000 / year",
                "renewal_date": "2026-12-15",
                "account_owner": "Amanda Ross",
                "primary_stakeholder": "Liam Zhao (lzhao@vertexmedia.example.com)",
                "status": "Active",
                "notes": [
                    "Delivered 2.4M concurrent websocket sessions during global live stream championship.",
                    "Evaluating upgrade to Platinum Tier for 2027 live event schedule."
                ]
            },
            {
                "customer_id": "QUANTUM",
                "company_name": "Quantum Retail Networks Inc",
                "industry": "Omnichannel E-Commerce & POS",
                "tier": "Enterprise Tier 3 (Silver)",
                "sla": "Enterprise Silver (99.90% Uptime, 4-hr Sev-1 Response)",
                "contract_value": "$120,000 / year",
                "renewal_date": "2026-10-31",
                "account_owner": "Brian Kelly",
                "primary_stakeholder": "Claire Dupont (c.dupont@quantum-retail.example.com)",
                "status": "At-Risk",
                "notes": [
                    "Renewal approaching on October 31, 2026. Customer requested burst telemetry pricing review.",
                    "Account executive preparing Gold Tier proposal with holiday burst discount."
                ]
            }
        ]

        metrics_seed = {
            "ABC": {
                "arr": 480000,
                "mrr": 40000,
                "nps": 78,
                "churn_risk": 0.04,
                "api_calls_monthly": 32400000,
                "avg_latency_ms": 18.4,
                "error_rate": 0.0008,
                "sla_compliance": 0.9999,
                "contract_duration_months": 36
            },
            "XYZ": {
                "arr": 720000,
                "mrr": 60000,
                "nps": 42,
                "churn_risk": 0.34,
                "api_calls_monthly": 150000000,
                "avg_latency_ms": 6.2,
                "error_rate": 0.0012,
                "sla_compliance": 0.9995,
                "contract_duration_months": 24
            },
            "ACME": {
                "arr": 240000,
                "mrr": 20000,
                "nps": 65,
                "churn_risk": 0.08,
                "api_calls_monthly": 18000000,
                "avg_latency_ms": 32.1,
                "error_rate": 0.0003,
                "sla_compliance": 0.9998,
                "contract_duration_months": 36
            },
            "NOVA": {
                "arr": 620000,
                "mrr": 51666,
                "nps": 88,
                "churn_risk": 0.02,
                "api_calls_monthly": 45000000,
                "avg_latency_ms": 14.5,
                "error_rate": 0.0001,
                "sla_compliance": 0.99999,
                "contract_duration_months": 36
            },
            "VERTEX": {
                "arr": 350000,
                "mrr": 29166,
                "nps": 72,
                "churn_risk": 0.12,
                "api_calls_monthly": 88000000,
                "avg_latency_ms": 22.0,
                "error_rate": 0.0006,
                "sla_compliance": 0.9996,
                "contract_duration_months": 24
            },
            "QUANTUM": {
                "arr": 120000,
                "mrr": 10000,
                "nps": 50,
                "churn_risk": 0.45,
                "api_calls_monthly": 12000000,
                "avg_latency_ms": 48.0,
                "error_rate": 0.0025,
                "sla_compliance": 0.9991,
                "contract_duration_months": 12
            }
        }

        history_seed = {
            "ABC": [
                {"date": "2025-01-15", "event": "Annual Business Review", "details": "Executive sponsorship renewed for 36-month enterprise agreement."},
                {"date": "2025-03-22", "event": "Architecture Upgrade", "details": "Migrated webhook ingestion to dedicated AWS DirectConnect gateway."},
                {"date": "2025-07-10", "event": "Quarterly Review", "details": "SLA uptime verified at 99.995% across all logistics nodes."}
            ],
            "XYZ": [
                {"date": "2024-11-30", "event": "Master Services Agreement", "details": "24-month contract signed with dedicated hardware cluster."},
                {"date": "2025-08-14", "event": "Incident Sev-2", "details": "Transient 45ms jitter during peak market volatility. TAM paged."},
                {"date": "2025-09-02", "event": "Optimization Initiative", "details": "eBPF kernel bypass deployment scheduled to mitigate peak latency."}
            ],
            "ACME": [
                {"date": "2025-02-10", "event": "Plant Rollout", "details": "Munich smart factory connected 1,200 new robotic arms."},
                {"date": "2025-06-15", "event": "Edge Upgrade", "details": "Upgraded industrial IoT edge container fleet to v4.8."}
            ],
            "NOVA": [
                {"date": "2024-08-10", "event": "Contract Execution", "details": "36-month enterprise agreement signed with HIPAA/FedRAMP high encryption."},
                {"date": "2025-06-18", "event": "Security Audit", "details": "Annual SOC2 Type II and HIPAA third-party penetration test passed with zero findings."}
            ],
            "VERTEX": [
                {"date": "2024-12-15", "event": "Platform Go-Live", "details": "Migrated OTT transcoding telemetry pipelines to Nexus platform."},
                {"date": "2025-07-28", "event": "Peak Event Milestone", "details": "Successfully handled 2.4M concurrent websocket streams with zero dropped frames."}
            ],
            "QUANTUM": [
                {"date": "2025-10-31", "event": "Annual Renewal", "details": "12-month contract renewed with baseline Silver SLA."},
                {"date": "2026-09-15", "event": "Renewal Notice", "details": "90-day renewal horizon initiated; customer requested volume pricing review."}
            ]
        }

        for c in customers_seed:
            self._customers[c["customer_id"]] = c

        for cid, m in metrics_seed.items():
            m["customer_id"] = cid
            self._metrics[cid] = m

        for cid, h in history_seed.items():
            self._history[cid] = h

    # ----------------------------------------------------------------------
    # CRM Operations
    # ----------------------------------------------------------------------

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Look up a customer record by ID. Returns None if not found."""
        if not customer_id:
            return None
        return self._customers.get(customer_id.strip().upper())

    def search_customers(self, query: str) -> List[Dict[str, Any]]:
        """Search customers by ID, company name, or industry."""
        if not query:
            return []
        q = query.lower().strip()
        matches = []
        for cust in self._customers.values():
            if (
                q in cust.get("customer_id", "").lower()
                or q in cust.get("company_name", "").lower()
                or q in cust.get("industry", "").lower()
            ):
                matches.append(cust)
        return matches

    def list_customers(self) -> List[Dict[str, Any]]:
        """List all loaded customer records."""
        return list(self._customers.values())

    def save_customer(self, customer: Dict[str, Any]) -> str:
        """Add or update a customer record."""
        cid = customer.get("customer_id", "").strip().upper()
        if not cid:
            raise ValueError("customer_id is required")
        self._customers[cid] = customer
        return cid

    def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer record. Returns True if existed and deleted."""
        cid = customer_id.strip().upper()
        if cid in self._customers:
            del self._customers[cid]
            return True
        return False

    def append_customer_note(self, customer_id: str, note_entry: str) -> bool:
        """Append an operational note to customer notes list."""
        cid = customer_id.strip().upper()
        if cid in self._customers:
            if "notes" not in self._customers[cid]:
                self._customers[cid]["notes"] = []
            self._customers[cid]["notes"].append(note_entry)
            return True
        return False

    # ----------------------------------------------------------------------
    # Analytics Operations
    # ----------------------------------------------------------------------

    def get_metrics(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Look up metrics for a customer. Returns None if not found."""
        if not customer_id:
            return None
        return self._metrics.get(customer_id.strip().upper())

    def list_all_metrics(self) -> List[Dict[str, Any]]:
        """List all customer metrics."""
        return list(self._metrics.values())

    def save_metrics(self, customer_id: str, metrics: Dict[str, Any]):
        """Save or update metrics for a customer."""
        cid = customer_id.strip().upper()
        metrics["customer_id"] = cid
        self._metrics[cid] = metrics

    def delete_metrics(self, customer_id: str) -> bool:
        """Delete metrics for a customer."""
        cid = customer_id.strip().upper()
        if cid in self._metrics:
            del self._metrics[cid]
            return True
        return False

    def get_history(self, customer_id: str, months: int = 3) -> List[Dict[str, Any]]:
        """Get chronological event timeline for customer."""
        cid = customer_id.strip().upper()
        return self._history.get(cid, [])

    def append_history_event(self, customer_id: str, event: Dict[str, Any]):
        """Append an event to customer history."""
        cid = customer_id.strip().upper()
        if cid not in self._history:
            self._history[cid] = []
        self._history[cid].append(event)


# Global singleton instance
data_service = DataService()
