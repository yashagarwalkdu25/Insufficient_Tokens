"""
Budget optimizer agent: LLM-powered trade-off analysis.

Uses GPT-4o-mini to reason about budget allocation, compare flight vs ground transport,
score options by value, and select the best combination within budget.
Falls back to heuristic scoring when no API key.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.config import get_settings
from app.models.budget import BudgetTracker, BudgetCategory

logger = logging.getLogger(__name__)


def _score_option(option: dict, category: str, style: str, budget_total: float) -> float:
    """Heuristic score (0-100) for a transport/hotel/activity option."""
    price = float(option.get("total_price") or option.get("price") or option.get("price_per_night") or 0)
    rating = float(option.get("star_rating") or option.get("rating") or 3.0)

    # Price score: cheaper = higher score (relative to budget)
    budget_fraction = price / budget_total if budget_total > 0 else 1.0
    price_score = max(0, 100 - budget_fraction * 200)

    # Quality score from rating
    quality_score = (rating / 5.0) * 100

    # Style weights
    if style in ("backpacker", "budget"):
        return price_score * 0.6 + quality_score * 0.4
    elif style == "luxury":
        return price_score * 0.2 + quality_score * 0.8
    else:
        return price_score * 0.45 + quality_score * 0.55


def _llm_optimize(req: dict, flights: list, ground: list, hotels: list, activities: list, budget_total: float) -> dict | None:
    """Use GPT-4o-mini to reason about the best budget allocation and selections."""
    settings = get_settings()
    if not settings.has_openai:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Summarize options compactly
        flight_summary = []
        for i, f in enumerate(flights[:5]):
            ob = f.get("outbound") or {}
            price = f.get("total_price")
            flight_summary.append(f"F{i+1}: {ob.get('airline', '?')} {ob.get('departure_airport', '?')}→{ob.get('arrival_airport', '?')} ₹{price or '?'} url={bool(f.get('booking_url'))}")

        ground_summary = []
        for i, g in enumerate(ground[:5]):
            ground_summary.append(f"G{i+1}: {g.get('transport_type', '?')} by {g.get('operator', '?')} ₹{g.get('price', '?')} {g.get('duration_minutes', '?')}min")

        hotel_summary = []
        for i, h in enumerate(hotels[:5]):
            hotel_summary.append(f"H{i+1}: {h.get('name', '?')} ₹{h.get('price_per_night', '?')}/night ★{h.get('star_rating', '?')} url={bool(h.get('booking_url'))}")

        activity_summary = []
        for i, a in enumerate(activities[:8]):
            activity_summary.append(f"A{i+1}: {a.get('name', '?')} ₹{a.get('price', 0)} ({a.get('category', '?')})")

        prompt = f"""You are a travel budget optimizer for India. Analyze these options and select the best combination within ₹{budget_total} budget.

Trip: {req.get('destination')} from {req.get('origin')}, {req.get('start_date')} to {req.get('end_date')}, style={req.get('travel_style')}, type={req.get('traveler_type')}

FLIGHTS: {chr(10).join(flight_summary) if flight_summary else 'None found'}
GROUND TRANSPORT: {chr(10).join(ground_summary) if ground_summary else 'None'}
HOTELS: {chr(10).join(hotel_summary) if hotel_summary else 'None found'}
ACTIVITIES: {chr(10).join(activity_summary) if activity_summary else 'None found'}

Return JSON only:
{{
  "selected_flight_index": 0,
  "selected_ground_index": null,
  "prefer_ground_over_flight": false,
  "selected_hotel_index": 0,
  "selected_activity_indices": [0, 1, 2],
  "transport_budget_pct": 0.30,
  "accommodation_budget_pct": 0.35,
  "activities_budget_pct": 0.20,
  "meals_budget_pct": 0.10,
  "misc_budget_pct": 0.05,
  "reasoning": "Brief reasoning about trade-offs and why these selections are best.",
  "warnings": ["any budget warnings"]
}}

Rules:
- For backpacker/budget style: prefer ground transport over flights, cheaper stays
- For luxury: prefer flights, better hotels
- Select 2-4 activities per day
- Total must stay within ₹{budget_total}
- ONLY select from provided options (use indices)"""

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
        logger.warning("LLM budget optimization failed: %s", e)
        return None


def optimize_budget_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: LLM-powered budget optimization with heuristic fallback."""
    start_t = time.time()
    req = state.get("trip_request") or {}
    budget_total = float(req.get("budget") or 15000)
    style = (req.get("travel_style") or "balanced").lower()
    flights = state.get("flight_options") or []
    ground = state.get("ground_transport_options") or []
    hotels = state.get("hotel_options") or []
    activities = state.get("activity_options") or []

    reasoning_parts: list[str] = []
    tokens_used = 0

    # ── Try LLM optimization ──────────────────────────────────────────────
    llm_result = _llm_optimize(req, flights, ground, hotels, activities, budget_total)

    selected_flight = None
    selected_hotel = None
    selected_activities: list[dict] = []
    budget_alloc = {"transport": 0.30, "accommodation": 0.35, "activities": 0.20, "meals": 0.10, "misc": 0.05}
    warnings: list[str] = []

    if llm_result:
        reasoning_parts.append(f"LLM reasoning: {llm_result.get('reasoning', 'N/A')}")
        budget_alloc = {
            "transport": llm_result.get("transport_budget_pct", 0.30),
            "accommodation": llm_result.get("accommodation_budget_pct", 0.35),
            "activities": llm_result.get("activities_budget_pct", 0.20),
            "meals": llm_result.get("meals_budget_pct", 0.10),
            "misc": llm_result.get("misc_budget_pct", 0.05),
        }
        warnings = llm_result.get("warnings") or []

        # Select flight or ground transport based on LLM
        prefer_ground = llm_result.get("prefer_ground_over_flight", False)
        if prefer_ground and ground:
            gi = llm_result.get("selected_ground_index") or 0
            g = ground[min(gi, len(ground) - 1)]
            selected_flight = g if isinstance(g, dict) else g
            reasoning_parts.append(f"LLM chose ground transport (index {gi}) over flight for budget savings.")
        elif flights:
            fi = llm_result.get("selected_flight_index") or 0
            f = flights[min(fi, len(flights) - 1)]
            selected_flight = f if isinstance(f, dict) else (f.model_dump() if hasattr(f, "model_dump") else None)
            reasoning_parts.append(f"LLM chose flight option (index {fi}).")

        # Hotel
        if hotels:
            hi = llm_result.get("selected_hotel_index") or 0
            h = hotels[min(hi, len(hotels) - 1)]
            selected_hotel = h if isinstance(h, dict) else (h.model_dump() if hasattr(h, "model_dump") else None)
            reasoning_parts.append(f"LLM chose hotel (index {hi}): {selected_hotel.get('name', '?') if selected_hotel else '?'}.")

        # Activities
        act_indices = llm_result.get("selected_activity_indices") or list(range(min(5, len(activities))))
        for ai in act_indices:
            if 0 <= ai < len(activities):
                a = activities[ai]
                selected_activities.append(a if isinstance(a, dict) else (a.model_dump() if hasattr(a, "model_dump") else a))
    else:
        # ── Heuristic fallback ─────────────────────────────────────────────
        reasoning_parts.append("Using heuristic scoring (no LLM available).")

        # Score and sort flights
        if flights:
            scored = [(f, _score_option(f, "transport", style, budget_total)) for f in flights if isinstance(f, dict)]
            scored.sort(key=lambda x: x[1], reverse=True)
            if scored:
                selected_flight = scored[0][0]

        # Score and sort hotels
        if hotels:
            scored = [(h, _score_option(h, "hotel", style, budget_total)) for h in hotels if isinstance(h, dict)]
            scored.sort(key=lambda x: x[1], reverse=True)
            if scored:
                selected_hotel = scored[0][0]

        # Select activities within budget
        act_budget = budget_total * 0.2
        spent_act = 0
        for a in activities[:8]:
            price = (a.get("price") or 0) if isinstance(a, dict) else getattr(a, "price", 0)
            if spent_act + price <= act_budget:
                selected_activities.append(a if isinstance(a, dict) else (a.model_dump() if hasattr(a, "model_dump") else a))
                spent_act += price

    # ── Build BudgetTracker ────────────────────────────────────────────────
    transport_cost = (selected_flight.get("total_price") or selected_flight.get("price") or 500) if selected_flight else 500
    accom_cost = (selected_hotel.get("total_price") or selected_hotel.get("price_per_night", 0) * 3) if selected_hotel else 2000
    act_cost = sum((a.get("price") or 0) if isinstance(a, dict) else 0 for a in selected_activities)

    categories = [
        BudgetCategory(category="transport", allocated=budget_total * budget_alloc["transport"], spent=float(transport_cost), remaining=budget_total * budget_alloc["transport"] - float(transport_cost)),
        BudgetCategory(category="accommodation", allocated=budget_total * budget_alloc["accommodation"], spent=float(accom_cost), remaining=budget_total * budget_alloc["accommodation"] - float(accom_cost)),
        BudgetCategory(category="activities", allocated=budget_total * budget_alloc["activities"], spent=float(act_cost), remaining=budget_total * budget_alloc["activities"] - float(act_cost)),
        BudgetCategory(category="meals", allocated=budget_total * budget_alloc["meals"], spent=0, remaining=budget_total * budget_alloc["meals"]),
        BudgetCategory(category="misc", allocated=budget_total * budget_alloc["misc"], spent=0, remaining=budget_total * budget_alloc["misc"]),
    ]
    tracker = BudgetTracker(total_budget=budget_total, currency="INR", categories=categories, warnings=warnings)
    if tracker.is_over_budget():
        tracker.warnings.append("Over budget — consider reducing accommodation or switching to ground transport.")

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "budget_optimizer",
        "action": "optimize",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"Selected 1 transport, 1 hotel, {len(selected_activities)} activities within ₹{budget_total}",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {
        "selected_outbound_flight": selected_flight,
        "selected_return_flight": None,
        "selected_hotel": selected_hotel,
        "selected_activities": selected_activities,
        "budget_tracker": tracker.model_dump(),
        "budget_warnings": tracker.warnings,
        "agent_decisions": [decision],
        "current_stage": "budget_done",
    }
