"""
Analytics MCP Server
====================
Exposes business analytics, telemetry metrics, and customer event history tools,
resources, and prompt templates conforming to the official Model Context Protocol (MCP) standard.

Registered server ID: 'analytics_mcp'
Exposes tools:
  - Analytics.get_customer_metrics  : ARR, MRR, NPS, churn risk, SLA compliance
  - Analytics.get_customer_history  : Chronological event timeline

Exposes resources:
  - analytics://metrics/{customer_id} : Direct JSON telemetry and financial metrics
  - analytics://history/{customer_id} : Direct JSON event timeline

Exposes prompts:
  - analytics_churn_audit     : Churn risk and telemetry audit template
  - analytics_financial_review: ARR, MRR, and renewal capacity template

Direct CLI execution:
  python app/mcp/servers/analytics_server.py                    # STDIO transport
  python app/mcp/servers/analytics_server.py --transport sse   # SSE transport on port 8002
"""
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in sys.path for direct script execution
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
                            "description": "Unique customer identifier, e.g. 'STRIPE', 'SHOPIFY', 'SPOTIFY', 'DATADOG'",
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

# ----------------------------------------------------------------------
# Official Model Context Protocol (MCP) Server Instance
# ----------------------------------------------------------------------
try:
    from mcp.server.mcpserver import MCPServer
    mcp_server = MCPServer("Analytics MCP Server")

    # Tools
    @mcp_server.tool(
        name="Analytics.get_customer_metrics",
        description="Fetch real-time customer health metrics: ARR, MRR, NPS score, churn risk, active users, API volume, error rate, SLA compliance."
    )
    async def analytics_get_customer_metrics(customer_id: str) -> dict:
        """Fetch real-time customer health metrics."""
        return await analytics_server_instance.call_tool("Analytics.get_customer_metrics", {"customer_id": customer_id})

    @mcp_server.tool(
        name="Analytics.get_customer_history",
        description="Retrieve chronological event timeline for a customer including capacity upgrades, QBRs, and incident resolutions."
    )
    async def analytics_get_customer_history(customer_id: str, months: int = 3) -> dict:
        """Retrieve chronological event timeline for a customer."""
        return await analytics_server_instance.call_tool("Analytics.get_customer_history", {"customer_id": customer_id, "months": months})

    # Resources
    @mcp_server.resource("analytics://metrics/{customer_id}")
    def analytics_get_metrics_resource(customer_id: str) -> str:
        """Direct access resource reading real-time telemetry, ARR, MRR, NPS, and churn probability."""
        metrics = data_service.get_metrics(customer_id.upper())
        if not metrics:
            return json.dumps({"error": f"No telemetry metrics for customer '{customer_id}'"}, indent=2)
        return json.dumps(metrics, indent=2)

    @mcp_server.resource("analytics://history/{customer_id}")
    def analytics_get_history_resource(customer_id: str) -> str:
        """Direct access resource reading chronological account event timeline."""
        history = data_service.get_history(customer_id.upper(), months=6)
        return json.dumps({"customer_id": customer_id.upper(), "timeline": history}, indent=2)

    # Prompts
    @mcp_server.prompt("analytics_churn_audit")
    def analytics_churn_audit_prompt(customer_id: str) -> str:
        """Template for proactive telemetry churn risk analysis."""
        return (
            f"Perform an in-depth telemetry and retention audit for account '{customer_id.upper()}'.\n"
            f"1. Call 'Analytics.get_customer_metrics' for customer '{customer_id.upper()}'.\n"
            f"2. Evaluate churn probability against SLA compliance, error rates, and API call trend.\n"
            f"3. Recommend proactive engineering or Customer Success interventions if churn risk exceeds 5%."
        )

    @mcp_server.prompt("analytics_financial_review")
    def analytics_financial_review_prompt(customer_id: str) -> str:
        """Template for revenue and contract capacity analysis."""
        return (
            f"Generate a financial health summary for account '{customer_id.upper()}'.\n"
            f"Summarize ARR, MRR, quarterly growth, license seat utilization, and renewal timeline."
        )

except ImportError:
    mcp_server = None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analytics MCP Server (Official Model Context Protocol)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport protocol (stdio or sse)")
    parser.add_argument("--port", type=int, default=8002, help="Port for SSE transport (default: 8002)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for SSE transport")
    args = parser.parse_args()

    if mcp_server is None:
        sys.exit("Error: 'mcp' Python package is not installed.")

    if args.transport == "stdio":
        mcp_server.run(transport="stdio")
    else:
        mcp_server.run(transport="sse", host=args.host, port=args.port)
