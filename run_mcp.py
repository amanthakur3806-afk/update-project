"""
Luna Model Context Protocol (MCP) Runner
========================================
Runs independent, domain-bounded Luna MCP servers over standard transports (STDIO or SSE)
for direct connection with @modelcontextprotocol/inspector, Claude Desktop, or external MCP clients.

Each server operates as an autonomous, decoupled microservice:
  - crm: CRM MCP Server (Commercial profiles, customer search, meeting notes)
  - analytics: Analytics MCP Server (ARR, MRR, churn risk, telemetry metrics, event history)
  - operations: Customer Operations MCP Server (Account lifecycle, tasks, status updates, audit history)

Usage:
  # 1. Connect specific MCP server to MCP Inspector via STDIO:
  npx @modelcontextprotocol/inspector python run_mcp.py crm
  npx @modelcontextprotocol/inspector python run_mcp.py operations
  npx @modelcontextprotocol/inspector python run_mcp.py analytics

  # Or using python -m directly:
  npx @modelcontextprotocol/inspector python -m app.mcp.servers.crm_server
  npx @modelcontextprotocol/inspector python -m app.mcp.servers.operations_server
  npx @modelcontextprotocol/inspector python -m app.mcp.servers.analytics_server

  # 2. Run over standalone SSE transport (HTTP):
  python run_mcp.py crm --transport sse --port 8001
  python run_mcp.py operations --transport sse --port 8002
  python run_mcp.py analytics --transport sse --port 8003
"""
import sys
import argparse
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="Luna Multi-MCP Server Runner - Launch discrete, domain-specific MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  npx @modelcontextprotocol/inspector python run_mcp.py crm
  npx @modelcontextprotocol/inspector python run_mcp.py operations
  npx @modelcontextprotocol/inspector python run_mcp.py analytics
  python run_mcp.py crm --transport sse --port 8001
"""
    )
    parser.add_argument(
        "server",
        nargs="?",
        choices=["crm", "analytics", "operations"],
        help="Which MCP server to launch ('crm', 'analytics', or 'operations')"
    )
    parser.add_argument(
        "--server",
        dest="server_flag",
        choices=["crm", "analytics", "operations"],
        help="Alternative flag to specify target MCP server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: 'stdio')"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port number when running standalone SSE/HTTP transport (default: 8001)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address for standalone SSE/HTTP transport (default: 127.0.0.1)"
    )

    args = parser.parse_args()

    selected_server = args.server or args.server_flag

    if not selected_server:
        parser.print_help()
        print("\n[ERROR] You must specify which discrete MCP server to launch: 'crm', 'analytics', or 'operations'.")
        print("Example: python run_mcp.py crm")
        sys.exit(1)

    # Resolve target domain-specific server
    if selected_server == "crm":
        from app.mcp.servers.crm_server import mcp_server as target_server
    elif selected_server == "analytics":
        from app.mcp.servers.analytics_server import mcp_server as target_server
    elif selected_server == "operations":
        from app.mcp.servers.operations_server import mcp_server as target_server
    else:
        sys.exit(f"Unknown server: {selected_server}")

    if target_server is None:
        sys.exit("Error: 'mcp' Python package is not available in the current environment.")

    # Run selected transport
    if args.transport == "stdio":
        target_server.run(transport="stdio")
    else:
        target_server.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
