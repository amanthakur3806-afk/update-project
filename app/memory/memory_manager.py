"""
Memory Manager
Orchestrates short-term conversational context and semantic long-term memory across all user sessions.
Manages context window size to prevent token overflow and extracts persistent user facts.
"""
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.memory.store import MemoryStore

class MemoryManager:
    """Coordinates memory loading, relevance filtering, context window compression, and user context extraction."""

    def __init__(self, max_short_term_messages: int = 6, max_long_term_facts: int = 6):
        self.max_short_term_messages = max_short_term_messages
        self.max_long_term_facts = max_long_term_facts

    def load_memory_context(
        self,
        db: Session,
        conversation_id: Optional[str],
        query: str,
        entity_key: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load structured short-term dialogue and cross-chat long-term memory for an agent run.
        Includes persistent facts and preferences learned about the user across all their conversations.
        """
        short_term_history = []
        if conversation_id:
            recent_msgs = MemoryStore.get_recent_messages(
                db,
                conversation_id=conversation_id,
                limit=self.max_short_term_messages
            )
            for msg in recent_msgs:
                short_term_history.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # 1. User-specific persistent context & preferences across all chats
        user_facts = []
        if user_id:
            user_records = MemoryStore.search_user_memories(
                db,
                user_id=user_id,
                query=query,
                limit=self.max_long_term_facts
            )
            user_facts = [f"[User Context]: {rec.content}" for rec in user_records]

        # 2. Entity-specific facts (e.g. customer:ABC)
        entity_facts = []
        if entity_key:
            entity_records = MemoryStore.search_memories(
                db,
                query=query,
                entity_key=entity_key,
                user_id=None,
                limit=self.max_long_term_facts
            )
            entity_facts = [f"[{entity_key}]: {rec.content}" for rec in entity_records if f"[User Context]: {rec.content}" not in user_facts]

        combined_facts = user_facts + entity_facts

        return {
            "conversation_id": conversation_id,
            "short_term_history": short_term_history,
            "user_facts": user_facts,
            "entity_facts": entity_facts,
            "long_term_facts": combined_facts[:self.max_long_term_facts]
        }

    def extract_and_save_user_facts(
        self,
        db: Session,
        user_query: str,
        assistant_response: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Automatically analyze user prompts to extract and persist durable user preferences,
        business context, account metrics, and ongoing responsibilities across sessions,
        while filtering out emotional venting, complaints, and transient queries.
        """
        if not user_id or not user_query:
            return

        text = user_query.strip()
        saved_count = 0

        # -------------------------------------------------------------
        # 1. LLM-Based Intelligent Memory Distillation (Primary)
        # -------------------------------------------------------------
        try:
            from app.workflow.llm_provider import llm_provider
            llm_facts = llm_provider.extract_user_facts(text)
            for item in llm_facts:
                fact_text = item.get("fact", "").strip()
                mem_type = item.get("type", "user_context")
                imp = float(item.get("importance", 1.2))
                if len(fact_text) > 4 and len(fact_text) < 300:
                    MemoryStore.add_user_memory(
                        db=db,
                        user_id=user_id,
                        content=fact_text,
                        memory_type=mem_type,
                        conversation_id=conversation_id,
                        importance_score=imp
                    )
                    saved_count += 1
        except Exception:
            pass

        # -------------------------------------------------------------
        # 2. Heuristic & Semantic Pattern Extractor (Fast offline & fallback)
        # -------------------------------------------------------------
        extracted_facts = []

        # A. Explicit memory triggers: "remember that ...", "note that ...", "keep in mind that ..."
        explicit_patterns = [
            r"(?:please\s+)?(?:remember|note|keep in mind)\s+that\s+([^,\.!\n]+)",
            r"(?:please\s+)?remember\s+my\s+([^,\.!\n]+)",
            r"don'?t\s+forget\s+that\s+([^,\.!\n]+)",
        ]
        for pat in explicit_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                extracted_facts.append((m.group(1).strip(" .!"), "user_preference", 1.5))

        # B. Stated preferences: "I prefer ...", "I like ...", "always ...", "never ..."
        pref_patterns = [
            r"i\s+prefer\s+([^,\.!\n]+)",
            r"always\s+(?:format|show|give|provide|use)\s+([^,\.!\n]+)",
            r"my\s+preferred\s+(?:currency|format|tone|timezone|channel|model)\s+is\s+([^,\.!\n]+)",
        ]
        for pat in pref_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                extracted_facts.append((f"Preference: {m.group(0).strip(' .!')}", "user_preference", 1.2))

        # C. Business Metrics & Account Situation: e.g. "Abc revenue will go down by 12%"
        metric_pat = r"([A-Za-z0-9_\-\s]{2,25}?)\s+(?:revenue|churn|growth|arr|mrr|sales|budget|forecast|metrics|contract|deal)\s+(?:will\s+go|is|dropped|declined|increased|decreased|down|up|fall|falling)\s+(?:by\s+)?([0-9]+(?:\.[0-9]+)?%?|\$[0-9]+[kKmMbB]?|[A-Za-z0-9_\-]+)"
        m_metric = re.search(metric_pat, text, re.IGNORECASE)
        if m_metric:
            metric_snippet = m_metric.group(0).strip()
            # Clean up leading noise
            metric_clean = re.sub(r"^(?:so|and|but|that|because)\s+", "", metric_snippet, flags=re.IGNORECASE)
            extracted_facts.append((f"Business Context: {metric_clean}", "business_metric", 1.4))

        # D. Problem Ownership & Responsibilities: e.g. "so i need to fix it", "i need to handle X"
        resp_pat = r"i\s+need\s+to\s+(?:fix|resolve|handle|work\s+on|manage|address|improve|deliver|lead)\s+([^,\.!\n]+)"
        m_resp = re.search(resp_pat, text, re.IGNORECASE)
        if m_resp:
            task_target = m_resp.group(1).strip()
            # If target is a pronoun like "it" and we have a detected metric/entity, enrich it
            if task_target.lower() in ("it", "this", "that", "them") and m_metric:
                entity_name = m_metric.group(1).strip()
                extracted_facts.append((f"Responsibility: User is tasked with fixing {entity_name} revenue/situation", "user_context", 1.3))
            elif task_target.lower() not in ("it", "this", "that", "them"):
                # Filter out venting if target has noise words
                if not any(w in task_target.lower() for w in ["useless", "money", "leave", "quit", "angry"]):
                    extracted_facts.append((f"Responsibility: User needs to address {task_target}", "user_context", 1.2))

        # E. Work context & project assignments: "I am working on ...", "I am responsible for ...", "I manage ..."
        work_patterns = [
            r"i(?:'m|\s+am)\s+working\s+on\s+([^,\.!\n]+)",
            r"i(?:'m|\s+am)\s+leading\s+([^,\.!\n]+)",
            r"i\s+manage\s+(?:account|client|customer|project)\s+([^,\.!\n]+)",
            r"my\s+primary\s+(?:focus|project|goal|account)\s+is\s+([^,\.!\n]+)",
            r"my\s+team\s+is\s+([^,\.!\n]+)",
        ]
        for pat in work_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(0).strip(" .!")
                # Filter out venting
                if not any(w in val.lower() for w in ["useless", "money", "leave", "quit", "bad"]):
                    extracted_facts.append((f"Context: {val}", "user_context", 1.2))

        # F. Identity / personal info: "My name is ...", "I work in ..."
        identity_patterns = [
            r"my\s+name\s+is\s+([A-Z][a-zA-Z\s]+)",
            r"i\s+work\s+(?:as|in|at)\s+([^,\.!\n]+)",
        ]
        for pat in identity_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                extracted_facts.append((f"Profile: {m.group(0).strip(' .!')}", "user_profile", 1.0))

        # Persist heuristic extracted facts
        for fact_text, mem_type, imp in extracted_facts:
            if len(fact_text) > 4 and len(fact_text) < 300:
                MemoryStore.add_user_memory(
                    db=db,
                    user_id=user_id,
                    content=fact_text,
                    memory_type=mem_type,
                    conversation_id=conversation_id,
                    importance_score=imp
                )

    def save_turn(
        self,
        db: Session,
        conversation_id: Optional[str],
        agent_id: str,
        user_query: str,
        assistant_response: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Save a completed conversational exchange and extract long-term user memories."""
        if not conversation_id:
            return

        auto_title = user_query.strip().split("\n")[0]
        if len(auto_title) > 48:
            auto_title = auto_title[:45] + "..."

        MemoryStore.get_or_create_conversation(
            db=db,
            conversation_id=conversation_id,
            agent_id=agent_id,
            title=auto_title,
            session_id=session_id,
            user_id=user_id
        )
        MemoryStore.add_message(db, conversation_id, "user", user_query)
        MemoryStore.add_message(db, conversation_id, "assistant", assistant_response)

        # Extract and persist user facts
        if user_id:
            self.extract_and_save_user_facts(
                db=db,
                user_query=user_query,
                assistant_response=assistant_response,
                conversation_id=conversation_id,
                user_id=user_id
            )

memory_manager = MemoryManager()
