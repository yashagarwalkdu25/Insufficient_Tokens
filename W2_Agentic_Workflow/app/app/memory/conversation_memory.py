"""
Conversation memory: store messages, compress old ones, provide context for agents.
Uses tiktoken for token counting.
"""
import logging
from typing import Any

from app.database import get_db

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


class ConversationMemoryManager:
    """Add messages, compress old, get context for agent."""

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Insert into conversation_history."""
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO conversation_history (session_id, role, content, compressed_summary) VALUES (?, ?, ?, NULL)",
                (session_id, role, content),
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_messages(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Last N messages as list of dicts (role, content, compressed_summary, created_at)."""
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT role, content, compressed_summary, created_at FROM conversation_history
                   WHERE session_id = ? ORDER BY id DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()

    def compress_old_messages(self, session_id: str) -> None:
        """Messages older than last 3: summarize with GPT-4o-mini, store in compressed_summary."""
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id, content FROM conversation_history WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        finally:
            conn.close()
        if len(rows) <= 3:
            return
        to_compress = rows[:-3]
        try:
            from app.config import get_settings
            settings = get_settings()
            if not settings.has_openai:
                return
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            text = "\n".join(r["content"][:500] for r in to_compress)
            r = client.chat.completions.create(
                model=settings.GPT4O_MINI_MODEL,
                messages=[{"role": "user", "content": f"Summarize this conversation in 2-3 sentences:\n{text}"}],
            )
            summary = (r.choices[0].message.content or "").strip()
            if not summary:
                return
            conn = get_db()
            try:
                conn.execute(
                    "UPDATE conversation_history SET compressed_summary = ? WHERE id = ?",
                    (summary, to_compress[0]["id"]),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.warning("Compress messages failed: %s", e)

    def get_context_for_agent(self, session_id: str, max_tokens: int = 500) -> str:
        """Last 3 messages full text + compressed summary of older."""
        messages = self.get_recent_messages(session_id, limit=20)
        if not messages:
            return ""
        # Last 3 full
        recent = messages[-3:]
        parts = []
        for m in recent:
            parts.append(f"{m['role']}: {m['content']}")
        summary = None
        if len(messages) > 3:
            for m in messages[:-3]:
                if m.get("compressed_summary"):
                    summary = m["compressed_summary"]
                    break
        if summary:
            parts.insert(0, f"[Earlier: {summary}]")
        text = "\n".join(parts)
        if _estimate_tokens(text) > max_tokens:
            text = text[-max_tokens * 4:]
        return text
