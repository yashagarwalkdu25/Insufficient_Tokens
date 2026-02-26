"""Hotel search agent: LiteAPI + Tavily web search. No hardcoded fallbacks."""
from __future__ import annotations

import logging
import time
from typing import Any

from app.api.liteapi_client import LiteAPIClient
from app.api.tavily_client import TavilySearchClient
from app.api.booking_links import generate_booking_hotel_url, generate_makemytrip_hotel_url
from app.config import get_settings

logger = logging.getLogger(__name__)


def search_hotels_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: search hotels via LiteAPI then Tavily. Returns partial state update."""
    start = time.time()

    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    travel_style = req.get("travel_style", "midrange")

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

    # Strategy 1: LiteAPI
    try:
        client = LiteAPIClient()
        hotels = client.search_hotels(dest, checkin, checkout)
        for h in hotels:
            out.append(h.model_dump() if hasattr(h, "model_dump") else h)
        if hotels:
            reasoning_parts.append(f"LiteAPI returned {len(hotels)} hotels in {dest}.")
    except Exception as e:
        reasoning_parts.append(f"LiteAPI failed ({e}); trying Tavily web search.")

    # Strategy 2: Tavily web search for real hotel data
    if not out:
        try:
            tavily = TavilySearchClient()
            if tavily.available:
                tavily_hotels = tavily.search_hotels(dest, checkin, checkout, travel_style)
                if tavily_hotels:
                    booking_url = generate_booking_hotel_url(dest, checkin, checkout)
                    mmt_url = generate_makemytrip_hotel_url(dest, checkin, checkout)
                    for h in tavily_hotels:
                        h["booking_urls"] = {
                            "booking_com": booking_url,
                            "makemytrip": mmt_url,
                        }
                        out.append(h)
                    reasoning_parts.append(
                        f"Tavily web search found {len(tavily_hotels)} hotel results for {dest}."
                    )
        except Exception as e:
            reasoning_parts.append(f"Tavily hotel search failed ({e}).")

    # Attach booking URLs to all results
    if out:
        booking_url = generate_booking_hotel_url(dest, checkin, checkout)
        mmt_url = generate_makemytrip_hotel_url(dest, checkin, checkout)
        for hotel in out:
            if "booking_urls" not in hotel:
                hotel["booking_urls"] = {
                    "booking_com": booking_url,
                    "makemytrip": mmt_url,
                }
    else:
        reasoning_parts.append("No hotel data found from any source.")

    latency_ms = int((time.time() - start) * 1000)
    decision = {
        "agent_name": "hotel_search",
        "action": "search",
        "reasoning": " ".join(reasoning_parts) or f"Searched hotels in {dest}.",
        "result_summary": f"Found {len(out)} hotel options",
        "tokens_used": 0,
        "latency_ms": latency_ms,
    }
    return {"hotel_options": out, "agent_decisions": [decision]}
