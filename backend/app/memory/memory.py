"""Conversation episodic memory stored in MongoDB."""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.db.mongodb import get_db

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Stores and retrieves episodic memory entries for the chat agent.
    Each entry records what the agent did and the outcome so future
    interactions with the same user or topic can be guided by past results.
    """

    async def store(
        self,
        thread_id: str,
        user_id: str,
        query: str,
        response_summary: str,
        tools_used: list[str],
        kb_sources: list[str],
    ):
        doc = {
            "thread_id": thread_id,
            "user_id": user_id,
            "query": query,
            "response_summary": response_summary[:500],
            "tools_used": tools_used,
            "kb_sources": kb_sources,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await get_db().episodic_memory.insert_one(doc)
        except Exception as exc:
            logger.warning("Failed to store episodic memory: %s", exc)

    async def recall(self, user_id: str, limit: int = 5) -> list[dict]:
        """Retrieve recent memory entries for a user."""
        try:
            cursor = (
                get_db().episodic_memory
                .find({"user_id": user_id}, {"_id": 0})
                .sort("created_at", -1)
                .limit(limit)
            )
            return [doc async for doc in cursor]
        except Exception as exc:
            logger.warning("Failed to recall episodic memory: %s", exc)
            return []

    def build_context_block(self, memories: list[dict]) -> str:
        if not memories:
            return ""
        lines = ["Recent conversation context (from memory):"]
        for m in reversed(memories):
            lines.append(f"- Query: {m['query']}")
            if m.get("kb_sources"):
                lines.append(f"  Sources used: {', '.join(m['kb_sources'])}")
        return "\n".join(lines)


episodic_memory = ConversationMemory()
