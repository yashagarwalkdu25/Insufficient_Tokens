"""
Itinerary builder agent: LLM-powered day-by-day trip planning.

Uses GPT-4o to create intelligent day-by-day plans with:
- Logical activity ordering (outdoor early, temples morning, markets evening)
- Travel time awareness
- Weather-aware scheduling
- Opening hours validation
- Budget tracking per day

Falls back to template-based builder when no API key.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any, Optional

from app.config import get_settings
from app.models.trip import Trip, DayPlan, ItineraryItem

logger = logging.getLogger(__name__)


def _llm_build_itinerary(req: dict, selected_activities: list, selected_hotel: dict | None, selected_flight: dict | None, weather: dict | None, events: list, tips: list) -> list[dict] | None:
    """Use GPT-4o to build an intelligent day-by-day itinerary."""
    settings = get_settings()
    if not settings.has_openai:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        dest = req.get("destination", "?")
        origin = req.get("origin", "Delhi")
        start_date = req.get("start_date", "")
        end_date = req.get("end_date", "")
        style = req.get("travel_style", "balanced")
        interests = req.get("interests", [])

        # Compact activity list
        act_lines = []
        for i, a in enumerate(selected_activities[:10]):
            name = a.get("name", "Activity") if isinstance(a, dict) else str(a)
            price = (a.get("price") or 0) if isinstance(a, dict) else 0
            cat = (a.get("category") or "general") if isinstance(a, dict) else "general"
            hours = a.get("opening_hours") if isinstance(a, dict) else None
            act_lines.append(f"A{i}: {name} (₹{price}, {cat}, hours={hours})")

        weather_summary = ""
        if weather and isinstance(weather, dict):
            w = weather.get("summary", "")
            weather_summary = w[:300] if w else ""

        event_lines = [f"Event: {e.get('name', '?')} — {e.get('recommendation', '')}" for e in (events or [])[:3]]
        tip_lines = [f"Tip: {t.get('title', '?')}: {(t.get('content') or '')[:80]}" for t in (tips or [])[:3]]

        hotel_name = (selected_hotel.get("name", "Hotel") if selected_hotel else "TBD")

        prompt = f"""You are an expert India travel planner. Build a detailed day-by-day itinerary.

TRIP: {origin} → {dest}, {start_date} to {end_date}, style={style}, interests={interests}
HOTEL: {hotel_name}
TRANSPORT: {json.dumps(selected_flight, default=str)[:200] if selected_flight else "TBD"}

AVAILABLE ACTIVITIES (use these ONLY, reference by index A0, A1...):
{chr(10).join(act_lines) if act_lines else "No activities — suggest free exploration."}

WEATHER: {weather_summary or "No forecast available."}
EVENTS: {chr(10).join(event_lines) if event_lines else "None"}
LOCAL TIPS: {chr(10).join(tip_lines) if tip_lines else "None"}

RULES:
1. Day 1: arrival + lighter schedule. Last day: checkout + departure.
2. Outdoor activities early morning (before heat). Temples 6-9 AM. Markets/shopping evening.
3. Include meals (breakfast, lunch, dinner) with estimated costs.
4. Add travel/transit between activities (estimate 20-40 min in cities).
5. If weather shows rain, schedule indoor activities for that day.
6. Include 1 free-time slot per day.
7. Respect opening hours if provided.
8. Each item needs: time (HH:MM), end_time, title, description, item_type (transport/activity/meal/hotel/free_time), cost (INR).

Return JSON array of day objects:
[
  {{
    "day_number": 1,
    "title": "Arrival & First Impressions",
    "tip_of_the_day": "optional local tip",
    "items": [
      {{"time": "09:00", "end_time": "10:00", "title": "...", "description": "...", "item_type": "transport", "cost": 0, "activity_index": null, "travel_duration_to_next": 25, "travel_mode_to_next": "auto"}}
    ]
  }}
]

IMPORTANT: Only reference activities by their A-index. For meals, use item_type="meal". Be specific and realistic about India travel."""

        r = client.chat.completions.create(
            model=settings.GPT4O_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        content = (r.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM itinerary builder failed: %s", e)
        return None


def _template_itinerary(req: dict, selected_activities: list, selected_hotel: dict | None) -> list[dict]:
    """Fallback template-based itinerary."""
    dest = (req.get("destination") or "").strip()
    start_date = req.get("start_date")
    end_date = req.get("end_date")

    if not start_date or not end_date:
        sd = date.today()
        ed = sd + timedelta(days=2)
    else:
        sd = start_date if isinstance(start_date, date) else date.fromisoformat(str(start_date)[:10])
        ed = end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date)[:10])

    days_list = []
    d = sd
    day_num = 1
    act_idx = 0
    while d <= ed:
        items = []
        if day_num == 1:
            items.append({"time": "09:00", "end_time": "10:00", "title": f"Arrive in {dest}", "description": f"Travel from {req.get('origin', 'Delhi')} and settle in.", "item_type": "transport", "cost": 0, "travel_duration_to_next": 30, "travel_mode_to_next": "auto"})
            if selected_hotel:
                items.append({"time": "10:00", "end_time": "11:00", "title": f"Check-in: {selected_hotel.get('name', 'Hotel')}", "description": "Hotel check-in and freshen up.", "item_type": "hotel", "cost": 0, "travel_duration_to_next": 15, "travel_mode_to_next": "walk"})
            items.append({"time": "11:00", "end_time": "12:00", "title": "Breakfast & explore neighbourhood", "item_type": "meal", "cost": 200, "travel_duration_to_next": 20, "travel_mode_to_next": "walk"})

        # Add 2-3 activities per day
        daily_acts = 3 if day_num > 1 and d < ed else 2
        for i in range(daily_acts):
            if act_idx < len(selected_activities):
                a = selected_activities[act_idx]
                name = a.get("name", "Activity") if isinstance(a, dict) else str(a)
                price = (a.get("price") or 0) if isinstance(a, dict) else 0
                cat = (a.get("category") or "activity") if isinstance(a, dict) else "activity"
                addr = (a.get("address") or "") if isinstance(a, dict) else ""
                phone = (a.get("phone") or "") if isinstance(a, dict) else ""
                contact = f"{phone} | {addr}" if phone and addr else (phone or addr or None)
                hour = 10 + i * 3 if day_num > 1 else 13 + i * 3
                items.append({
                    "time": f"{hour:02d}:00",
                    "end_time": f"{hour + 2:02d}:00",
                    "title": name,
                    "description": (a.get("description") or f"Enjoy {name} in {dest}.") if isinstance(a, dict) else f"Visit {name}.",
                    "item_type": "activity",
                    "cost": price,
                    "contact_info": contact,
                    "travel_duration_to_next": 25,
                    "travel_mode_to_next": "auto",
                })
                act_idx += 1

        # Lunch
        items.append({"time": "13:00", "end_time": "14:00", "title": f"Lunch — local cuisine in {dest}", "item_type": "meal", "cost": 300, "travel_duration_to_next": 15, "travel_mode_to_next": "walk"})

        # Evening
        if d < ed:
            items.append({"time": "18:00", "end_time": "19:30", "title": "Evening stroll & free time", "item_type": "free_time", "cost": 0, "travel_duration_to_next": 10, "travel_mode_to_next": "walk"})
            items.append({"time": "19:30", "end_time": "21:00", "title": "Dinner", "item_type": "meal", "cost": 350, "travel_duration_to_next": 15, "travel_mode_to_next": "auto"})

        if d == ed:
            items.append({"time": "10:00", "end_time": "11:00", "title": f"Check-out & depart {dest}", "item_type": "transport", "cost": 0})

        days_list.append({
            "day_number": day_num,
            "title": f"Day {day_num}" + (" — Arrival" if day_num == 1 else (" — Departure" if d == ed else "")),
            "items": items,
        })
        d += timedelta(days=1)
        day_num += 1

    return days_list


def build_itinerary_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: build intelligent day-by-day itinerary with LLM or template fallback."""
    start_t = time.time()
    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    origin = (req.get("origin") or "Delhi").strip()
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    style = req.get("travel_style") or "balanced"
    traveler_type = req.get("traveler_type") or "solo"
    selected_activities = state.get("selected_activities") or []
    selected_hotel = state.get("selected_hotel")
    selected_flight = state.get("selected_outbound_flight")
    weather = state.get("weather")
    events = state.get("events") or []
    tips = state.get("local_tips") or []

    reasoning_parts: list[str] = []
    tokens_used = 0

    # ── Try LLM itinerary ─────────────────────────────────────────────────
    llm_days = _llm_build_itinerary(req, selected_activities, selected_hotel, selected_flight, weather, events, tips)

    if llm_days and isinstance(llm_days, list):
        reasoning_parts.append(f"LLM generated {len(llm_days)}-day itinerary with intelligent scheduling.")
        raw_days = llm_days
    else:
        reasoning_parts.append("Using template-based itinerary builder (no LLM or LLM failed).")
        raw_days = _template_itinerary(req, selected_activities, selected_hotel)

    # ── Parse into Pydantic models ─────────────────────────────────────────
    if not start_date or not end_date:
        sd = date.today()
        ed = sd + timedelta(days=2)
    else:
        sd = start_date if isinstance(start_date, date) else date.fromisoformat(str(start_date)[:10])
        ed = end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date)[:10])

    days: list[DayPlan] = []
    d = sd
    for raw_day in raw_days:
        items: list[ItineraryItem] = []
        for raw_item in raw_day.get("items", []):
            try:
                # Map activity_index to real activity data for contact_info
                act_idx = raw_item.get("activity_index")
                contact = raw_item.get("contact_info")
                if act_idx is not None and 0 <= act_idx < len(selected_activities):
                    act = selected_activities[act_idx]
                    phone = (act.get("phone") or "") if isinstance(act, dict) else ""
                    addr = (act.get("address") or "") if isinstance(act, dict) else ""
                    if not contact and (phone or addr):
                        contact = f"{phone} | {addr}" if phone and addr else (phone or addr)

                items.append(ItineraryItem(
                    time=raw_item.get("time", "09:00"),
                    end_time=raw_item.get("end_time"),
                    title=raw_item.get("title", "Activity"),
                    description=raw_item.get("description"),
                    item_type=raw_item.get("item_type", "activity"),
                    cost=float(raw_item.get("cost", 0)),
                    source="llm" if llm_days else "curated",
                    verified=not bool(llm_days),
                    travel_duration_to_next=raw_item.get("travel_duration_to_next"),
                    travel_mode_to_next=raw_item.get("travel_mode_to_next"),
                    contact_info=contact,
                ))
            except Exception:
                continue

        day_cost = sum(it.cost for it in items)
        day_num = raw_day.get("day_number", len(days) + 1)
        days.append(DayPlan(
            day_number=day_num,
            date=d,
            title=raw_day.get("title") or f"Day {day_num}",
            items=items,
            day_cost=day_cost,
            tip_of_the_day=raw_day.get("tip_of_the_day"),
        ))
        d += timedelta(days=1)

    total_cost = sum(dp.day_cost for dp in days)
    trip = Trip(
        destination=dest,
        origin=origin,
        start_date=sd,
        end_date=ed,
        days=days,
        total_cost=total_cost,
        currency="INR",
        traveler_type=traveler_type,
        travel_style=style,
    )

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "itinerary_builder",
        "action": "build",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"{len(days)} days, ₹{total_cost:,.0f} total, {'LLM-powered' if llm_days else 'template-based'}",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {"trip": trip.model_dump(), "current_stage": "itinerary_done", "agent_decisions": [decision]}
