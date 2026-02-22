"""Festival/events check: curated data + LLM-generated local events fallback."""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

from app.config import get_settings
from app.data.india_festivals import get_festivals_for_dates
from app.models.events import Event

logger = logging.getLogger(__name__)


def _llm_local_events(dest: str, start_str: str, end_str: str) -> list[dict]:
    """Use GPT-4o-mini to generate local events, festivals, and cultural happenings."""
    settings = get_settings()
    if not settings.has_openai:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": (
                f"What festivals, local events, cultural happenings, or significant occasions "
                f"are likely in or near {dest}, India between {start_str} and {end_str}?\n\n"
                f"Consider: regional festivals, temple events, local fairs/melas, seasonal celebrations, "
                f"food festivals, national holidays observed locally, and any cultural events.\n\n"
                f"Return ONLY a JSON array:\n"
                f'[{{"name": "<event name>", '
                f'"description": "<2-3 sentence description>", '
                f'"event_type": "<festival/holiday/fair/cultural/religious/seasonal>", '
                f'"start_date": "<YYYY-MM-DD>", '
                f'"end_date": "<YYYY-MM-DD>", '
                f'"location": "<specific location or area in {dest}>", '
                f'"impact": "<positive/negative/neutral>", '
                f'"impact_details": "<how this affects travelers: crowds, closures, unique experiences, etc.>", '
                f'"recommendation": "<practical advice for travelers>"}}]\n\n'
                f"If there are no notable events, return an array with 1-2 general cultural observations "
                f"about visiting {dest} during this period. Be realistic and specific to {dest}."
            )}],
            temperature=0.5,
        )
        content = (resp.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM festival/events generation failed for %s: %s", dest, e)
        return []


def check_festivals_node(state: dict[str, Any]) -> dict[str, Any]:
    """Get festivals for trip dates; return events."""
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
    tokens_used = 0

    # ── Curated festival data ──────────────────────────────────────────────
    fests = get_festivals_for_dates(dest, sd, ed)
    for f in fests:
        events.append(Event(
            name=f["name"],
            description=f.get("description"),
            start_date=sd,
            end_date=ed,
            location=f.get("locations", ["All India"])[0],
            event_type="festival",
            impact="positive" if f.get("impact") == "positive" else "neutral",
            recommendation=f.get("recommendation"),
            source="curated",
            verified=True,
        ).model_dump())

    if events:
        reasoning_parts.append(f"Found {len(events)} curated festivals for {dest}.")

    # ── LLM fallback for local events ──────────────────────────────────────
    if not events:
        llm_events = _llm_local_events(dest, start_str, end_str)
        if llm_events:
            for ev in llm_events:
                # Parse dates from LLM, fall back to trip dates
                try:
                    ev_sd = date.fromisoformat(str(ev.get("start_date", start_str))[:10])
                except (ValueError, TypeError):
                    ev_sd = sd
                try:
                    ev_ed = date.fromisoformat(str(ev.get("end_date", end_str))[:10])
                except (ValueError, TypeError):
                    ev_ed = ed

                # Validate impact value
                impact_raw = str(ev.get("impact", "neutral")).lower().strip()
                if impact_raw not in ("positive", "negative", "neutral"):
                    impact_raw = "neutral"

                # Build recommendation with impact details if available
                recommendation = ev.get("recommendation", "")
                impact_details = ev.get("impact_details", "")
                if impact_details and recommendation:
                    recommendation = f"{recommendation} ({impact_details})"
                elif impact_details:
                    recommendation = impact_details

                events.append(Event(
                    name=ev.get("name", "Local Event"),
                    description=ev.get("description"),
                    start_date=ev_sd,
                    end_date=ev_ed,
                    location=ev.get("location", dest),
                    event_type=ev.get("event_type", "cultural"),
                    impact=impact_raw,
                    recommendation=recommendation or None,
                    source="llm",
                    verified=False,
                ).model_dump())

            reasoning_parts.append(
                f"GPT-4o-mini generated {len(llm_events)} local events/festivals for {dest} "
                f"({start_str} to {end_str})."
            )
            tokens_used = 200  # approximate
        else:
            reasoning_parts.append(f"No festivals or events found for {dest} in this period.")

    latency_ms = int((time.time() - start) * 1000)
    decision = {
        "agent_name": "festival_check",
        "action": "check",
        "reasoning": " ".join(reasoning_parts) or f"Checked events for {dest}.",
        "result_summary": f"{len(events)} events",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {"events": events, "agent_decisions": [decision]}
