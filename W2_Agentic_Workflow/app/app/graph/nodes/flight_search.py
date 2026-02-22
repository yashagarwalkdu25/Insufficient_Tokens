"""Flight + ground-transport search agent.

- Estimates distance between origin and destination; for short hops (< 200 km)
  flights are skipped entirely and only ground transport is returned.
- When the destination city has no IATA code in INDIA_CITIES, the nearest major
  airport is located automatically.
- Flight prices: Amadeus API -> LLM estimates -> booking URL fallback.
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
from app.api.booking_links import (
    generate_skyscanner_flight_url,
    generate_makemytrip_flight_url,
)
from app.config import get_settings
from app.data.india_cities import get_city, INDIA_CITIES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Distance threshold below which flights are skipped (km)
# ---------------------------------------------------------------------------
SHORT_DISTANCE_KM = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _find_nearest_airport(city_name: str) -> tuple[str, str]:
    """Find the nearest INDIA_CITIES entry that has a valid IATA code.

    Returns (*airport_city_name*, *iata_code*).  Falls back to ``("Delhi", "DEL")``.
    """
    coords = _get_coords(city_name)
    if coords is None:
        return ("Delhi", "DEL")

    best_city = "Delhi"
    best_iata = "DEL"
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
    return (best_city, best_iata)


def _estimate_distance_with_llm(origin: str, destination: str) -> float | None:
    """Ask GPT-4o-mini to estimate the straight-line distance in km.

    Used when one or both cities are not in INDIA_CITIES so we have no coords.
    Returns the estimated distance or *None* on failure.
    """
    settings = get_settings()
    if not settings.has_openai:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = (
            f"What is the approximate straight-line distance in kilometres between "
            f"{origin} and {destination} in India? Reply with ONLY a single integer "
            f"(no units, no text). Example: 350"
        )
        r = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=20,
        )
        content = (r.choices[0].message.content or "").strip()
        return float(content)
    except Exception as e:
        logger.warning("LLM distance estimation failed: %s", e)
        return None


def _estimate_distance(origin: str, destination: str) -> float | None:
    """Return estimated distance in km using coords or LLM fallback."""
    o_coords = _get_coords(origin)
    d_coords = _get_coords(destination)
    if o_coords and d_coords:
        return _haversine_km(o_coords[0], o_coords[1], d_coords[0], d_coords[1])
    # Fallback to LLM
    return _estimate_distance_with_llm(origin, destination)


def _llm_estimate_transport_prices(
    origin: str,
    destination: str,
    distance_km: float | None,
    include_flights: bool,
) -> dict | None:
    """Ask GPT-4o-mini for realistic transport price estimates.

    Returns a dict like::

        {
            "flights": [
                {"airline": "IndiGo", "price_inr": 4500, "duration_minutes": 120},
                ...
            ],
            "trains": [
                {"class": "3A", "price_inr": 800, "duration_minutes": 480, "operator": "IRCTC"},
                ...
            ],
            "buses": [
                {"type": "AC Sleeper", "price_inr": 600, "duration_minutes": 360, "operator": "RedBus"},
                ...
            ],
            "taxi": {"price_inr": 3000, "duration_minutes": 180},
            "reasoning": "..."
        }

    Returns *None* on failure.
    """
    settings = get_settings()
    if not settings.has_openai:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        distance_info = f"(approx {int(distance_km)} km apart)" if distance_km else ""
        flight_instruction = (
            "Include 2-3 realistic flight options with airline names common on this route."
            if include_flights
            else "Do NOT include flights — the cities are too close for commercial flights."
        )

        prompt = f"""You are an Indian travel pricing expert. Estimate realistic 2025 transport prices
for travelling from {origin} to {destination} {distance_info}.

{flight_instruction}

Return ONLY valid JSON (no markdown fences):
{{
  "flights": [
    {{"airline": "...", "price_inr": <int>, "duration_minutes": <int>}}
  ],
  "trains": [
    {{"class": "3A/2A/SL", "price_inr": <int>, "duration_minutes": <int>, "operator": "IRCTC"}}
  ],
  "buses": [
    {{"type": "AC Sleeper/Non-AC", "price_inr": <int>, "duration_minutes": <int>, "operator": "RedBus"}}
  ],
  "cab_options": [
    {{"service": "Ola/Uber/Rapido", "type": "Sedan/SUV/Auto", "price_inr": <int>, "duration_minutes": <int>}}
  ],
  "reasoning": "Brief explanation of pricing logic"
}}

Rules:
- All prices in INR
- If flights don't operate on this route, return empty flights list
- For trains include at least 2 classes (e.g. Sleeper, 3AC)
- For buses include AC and non-AC options
- Include cab_options with Ola, Uber, and Rapido estimates (Sedan, SUV, Auto-rickshaw where applicable)
- For distances < 50km include auto-rickshaw via Rapido/Ola Auto
- For distances 50-500km include outstation cab options (Ola Outstation, Uber Intercity)
- Prices must be realistic for Indian domestic travel in 2025"""

        r = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        content = (r.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM transport pricing failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 1.  Resolve IATA codes (find nearest airport for unknown cities)
    # ------------------------------------------------------------------
    origin_iata = _get_iata(origin)
    dest_iata = _get_iata(dest)

    nearest_airport_note = ""
    if not origin_iata:
        airport_city, origin_iata = _find_nearest_airport(origin)
        nearest_airport_note += f"Origin '{origin}' has no airport — using nearest: {airport_city} ({origin_iata}). "
    if not dest_iata:
        airport_city, dest_iata = _find_nearest_airport(dest)
        nearest_airport_note += f"Destination '{dest}' has no airport — using nearest: {airport_city} ({dest_iata}). "

    if nearest_airport_note:
        reasoning_parts.append(nearest_airport_note.strip())

    # ------------------------------------------------------------------
    # 2.  Estimate distance and decide if flights make sense
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 3.  Flight search (only if distance warrants it)
    # ------------------------------------------------------------------
    amadeus_ok = False
    if not is_short_distance:
        # 3a. Try Amadeus API
        try:
            client = AmadeusClient()
            flights = client.search_flights(origin_iata, dest_iata, dep_str, ret_str)
            for f in flights:
                out_flights.append(f.model_dump() if hasattr(f, "model_dump") else f)
            if flights:
                amadeus_ok = True
                reasoning_parts.append(f"Amadeus API returned {len(flights)} flight options.")
        except Exception as e:
            reasoning_parts.append(f"Amadeus API failed ({e}); will try LLM estimates.")

        # 3b. If Amadeus failed, use LLM price estimates + booking URLs
        if not out_flights:
            llm_prices = _llm_estimate_transport_prices(
                origin, dest, distance_km, include_flights=True,
            )

            if llm_prices and llm_prices.get("flights"):
                for i, fp in enumerate(llm_prices["flights"][:3]):
                    airline = fp.get("airline", "Airline")
                    price = fp.get("price_inr") or fp.get("price_INR") or 0
                    duration = fp.get("duration_minutes", 120)

                    # Build real booking URLs so users can verify / book
                    if i == 0:
                        url = generate_skyscanner_flight_url(
                            origin_iata, dest_iata, dep_str,
                        )
                    else:
                        url = generate_makemytrip_flight_url(
                            origin_iata, dest_iata, dep_str,
                        )

                    out_flights.append({
                        "outbound": {
                            "airline": airline,
                            "departure_airport": origin_iata,
                            "arrival_airport": dest_iata,
                            "duration_minutes": duration,
                        },
                        "return_segment": None,
                        "total_price": price,
                        "currency": "INR",
                        "booking_url": url,
                        "source": "llm",
                        "verified": False,
                        "price_note": "LLM-estimated price — verify on booking site",
                    })

                reasoning_parts.append(
                    f"LLM estimated {len(out_flights)} flight options with realistic prices."
                )
            else:
                # Last-resort: booking URLs with no price
                url = generate_skyscanner_flight_url(origin_iata, dest_iata, dep_str)
                out_flights.append({
                    "outbound": {
                        "airline": "Search on Skyscanner",
                        "departure_airport": origin_iata,
                        "arrival_airport": dest_iata,
                    },
                    "return_segment": None,
                    "total_price": None,
                    "currency": "INR",
                    "booking_url": url,
                    "source": "curated",
                    "verified": False,
                })
                url2 = generate_makemytrip_flight_url(origin_iata, dest_iata, dep_str)
                out_flights.append({
                    "outbound": {
                        "airline": "Search on MakeMyTrip",
                        "departure_airport": origin_iata,
                        "arrival_airport": dest_iata,
                    },
                    "return_segment": None,
                    "total_price": None,
                    "currency": "INR",
                    "booking_url": url2,
                    "source": "curated",
                    "verified": False,
                })
                reasoning_parts.append(
                    "Generated Skyscanner + MakeMyTrip booking URLs as fallback (no price available)."
                )

    # ------------------------------------------------------------------
    # 4.  Ground transport (always included) — uses real fare calculators
    # ------------------------------------------------------------------
    try:
        from app.api.fare_calculator import get_all_ground_transport

        dk = distance_km or 100  # fallback if distance unknown
        out_ground = get_all_ground_transport(origin, dest, dk, dep_str)
        reasoning_parts.append(
            f"Calculated {len(out_ground)} ground-transport options using "
            f"Indian Railways fare structure + Ola/Uber/Rapido rate cards "
            f"for {origin} -> {dest} (~{int(dk * 1.3)} km road distance)."
        )
    except Exception as e:
        logger.warning("Fare calculator failed: %s", e)
        reasoning_parts.append(f"Ground transport calculation error: {e}")

    # ------------------------------------------------------------------
    # 5.  Build agent decision and return
    # ------------------------------------------------------------------
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
