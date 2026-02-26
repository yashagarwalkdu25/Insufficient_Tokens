"""Festival/events check: Tavily web search for real-time event data. No hardcoded data."""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

from app.config import get_settings
from app.api.tavily_client import TavilySearchClient
from app.models.events import Event

logger = logging.getLogger(__name__)


def check_festivals_node(state: dict[str, Any]) -> dict[str, Any]:
    """Get festivals/events for trip dates via Tavily web search; return events."""
    start = time.time()
    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    if not dest or not start_date or not end_date:
        return {
            "events": [],
            "agent_decisions": [{
                "agent_name": "festival_check",
                "action": "check",
                "reasoning": "Missing dates/dest",
                "result_summary": "Skipped",
                "tokens_used": 0,
                "latency_ms": 0,
            }],
        }

    sd = start_date if isinstance(start_date, date) else date.fromisoformat(str(start_date)[:10])
    ed = end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date)[:10])
    start_str = sd.isoformat()
    end_str = ed.isoformat()

    events: list[dict] = []
    reasoning_parts: list[str] = []

    # Strategy 1: Tavily web search for festivals and events
    try:
        tavily = TavilySearchClient()
        if tavily.available:
            tavily_events = tavily.search_festivals(dest, start_str, end_str)
            if tavily_events:
                for ev in tavily_events:
                    events.append(Event(
                        name=ev.get("name", "Event"),
                        description=ev.get("description"),
                        start_date=sd,
                        end_date=ed,
                        location=dest,
                        event_type="cultural",
                        impact="neutral",
                        recommendation=None,
                        source="tavily_web",
                        verified=False,
                    ).model_dump())
                reasoning_parts.append(
                    f"Tavily web search found {len(tavily_events)} events/festivals for {dest} "
                    f"({start_str} to {end_str})."
                )
    except Exception as e:
        reasoning_parts.append(f"Tavily festival search failed ({e}).")

    if not events:
        reasoning_parts.append(f"No festivals or events found for {dest} in this period.")

    latency_ms = int((time.time() - start) * 1000)
    decision = {
        "agent_name": "festival_check",
        "action": "check",
        "reasoning": " ".join(reasoning_parts) or f"Checked events for {dest}.",
        "result_summary": f"{len(events)} events",
        "tokens_used": 0,
        "latency_ms": latency_ms,
    }
    return {"events": events, "agent_decisions": [decision]}
