"""
User profile: get/update preferences, learn from trip, summary for agents.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.database import get_db

logger = logging.getLogger(__name__)


class UserProfileManager:
    """Read/write user_profiles; learn_from_trip; get_preferences_summary."""

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        """Get user_profiles row as dict."""
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT user_id, preferred_style, budget_range_min, budget_range_max, home_city, interests, past_destinations, updated_at FROM user_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("interests"):
                try:
                    d["interests"] = json.loads(d["interests"])
                except Exception:
                    d["interests"] = []
            if d.get("past_destinations"):
                try:
                    d["past_destinations"] = json.loads(d["past_destinations"])
                except Exception:
                    d["past_destinations"] = []
            return d
        finally:
            conn.close()

    def update_profile(self, user_id: str, **kwargs: Any) -> None:
        """Update specific fields in user_profiles."""
        allowed = {"preferred_style", "budget_range_min", "budget_range_max", "home_city", "interests", "past_destinations"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_parts = []
        values = []
        for k, v in updates.items():
            if k in ("interests", "past_destinations") and isinstance(v, (list, dict)):
                v = json.dumps(v)
            set_parts.append(f"{k} = ?")
            values.append(v)
        values.append(user_id)
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO user_profiles (user_id, updated_at) VALUES (?, CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO NOTHING",
                (user_id,),
            )
            conn.execute(
                f"UPDATE user_profiles SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                values,
            )
            conn.commit()
        finally:
            conn.close()

    def learn_from_trip(
        self,
        user_id: str,
        trip_request: Any,
        trip: Any,
    ) -> None:
        """Update preferred_style, past_destinations, budget_range, interests from completed trip."""
        style = getattr(trip_request, "travel_style", None) or (trip_request.get("travel_style") if isinstance(trip_request, dict) else None)
        dest = getattr(trip_request, "destination", None) or (trip_request.get("destination") if isinstance(trip_request, dict) else None)
        budget = getattr(trip_request, "budget", None) or (trip_request.get("budget") if isinstance(trip_request, dict) else None)
        interests = getattr(trip_request, "interests", None) or (trip_request.get("interests") if isinstance(trip_request, dict) else [])
        total = getattr(trip, "total_cost", None) or (trip.get("total_cost") if isinstance(trip, dict) else None)
        profile = self.get_profile(user_id) or {}
        past = list(profile.get("past_destinations") or [])
        if dest and dest not in past:
            past.append(dest)
        self.update_profile(
            user_id,
            preferred_style=style or profile.get("preferred_style"),
            past_destinations=past,
            budget_range_min=profile.get("budget_range_min") or (budget * 0.8 if budget else None),
            budget_range_max=profile.get("budget_range_max") or (total or budget),
            interests=interests or profile.get("interests"),
        )

    def get_preferences_summary(self, user_id: str) -> str:
        """Human-readable summary for agents."""
        p = self.get_profile(user_id)
        if not p:
            return "No prior preferences."
        parts = []
        if p.get("preferred_style"):
            parts.append(f"prefers {p['preferred_style']} travel")
        if p.get("budget_range_min") or p.get("budget_range_max"):
            parts.append(f"typically budgets ₹{p.get('budget_range_min', '?')}-₹{p.get('budget_range_max', '?')}")
        if p.get("past_destinations"):
            parts.append(f"has visited {', '.join(p['past_destinations'][:5])}")
        if p.get("interests"):
            parts.append(f"interested in {', '.join(p['interests'][:8])}")
        return "User " + "; ".join(parts) if parts else "No prior preferences."
