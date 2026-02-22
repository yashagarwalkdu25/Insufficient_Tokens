"""Hotel search agent: LiteAPI + LLM-generated realistic options + booking URL fallback."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.api.liteapi_client import LiteAPIClient
from app.api.booking_links import generate_booking_hotel_url, generate_makemytrip_hotel_url
from app.config import get_settings

logger = logging.getLogger(__name__)


def _llm_hotel_options(
    dest: str,
    checkin: str,
    checkout: str,
    travel_style: str,
    budget_total: float | None = None,
) -> list[dict]:
    """Use GPT-4o-mini to generate realistic hotel options with estimated prices."""
    settings = get_settings()
    if not settings.has_openai:
        return []

    # Map travel_style to price guidance
    style_guidance = {
        "backpacker": "budget hostels and guesthouses (INR 500-1500 per night)",
        "budget": "budget hotels and guesthouses (INR 800-2000 per night)",
        "midrange": "mid-range 3-star hotels (INR 2500-6000 per night)",
        "luxury": "luxury 4-5 star hotels and resorts (INR 8000-25000+ per night)",
        "comfort": "comfortable 3-4 star hotels (INR 3000-8000 per night)",
    }
    price_hint = style_guidance.get(
        (travel_style or "midrange").lower(),
        "mid-range hotels (INR 2500-6000 per night)",
    )

    budget_note = ""
    if budget_total and budget_total > 0:
        budget_note = f" The total trip budget is approximately INR {budget_total:.0f}."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": (
                f"Suggest 4 realistic hotel options in {dest}, India for a {travel_style or 'midrange'} traveler.\n"
                f"Check-in: {checkin}, Check-out: {checkout}\n"
                f"Price range: {price_hint}.{budget_note}\n\n"
                f"Return ONLY a JSON array with this structure:\n"
                f'[{{"name": "<real hotel name in {dest}>", '
                f'"address": "<realistic address>", '
                f'"star_rating": <1-5>, '
                f'"price_per_night": <int in INR>, '
                f'"total_price": <int in INR for entire stay>, '
                f'"currency": "INR", '
                f'"amenities": ["wifi", "breakfast", ...], '
                f'"description": "<1 sentence about the hotel>", '
                f'"why_recommended": "<why this suits the travel style>"}}]\n\n'
                f"Use real or realistic hotel names for {dest}. "
                f"Prices must be realistic for the city and style. "
                f"Include a mix of options within the price range. "
                f"Total price = price_per_night * number of nights."
            )}],
            temperature=0.7,
        )
        content = (resp.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        hotels = json.loads(content)

        # Normalize and tag each hotel
        result = []
        for h in hotels:
            result.append({
                "name": h.get("name", f"Hotel in {dest}"),
                "address": h.get("address"),
                "star_rating": h.get("star_rating", 3),
                "price_per_night": int(h.get("price_per_night", 0)),
                "total_price": int(h.get("total_price", 0)),
                "currency": h.get("currency", "INR"),
                "amenities": h.get("amenities", []),
                "description": h.get("description", ""),
                "why_recommended": h.get("why_recommended", ""),
                "source": "llm",
                "verified": False,
            })
        return result
    except Exception as e:
        logger.warning("LLM hotel generation failed for %s: %s", dest, e)
        return []


def search_hotels_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: search hotels. Returns partial state update."""
    start = time.time()

    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    travel_style = req.get("travel_style", "midrange")
    # budget_total should be a number (total trip budget in INR), not a style string
    raw_budget = req.get("budget_total") or req.get("total_budget")
    try:
        budget_total = float(raw_budget) if raw_budget else None
    except (ValueError, TypeError):
        budget_total = None

    if not dest:
        return {
            "hotel_options": [],
            "agent_decisions": [{
                "agent_name": "hotel_search",
                "action": "search",
                "reasoning": "No destination — skipping hotel search.",
                "result_summary": "Skipped",
                "tokens_used": 0,
                "latency_ms": 0,
            }],
        }

    checkin = start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date)
    checkout = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)
    reasoning_parts: list[str] = []
    out: list[dict] = []
    tokens_used = 0

    # ── Try LiteAPI ────────────────────────────────────────────────────────
    try:
        client = LiteAPIClient()
        hotels = client.search_hotels(dest, checkin, checkout)
        for h in hotels:
            out.append(h.model_dump() if hasattr(h, "model_dump") else h)
        if hotels:
            reasoning_parts.append(f"LiteAPI returned {len(hotels)} hotels in {dest}.")
    except Exception as e:
        reasoning_parts.append(f"LiteAPI failed ({e}); trying LLM fallback.")

    # ── Fallback: LLM-generated realistic hotel options ────────────────────
    if not out:
        llm_hotels = _llm_hotel_options(dest, checkin, checkout, travel_style, budget_total)
        if llm_hotels:
            out.extend(llm_hotels)
            reasoning_parts.append(
                f"GPT-4o-mini generated {len(llm_hotels)} realistic hotel options for {dest} "
                f"(style: {travel_style})."
            )
            tokens_used = 300  # approximate

    # ── Supplement: booking URLs (always add for reference) ────────────────
    booking_url = generate_booking_hotel_url(dest, checkin, checkout)
    mmt_url = generate_makemytrip_hotel_url(dest, checkin, checkout)

    if out:
        # Attach booking URLs to existing options as supplementary links
        for hotel in out:
            if "booking_urls" not in hotel:
                hotel["booking_urls"] = {
                    "booking_com": booking_url,
                    "makemytrip": mmt_url,
                }
    else:
        # Nothing worked at all: add URL-only entries as last resort
        out.append({
            "name": f"Hotels in {dest} — Booking.com",
            "address": None,
            "price_per_night": 0,
            "total_price": 0,
            "currency": "INR",
            "booking_url": booking_url,
            "source": "curated",
            "verified": False,
        })
        out.append({
            "name": f"Hotels in {dest} — MakeMyTrip",
            "address": None,
            "price_per_night": 0,
            "total_price": 0,
            "currency": "INR",
            "booking_url": mmt_url,
            "source": "curated",
            "verified": False,
        })
        reasoning_parts.append("Generated Booking.com + MakeMyTrip URLs as last-resort fallback.")

    latency_ms = int((time.time() - start) * 1000)
    decision = {
        "agent_name": "hotel_search",
        "action": "search",
        "reasoning": " ".join(reasoning_parts) or f"Searched hotels in {dest}.",
        "result_summary": f"Found {len(out)} hotel options",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {"hotel_options": out, "agent_decisions": [decision]}
