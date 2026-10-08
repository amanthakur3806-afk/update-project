"""
Memory Store Operations
Database access layer for Conversations, Messages, and Semantic Memories.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.memory import Conversation, Message, Memory

class MemoryStore:
    """Provides persistence operations for conversation turns and persistent facts."""

    @staticmethod
    def get_or_create_conversation(
        db: Session,
        conversation_id: str,
        agent_id: str,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Conversation:
        conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
        if not conv:
            conv = Conversation(
                conversation_id=conversation_id,
                agent_id=agent_id,
                title=title or "New Chat",
                session_id=session_id,
                user_id=user_id,
                metadata_json={}
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
        else:
            changed = False
            if user_id and not conv.user_id:
                conv.user_id = user_id
                changed = True
            if title and conv.title in ("New Chat", None, ""):
                conv.title = title
                changed = True
            if changed:
                db.commit()
                db.refresh(conv)
        return conv

    @staticmethod
    def update_conversation_title(db: Session, conversation_id: str, title: str) -> Optional[Conversation]:
        conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
        if conv:
            conv.title = title
            db.commit()
            db.refresh(conv)
        return conv

    @staticmethod
    def add_message(db: Session, conversation_id: str, role: str, content: str) -> Message:
        token_count = len(content.split())
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            token_count=token_count
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def get_recent_messages(db: Session, conversation_id: str, limit: int = 10) -> List[Message]:
        return (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .all()
        )[::-1]  # Return in chronological order

    @staticmethod
    def add_long_term_memory(
        db: Session,
        content: str,
        entity_key: Optional[str] = None,
        memory_type: str = "long_term_fact",
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        importance_score: float = 1.0
    ) -> Memory:
        # Check duplicate
        clean_content = content.strip()
        existing = db.query(Memory).filter(
            Memory.content == clean_content,
            or_(Memory.user_id == user_id, Memory.entity_key == entity_key)
        ).first()
        if existing:
            return existing

        mem = Memory(
            content=clean_content,
            entity_key=entity_key,
            memory_type=memory_type,
            conversation_id=conversation_id,
            user_id=user_id,
            importance_score=importance_score
        )
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return mem

    @staticmethod
    def add_user_memory(
        db: Session,
        user_id: str,
        content: str,
        memory_type: str = "user_preference",
        conversation_id: Optional[str] = None,
        importance_score: float = 1.0
    ) -> Memory:
        """Persist a learned user context or preference that applies across all conversations."""
        return MemoryStore.add_long_term_memory(
            db=db,
            content=content,
            entity_key=f"user:{user_id}",
            memory_type=memory_type,
            conversation_id=conversation_id,
            user_id=user_id,
            importance_score=importance_score
        )

    @staticmethod
    def search_user_memories(
        db: Session,
        user_id: str,
        query: Optional[str] = None,
        limit: int = 6
    ) -> List[Memory]:
        """
        Retrieve persistent memories for a specific user across all their conversations.
        """
        if not user_id:
            return []

        user_mems = db.query(Memory).filter(
            or_(
                Memory.user_id == user_id,
                Memory.entity_key == f"user:{user_id}"
            )
        ).order_by(Memory.created_at.desc()).all()

        if not query or not query.strip():
            return user_mems[:limit]

        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        scored = []
        for mem in user_mems:
            content_lower = mem.content.lower()
            overlap = sum(1 for t in query_terms if t in content_lower)
            # Prioritize higher importance and recency
            score = (overlap + 1.0) * mem.importance_score
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in scored[:limit]]

    @staticmethod
    def search_memories(
        db: Session,
        query: str,
        entity_key: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Memory]:
        """
        Search memories relevant to the entity or keywords in query.
        """
        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        
        mem_query = db.query(Memory)
        if entity_key and user_id:
            mem_query = mem_query.filter(
                or_(
                    Memory.entity_key == entity_key,
                    Memory.user_id == user_id,
                    Memory.entity_key == f"user:{user_id}"
                )
            )
        elif entity_key:
            mem_query = mem_query.filter(Memory.entity_key == entity_key)
        elif user_id:
            mem_query = mem_query.filter(
                or_(
                    Memory.user_id == user_id,
                    Memory.entity_key == f"user:{user_id}"
                )
            )

        all_memories = mem_query.all()
        scored_memories = []

        for mem in all_memories:
            content_lower = mem.content.lower()
            overlap = sum(1 for term in query_terms if term in content_lower)
            # Bonus score if entity matches
            if entity_key and mem.entity_key == entity_key:
                overlap += 2
            if user_id and (mem.user_id == user_id or mem.entity_key == f"user:{user_id}"):
                overlap += 1
            
            if overlap > 0 or not query_terms:
                scored_memories.append((overlap * mem.importance_score, mem))

        # Sort by relevance score descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in scored_memories[:limit]]
