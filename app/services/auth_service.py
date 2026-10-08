"""
Authentication & JWT Token Service
Provides cryptographic password hashing (PBKDF2-HMAC-SHA256) and JWT tokens.
"""
import os
import hashlib
import hmac
import datetime
from typing import Optional, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


class AuthService:
    """Handles password hashing, token issuance, and authentication verification."""

    @staticmethod
    def generate_salt() -> str:
        """Generate a secure random 16-byte salt formatted as hex."""
        return os.urandom(16).hex()

    @classmethod
    def hash_password(cls, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """
        Hash a password using PBKDF2-HMAC-SHA256 with 100,000 iterations.
        Returns (hashed_password_hex, salt_hex).
        """
        if not salt:
            salt = cls.generate_salt()
        salt_bytes = bytes.fromhex(salt)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt_bytes,
            100_000
        )
        return derived.hex(), salt

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str, salt: str) -> bool:
        """Verify password against stored hash using constant-time comparison."""
        try:
            salt_bytes = bytes.fromhex(salt)
            derived = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt_bytes,
                100_000
            )
            return hmac.compare_digest(derived.hex(), hashed_password)
        except Exception:
            return False

    @staticmethod
    def create_access_token(user: User, expires_hours: Optional[int] = None) -> str:
        """Create signed JWT access token containing essential user claims."""
        hours = expires_hours or settings.JWT_EXPIRATION_HOURS
        now = datetime.datetime.now(datetime.timezone.utc)
        exp = now + datetime.timedelta(hours=hours)

        payload = {
            "sub": user.user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "department": user.department,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp())
        }

        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return token

    @staticmethod
    def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate signed JWT token."""
        try:
            decoded = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return decoded
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None


auth_service = AuthService()


def get_current_user_optional(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Retrieve currently authenticated user from Bearer token if present."""
    if not auth_header or not auth_header.credentials:
        return None

    payload = auth_service.decode_access_token(auth_header.credentials)
    if not payload or "sub" not in payload:
        return None

    user = db.query(User).filter(User.user_id == payload["sub"], User.is_active == True).first()
    return user


def get_current_user_required(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Ensure request contains a valid JWT token and return authenticated User."""
    user = get_current_user_optional(auth_header=auth_header, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
