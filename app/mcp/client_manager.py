"""
Multi-MCP Client Manager
Manages server registries, dynamic tool discovery, agent-level permission enforcement,
and resilient tool execution across multiple MCP servers.
"""
import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from app.mcp.servers.crm_server import crm_server_instance
from app.mcp.servers.analytics_server import analytics_server_instance
from app.mcp.servers.operations_server import operations_server_instance

logger = logging.getLogger("mcp_manager")

class ToolPermissionError(Exception):
    """Raised when an agent attempts to execute an unauthorized tool."""
    pass

class ToolNotFoundError(Exception):
    """Raised when a requested tool is not registered in the catalog."""
    pass


class MCPClientManager:
    """Coordinates multiple MCP servers, tool discovery, permissions, and tool execution."""

    def __init__(self):
        # Server registry mapping server_id to server handler
        self._servers: Dict[str, Any] = {
            "crm_mcp": crm_server_instance,
            "analytics_mcp": analytics_server_instance,
            "operations_mcp": operations_server_instance,
        }
        self._metadata: Dict[str, Dict[str, Any]] = {
            "crm_mcp": {
                "server_id": "crm_mcp",
                "server_name": "CRM MCP Server",
                "transport": "inprocess",
                "status": "connected",
            },
            "analytics_mcp": {
                "server_id": "analytics_mcp",
                "server_name": "Analytics MCP Server",
                "transport": "inprocess",
                "status": "connected",
            },
            "operations_mcp": {
                "server_id": "operations_mcp",
                "server_name": "Customer Operations MCP Server",
                "transport": "inprocess",
                "status": "connected",
                "enabled": True,
            },
        }
        # Runtime Tool Registry
        self._tool_registry: Dict[str, Dict[str, Any]] = {}
        self._build_tool_registry()

    def _build_tool_registry(self) -> None:
        """Construct canonical tool registry from connected MCP servers."""
        self._tool_registry.clear()
        
        # Metadata for tool safety and idempotency
        write_tools = {
            "operations.create_customer",
            "operations.update_customer_status",
            "operations.add_customer_note",
            "operations.create_follow_up_task",
            "operations.update_follow_up_task_status",
            "crm.update_notes",
        }

        for server_id, server in self._servers.items():
            try:
                tools = server.list_tools()
                for tool in tools:
                    name = tool.get("name", "").strip()
                    if not name:
                        continue
                    canon_key = name.lower()
                    
                    # Tool classification
                    is_read_only = canon_key not in write_tools
                    safe_to_retry = is_read_only  # Writes are not safe to retry without idempotency key

                    self._tool_registry[canon_key] = {
                        "canonical_name": name,
                        "server_id": server_id,
                        "server": server,
                        "definition": tool,
                        "read_only": is_read_only,
                        "safe_to_retry": safe_to_retry,
                    }
            except Exception as exc:
                logger.error(f"Error building tool registry from server {server_id}: {exc}")

    def register_server(self, server_id: str, server_instance: Any):
        """Register an active MCP server instance."""
        self._servers[server_id] = server_instance
        self._metadata.setdefault(server_id, {
            "server_id": server_id,
            "server_name": server_id,
            "transport": "inprocess",
        })
        self._metadata[server_id]["status"] = "connected"
        self._build_tool_registry()

    def sync_database_servers(self, records: List[Any]) -> None:
        """Sync the database catalog into the runtime registry."""
        for record in records:
            metadata = {
                "server_id": record.server_id,
                "server_name": record.server_name,
                "server_url": record.server_url,
                "transport": record.transport,
                "status": "connected" if record.server_id in self._servers else "registered",
                "enabled": record.enabled,
            }
            self._metadata[record.server_id] = metadata
        self._build_tool_registry()

    def get_tool_server_id(self, tool_name: str) -> Optional[str]:
        """Resolve a discovered tool to its MCP server id using registry lookup."""
        canon_key = tool_name.strip().lower()
        entry = self._tool_registry.get(canon_key)
        return entry["server_id"] if entry else None

    def list_servers(self) -> List[Dict[str, Any]]:
        """List metadata of all connected MCP servers."""
        return list(self._metadata.values())

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover tools across all connected MCP servers via registry."""
        if not self._tool_registry:
            self._build_tool_registry()
        return [entry["definition"] for entry in self._tool_registry.values()]

    async def get_tools_for_agent(self, allowed_tools: List[str]) -> List[Dict[str, Any]]:
        """Filter discovered tools by agent-specific tool permissions."""
        if not allowed_tools:
            return []
        if not self._tool_registry:
            self._build_tool_registry()

        allowed_canon = {t.strip().lower() for t in allowed_tools}
        filtered = []
        for canon_key, entry in self._tool_registry.items():
            # Match canonical full name or bare name if exact
            if canon_key in allowed_canon:
                filtered.append(entry["definition"])
            else:
                # Handle cases where DB has 'CRM.get_customer' or 'crm.get_customer'
                for allowed in allowed_canon:
                    if canon_key == allowed or canon_key == allowed.lower():
                        filtered.append(entry["definition"])
                        break
        return filtered

    def check_tool_permission(self, tool_name: str, allowed_tools: List[str]) -> bool:
        """Validate if a specific tool is authorized for the given agent."""
        tool_canon = tool_name.strip().lower()
        allowed_canon = {t.strip().lower() for t in allowed_tools}
        
        # Check canonical match
        if tool_canon in allowed_canon:
            return True
            
        # Check if mapped to registered tool
        entry = self._tool_registry.get(tool_canon)
        if entry:
            return entry["canonical_name"].lower() in allowed_canon
            
        return False

    def _resolve_server(self, tool_name: str) -> Optional[Any]:
        """Find the corresponding MCP server for a tool using registry lookup."""
        canon_key = tool_name.strip().lower()
        entry = self._tool_registry.get(canon_key)
        if entry:
            return entry["server"]
        return None

    def get_tool_metadata(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve tool registry metadata (read_only, safe_to_retry, etc.)."""
        return self._tool_registry.get(tool_name.strip().lower())

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        allowed_tools: List[str],
        timeout_seconds: float = 10.0,
        max_retries: int = 1
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool with explicit permission checking, timeout, safe retries,
        and separated transport vs business success semantics.
        """
        start_time = time.time()
        
        # 1. Permission check
        if not self.check_tool_permission(tool_name, allowed_tools):
            duration_ms = round((time.time() - start_time) * 1000, 2)
            raise ToolPermissionError(
                f"Tool '{tool_name}' is not in the allowed tools list for this agent: {allowed_tools}"
            )

        # 2. Registry lookup & Server resolution
        meta = self.get_tool_metadata(tool_name)
        server = self._resolve_server(tool_name)
        if not server or not meta:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "success": False,
                "tool_success": False,
                "transport_success": False,
                "tool_name": tool_name,
                "arguments": arguments,
                "error": f"Tool '{tool_name}' is not registered in the MCP tool registry.",
                "duration_ms": duration_ms,
                "attempts": 0
            }

        # 3. Determine safe retry count
        allowed_attempts = (max_retries + 1) if meta.get("safe_to_retry", False) else 1

        last_error = None
        for attempt in range(allowed_attempts):
            try:
                result = await asyncio.wait_for(
                    server.call_tool(tool_name, arguments),
                    timeout=timeout_seconds
                )
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                # Determine tool business success vs business failure
                tool_success = True
                if isinstance(result, dict):
                    if result.get("success") is False or result.get("found") is False:
                        tool_success = False
                        if result.get("error"):
                            last_error = result.get("error")
                
                return {
                    "success": tool_success,  # Overall business success
                    "tool_success": tool_success,
                    "transport_success": True,
                    "tool_name": meta["canonical_name"],
                    "arguments": arguments,
                    "result": result,
                    "error": last_error,
                    "duration_ms": duration_ms,
                    "attempts": attempt + 1
                }
            except asyncio.TimeoutError:
                last_error = f"Tool execution timed out after {timeout_seconds}s"
            except Exception as e:
                last_error = str(e)
            
            # Brief delay before retry if safe
            if attempt < allowed_attempts - 1:
                await asyncio.sleep(0.2)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "tool_success": False,
            "transport_success": False,
            "tool_name": meta["canonical_name"],
            "arguments": arguments,
            "result": {"success": False, "error": last_error},
            "error": last_error,
            "duration_ms": duration_ms,
            "attempts": allowed_attempts
        }

# Global singleton
mcp_client_manager = MCPClientManager()
