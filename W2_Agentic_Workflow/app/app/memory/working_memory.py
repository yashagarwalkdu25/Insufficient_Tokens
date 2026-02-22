"""
Working memory: persist and load trip_sessions state (JSON).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.database import get_db

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> str:
    def default(o: Any) -> Any:
        if hasattr(o, "model_dump"):
            return o.model_dump()
        if hasattr(o, "isoformat"):
            return o.isoformat()
        raise TypeError(type(o))

    return json.dumps(obj, default=default)


def _deserialize(s: str) -> Any:
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Corrupted state JSON: %s", e)
        return None


class WorkingMemoryManager:
    """Save/load session state to trip_sessions table."""

    def save_state(self, session_id: str, state_dict: dict[str, Any]) -> None:
        """Serialize state to JSON and save to trip_sessions."""
        conn = get_db()
        try:
            state_json = _serialize(state_dict)
            conn.execute(
                """INSERT INTO trip_sessions (id, user_id, state_json, status, current_stage, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(id) DO UPDATE SET state_json = ?, current_stage = ?, updated_at = CURRENT_TIMESTAMP""",
                (
                    session_id,
                    state_dict.get("user_id", ""),
                    state_json,
                    state_dict.get("status", "active"),
                    state_dict.get("current_stage", ""),
                    state_json,
                    state_dict.get("current_stage", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def load_state(self, session_id: str) -> Optional[dict[str, Any]]:
        """Load state from trip_sessions; deserialize. None if not found or corrupted."""
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT state_json FROM trip_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            return _deserialize(row["state_json"])
        finally:
            conn.close()

    def update_stage(self, session_id: str, stage: str) -> None:
        """Update current_stage for session."""
        conn = get_db()
        try:
            conn.execute(
                "UPDATE trip_sessions SET current_stage = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (stage, session_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_active_session(self, user_id: str) -> Optional[str]:
        """Find active trip_session id for user."""
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id FROM trip_sessions WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            return row["id"] if row else None
        finally:
            conn.close()
