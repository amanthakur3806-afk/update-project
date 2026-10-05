"""Request/response contracts for the Customer Operations Agent."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class CustomerStatusUpdateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    reason: Optional[str] = None


class CustomerNoteCreateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    note: str = Field(..., min_length=1)
    created_by: str = Field(default="customer_operations_agent", min_length=1)


class FollowUpTaskCreateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    due_date: Optional[date] = None
    created_by: str = Field(default="customer_operations_agent", min_length=1)


class OperationAuditResponse(BaseModel):
    id: int
    agent_id: str
    tool_name: str
    customer_id: Optional[str] = None
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    success: bool
    created_at: datetime
