"""
User Model for Authentication & Multi-Tenant User Profiles
"""
import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(String(64), default="Account Executive", nullable=False)
    department = Column(String(64), default="Customer Operations", nullable=False)
    responsibilities = Column(Text, default="Account Management & Customer Operations", nullable=True)
    preferences = Column(JSON, default=lambda: {"concise_mode": False, "preferred_currency": "USD", "timezone": "UTC"})
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "department": self.department,
            "responsibilities": self.responsibilities,
            "preferences": self.preferences or {},
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_llm_profile(self) -> str:
        """Format essential user context for LLM prompt without useless clutter."""
        lines = [
            f"- **User**: {self.full_name} (@{self.username})",
            f"- **Role & Department**: {self.role} | {self.department}",
            f"- **Primary Focus**: {self.responsibilities or 'General Operations'}"
        ]
        if self.preferences:
            tz = self.preferences.get("timezone", "UTC")
            curr = self.preferences.get("preferred_currency", "USD")
            lines.append(f"- **Context**: Timezone {tz}, Currency {curr}")
        return "\n".join(lines)
