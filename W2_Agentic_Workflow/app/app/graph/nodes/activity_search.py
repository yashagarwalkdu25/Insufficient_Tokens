"""Activity search agent: Google Places + Tavily web search. No hardcoded curated data."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from openai import OpenAI

from app.api.google_places import GooglePlacesClient
from app.api.tavily_client import TavilySearchClient
from app.config import get_settings
from app.data.india_cities import get_city

logger = logging.getLogger(__name__)


def _geocode_city(city_name: str) -> tuple[float | None, float | None]:
    """Resolve city name to (lat, lon).

    Strategy:
      1. Look up the curated INDIA_CITIES database (instant, no network).
      2. Try Nominatim (free, no API key, generous rate-limit for single calls).
      3. Fall back to a quick GPT-4o-mini call that returns approximate coords.
    """
    city = get_city(city_name)
    if city:
        lat = city.get("latitude")
        lon = city.get("longitude")
        if lat is not None and lon is not None:
            return lat, lon

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


def search_activities_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: search activities via Google Places then Tavily. Returns partial state update."""
    start = time.time()

    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    interests = req.get("interests") or []
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

    lat, lon = _geocode_city(dest)

    # Strategy 1: Google Places API (needs lat/lon and API key)
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
            reasoning_parts.append(f"Google Places failed ({e}); trying Tavily web search.")

    # Strategy 2: Tavily web search for activities
    if not out:
        try:
            tavily = TavilySearchClient()
            if tavily.available:
                tavily_acts = tavily.search_activities(dest, interests)
                if tavily_acts:
                    for ta in tavily_acts:
                        out.append({
                            "name": ta.get("name", "Activity"),
                            "description": ta.get("description"),
                            "category": "general",
                            "duration_hours": 2.0,
                            "price": 0,
                            "currency": "INR",
                            "url": ta.get("url"),
                            "source": "tavily_web",
                            "verified": False,
                        })
                    reasoning_parts.append(
                        f"Tavily web search found {len(tavily_acts)} activity results for {dest}."
                    )
        except Exception as e:
            reasoning_parts.append(f"Tavily activity search failed ({e}).")

    if not out:
        reasoning_parts.append("No activities found from any source.")

    # Deduplicate by name
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
