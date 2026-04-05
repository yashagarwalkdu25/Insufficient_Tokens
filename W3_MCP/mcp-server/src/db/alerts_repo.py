"""PostgreSQL repository for user alerts and notifications."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from .pool import get_pool

logger = structlog.get_logger(__name__)

_ENSURE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS user_alerts (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    alert_type  VARCHAR(50) NOT NULL,
    symbol      VARCHAR(50),
    condition   TEXT        NOT NULL,
    threshold   NUMERIC(15,4),
    direction   VARCHAR(10) DEFAULT 'below',
    is_active   BOOLEAN     DEFAULT TRUE,
    is_triggered BOOLEAN    DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    trigger_value NUMERIC(15,4),
    trigger_message TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_user_active ON user_alerts(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON user_alerts(alert_type, is_active);

CREATE TABLE IF NOT EXISTS notification_log (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    alert_id    INTEGER REFERENCES user_alerts(id) ON DELETE SET NULL,
    title       VARCHAR(255) NOT NULL,
    message     TEXT        NOT NULL,
    severity    VARCHAR(20) DEFAULT 'info',
    is_read     BOOLEAN     DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notif_user_unread ON notification_log(user_id, is_read, created_at DESC);
"""

_initialised = False


async def _ensure_table() -> None:
    global _initialised
    if _initialised:
        return
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(_ENSURE_TABLES_SQL)
        _initialised = True
        logger.info("alerts_repo.table_ready")
    except Exception as exc:
        logger.error("alerts_repo.init_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------

async def create_alert(
    user_id: str,
    alert_type: str,
    symbol: str | None,
    condition: str,
    threshold: float | None = None,
    direction: str = "below",
) -> int | None:
    """Create a new alert rule. Returns the alert id."""
    await _ensure_table()
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO user_alerts (user_id, alert_type, symbol, condition, threshold, direction)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            user_id, alert_type, symbol, condition, threshold, direction,
        )
        return row["id"] if row else None
    except Exception as exc:
        logger.error("alerts_repo.create_failed", user_id=user_id, error=str(exc))
        return None


async def get_active_alerts(user_id: str) -> list[dict[str, Any]]:
    """Return all active (non-triggered) alerts for a user."""
    await _ensure_table()
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT id, alert_type, symbol, condition, threshold, direction,
                   is_triggered, triggered_at, trigger_value, trigger_message, created_at
            FROM user_alerts
            WHERE user_id = $1 AND is_active = TRUE
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("alerts_repo.get_active_failed", user_id=user_id, error=str(exc))
        return []


async def trigger_alert(
    alert_id: int,
    trigger_value: float | None,
    trigger_message: str,
) -> None:
    """Mark an alert as triggered."""
    await _ensure_table()
    try:
        pool = await get_pool()
        await pool.execute(
            """
            UPDATE user_alerts
            SET is_triggered = TRUE, triggered_at = $2, trigger_value = $3, trigger_message = $4
            WHERE id = $1
            """,
            alert_id, datetime.now(timezone.utc), trigger_value, trigger_message,
        )
    except Exception as exc:
        logger.error("alerts_repo.trigger_failed", alert_id=alert_id, error=str(exc))


async def delete_alert(user_id: str, alert_id: int) -> bool:
    """Soft-delete (deactivate) an alert."""
    await _ensure_table()
    try:
        pool = await get_pool()
        result = await pool.execute(
            "UPDATE user_alerts SET is_active = FALSE WHERE id = $1 AND user_id = $2",
            alert_id, user_id,
        )
        return "UPDATE 1" in result
    except Exception as exc:
        logger.error("alerts_repo.delete_failed", alert_id=alert_id, error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Notification CRUD
# ---------------------------------------------------------------------------

async def create_notification(
    user_id: str,
    title: str,
    message: str,
    severity: str = "info",
    alert_id: int | None = None,
) -> int | None:
    """Insert a notification for a user. Returns notification id."""
    await _ensure_table()
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO notification_log (user_id, alert_id, title, message, severity)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            user_id, alert_id, title, message, severity,
        )
        return row["id"] if row else None
    except Exception as exc:
        logger.error("alerts_repo.notif_create_failed", user_id=user_id, error=str(exc))
        return None


async def get_notifications(
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent notifications for a user."""
    await _ensure_table()
    try:
        pool = await get_pool()
        if unread_only:
            rows = await pool.fetch(
                """
                SELECT id, alert_id, title, message, severity, is_read, created_at
                FROM notification_log
                WHERE user_id = $1 AND is_read = FALSE
                ORDER BY created_at DESC LIMIT $2
                """,
                user_id, limit,
            )
        else:
            rows = await pool.fetch(
                """
                SELECT id, alert_id, title, message, severity, is_read, created_at
                FROM notification_log
                WHERE user_id = $1
                ORDER BY created_at DESC LIMIT $2
                """,
                user_id, limit,
            )
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("alerts_repo.notif_get_failed", user_id=user_id, error=str(exc))
        return []


async def mark_notifications_read(user_id: str, notification_ids: list[int] | None = None) -> int:
    """Mark notifications as read. If ids is None, mark all as read."""
    await _ensure_table()
    try:
        pool = await get_pool()
        if notification_ids:
            result = await pool.execute(
                "UPDATE notification_log SET is_read = TRUE WHERE user_id = $1 AND id = ANY($2::int[])",
                user_id, notification_ids,
            )
        else:
            result = await pool.execute(
                "UPDATE notification_log SET is_read = TRUE WHERE user_id = $1 AND is_read = FALSE",
                user_id,
            )
        count = int(result.split(" ")[-1]) if result else 0
        return count
    except Exception as exc:
        logger.error("alerts_repo.mark_read_failed", user_id=user_id, error=str(exc))
        return 0


async def get_unread_count(user_id: str) -> int:
    """Return count of unread notifications."""
    await _ensure_table()
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT COUNT(*) as cnt FROM notification_log WHERE user_id = $1 AND is_read = FALSE",
            user_id,
        )
        return row["cnt"] if row else 0
    except Exception as exc:
        logger.error("alerts_repo.unread_count_failed", user_id=user_id, error=str(exc))
        return 0
