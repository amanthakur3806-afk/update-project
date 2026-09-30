"""
Memory Management Endpoints
===========================
APIs to inspect, search, and delete short-term conversations and
long-term semantic memories.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.memory import Conversation, Message, Memory

router = APIRouter(prefix="/memory", tags=["Memory Management"])


class MemoryCreate(BaseModel):
    agent_id: str
    entity_key: str
    fact: str
    importance: float = 0.5


# --- Short-term Memory (Conversations) ---

@router.get("/conversations", summary="List active conversation sessions")
def list_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    results = []
    for c in convs:
        msg_count = db.query(Message).filter(Message.conversation_id == c.conversation_id).count()
        results.append({
            "conversation_id": c.conversation_id,
            "agent_id": c.agent_id,
            "title": c.title,
            "turns_count": msg_count,
            "updated_at": c.updated_at
        })
    return results


@router.get("/conversations/{conversation_id}/messages", summary="Get dialogue turns for a conversation")
def get_conversation_messages(conversation_id: str, db: Session = Depends(get_db)):
    msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id.asc()).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at
        }
        for m in msgs
    ]


@router.delete("/conversations/{conversation_id}", summary="Clear conversation history")
def clear_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()
    return {"success": True, "conversation_id": conversation_id, "message": "Conversation history cleared."}


# --- Long-term Memory (Semantic Facts) ---

@router.get("/items", summary="List long-term semantic memory facts")
def list_memories(search: Optional[str] = None, entity_key: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Memory)
    if entity_key:
        query = query.filter(Memory.entity_key == entity_key)
    if search:
        query = query.filter(Memory.content.ilike(f"%{search}%"))

    items = query.order_by(Memory.importance_score.desc()).all()
    return [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "entity_key": m.entity_key,
            "fact": m.content,
            "importance": m.importance_score,
            "created_at": m.created_at
        }
        for m in items
    ]


@router.post("/items", status_code=status.HTTP_201_CREATED, summary="Add a long-term memory fact")
def create_memory(payload: MemoryCreate, db: Session = Depends(get_db)):
    mem = Memory(
        entity_key=payload.entity_key,
        content=payload.fact,
        importance_score=payload.importance
    )
    db.add(mem)
    db.commit()
    return {"success": True, "id": mem.id, "message": "Memory fact persisted."}


@router.delete("/items/{memory_id}", summary="Delete a long-term memory fact (Test Anti-Stale Memory)")
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    mem = db.query(Memory).filter(Memory.id == memory_id).first()
    if not mem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory ID {memory_id} not found."
        )
    db.delete(mem)
    db.commit()
    return {"success": True, "memory_id": memory_id, "message": "Memory deleted."}
