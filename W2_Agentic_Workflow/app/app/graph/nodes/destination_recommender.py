"""Destination recommender: LLM-powered suggestions when user has no destination."""
import json
import logging
import random
import time
from datetime import date
from typing import Any

from app.config import get_settings
from app.data.india_cities import get_cities_for_interests, INDIA_CITIES

logger = logging.getLogger(__name__)


def _llm_recommend(req: dict[str, Any]) -> list[dict[str, Any]]:
    """Use GPT to recommend 3 destinations based on user preferences."""
    settings = get_settings()
    if not settings.has_openai:
        raise RuntimeError("OpenAI unavailable")

    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    interests = req.get("interests") or []
    style = req.get("travel_style") or "balanced"
    budget = req.get("budget", 15000)
    traveler_type = req.get("traveler_type", "solo")
    start_date = req.get("start_date", "")
    origin = req.get("origin", "")

    month = ""
    if start_date:
        try:
            month = date.fromisoformat(str(start_date)[:10]).strftime("%B")
        except (ValueError, TypeError):
            pass

    city_names = list(INDIA_CITIES.keys())

    r = client.chat.completions.create(
        model=settings.GPT4O_MINI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are TripSaathi, an expert Indian travel advisor. "
                    "Recommend exactly 3 Indian destinations from this list: "
                    f"{', '.join(city_names)}. "
                    "Pick the BEST matches considering the user's interests, budget, "
                    "travel style, season, and traveler type. Prioritize variety — "
                    "don't pick cities in the same state unless they're clearly the best fit.\n\n"
                    "Return ONLY a JSON array of 3 objects with keys: "
                    '"city" (exact name from list), "reason" (1 short sentence why this city fits).'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Interests: {', '.join(interests) if interests else 'open to anything'}\n"
                    f"Travel style: {style}\n"
                    f"Budget: ₹{budget:,.0f}\n"
                    f"Traveler type: {traveler_type}\n"
                    f"Origin: {origin or 'not specified'}\n"
                    f"Month of travel: {month or 'not specified'}\n"
                    "Suggest 3 destinations."
                ),
            },
        ],
        temperature=0.9,
    )

    content = (r.choices[0].message.content or "").strip()
    if "```" in content:
        content = content.split("```")[1].replace("json", "").strip()

    picks = json.loads(content)
    if not isinstance(picks, list) or len(picks) == 0:
        raise ValueError("LLM returned invalid format")

    options = []
    for p in picks[:3]:
        city_name = p.get("city", "").strip()
        city_data = INDIA_CITIES.get(city_name)
        if not city_data:
            for k, v in INDIA_CITIES.items():
                if k.lower() == city_name.lower():
                    city_data = v
                    city_name = k
                    break
        if not city_data:
            continue

        budget_label = (city_data.get("budget_range") or {}).get(
            style if style in ("backpacker", "midrange", "luxury") else "midrange", ""
        )
        options.append({
            "city": city_name,
            "state": city_data.get("state", ""),
            "why": p.get("reason", f"Great for {', '.join(city_data.get('known_for', [])[:3])}"),
            "budget": budget_label,
        })

    if not options:
        raise ValueError("No valid cities matched from LLM response")

    return options


def _fallback_recommend(req: dict[str, Any]) -> list[dict[str, Any]]:
    """Randomized fallback when LLM is unavailable."""
    interests = req.get("interests") or []
    style = req.get("travel_style") or "balanced"
    start_date = req.get("start_date", "")

    candidates = get_cities_for_interests(interests) if interests else list(INDIA_CITIES.values())
    if not candidates:
        candidates = list(INDIA_CITIES.values())

    travel_month = None
    if start_date:
        try:
            travel_month = date.fromisoformat(str(start_date)[:10]).month
        except (ValueError, TypeError):
            pass

    if travel_month:
        in_season = [c for c in candidates if travel_month in (c.get("best_season") or [])]
        not_avoided = [c for c in candidates if travel_month not in (c.get("avoid_season") or [])]
        candidates = in_season or not_avoided or candidates

    random.shuffle(candidates)

    seen_states: set[str] = set()
    diverse: list[dict] = []
    for c in candidates:
        st = c.get("state", "")
        if st not in seen_states:
            diverse.append(c)
            seen_states.add(st)
        if len(diverse) >= 3:
            break
    if len(diverse) < 3:
        for c in candidates:
            if c not in diverse:
                diverse.append(c)
            if len(diverse) >= 3:
                break

    budget_key = style if style in ("backpacker", "midrange", "luxury") else "midrange"
    options = []
    for c in diverse[:3]:
        options.append({
            "city": c.get("name"),
            "state": c.get("state"),
            "why": f"Great for {', '.join(c.get('known_for', [])[:3])}",
            "budget": (c.get("budget_range") or {}).get(budget_key, ""),
        })
    return options


def recommend_destinations_node(state: dict[str, Any]) -> dict[str, Any]:
    """Suggest 3 destinations; set requires_approval and destination_options."""
    start_t = time.time()
    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    if dest:
        return {
            "destination_options": [],
            "requires_approval": False,
            "current_stage": "intent_parsed",
            "agent_decisions": [],
        }

    options: list[dict[str, Any]] = []
    reasoning = "No destination specified by user."
    tokens_used = 0

    try:
        options = _llm_recommend(req)
        reasoning += " LLM recommended destinations based on preferences."
    except Exception as exc:
        logger.warning("LLM destination recommendation failed: %s", exc)
        reasoning += f" LLM unavailable ({exc}); using smart fallback."
        options = _fallback_recommend(req)

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "destination_recommender",
        "action": "recommend",
        "reasoning": reasoning,
        "result_summary": f"{len(options)} options: {', '.join(o.get('city', '') for o in options)}",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {
        "destination_options": options,
        "requires_approval": True,
        "approval_type": "destination",
        "current_stage": "destinations_recommended",
        "agent_decisions": [decision],
    }
