"""
MCP Server & Tool Discovery API Endpoints
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.mcp import MCPServer
from app.mcp.client_manager import mcp_client_manager
from app.schemas.mcp import MCPServerCreate, ToolMetadataResponse

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])

@router.get("/servers", summary="List registered MCP servers and connection status")
def list_mcp_servers(db: Session = Depends(get_db)):
    records = db.query(MCPServer).filter(MCPServer.enabled == True).order_by(MCPServer.server_name).all()
    mcp_client_manager.sync_database_servers(records)
    servers = mcp_client_manager.list_servers()
    return [server for server in servers if server.get("enabled", True)]


@router.post("/servers", status_code=status.HTTP_201_CREATED, summary="Register an MCP server")
def create_mcp_server(payload: MCPServerCreate, db: Session = Depends(get_db)):
    existing = db.query(MCPServer).filter(MCPServer.server_id == payload.server_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"MCP server '{payload.server_id}' already exists.")

    server = MCPServer(**payload.model_dump())
    db.add(server)
    db.commit()
    db.refresh(server)
    mcp_client_manager.sync_database_servers([server])
    result = {
        "server_id": server.server_id,
        "server_name": server.server_name,
        "server_url": server.server_url,
        "transport": server.transport,
        "configuration": server.configuration or {},
        "enabled": server.enabled,
        "status": "connected" if server.server_id in mcp_client_manager._servers else "registered",
        "created_at": server.created_at,
        "updated_at": server.updated_at,
    }
    return result

@router.get("/tools", response_model=List[ToolMetadataResponse], summary="Discover all available tools dynamically across MCP servers")
async def list_mcp_tools():
    tools = await mcp_client_manager.discover_tools()
    results = []
    for t in tools:
        results.append(ToolMetadataResponse(
            tool_name=t["name"],
            server_id=t.get("server_id", "unknown"),
            description=t.get("description", ""),
            parameters=t.get("parameters", {}),
            enabled=True
        ))
    return results
