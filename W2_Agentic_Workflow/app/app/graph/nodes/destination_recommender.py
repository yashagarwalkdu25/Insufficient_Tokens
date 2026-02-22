"""Destination recommender when user has no destination."""
import time
from typing import Any

from app.data.india_cities import get_cities_for_interests, INDIA_CITIES


def recommend_destinations_node(state: dict[str, Any]) -> dict[str, Any]:
    """Suggest 3 destinations; set requires_approval and destination_options."""
    start = time.time()
    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    if dest:
        return {"destination_options": [], "requires_approval": False, "current_stage": "intent_parsed", "agent_decisions": []}

    interests = req.get("interests") or []
    style = req.get("travel_style") or "balanced"
    cities = get_cities_for_interests(interests) if interests else list(INDIA_CITIES.values())
    options = []
    for c in (cities or list(INDIA_CITIES.values()))[:3]:
        options.append({
            "city": c.get("name"),
            "state": c.get("state"),
            "why": f"Matches your interests: {', '.join(c.get('known_for', [])[:3])}",
            "budget": (c.get("budget_range") or {}).get(style, ""),
        })

    latency_ms = int((time.time() - start) * 1000)
    decision = {"agent_name": "destination_recommender", "action": "recommend", "reasoning": "No destination", "result_summary": f"{len(options)} options", "tokens_used": 0, "latency_ms": latency_ms}
    return {
        "destination_options": options,
        "requires_approval": True,
        "approval_type": "destination",
        "current_stage": "destinations_recommended",
        "agent_decisions": [decision],
    }
