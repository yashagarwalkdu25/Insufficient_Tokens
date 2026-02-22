"""Activity search agent: Google Places + curated india_activities + LLM fallback."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from openai import OpenAI

from app.api.google_places import GooglePlacesClient
from app.config import get_settings
from app.data.india_activities import get_activities
from app.data.india_cities import get_city

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geocoding helpers
# ---------------------------------------------------------------------------

def _geocode_city(city_name: str) -> tuple[float | None, float | None]:
    """Resolve city name to (lat, lon).

    Strategy:
      1. Look up the curated INDIA_CITIES database (instant, no network).
      2. Try Nominatim (free, no API key, generous rate-limit for single calls).
      3. Fall back to a quick GPT-4o-mini call that returns approximate coords.
    """
    # --- 1. Curated database -------------------------------------------------
    city = get_city(city_name)
    if city:
        lat = city.get("latitude")
        lon = city.get("longitude")
        if lat is not None and lon is not None:
            return lat, lon

    # --- 2. Nominatim (OpenStreetMap) ----------------------------------------
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{city_name}, India",
            "format": "json",
            "limit": 1,
        }
        headers = {"User-Agent": "YatraAI/1.0 (travel-planner)"}
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            results = resp.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            logger.info("Nominatim geocoded %s -> (%s, %s)", city_name, lat, lon)
            return lat, lon
    except Exception as exc:
        logger.warning("Nominatim geocoding failed for %s: %s", city_name, exc)

    # --- 3. LLM approximate geocoding ----------------------------------------
    settings = get_settings()
    if not settings.has_openai:
        logger.warning("No OpenAI key; cannot LLM-geocode %s", city_name)
        return None, None

    try:
        llm = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = llm.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            temperature=0,
            max_tokens=80,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a geocoding assistant. Return ONLY a JSON object "
                        'with keys "latitude" and "longitude" (float) for the '
                        "requested Indian city. No extra text."
                    ),
                },
                {"role": "user", "content": f"Coordinates of {city_name}, India"},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw)
        lat = float(data["latitude"])
        lon = float(data["longitude"])
        logger.info("LLM geocoded %s -> (%s, %s)", city_name, lat, lon)
        return lat, lon
    except Exception as exc:
        logger.warning("LLM geocoding failed for %s: %s", city_name, exc)

    return None, None


# ---------------------------------------------------------------------------
# LLM activity generation fallback
# ---------------------------------------------------------------------------

_LLM_ACTIVITY_SYSTEM_PROMPT = """\
You are a knowledgeable Indian travel expert. Generate realistic activities \
and things to do for the given city. Return ONLY a JSON array of objects. \
Each object MUST have these keys:
  name            - real place / activity name (string)
  description     - 1-2 sentence description (string)
  category        - one of: adventure, culture, nature, spiritual, shopping, food, nightlife (string)
  duration_hours  - estimated duration in hours (float)
  price           - estimated entry/participation fee in INR; use 0 for free (int)
  latitude        - approximate latitude (float)
  longitude       - approximate longitude (float)
  address         - human-readable address (string)
  opening_hours   - dict like {"Daily": "09:00-18:00"} or null (object|null)
  phone           - phone number or null (string|null)

Guidelines:
- Use REAL place names that actually exist in or near the city.
- Vary prices realistically: temples/parks can be free (0), museums 50-500 INR, \
  adventure activities 500-5000 INR, food tours 300-1500 INR.
- Include a mix of categories relevant to the traveler's interests.
- Generate 6-8 activities.
- Return ONLY the JSON array, no markdown fences or extra text.\
"""


def _llm_generate_activities(
    dest: str,
    interests: list[str],
    budget: str | None = None,
    style: str | None = None,
) -> list[dict[str, Any]]:
    """Call GPT-4o-mini to generate realistic activities when other sources fail."""
    settings = get_settings()
    if not settings.has_openai:
        logger.warning("No OpenAI key; cannot LLM-generate activities for %s", dest)
        return []

    interest_str = ", ".join(interests) if interests else "general sightseeing"
    budget_str = f" Budget style: {budget}." if budget else ""
    style_str = f" Travel style: {style}." if style else ""

    user_prompt = (
        f"City: {dest}, India.\n"
        f"Traveler interests: {interest_str}.{budget_str}{style_str}\n"
        "Generate 6-8 activities."
    )

    try:
        llm = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = llm.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            temperature=0.7,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": _LLM_ACTIVITY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if the model wraps output
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        items = json.loads(raw)
        if not isinstance(items, list):
            logger.warning("LLM returned non-list for activities: %s", type(items))
            return []

        activities: list[dict[str, Any]] = []
        for item in items:
            activities.append({
                "name": item.get("name", "Unknown Activity"),
                "description": item.get("description"),
                "category": item.get("category", "culture"),
                "duration_hours": float(item.get("duration_hours", 2.0)),
                "price": float(item.get("price", 0)),
                "currency": "INR",
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "address": item.get("address"),
                "opening_hours": item.get("opening_hours"),
                "phone": item.get("phone"),
                "source": "llm",
                "verified": False,
            })
        logger.info(
            "LLM generated %d activities for %s", len(activities), dest
        )
        return activities
    except Exception as exc:
        logger.error("LLM activity generation failed for %s: %s", dest, exc)
        return []


# ---------------------------------------------------------------------------
# Main LangGraph node
# ---------------------------------------------------------------------------

def search_activities_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: search activities and restaurants. Returns partial state update."""
    start = time.time()

    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    interests = req.get("interests") or []
    budget = req.get("budget")
    style = req.get("travel_style")
    if not dest:
        return {
            "activity_options": [],
            "agent_decisions": [{
                "agent_name": "activity_search",
                "action": "search",
                "reasoning": "No destination — skipping activity search.",
                "result_summary": "Skipped",
                "tokens_used": 0,
                "latency_ms": 0,
            }],
        }

    out: list[dict] = []
    reasoning_parts: list[str] = []

    # --- Geocode (curated -> Nominatim -> LLM) --------------------------------
    lat, lon = _geocode_city(dest)

    # --- Google Places API (needs lat/lon and API key) -------------------------
    if lat is not None and lon is not None:
        try:
            client = GooglePlacesClient()
            for q in (interests[:3] or ["things to do", "attractions"]):
                acts = client.search_activities(q, lat, lon, max_results=5)
                for a in acts:
                    out.append(a.model_dump() if hasattr(a, "model_dump") else a)
            if out:
                reasoning_parts.append(
                    f"Google Places returned {len(out)} activities for "
                    f"'{', '.join(interests[:3])}'."
                )
        except Exception as e:
            reasoning_parts.append(f"Google Places failed ({e}); using curated fallback.")

    # --- Curated activities (only for ~20 known cities) ------------------------
    curated = get_activities(dest, interests)
    for c in curated:
        out.append({
            "name": c.get("name"),
            "description": c.get("description"),
            "category": c.get("category"),
            "duration_hours": c.get("duration_hours", 2),
            "price": c.get("estimated_price", 0),
            "currency": "INR",
            "latitude": c.get("latitude"),
            "longitude": c.get("longitude"),
            "address": c.get("address"),
            "opening_hours": c.get("opening_hours"),
            "phone": c.get("phone"),
            "source": "curated",
            "verified": True,
        })
    if curated:
        reasoning_parts.append(f"Added {len(curated)} curated activities for {dest}.")

    # --- LLM fallback (when both Google Places and curated give nothing) -------
    if not out:
        reasoning_parts.append(
            f"No Google Places or curated results for {dest}; invoking LLM fallback."
        )
        llm_acts = _llm_generate_activities(dest, interests, budget, style)
        out.extend(llm_acts)
        if llm_acts:
            reasoning_parts.append(
                f"LLM generated {len(llm_acts)} activities for {dest}."
            )
        else:
            reasoning_parts.append("LLM fallback also returned 0 activities.")

    # --- Deduplicate by name ---------------------------------------------------
    seen: set[str] = set()
    unique: list[dict] = []
    for a in out:
        n = (a.get("name") or "").strip()
        if n and n not in seen:
            seen.add(n)
            unique.append(a)

    latency_ms = int((time.time() - start) * 1000)
    decision = {
        "agent_name": "activity_search",
        "action": "search",
        "reasoning": " ".join(reasoning_parts) or f"Searched activities in {dest}.",
        "result_summary": f"Found {len(unique)} unique activities",
        "tokens_used": 0,
        "latency_ms": latency_ms,
    }
    return {"activity_options": unique[:15], "agent_decisions": [decision]}
