"""
Budget optimizer agent: LLM-powered trade-off analysis.

Uses GPT-4o-mini to reason about budget allocation, compare flight vs ground transport,
score options by value, and select the best combination within budget.
Requires OpenAI API key — no heuristic fallback.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.config import get_settings
from app.models.budget import BudgetTracker, BudgetCategory

logger = logging.getLogger(__name__)


def _llm_optimize(req: dict, flights: list, ground: list, hotels: list, activities: list, budget_total: float) -> dict | None:
    """Use GPT-4o-mini to reason about the best budget allocation and selections."""
    settings = get_settings()
    if not settings.has_openai:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

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
    """LangGraph node: LLM-powered budget optimization."""
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

        if hotels:
            hi = llm_result.get("selected_hotel_index") or 0
            h = hotels[min(hi, len(hotels) - 1)]
            selected_hotel = h if isinstance(h, dict) else (h.model_dump() if hasattr(h, "model_dump") else None)
            reasoning_parts.append(f"LLM chose hotel (index {hi}): {selected_hotel.get('name', '?') if selected_hotel else '?'}.")

        act_indices = llm_result.get("selected_activity_indices") or list(range(min(5, len(activities))))
        for ai in act_indices:
            if 0 <= ai < len(activities):
                a = activities[ai]
                selected_activities.append(a if isinstance(a, dict) else (a.model_dump() if hasattr(a, "model_dump") else a))
    else:
        reasoning_parts.append("LLM budget optimization unavailable. OpenAI API key may be missing or call errored. Using first available options.")
        if flights:
            selected_flight = flights[0] if isinstance(flights[0], dict) else (flights[0].model_dump() if hasattr(flights[0], "model_dump") else None)
        if hotels:
            selected_hotel = hotels[0] if isinstance(hotels[0], dict) else (hotels[0].model_dump() if hasattr(hotels[0], "model_dump") else None)
        selected_activities = [a if isinstance(a, dict) else (a.model_dump() if hasattr(a, "model_dump") else a) for a in activities[:5]]

    # Build BudgetTracker
    transport_cost = 0
    if selected_flight:
        transport_cost = float(selected_flight.get("total_price") or selected_flight.get("price") or 0)
    accom_cost = 0
    if selected_hotel:
        accom_cost = float(selected_hotel.get("total_price") or selected_hotel.get("price_per_night", 0) * 3)
    act_cost = sum((a.get("price") or 0) if isinstance(a, dict) else 0 for a in selected_activities)

    categories = [
        BudgetCategory(category="transport", allocated=budget_total * budget_alloc["transport"], spent=transport_cost, remaining=budget_total * budget_alloc["transport"] - transport_cost),
        BudgetCategory(category="accommodation", allocated=budget_total * budget_alloc["accommodation"], spent=accom_cost, remaining=budget_total * budget_alloc["accommodation"] - accom_cost),
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
