"""
Authentication API Endpoints
Register, Login, Me, Profile Update, and Demo Accounts
"""
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.user import User
from app.services.auth_service import (
    auth_service,
    get_current_user_required,
    get_current_user_optional
)
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserProfileResponse,
    AuthTokenResponse,
    UpdateProfileRequest,
    DemoAccountResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication & Users"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED, summary="Register a new user account")
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """Create a new user, hash credentials with PBKDF2, and return JWT access token."""
    existing_email = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    existing_user = db.query(User).filter(User.username == payload.username.lower().strip()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="This username is already taken.")

    hashed_password, salt = auth_service.hash_password(payload.password)
    user_id = f"usr_{uuid.uuid4().hex[:12]}"

    user = User(
        user_id=user_id,
        email=payload.email.lower().strip(),
        username=payload.username.lower().strip(),
        hashed_password=hashed_password,
        salt=salt,
        full_name=payload.full_name.strip(),
        role=payload.role or "Account Executive",
        department=payload.department or "Commercial Sales",
        responsibilities=payload.responsibilities or "Enterprise account intelligence and operations",
        preferences=payload.preferences or {"concise_mode": False, "preferred_currency": "USD", "timezone": "UTC"},
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth_service.create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@router.post("/login", response_model=AuthTokenResponse, summary="Login with username or email")
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with username or email + password, returning JWT token."""
    login_id = payload.username_or_email.lower().strip()
    user = db.query(User).filter(
        or_(User.username == login_id, User.email == login_id),
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Check your username/email and password."
        )

    is_valid = auth_service.verify_password(payload.password, user.hashed_password, user.salt)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Check your username/email and password."
        )

    token = auth_service.create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@router.get("/me", response_model=UserProfileResponse, summary="Get current authenticated user profile")
def get_me(current_user: User = Depends(get_current_user_required)):
    """Retrieve full user profile and preferences for the active token."""
    return current_user.to_dict()


@router.patch("/profile", response_model=UserProfileResponse, summary="Update user profile and preferences")
def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Update profile information or preferences for the active user."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.role is not None:
        current_user.role = payload.role.strip()
    if payload.department is not None:
        current_user.department = payload.department.strip()
    if payload.responsibilities is not None:
        current_user.responsibilities = payload.responsibilities.strip()
    if payload.preferences is not None:
        merged = dict(current_user.preferences or {})
        merged.update(payload.preferences)
        current_user.preferences = merged

    db.commit()
    db.refresh(current_user)
    return current_user.to_dict()


@router.get("/demo-accounts", response_model=List[DemoAccountResponse], summary="List available 1-click demo accounts")
def list_demo_accounts():
    """Returns curated demo accounts available for instant 1-click login."""
    return [
        {
            "username": "sarah",
            "email": "sarah.jenkins@enterprise.com",
            "full_name": "Sarah Jenkins",
            "role": "Senior Enterprise Account Executive",
            "department": "Commercial Sales",
            "description": "Primary AE managing accounts ABC & XYZ. Focus on contract renewals, multi-year volume pricing, and SLA governance."
        },
        {
            "username": "alex",
            "email": "alex.chen@enterprise.com",
            "full_name": "Alex Chen",
            "role": "Lead Support Operations Architect",
            "department": "Customer Operations",
            "description": "Technical Operations Lead managing platform uptime, Sev-1 incident protocols, and task execution for NOVA & QUANTUM."
        },
        {
            "username": "admin",
            "email": "admin@enterprise.com",
            "full_name": "Elena Rostova",
            "role": "Executive VP Operations & Strategy",
            "department": "Executive Leadership",
            "description": "Executive portfolio oversight, company-wide ARR/MRR health metrics, churn risk auditing, and compliance policy verification."
        }
    ]
