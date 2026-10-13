"""
CRM MCP Server
==============
Exposes customer relationship management (CRM) tools, resources, and prompt templates
conforming to the official Model Context Protocol (MCP) standard.

Registered server ID: 'crm_mcp'
Exposes tools:
  - CRM.get_customer      : Look up a customer profile by customer ID
  - CRM.search_customer   : Search customers by company name, industry, or ID
  - CRM.update_notes      : Append an operational note to a customer record

Exposes resources:
  - crm://customers               : Direct JSON list of all active CRM accounts
  - crm://customers/{customer_id} : Direct JSON dossier of a specific customer

Exposes prompts:
  - crm_account_briefing   : Executive commercial briefing template
  - crm_stakeholder_dossier: Stakeholder mapping and ownership template

Direct CLI execution:
  python app/mcp/servers/crm_server.py                    # STDIO transport
  python app/mcp/servers/crm_server.py --transport sse   # SSE transport on port 8001
"""
import sys
import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in sys.path for direct script execution
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.services.data_service import data_service


class CRMMCPServer:
    """
    In-process CRM MCP server communicating with the dynamic data service.
    """

    def __init__(self, server_id: str = "crm_mcp"):
        self.server_id = server_id

    # ------------------------------------------------------------------
    # Tool Discovery
    # ------------------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return available CRM tools with JSON Schema parameters."""
        return [
            {
                "name": "CRM.get_customer",
                "server_id": self.server_id,
                "description": (
                    "Retrieve the commercial CRM profile and stakeholder dossier for a customer. "
                    "Returns company name, enterprise tier, commercial SLA terms, executive stakeholders, contract value, and relationship history."
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
                "name": "CRM.search_customer",
                "server_id": self.server_id,
                "description": (
                    "Search the enterprise CRM customer directory across company names, industries, tiers, or customer ID keywords. "
                    "Returns matching customer profiles."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword matching company name, industry, or customer ID",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "CRM.update_notes",
                "server_id": self.server_id,
                "description": (
                    "Append a strategic commercial or executive stakeholder meeting note to a customer's CRM record. "
                    "Notes are timestamped automatically in UTC."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID, e.g. 'STRIPE', 'SPOTIFY'",
                        },
                        "note": {
                            "type": "string",
                            "description": "Commercial or relationship note content to append",
                        },
                    },
                    "required": ["customer_id", "note"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the specified CRM tool with given arguments.
        Resolves tool names case-insensitively and handles 'CRM.' / 'crm.' prefix.
        """
        normalized = tool_name.lower().replace("crm.", "").strip()

        if normalized == "get_customer":
            return self._get_customer(arguments)
        elif normalized == "search_customer":
            return self._search_customer(arguments)
        elif normalized == "update_notes":
            return self._update_notes(arguments)
        else:
            raise NotImplementedError(
                f"Tool '{tool_name}' is not implemented by the CRM MCP server. "
                f"Available tools: CRM.get_customer, CRM.search_customer, CRM.update_notes"
            )

    # ------------------------------------------------------------------
    # Internal Handlers (Pure Delegation to data_service)
    # ------------------------------------------------------------------

    def _get_customer(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Look up customer in the dynamic data service."""
        customer_id = arguments.get("customer_id", "").strip().upper()
        if not customer_id:
            raise ValueError("Missing required argument: 'customer_id'")

        customer = data_service.get_customer(customer_id)
        if not customer:
            return {
                "found": False,
                "customer_id": customer_id,
                "message": f"Customer '{customer_id}' was not found in the CRM data source.",
                "suggestion": "Verify the customer ID or import customer records in the CRM Data Manager."
            }

        return {"found": True, "customer": customer}

    def _search_customer(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search customers in dynamic data service."""
        query = arguments.get("query", "").strip()
        if not query:
            return {"count": 0, "results": []}

        results = data_service.search_customers(query)
        return {"count": len(results), "query": query, "results": results}

    def _update_notes(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Append operational note to customer record."""
        customer_id = arguments.get("customer_id", "").strip().upper()
        note = arguments.get("note", "").strip()

        if not customer_id:
            raise ValueError("Missing required argument: 'customer_id'")
        if not note:
            raise ValueError("Missing required argument: 'note'")

        customer = data_service.get_customer(customer_id)
        if not customer:
            return {
                "success": False,
                "error": f"Customer '{customer_id}' does not exist in CRM data source.",
            }

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        timestamped_note = f"[{timestamp}] {note}"
        data_service.append_customer_note(customer_id, timestamped_note)

        updated_customer = data_service.get_customer(customer_id)
        notes_count = len(updated_customer.get("notes", []))

        return {
            "success": True,
            "customer_id": customer_id,
            "notes_count": notes_count,
        }


# Global singleton
crm_server_instance = CRMMCPServer()

# ----------------------------------------------------------------------
# Official Model Context Protocol (MCP) Server Instance
# ----------------------------------------------------------------------
try:
    from mcp.server.mcpserver import MCPServer
    mcp_server = MCPServer("CRM MCP Server")

    # Tools
    @mcp_server.tool(
        name="CRM.get_customer",
        description="Retrieve the commercial CRM profile and stakeholder dossier for a customer (e.g. 'SPOTIFY', 'STRIPE', 'DATADOG', 'SHOPIFY')."
    )
    async def crm_get_customer(customer_id: str) -> dict:
        """Retrieve commercial CRM profile by customer ID."""
        return await crm_server_instance.call_tool("CRM.get_customer", {"customer_id": customer_id})

    @mcp_server.tool(
        name="CRM.search_customer",
        description="Search enterprise CRM customer directory across company names, industries, tiers, or customer ID keywords."
    )
    async def crm_search_customer(query: str) -> dict:
        """Search enterprise CRM customer directory."""
        return await crm_server_instance.call_tool("CRM.search_customer", {"query": query})

    @mcp_server.tool(
        name="CRM.update_notes",
        description="Append a strategic commercial or executive stakeholder meeting note to a customer's CRM record."
    )
    async def crm_update_notes(customer_id: str, note: str) -> dict:
        """Append commercial or relationship note."""
        return await crm_server_instance.call_tool("CRM.update_notes", {"customer_id": customer_id, "note": note})

    # Resources
    @mcp_server.resource("crm://customers")
    def crm_list_all_customers_resource() -> str:
        """Direct access resource listing all customer records currently in the CRM catalog."""
        customers = data_service.list_customers()
        return json.dumps(customers, indent=2)

    @mcp_server.resource("crm://customers/{customer_id}")
    def crm_get_customer_dossier_resource(customer_id: str) -> str:
        """Direct access resource reading a specific customer's CRM dossier and commercial contracts."""
        record = data_service.get_customer(customer_id.upper())
        if not record:
            return json.dumps({"error": f"Customer '{customer_id}' not found in CRM"}, indent=2)
        return json.dumps(record, indent=2)

    # Prompts
    @mcp_server.prompt("crm_account_briefing")
    def crm_account_briefing_prompt(customer_id: str) -> str:
        """Executive prompt template to synthesize commercial health, tier commitments, and stakeholder alignments."""
        return (
            f"You are conducting an executive commercial briefing for account '{customer_id.upper()}'.\n"
            f"1. Query 'CRM.get_customer' with customer_id='{customer_id.upper()}' to examine the account profile.\n"
            f"2. Summarize contract tier, SLA commitments, active executive stakeholders, and commercial notes.\n"
            f"3. Highlight upcoming contract renewal terms and strategic relationship priorities."
        )

    @mcp_server.prompt("crm_stakeholder_dossier")
    def crm_stakeholder_dossier_prompt(customer_id: str) -> str:
        """Stakeholder mapping prompt template for enterprise account management."""
        return (
            f"Please map the executive and operational stakeholders for account '{customer_id.upper()}'.\n"
            f"Identify the account owner, primary executive sponsor, SLA escalation contacts, and meeting notes history."
        )

except ImportError:
    mcp_server = None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CRM MCP Server (Official Model Context Protocol)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport protocol (stdio or sse)")
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE transport (default: 8001)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for SSE transport")
    args = parser.parse_args()

    if mcp_server is None:
        sys.exit("Error: 'mcp' Python package is not installed.")

    if args.transport == "stdio":
        mcp_server.run(transport="stdio")
    else:
        mcp_server.run(transport="sse", host=args.host, port=args.port)
