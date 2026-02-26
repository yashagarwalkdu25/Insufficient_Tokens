"""
Vibe scorer agent: LLM-powered match scoring between itinerary and user preferences.

Uses GPT-4o-mini to analyze how well the trip matches user interests and style,
generating a 0-100 score with category breakdowns and a catchy tagline.
Requires OpenAI API key.
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
            max_tokens=600,
            timeout=20,
        )
        content = (r.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM vibe scoring failed: %s", e)
        return None


def score_vibe_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: score how well the trip matches preferences using LLM."""
    start_t = time.time()
    trip = state.get("trip") or {}
    req = state.get("trip_request") or {}
    reasoning_parts: list[str] = []
    tokens_used = 0

    llm_result = _llm_score(req, trip)
    if llm_result:
        reasoning_parts.append(f"LLM vibe score: {llm_result.get('overall_score', '?')}/100. Tagline: \"{llm_result.get('tagline', '')}\"")
        score_data = llm_result
    else:
        reasoning_parts.append("LLM vibe scoring unavailable. OpenAI API key may be missing.")
        score_data = {
            "overall_score": 0,
            "breakdown": {},
            "tagline": "Score unavailable — configure OpenAI API key",
            "perfect_matches": [],
            "considerations": ["Vibe scoring requires an OpenAI API key"],
        }

    vs = VibeScore(
        overall_score=max(0, min(100, score_data.get("overall_score", 0))),
        breakdown=score_data.get("breakdown", {}),
        tagline=score_data.get("tagline", "Score unavailable"),
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
