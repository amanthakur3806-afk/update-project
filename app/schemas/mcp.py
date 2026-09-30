from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict
import datetime


class MCPServerCreate(BaseModel):
    server_id: str
    server_name: str
    server_url: Optional[str] = None
    transport: str = "inprocess"
    configuration: Dict[str, Any] = {}
    enabled: bool = True


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_id: str
    server_name: str
    server_url: Optional[str] = None
    transport: str
    configuration: Dict[str, Any]
    enabled: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ToolParamSchema(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    required: bool = True


class ToolMetadataResponse(BaseModel):
    tool_name: str
    server_id: str
    description: str
    parameters: Dict[str, Any]
    enabled: bool = True
