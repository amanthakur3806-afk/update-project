"""
Memory Management Endpoints
===========================
APIs to inspect, search, and delete short-term conversations and
long-term semantic memories.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from app.database import get_db
from app.models.memory import Conversation, Message, Memory
from app.models.user import User
from app.services.auth_service import get_current_user_optional

router = APIRouter(prefix="/memory", tags=["Memory Management"])


class MemoryCreate(BaseModel):
    agent_id: str
    entity_key: str
    fact: str
    importance: float = 0.5


class ConversationCreate(BaseModel):
    conversation_id: Optional[str] = None
    agent_id: str = "luna"
    title: Optional[str] = "New Chat"
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# --- Short-term Memory (Conversations & Multi-Chat Sessions) ---

@router.get("/conversations", summary="List active conversation sessions")
def list_conversations(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    query = db.query(Conversation)
    target_user_id = user_id or (current_user.user_id if current_user else None)
    if target_user_id:
        query = query.filter(Conversation.user_id == target_user_id)
    if session_id:
        query = query.filter(Conversation.session_id == session_id)
    convs = query.order_by(Conversation.updated_at.desc()).all()
    results = []
    for c in convs:
        msg_count = db.query(Message).filter(Message.conversation_id == c.conversation_id).count()
        results.append({
            "conversation_id": c.conversation_id,
            "agent_id": c.agent_id,
            "title": c.title or "New Chat",
            "session_id": c.session_id,
            "user_id": c.user_id,
            "turns_count": msg_count,
            "created_at": c.created_at,
            "updated_at": c.updated_at
        })
    return results


@router.post("/conversations", status_code=status.HTTP_201_CREATED, summary="Create a new conversation session")
def create_conversation(
    payload: ConversationCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    import uuid
    cid = payload.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    conv = db.query(Conversation).filter(Conversation.conversation_id == cid).first()
    effective_user_id = payload.user_id or (current_user.user_id if current_user else None)
    if conv:
        if effective_user_id and not conv.user_id:
            conv.user_id = effective_user_id
            db.commit()
            db.refresh(conv)
        return {
            "conversation_id": conv.conversation_id,
            "agent_id": conv.agent_id,
            "title": conv.title,
            "session_id": conv.session_id,
            "user_id": conv.user_id,
            "created_at": conv.created_at,
            "message": "Existing conversation returned"
        }
    new_conv = Conversation(
        conversation_id=cid,
        agent_id=payload.agent_id,
        title=payload.title or "New Chat",
        session_id=payload.session_id,
        user_id=effective_user_id,
        metadata_json=payload.metadata or {}
    )
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    return {
        "conversation_id": new_conv.conversation_id,
        "agent_id": new_conv.agent_id,
        "title": new_conv.title,
        "session_id": new_conv.session_id,
        "user_id": new_conv.user_id,
        "created_at": new_conv.created_at,
        "message": "Conversation session created"
    }


@router.get("/conversations/{conversation_id}", summary="Get conversation details and full history")
def get_conversation(
    conversation_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    if conv.user_id is None and current_user:
        conv.user_id = current_user.user_id
        db.commit()
        db.refresh(conv)
    elif conv.user_id and current_user and conv.user_id != current_user.user_id and current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This conversation belongs to another user."
        )
    msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id.asc()).all()
    return {
        "conversation_id": conv.conversation_id,
        "agent_id": conv.agent_id,
        "title": conv.title,
        "session_id": conv.session_id,
        "user_id": conv.user_id,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at
            }
            for m in msgs
        ]
    }


@router.patch("/conversations/{conversation_id}", summary="Update conversation session title or metadata")
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    if conv.user_id and current_user and conv.user_id != current_user.user_id and current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot modify another user's conversation."
        )
    if payload.title is not None:
        conv.title = payload.title
    if payload.metadata is not None:
        conv.metadata_json = payload.metadata
    db.commit()
    db.refresh(conv)
    return {
        "success": True,
        "conversation_id": conv.conversation_id,
        "title": conv.title,
        "message": "Conversation updated successfully."
    }


@router.get("/conversations/{conversation_id}/messages", summary="Get dialogue turns for a conversation")
def get_conversation_messages(
    conversation_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if conv and conv.user_id and current_user and conv.user_id != current_user.user_id and current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This conversation belongs to another user."
        )
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
def clear_conversation(
    conversation_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    if conv.user_id and current_user and conv.user_id != current_user.user_id and current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot delete another user's conversation."
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


# --- User-Specific Persistent Context & Cross-Session Memory ---

class UserMemoryCreate(BaseModel):
    content: str
    memory_type: str = "user_preference"
    importance: float = 1.0


@router.get("/user", summary="Get persistent memories learned across chats for current user")
def get_user_memories(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    if not current_user:
        return []
    mems = db.query(Memory).filter(
        or_(
            Memory.user_id == current_user.user_id,
            Memory.entity_key == f"user:{current_user.user_id}"
        )
    ).order_by(Memory.importance_score.desc(), Memory.created_at.desc()).all()
    return [m.to_dict() for m in mems]


@router.post("/user", status_code=status.HTTP_201_CREATED, summary="Add custom preference/fact to user persistent memory")
def add_user_memory(
    payload: UserMemoryCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to save user memory.")
    mem = Memory(
        user_id=current_user.user_id,
        entity_key=f"user:{current_user.user_id}",
        memory_type=payload.memory_type,
        content=payload.content.strip(),
        importance_score=payload.importance
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return {"success": True, "memory": mem.to_dict(), "message": "User memory persisted."}


@router.delete("/user/{memory_id}", summary="Delete a specific user memory")
def delete_user_memory(
    memory_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    mem = db.query(Memory).filter(Memory.id == memory_id).first()
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory record not found.")
    if mem.user_id and mem.user_id != current_user.user_id and current_user.role != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    db.delete(mem)
    db.commit()
    return {"success": True, "message": "User memory removed."}

