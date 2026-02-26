"""
Itinerary builder agent: LLM-powered day-by-day trip planning.

Uses GPT-4o to create intelligent day-by-day plans with:
- Logical activity ordering (outdoor early, temples morning, markets evening)
- Travel time awareness
- Weather-aware scheduling
- Opening hours validation
- Budget tracking per day
- Post-process verification against real activity data

Requires OpenAI API key — no fallback templates.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, timedelta
from typing import Any, Optional

from app.config import get_settings
from app.models.trip import Trip, DayPlan, ItineraryItem

logger = logging.getLogger(__name__)


def _build_activity_lines(selected_activities: list) -> list[str]:
    """Format up to 15 activities with rich detail for the LLM prompt."""
    act_lines: list[str] = []
    for i, a in enumerate(selected_activities[:15]):
        if isinstance(a, dict):
            name = a.get("name", "Activity")
            price = a.get("price") or 0
            cat = a.get("category") or "general"
            hours = a.get("opening_hours")
            addr = a.get("address") or ""
            phone = a.get("phone") or ""
            lat = a.get("latitude")
            lon = a.get("longitude")
            src = a.get("source") or "unknown"
            verified = a.get("verified", False)
            rating = a.get("rating")
        else:
            name, price, cat = str(a), 0, "general"
            hours = addr = phone = src = ""
            lat = lon = rating = None
            verified = False

        parts = [f"A{i}: {name} | ₹{price} | {cat}"]
        if addr:
            parts.append(f"addr={addr}")
        if phone:
            parts.append(f"phone={phone}")
        if lat is not None and lon is not None:
            parts.append(f"geo=({lat},{lon})")
        if rating is not None:
            parts.append(f"rating={rating}")
        if hours:
            parts.append(f"hours={hours}")
        parts.append(f"source={src}, verified={verified}")
        act_lines.append(" | ".join(parts))
    return act_lines


def _extract_json_lenient(content: str) -> list[dict] | None:
    """Try multiple strategies to extract a JSON array from LLM output."""
    content = content.strip()

    if "```" in content:
        blocks = content.split("```")
        for block in blocks[1::2]:
            cleaned = block.strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\[.*\]', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            logger.warning("Regex-extracted JSON also invalid: %s", e)

    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            single = json.loads(match.group(0))
            if isinstance(single, dict):
                return [single]
        except json.JSONDecodeError as e:
            logger.warning("Single-object JSON extraction failed: %s", e)

    return None


def _build_activity_lookup(selected_activities: list) -> dict[str, dict]:
    """Build a name-based lookup (lowercased) for post-process verification."""
    lookup: dict[str, dict] = {}
    for a in selected_activities:
        if isinstance(a, dict):
            name = (a.get("name") or "").strip().lower()
            if name:
                lookup[name] = a
    return lookup


def _verify_item(raw_item: dict, act_idx: int | None, selected_activities: list, activity_lookup: dict[str, dict]) -> tuple[bool, str, float | None, dict | None]:
    """
    Verify whether an itinerary item references a real activity.

    Returns (verified, source, corrected_cost, matched_activity).
    """
    if act_idx is not None and 0 <= act_idx < len(selected_activities):
        act = selected_activities[act_idx]
        if isinstance(act, dict):
            real_price = act.get("price")
            return True, "api", float(real_price) if real_price is not None else None, act

    title = (raw_item.get("title") or "").strip().lower()
    if title and title in activity_lookup:
        act = activity_lookup[title]
        real_price = act.get("price")
        return True, "api", float(real_price) if real_price is not None else None, act

    for key, act in activity_lookup.items():
        if key in title or title in key:
            real_price = act.get("price")
            return True, "api", float(real_price) if real_price is not None else None, act

    item_type = raw_item.get("item_type", "activity")
    if item_type in ("meal", "transport", "hotel", "free_time"):
        return False, "llm", None, None

    return False, "llm", None, None


def _llm_build_itinerary(req: dict, selected_activities: list, selected_hotel: dict | None, selected_flight: dict | None, weather: dict | None, events: list, tips: list, modification: str | None = None) -> list[dict] | None:
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

        act_lines = _build_activity_lines(selected_activities)

        weather_summary = ""
        if weather and isinstance(weather, dict):
            w = weather.get("summary", "")
            weather_summary = w[:300] if w else ""

        event_lines = [f"Event: {e.get('name', '?')} — {e.get('recommendation', '')}" for e in (events or [])[:3]]
        tip_lines = [f"Tip: {t.get('title', '?')}: {(t.get('content') or '')[:80]}" for t in (tips or [])[:3]]

        hotel_name = (selected_hotel.get("name", "Hotel") if selected_hotel else "TBD")
        hotel_cost = 0
        if selected_hotel:
            hotel_cost = float(selected_hotel.get("price_per_night") or selected_hotel.get("total_price") or 0)

        transport_cost = 0
        transport_mode = "train"
        transport_desc = "TBD"
        if selected_flight:
            transport_cost = float(selected_flight.get("total_price") or selected_flight.get("price") or 0)
            t_type = (selected_flight.get("transport_type") or "").lower()
            if "train" in t_type or "rail" in t_type or "express" in t_type:
                transport_mode = "train"
            elif "bus" in t_type:
                transport_mode = "bus"
            elif "cab" in t_type or "taxi" in t_type:
                transport_mode = "cab"
            elif selected_flight.get("outbound", {}).get("airline"):
                transport_mode = "flight"
            transport_name = selected_flight.get("outbound", {}).get("airline") or t_type or "Transport"
            transport_desc = f"{transport_mode.title()} — {transport_name} — ₹{transport_cost:,.0f}"

        prompt = f"""You are an expert India travel planner with deep knowledge of {dest}. Build a detailed day-by-day itinerary.

TRIP: {origin} → {dest}, {start_date} to {end_date}, style={style}, interests={interests}
HOTEL: {hotel_name} (₹{hotel_cost:,.0f}/night)
BOOKED TRANSPORT: {transport_desc}

SEARCHED ACTIVITIES (prefer these if relevant, reference by index A0, A1...):
{chr(10).join(act_lines) if act_lines else "No search results available."}

WEATHER: {weather_summary or "No forecast available."}
EVENTS: {chr(10).join(event_lines) if event_lines else "None"}
LOCAL TIPS: {chr(10).join(tip_lines) if tip_lines else "None"}

RULES:
1. Day 1: arrival + lighter schedule. Last day: checkout + departure.
2. Outdoor activities early morning (before heat). Temples 6-9 AM. Markets/shopping evening.
3. Include meals (breakfast, lunch, dinner) with realistic local prices.
4. Add travel/transit between activities with realistic durations.
5. If weather shows rain, schedule indoor activities for that day.
6. Include 1 free-time slot per day.
7. Respect opening hours if provided.
8. Each item needs: time (HH:MM), end_time, title, description, item_type, travel_mode (for transport items), cost (INR).

TRANSPORT RULES (CRITICAL):
- Use ONLY the booked transport mode: "{transport_mode}" for the main {origin}→{dest} journey.
- NEVER invent a flight if the transport mode is train, bus, or cab.
- For transport items set "travel_mode" to one of: flight/train/bus/cab/auto/walk/metro.
- "Return to Hotel" is NOT a transport item with travel_mode=flight. Use item_type="transport" travel_mode="cab" or "walk" for hotel returns.
- Only use travel_mode="flight" if there is an actual commercial flight between two cities with an airport. {origin} and {dest} may not have commercial airports — use train/bus/cab in that case.

CRITICAL REQUIREMENTS:
- Include the TOP tourist attractions and landmarks of {dest}. Use REAL, SPECIFIC place names.
- For meals: use REAL, NAMED local restaurants. Include realistic prices.
- For hotels: use the actual hotel name "{hotel_name}" for check-in/check-out items. Hotel night cost: ₹{hotel_cost:,.0f} (add this as the check-in item cost).
- For the main journey transport item on Day 1: use cost ₹{transport_cost:,.0f} and travel_mode="{transport_mode}".
- All costs must be realistic INR amounts. NEVER use ₹0 unless genuinely free.
- Typical Indian meal costs: street food ₹50-150, casual restaurant ₹200-500, mid-range ₹500-1000.
- Entry fees: major monuments ₹50-750 (Indian citizens), museums ₹20-200.

Return JSON array of day objects:
[
  {{
    "day_number": 1,
    "title": "Arrival & First Impressions",
    "tip_of_the_day": "optional local tip",
    "items": [
      {{"time": "07:00", "end_time": "09:30", "title": "Train from {origin} to {dest}", "description": "...", "item_type": "transport", "travel_mode": "{transport_mode}", "cost": {transport_cost}, "activity_index": null, "travel_duration_to_next": 20, "travel_mode_to_next": "cab"}}
    ]
  }}
]

Be specific, use real place names, and make this a trip that a real traveler would love.
{f"{chr(10)}USER MODIFICATION REQUEST: {modification}{chr(10)}Apply this change. This takes priority over all other instructions." if modification else ""}"""

        r = client.chat.completions.create(
            model=settings.GPT4O_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        content = (r.choices[0].message.content or "").strip()
        parsed = _extract_json_lenient(content)
        if parsed is None:
            logger.error("LLM returned unparseable content (first 500 chars): %s", content[:500])
        return parsed
    except json.JSONDecodeError as e:
        logger.error("JSON parse error in LLM itinerary response: %s — raw snippet: %s", e, content[:300] if 'content' in dir() else "N/A")
        return None
    except Exception as e:
        logger.warning("LLM itinerary builder failed: %s", e)
        return None


def build_itinerary_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: build intelligent day-by-day itinerary with LLM."""
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

    modification = state.get("user_feedback") if state.get("is_replanning") else None

    reasoning_parts: list[str] = []
    tokens_used = 0

    raw_days = _llm_build_itinerary(req, selected_activities, selected_hotel, selected_flight, weather, events, tips, modification)

    if raw_days and isinstance(raw_days, list):
        reasoning_parts.append(f"LLM generated {len(raw_days)}-day itinerary with intelligent scheduling.")
    else:
        reasoning_parts.append("LLM itinerary generation failed. OpenAI API key may be missing or call errored.")
        raw_days = []

    if not start_date or not end_date:
        sd = date.today()
        ed = sd + timedelta(days=2)
    else:
        sd = start_date if isinstance(start_date, date) else date.fromisoformat(str(start_date)[:10])
        ed = end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date)[:10])

    activity_lookup = _build_activity_lookup(selected_activities)
    verified_count = 0
    unverified_count = 0

    days: list[DayPlan] = []
    d = sd
    for raw_day in raw_days:
        items: list[ItineraryItem] = []
        for raw_item in raw_day.get("items", []):
            try:
                act_idx = raw_item.get("activity_index")
                contact = raw_item.get("contact_info")
                item_lat = raw_item.get("latitude")
                item_lon = raw_item.get("longitude")
                item_address = raw_item.get("location")

                verified, source, corrected_cost, matched_act = _verify_item(
                    raw_item, act_idx, selected_activities, activity_lookup
                )

                if matched_act and isinstance(matched_act, dict):
                    phone = matched_act.get("phone") or ""
                    addr = matched_act.get("address") or ""
                    if not contact and (phone or addr):
                        contact = f"{phone} | {addr}" if phone and addr else (phone or addr)
                    if item_lat is None and matched_act.get("latitude"):
                        item_lat = matched_act["latitude"]
                    if item_lon is None and matched_act.get("longitude"):
                        item_lon = matched_act["longitude"]
                    if not item_address and addr:
                        item_address = addr

                item_cost = corrected_cost if corrected_cost is not None else float(raw_item.get("cost", 0))

                if verified:
                    verified_count += 1
                else:
                    unverified_count += 1

                items.append(ItineraryItem(
                    time=raw_item.get("time", "09:00"),
                    end_time=raw_item.get("end_time"),
                    title=raw_item.get("title", "Activity"),
                    description=raw_item.get("description"),
                    item_type=raw_item.get("item_type", "activity"),
                    travel_mode=raw_item.get("travel_mode"),
                    cost=item_cost,
                    latitude=float(item_lat) if item_lat is not None else None,
                    longitude=float(item_lon) if item_lon is not None else None,
                    location=item_address,
                    source=source,
                    verified=verified,
                    travel_duration_to_next=raw_item.get("travel_duration_to_next"),
                    travel_mode_to_next=raw_item.get("travel_mode_to_next"),
                    contact_info=contact,
                ))
            except Exception as e:
                logger.debug("Skipping malformed itinerary item: %s", e)
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

    if verified_count or unverified_count:
        reasoning_parts.append(
            f"Post-validation: {verified_count} items verified against real data, "
            f"{unverified_count} items unverified (LLM-generated)."
        )

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
        "result_summary": f"{len(days)} days, ₹{total_cost:,.0f} total, LLM-powered, {verified_count} verified / {unverified_count} unverified",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {"trip": trip.model_dump(), "current_stage": "itinerary_done", "agent_decisions": [decision]}
