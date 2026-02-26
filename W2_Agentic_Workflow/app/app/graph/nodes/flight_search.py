"""Flight + ground-transport search agent.

- Estimates distance between origin and destination; for short hops (< 200 km)
  flights are skipped entirely and only ground transport is returned.
- When the destination city has no IATA code in INDIA_CITIES, the nearest major
  airport is located automatically.
- Flight prices: Amadeus API -> Tavily web search.
- Ground transport (trains, buses, cabs): uses formula-based fare calculators
  with real Indian Railways fare structure and Ola/Uber/Rapido rate cards.
"""
from __future__ import annotations

import json
import logging
import math
import time
from typing import Any

from app.api.amadeus_client import AmadeusClient
from app.api.tavily_client import TavilySearchClient
from app.api.booking_links import (
    generate_skyscanner_flight_url,
    generate_makemytrip_flight_url,
)
from app.config import get_settings
from app.data.india_cities import get_city, INDIA_CITIES

logger = logging.getLogger(__name__)

SHORT_DISTANCE_KM = 200


def _get_iata(city_name: str) -> str:
    """Return the IATA code for *city_name* if it exists in INDIA_CITIES."""
    c = get_city(city_name)
    if c:
        return c.get("iata_code", "") or ""
    for name, data in INDIA_CITIES.items():
        if city_name.lower() in name.lower():
            return data.get("iata_code", "")
    return ""


def _get_coords(city_name: str) -> tuple[float, float] | None:
    """Return (latitude, longitude) for a city if known, else *None*."""
    c = get_city(city_name)
    if c and c.get("latitude") and c.get("longitude"):
        return (c["latitude"], c["longitude"])
    for name, data in INDIA_CITIES.items():
        if city_name.lower() in name.lower():
            if data.get("latitude") and data.get("longitude"):
                return (data["latitude"], data["longitude"])
    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _find_nearest_airport(city_name: str) -> tuple[str, str] | None:
    """Find the nearest INDIA_CITIES entry that has a valid IATA code.

    Returns (*airport_city_name*, *iata_code*) or None if coords are unknown.
    """
    coords = _get_coords(city_name)
    if coords is None:
        return None

    best_city = None
    best_iata = None
    best_dist = float("inf")
    for name, data in INDIA_CITIES.items():
        iata = data.get("iata_code", "")
        lat = data.get("latitude")
        lon = data.get("longitude")
        if not iata or not lat or not lon:
            continue
        d = _haversine_km(coords[0], coords[1], lat, lon)
        if d < best_dist:
            best_dist = d
            best_city = name
            best_iata = iata
    if best_city and best_iata:
        return (best_city, best_iata)
    return None


def _estimate_distance(origin: str, destination: str) -> float | None:
    """Return estimated distance in km using coords."""
    o_coords = _get_coords(origin)
    d_coords = _get_coords(destination)
    if o_coords and d_coords:
        return _haversine_km(o_coords[0], o_coords[1], d_coords[0], d_coords[1])
    return None


def search_flights_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: search flights and ground transport. Returns partial state update."""
    start = time.time()

    req = state.get("trip_request") or {}
    origin = (req.get("origin") or "Delhi").strip()
    dest = (req.get("destination") or "").strip()
    start_date = req.get("start_date")
    end_date = req.get("end_date")

    if not dest:
        return {
            "flight_options": [],
            "ground_transport_options": [],
            "agent_decisions": [{
                "agent_name": "flight_search",
                "action": "search",
                "reasoning": "No destination specified — skipping flight search.",
                "result_summary": "Skipped",
                "tokens_used": 0,
                "latency_ms": 0,
            }],
        }

    out_flights: list[dict] = []
    out_ground: list[dict] = []
    dep_str = start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date)
    ret_str = (
        end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)
    ) if end_date else None

    reasoning_parts: list[str] = []
    tokens_used = 0

    # 1. Resolve IATA codes
    origin_iata = _get_iata(origin)
    dest_iata = _get_iata(dest)

    nearest_airport_note = ""
    if not origin_iata:
        result = _find_nearest_airport(origin)
        if result:
            airport_city, origin_iata = result
            nearest_airport_note += f"Origin '{origin}' has no airport — using nearest: {airport_city} ({origin_iata}). "
        else:
            nearest_airport_note += f"Origin '{origin}' has no known airport and coordinates unavailable. "

    if not dest_iata:
        result = _find_nearest_airport(dest)
        if result:
            airport_city, dest_iata = result
            nearest_airport_note += f"Destination '{dest}' has no airport — using nearest: {airport_city} ({dest_iata}). "
        else:
            nearest_airport_note += f"Destination '{dest}' has no known airport and coordinates unavailable. "

    if nearest_airport_note:
        reasoning_parts.append(nearest_airport_note.strip())

    # 2. Estimate distance and decide if flights make sense
    distance_km = _estimate_distance(origin, dest)
    is_short_distance = False

    if distance_km is not None:
        reasoning_parts.append(f"Estimated distance: {int(distance_km)} km.")
        if distance_km < SHORT_DISTANCE_KM:
            is_short_distance = True
            reasoning_parts.append(
                f"Distance < {SHORT_DISTANCE_KM} km — flights not practical. "
                f"Recommending ground transport only."
            )
    else:
        reasoning_parts.append("Could not estimate distance; will attempt flight search.")

    # 3. Flight search (only if distance warrants it)
    if not is_short_distance:
        # 3a. Try Amadeus API (only if we have IATA codes)
        if origin_iata and dest_iata:
            try:
                client = AmadeusClient()
                flights = client.search_flights(origin_iata, dest_iata, dep_str, ret_str)
                for f in flights:
                    out_flights.append(f.model_dump() if hasattr(f, "model_dump") else f)
                if flights:
                    reasoning_parts.append(f"Amadeus API returned {len(flights)} flight options.")
            except Exception as e:
                reasoning_parts.append(f"Amadeus API failed ({e}); trying Tavily web search.")

        # 3b. Tavily web search for flight information
        if not out_flights:
            try:
                tavily = TavilySearchClient()
                if tavily.available:
                    tavily_flights = tavily.search_flights(origin, dest, dep_str)
                    if tavily_flights:
                        sky_url = generate_skyscanner_flight_url(
                            origin_iata or origin, dest_iata or dest, dep_str,
                        )
                        mmt_url = generate_makemytrip_flight_url(
                            origin_iata or origin, dest_iata or dest, dep_str,
                        )
                        for i, tf in enumerate(tavily_flights[:5]):
                            out_flights.append({
                                "outbound": {
                                    "airline": tf.get("title", "Search results"),
                                    "departure_airport": origin_iata or origin,
                                    "arrival_airport": dest_iata or dest,
                                },
                                "return_segment": None,
                                "total_price": None,
                                "currency": "INR",
                                "booking_url": tf.get("booking_url") or (sky_url if i == 0 else mmt_url),
                                "description": tf.get("content", ""),
                                "source": "tavily_web",
                                "verified": False,
                            })
                        reasoning_parts.append(
                            f"Tavily web search found {len(out_flights)} flight-related results."
                        )
            except Exception as e:
                reasoning_parts.append(f"Tavily flight search failed ({e}).")

        if not out_flights and not is_short_distance:
            reasoning_parts.append("No flight data found from any source.")

    # 4. Ground transport (always included) — uses real fare calculators
    if distance_km is not None:
        try:
            from app.api.fare_calculator import get_all_ground_transport
            out_ground = get_all_ground_transport(origin, dest, distance_km, dep_str)
            reasoning_parts.append(
                f"Calculated {len(out_ground)} ground-transport options using "
                f"Indian Railways fare structure + Ola/Uber/Rapido rate cards "
                f"for {origin} -> {dest} (~{int(distance_km * 1.3)} km road distance)."
            )
        except Exception as e:
            logger.warning("Fare calculator failed: %s", e)
            reasoning_parts.append(f"Ground transport calculation error: {e}")
    else:
        reasoning_parts.append("Distance unknown — could not calculate ground transport fares.")

    # 5. Build agent decision and return
    latency_ms = int((time.time() - start) * 1000)
    decision = {
        "agent_name": "flight_search",
        "action": "search",
        "reasoning": " ".join(reasoning_parts) or f"Searched flights from {origin} to {dest}.",
        "result_summary": (
            f"Found {len(out_flights)} flight(s), {len(out_ground)} ground option(s). "
            f"{'Short distance — ground only.' if is_short_distance else ''}"
        ).strip(),
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {
        "flight_options": out_flights,
        "ground_transport_options": out_ground,
        "agent_decisions": [decision],
    }
