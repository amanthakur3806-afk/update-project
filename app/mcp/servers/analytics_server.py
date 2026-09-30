"""
Analytics MCP Server
====================
Exposes business analytics and usage metric tools conforming to the
Model Context Protocol (MCP) standard.

Registered server ID: 'analytics_mcp'
Exposes tools:
  - Analytics.get_customer_metrics  : ARR, MRR, NPS, churn risk, SLA compliance
  - Analytics.get_customer_history  : Chronological event timeline

Tool name aliases supported:
  - 'Analytics.get_metrics'   -> 'Analytics.get_customer_metrics'
  - 'Analytics.get_history'   -> 'Analytics.get_customer_history'

Zero hardcoded business data:
  Delegates all metrics and event history to `data_service`.
  If metrics are missing, returns an explicit `found: False` status
  (Zero Silent Fallbacks rule).
"""
from typing import Dict, Any, List
from app.services.data_service import data_service


class AnalyticsMCPServer:
    """
    In-process Analytics MCP server communicating with the dynamic data service.
    """

    def __init__(self, server_id: str = "analytics_mcp"):
        self.server_id = server_id

    # ------------------------------------------------------------------
    # Tool Discovery
    # ------------------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return available analytics tools with JSON Schema parameters."""
        return [
            {
                "name": "Analytics.get_customer_metrics",
                "server_id": self.server_id,
                "description": (
                    "Fetch real-time customer health metrics: ARR, MRR, NPS score, churn risk, "
                    "active users, API call volume, error rate, and SLA compliance percentage."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer identifier, e.g. 'ABC', 'XYZ', 'ACME'",
                        }
                    },
                    "required": ["customer_id"],
                },
            },
            {
                "name": "Analytics.get_customer_history",
                "server_id": self.server_id,
                "description": (
                    "Retrieve a chronological event timeline for a customer including "
                    "capacity upgrades, quarterly business reviews, and incident resolutions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer identifier",
                        },
                        "months": {
                            "type": "integer",
                            "description": "Number of past months of history to return (default: 3)",
                            "default": 3,
                        },
                    },
                    "required": ["customer_id"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the specified analytics tool with given arguments.
        Supports aliases (Analytics.get_metrics, Analytics.get_history).
        """
        normalized = tool_name.lower().replace("analytics.", "").strip()

        if normalized in ("get_customer_metrics", "get_metrics"):
            return self._get_customer_metrics(arguments)
        elif normalized in ("get_customer_history", "get_history"):
            return self._get_customer_history(arguments)
        else:
            raise NotImplementedError(
                f"Tool '{tool_name}' is not implemented by the Analytics MCP server. "
                f"Available: Analytics.get_customer_metrics, Analytics.get_customer_history"
            )

    # ------------------------------------------------------------------
    # Internal Handlers (Pure Delegation to data_service)
    # ------------------------------------------------------------------

    def _get_customer_metrics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve health metrics from data_service."""
        customer_id = arguments.get("customer_id", "").strip().upper()
        if not customer_id:
            raise ValueError("Missing required argument: 'customer_id'")

        metrics = data_service.get_metrics(customer_id)
        if not metrics:
            return {
                "found": False,
                "customer_id": customer_id,
                "message": f"No analytics metrics found for customer '{customer_id}'.",
                "suggestion": "Verify customer ID or upload metrics to the Analytics Data Manager."
            }

        return {"found": True, "metrics": metrics}

    def _get_customer_history(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve event history timeline from data_service."""
        customer_id = arguments.get("customer_id", "").strip().upper()
        months = int(arguments.get("months", 3))

        if not customer_id:
            raise ValueError("Missing required argument: 'customer_id'")

        history = data_service.get_history(customer_id, months=months)
        return {
            "customer_id": customer_id,
            "months_requested": months,
            "event_count": len(history),
            "timeline": history,
        }


# Global singleton
analytics_server_instance = AnalyticsMCPServer()
