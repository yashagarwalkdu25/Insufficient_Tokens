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


def _enrich_activity_prices(activities: list[dict], dest: str) -> list[dict]:
    """Use GPT-4o-mini to estimate realistic INR prices and categories for a list of activities."""
    settings = get_settings()
    if not settings.has_openai or not activities:
        # Fallback: assign category-based defaults without LLM
        for a in activities:
            if a.get("price") is None:
                a["price"] = 0
        return activities

    try:
        llm = OpenAI(api_key=settings.OPENAI_API_KEY)
        names_list = "\n".join(
            f"{i}. {a['name']} — {(a.get('description') or '')[:80]}"
            for i, a in enumerate(activities)
        )
        prompt = (
            f"You are a travel pricing expert for {dest}, India.\n"
            f"For each activity below, provide a realistic INR price (entry fee / booking cost per person) "
            f"and the best category from: adventure, culture, nature, food, wellness, spiritual, shopping, sightseeing.\n"
            f"Use 0 only if the activity is genuinely free (e.g. a public park, temple with no entry fee).\n"
            f"For paid experiences like Bungee Jumping, Rafting, Paragliding, Yoga classes, Food tours — "
            f"use realistic market rates in INR.\n\n"
            f"Activities:\n{names_list}\n\n"
            f"Return ONLY a JSON array with one object per activity in order:\n"
            f'[{{"price": 1500, "category": "adventure", "duration_hours": 2.0}}, ...]\n'
            f"No markdown, no extra text."
        )
        resp = llm.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            temperature=0.2,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
        enrichments = json.loads(raw)
        for i, enrichment in enumerate(enrichments):
            if i < len(activities):
                activities[i]["price"] = int(enrichment.get("price") or 0)
                activities[i]["category"] = enrichment.get("category") or activities[i].get("category") or "general"
                activities[i]["duration_hours"] = float(enrichment.get("duration_hours") or activities[i].get("duration_hours") or 2.0)
        logger.info("Enriched prices for %d Tavily activities in %s", len(activities), dest)
    except Exception as e:
        logger.warning("Activity price enrichment failed: %s", e)
        for a in activities:
            if a.get("price") is None:
                a["price"] = 0
    return activities


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
                    raw_tavily = [
                        {
                            "name": ta.get("name", "Activity"),
                            "description": ta.get("description") or "",
                            "category": "general",
                            "duration_hours": 2.0,
                            "price": None,  # unknown — will be enriched below
                            "currency": "INR",
                            "url": ta.get("url"),
                            "source": "tavily_web",
                            "verified": False,
                        }
                        for ta in tavily_acts
                    ]
                    # Enrich prices via LLM
                    enriched = _enrich_activity_prices(raw_tavily, dest)
                    out.extend(enriched)
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
