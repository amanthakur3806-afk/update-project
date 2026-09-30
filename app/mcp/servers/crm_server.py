"""
CRM MCP Server
==============
Exposes customer relationship management (CRM) tools conforming to the
Model Context Protocol (MCP) standard.

Registered server ID: 'crm_mcp'
Exposes tools:
  - CRM.get_customer      : Look up a customer profile by customer ID
  - CRM.search_customer   : Search customers by company name, industry, or ID
  - CRM.update_notes      : Append an operational note to a customer record

Zero hardcoded business data:
  Delegates all data operations to `data_service`.
  If a customer does not exist, returns an explicit `found: False` status
  rather than fabricating records (Zero Silent Fallbacks rule).
"""
import datetime
from typing import Dict, Any, List
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
                    "Retrieve a comprehensive CRM profile for a customer by their unique ID. "
                    "Returns company name, tier, SLA, stakeholders, contract value, and operational notes."
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
                "name": "CRM.search_customer",
                "server_id": self.server_id,
                "description": (
                    "Search the CRM directory by company name, industry, or customer ID keyword. "
                    "Returns a list of matching customer records."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term to match against company name, industry, or customer ID",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "CRM.update_notes",
                "server_id": self.server_id,
                "description": (
                    "Append an operational note to a customer's CRM record. "
                    "Notes are timestamped automatically."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID",
                        },
                        "note": {
                            "type": "string",
                            "description": "Note content to append to the customer record",
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
            "last_note": timestamped_note,
        }


# Global singleton
crm_server_instance = CRMMCPServer()
