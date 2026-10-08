"""
Authentication & User Profile Pydantic Schemas
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: Optional[str] = "Account Executive"
    department: Optional[str] = "Commercial Sales"
    responsibilities: Optional[str] = "Enterprise account intelligence and customer operations"
    preferences: Optional[Dict[str, Any]] = None


class UserLoginRequest(BaseModel):
    username_or_email: str
    password: str


class UserProfileResponse(BaseModel):
    id: int
    user_id: str
    email: str
    username: str
    full_name: str
    role: str
    department: str
    responsibilities: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    responsibilities: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class DemoAccountResponse(BaseModel):
    username: str
    email: str
    full_name: str
    role: str
    department: str
    description: str
