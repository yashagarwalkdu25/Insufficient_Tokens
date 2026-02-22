"""
SQLite database setup and helpers for TripSaathi.
Tables: users, user_profiles, trip_sessions, conversation_history, agent_decisions, api_cache.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from app.config import get_settings


def _get_db_path() -> str:
    path = get_settings().DB_PATH
    if not Path(path).is_absolute():
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, path)
    return path


def get_db() -> sqlite3.Connection:
    """Return a connection with row_factory for dict-like rows."""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they do not exist."""
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                session_id TEXT UNIQUE NOT NULL,
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT NOT NULL PRIMARY KEY,
                preferred_style TEXT,
                budget_range_min REAL,
                budget_range_max REAL,
                home_city TEXT,
                interests TEXT,
                past_destinations TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS trip_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                state_json TEXT,
                status TEXT,
                current_stage TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                compressed_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES trip_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS agent_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                action TEXT,
                reasoning TEXT,
                result_summary TEXT,
                tokens_used INTEGER,
                latency_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES trip_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shared_trips (
                trip_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_or_create_user(session_id: str) -> dict[str, Any]:
    """
    Get existing user by session_id or create one. Returns user as dict with column names as keys.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, session_id, display_name, created_at, last_active FROM users WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row:
            conn.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
            conn.commit()
            return dict(row)

        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, session_id, display_name, created_at, last_active) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (user_id, session_id, None),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, session_id, display_name, created_at, last_active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def generate_short_id() -> str:
    """Generate 8-char alphanumeric ID for shared trips."""
    import random
    import string
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def save_shared_trip(trip_id: str, state: dict) -> str:
    """Save state to shared_trips; returns trip_id. Overwrites if exists."""
    import json
    conn = get_db()
    try:
        state_json = json.dumps(state, default=str)
        conn.execute(
            "INSERT OR REPLACE INTO shared_trips (trip_id, state_json, created_at, expires_at) VALUES (?, ?, CURRENT_TIMESTAMP, NULL)",
            (trip_id, state_json),
        )
        conn.commit()
        return trip_id
    finally:
        conn.close()


def load_shared_trip(trip_id: str) -> dict | None:
    """Load shared trip state by trip_id; None if not found or expired."""
    import json
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT state_json, expires_at FROM shared_trips WHERE trip_id = ?",
            (trip_id,),
        ).fetchone()
        if not row:
            return None
        state_json, expires_at = row["state_json"], row["expires_at"]
        if expires_at:
            from datetime import datetime
            if datetime.fromisoformat(expires_at) < datetime.utcnow():
                return None
        return json.loads(state_json)
    except Exception:
        return None
    finally:
        conn.close()
