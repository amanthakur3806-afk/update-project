import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(String(64), primary_key=True, index=True)
    agent_id = Column(String(64), nullable=False, index=True)
    title = Column(String(256), default="New Chat", nullable=True)
    session_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=True, index=True)  # User this memory belongs to
    conversation_id = Column(String(64), nullable=True, index=True)
    entity_key = Column(String(128), nullable=True, index=True)  # e.g., "customer:ABC" or "user:usr_123"
    memory_type = Column(String(32), default="long_term_fact", nullable=False)  # user_fact, user_preference, customer_fact
    content = Column(Text, nullable=False)
    importance_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "entity_key": self.entity_key,
            "memory_type": self.memory_type,
            "content": self.content,
            "importance_score": self.importance_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
