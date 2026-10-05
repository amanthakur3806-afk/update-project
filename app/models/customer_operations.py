"""Database models for the future Customer Operations Agent.

These tables define the write-side contract only. The MCP write operations are
intentionally scaffolded and do not mutate these tables yet.
"""
import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CustomerAccount(Base):
    __tablename__ = "customer_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(64), unique=True, nullable=False, index=True)
    company_name = Column(String(256), nullable=False)
    status = Column(String(32), default="active", nullable=False)
    renewal_date = Column(Date, nullable=True)
    owner = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    notes = relationship("CustomerOperationNote", back_populates="customer", cascade="all, delete-orphan")
    tasks = relationship("FollowUpTask", back_populates="customer", cascade="all, delete-orphan")


class CustomerOperationNote(Base):
    __tablename__ = "customer_operation_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    customer = relationship("CustomerAccount", back_populates="notes")


class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    due_date = Column(Date, nullable=True)
    status = Column(String(32), default="open", nullable=False)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    customer = relationship("CustomerAccount", back_populates="tasks")


class OperationAuditLog(Base):
    __tablename__ = "operation_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(64), nullable=False, index=True)
    tool_name = Column(String(128), nullable=False)
    customer_id = Column(String(64), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    success = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
