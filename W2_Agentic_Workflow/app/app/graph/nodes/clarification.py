"""Clarification agent: detect missing trip info and ask a friendly follow-up question."""
from __future__ import annotations

import logging
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

REQUIRED_FIELDS: dict[str, str] = {
    "destination": "where you'd like to go",
    "start_date": "your travel dates",
    "end_date": "when you plan to return",
    "budget": "your approximate budget",
    "traveler_type": "who's traveling (solo, couple, family, group)",
    "interests": "what kind of experiences you enjoy",
}


def _detect_missing(trip_request: dict) -> list[str]:
    """Return human-readable descriptions of fields still missing from the request."""
    missing: list[str] = []
    for field, label in REQUIRED_FIELDS.items():
        val = trip_request.get(field)
        if val is None or val == "" or val == []:
            missing.append(label)
    return missing


def _llm_question(missing: list[str], trip_request: dict) -> tuple[str, int]:
    """Generate a warm follow-up question via GPT-4o-mini. Returns (question, tokens_used)."""
    settings = get_settings()
    if not settings.has_openai:
        raise RuntimeError("OpenAI unavailable")

    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    known_parts = []
    if trip_request.get("destination"):
        known_parts.append(f"destination: {trip_request['destination']}")
    if trip_request.get("origin"):
        known_parts.append(f"origin: {trip_request['origin']}")
    if trip_request.get("budget"):
        known_parts.append(f"budget: ₹{trip_request['budget']}")
    if trip_request.get("traveler_type"):
        known_parts.append(f"traveler type: {trip_request['traveler_type']}")
    if trip_request.get("interests"):
        known_parts.append(f"interests: {', '.join(trip_request['interests'])}")

    known_str = "; ".join(known_parts) if known_parts else "nothing yet"
    missing_str = ", ".join(missing)

    r = client.chat.completions.create(
        model=settings.GPT4O_MINI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are TripSaathi, a warm and friendly Indian travel assistant. "
                    "The user started planning a trip but some information is missing. "
                    "Ask a short, conversational follow-up question to gather the missing info. "
                    "Be specific about what you need but keep it casual (1-3 sentences). "
                    "Do NOT list bullet points; weave the questions naturally."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"What I know so far: {known_str}\n"
                    f"Still need: {missing_str}\n"
                    "Write a friendly follow-up question."
                ),
            },
        ],
        temperature=0.7,
    )
    text = (r.choices[0].message.content or "").strip()
    tokens = getattr(r.usage, "total_tokens", 0) if hasattr(r, "usage") else 0
    return text, tokens


def _template_question(missing: list[str]) -> str:
    """Deterministic fallback when OpenAI is not available."""
    if len(missing) == 1:
        return f"I'd love to help plan your trip! Could you tell me {missing[0]}?"
    joined = ", ".join(missing[:-1]) + f" and {missing[-1]}"
    return f"I'd love to help plan your trip! Could you share {joined}? That'll help me craft the perfect itinerary for you."


def clarification_node(state: dict[str, Any]) -> dict[str, Any]:
    """Detect missing trip details and ask the user a friendly follow-up question."""
    start_t = time.time()
    trip_request = state.get("trip_request") or {}
    reasoning_parts: list[str] = []
    tokens_used = 0

    missing = _detect_missing(trip_request)
    reasoning_parts.append(
        f"Missing fields: {', '.join(missing)}" if missing else "All required fields present."
    )

    if not missing:
        latency_ms = int((time.time() - start_t) * 1000)
        return {
            "current_stage": "clarification_done",
            "agent_decisions": [{
                "agent_name": "clarification",
                "action": "check_completeness",
                "reasoning": "All required information is present — no clarification needed.",
                "result_summary": "Complete",
                "tokens_used": 0,
                "latency_ms": latency_ms,
            }],
        }

    question = ""
    try:
        question, tokens_used = _llm_question(missing, trip_request)
        reasoning_parts.append("Generated follow-up question via LLM.")
    except Exception as exc:
        logger.warning("LLM clarification question failed: %s", exc)
        reasoning_parts.append(f"LLM unavailable ({exc}); using template fallback.")

    if not question:
        question = _template_question(missing)
        reasoning_parts.append("Used template-based question.")

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "clarification",
        "action": "ask_missing_info",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"Asked about {len(missing)} missing field(s)",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }

    return {
        "requires_approval": True,
        "approval_type": "clarification",
        "current_stage": "clarification",
        "conversation_response": question,
        "agent_decisions": [decision],
    }
