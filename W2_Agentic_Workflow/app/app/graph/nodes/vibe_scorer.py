"""
Vibe scorer agent: LLM-powered match scoring between itinerary and user preferences.

Uses GPT-4o-mini to analyze how well the trip matches user interests and style,
generating a 0-100 score with category breakdowns and a catchy tagline.
Falls back to heuristic scoring when no API key.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.config import get_settings
from app.models.events import VibeScore

logger = logging.getLogger(__name__)


def _llm_score(req: dict, trip: dict) -> dict | None:
    """Use GPT-4o-mini to score the trip match."""
    settings = get_settings()
    if not settings.has_openai:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        interests = req.get("interests", [])
        style = req.get("travel_style", "balanced")
        dest = req.get("destination", "?")
        days = trip.get("days", [])
        total_cost = trip.get("total_cost", 0)
        budget = req.get("budget", 15000)

        # Extract activity names from itinerary
        activities = []
        for day in days:
            for item in day.get("items", []):
                if item.get("item_type") == "activity":
                    activities.append(item.get("title", ""))

        prompt = f"""Score how well this trip matches the traveler's preferences. Return JSON only.

TRAVELER: interests={interests}, style={style}, budget=₹{budget}
TRIP: {dest}, {len(days)} days, total ₹{total_cost}
ACTIVITIES: {', '.join(activities[:10])}

Return:
{{
  "overall_score": 0-100,
  "breakdown": {{"adventure": 0-100, "culture": 0-100, "value": 0-100, "comfort": 0-100, "authenticity": 0-100}},
  "tagline": "8 words max, catchy trip summary",
  "perfect_matches": ["what matches well (2-4 items)"],
  "considerations": ["what could be improved (0-2 items)"]
}}

Score higher if activities match interests. Score value based on budget utilization. Be honest but optimistic."""

        r = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = (r.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM vibe scoring failed: %s", e)
        return None


def _heuristic_score(req: dict, trip: dict) -> dict:
    """Heuristic scoring based on keyword matching."""
    interests = set(i.lower() for i in (req.get("interests") or []))
    style = (req.get("travel_style") or "balanced").lower()
    budget = float(req.get("budget") or 15000)
    total_cost = float(trip.get("total_cost") or 0)
    days = trip.get("days", [])

    # Count activity category matches
    activity_cats = set()
    activity_names = []
    for day in days:
        for item in day.get("items", []):
            if item.get("item_type") == "activity":
                activity_cats.add((item.get("category") or "general").lower())
                activity_names.append(item.get("title", "").lower())

    # Interest match
    interest_matches = sum(1 for i in interests if any(i in n for n in activity_names))
    interest_score = min(100, int((interest_matches / max(1, len(interests))) * 100) + 20)

    # Value score
    if total_cost <= 0:
        value_score = 80
    elif total_cost <= budget:
        value_score = 90
    elif total_cost <= budget * 1.1:
        value_score = 70
    else:
        value_score = 50

    # Comfort score based on style
    comfort_score = 75
    if style == "luxury":
        comfort_score = 65  # Hard to match perfectly
    elif style == "backpacker":
        comfort_score = 85

    overall = int(interest_score * 0.4 + value_score * 0.3 + comfort_score * 0.3)
    breakdown = {
        "adventure": interest_score if "adventure" in interests else 70,
        "culture": interest_score if "culture" in interests else 75,
        "value": value_score,
        "comfort": comfort_score,
        "authenticity": 80,
    }
    perfect = ["Matches your travel style"]
    if interest_matches > 0:
        perfect.append(f"{interest_matches} activities match your interests")
    if total_cost <= budget:
        perfect.append("Within budget")
    considerations = []
    if total_cost > budget:
        considerations.append("Slightly over budget — consider swapping an activity")
    if interest_matches == 0 and interests:
        considerations.append("Could add more activities matching your interests")

    return {
        "overall_score": overall,
        "breakdown": breakdown,
        "tagline": f"Your perfect {req.get('destination', '')} adventure awaits!",
        "perfect_matches": perfect,
        "considerations": considerations,
    }


def score_vibe_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: score how well the trip matches preferences using LLM or heuristics."""
    start_t = time.time()
    trip = state.get("trip") or {}
    req = state.get("trip_request") or {}
    reasoning_parts: list[str] = []
    tokens_used = 0

    # ── Try LLM scoring ───────────────────────────────────────────────────
    llm_result = _llm_score(req, trip)
    if llm_result:
        reasoning_parts.append(f"LLM vibe score: {llm_result.get('overall_score', '?')}/100. Tagline: \"{llm_result.get('tagline', '')}\"")
        score_data = llm_result
    else:
        reasoning_parts.append("Using heuristic scoring (no LLM available).")
        score_data = _heuristic_score(req, trip)

    vs = VibeScore(
        overall_score=max(0, min(100, score_data.get("overall_score", 75))),
        breakdown=score_data.get("breakdown", {}),
        tagline=score_data.get("tagline", "A solid match for your trip style."),
        perfect_matches=score_data.get("perfect_matches", []),
        considerations=score_data.get("considerations", []),
    )

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "vibe_scorer",
        "action": "score",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"Vibe score: {vs.overall_score}/100 — \"{vs.tagline}\"",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {"vibe_score": vs.model_dump(), "current_stage": "vibe_scored", "agent_decisions": [decision]}
