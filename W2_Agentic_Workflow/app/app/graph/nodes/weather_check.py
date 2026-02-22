"""Weather check agent: OpenWeatherMap + Nominatim geocoding + LLM seasonal fallback."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any

import httpx

from app.api.weather_client import WeatherClient
from app.config import get_settings
from app.data.india_cities import get_city

logger = logging.getLogger(__name__)


def _geocode_city(city_name: str) -> tuple[float | None, float | None]:
    """Resolve city to (lat, lon) using india_cities -> Nominatim -> GPT-4o-mini."""
    # 1. Try curated INDIA_CITIES database first
    city = get_city(city_name)
    if city and city.get("latitude") and city.get("longitude"):
        logger.info("Geocoded %s via india_cities DB", city_name)
        return city["latitude"], city["longitude"]

    # 2. Try Nominatim free geocoding API
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"{city_name} India", "format": "json", "limit": 1},
                headers={"User-Agent": "YatraAI/1.0 (travel-planner)"},
            )
            r.raise_for_status()
            results = r.json()
            if results and len(results) > 0:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                logger.info("Geocoded %s via Nominatim: lat=%s, lon=%s", city_name, lat, lon)
                return lat, lon
    except Exception as e:
        logger.warning("Nominatim geocoding failed for %s: %s", city_name, e)

    # 3. Fallback: ask GPT-4o-mini for approximate coordinates
    settings = get_settings()
    if settings.has_openai:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            resp = openai_client.chat.completions.create(
                model=settings.GPT4O_MINI_MODEL,
                messages=[{"role": "user", "content": (
                    f"What are the approximate latitude and longitude coordinates of {city_name}, India? "
                    f"Return ONLY a JSON object: {{\"latitude\": <float>, \"longitude\": <float>}}"
                )}],
                temperature=0.0,
            )
            content = (resp.choices[0].message.content or "").strip()
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            coords = json.loads(content)
            lat = float(coords["latitude"])
            lon = float(coords["longitude"])
            logger.info("Geocoded %s via GPT-4o-mini: lat=%s, lon=%s", city_name, lat, lon)
            return lat, lon
        except Exception as e:
            logger.warning("LLM geocoding failed for %s: %s", city_name, e)

    return None, None


def _llm_seasonal_weather(city_name: str, start_date: str, end_date: str) -> dict[str, Any] | None:
    """Use GPT-4o-mini to generate a seasonal weather summary when forecast API cannot cover the date range."""
    settings = get_settings()
    if not settings.has_openai:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": (
                f"Provide a realistic weather forecast for {city_name}, India from {start_date} to {end_date}.\n"
                f"Based on historical seasonal data for this city and these months, generate day-by-day weather.\n\n"
                f"Return ONLY a JSON object with this structure:\n"
                f'{{"forecast": {{"YYYY-MM-DD": {{"temp_min": <int>, "temp_max": <int>, '
                f'"condition": "<Clear/Clouds/Rain/Haze/etc>", "rain_probability": <int 0-100>}}, ...}}, '
                f'"summary": "<2-3 sentence overall weather summary for the trip>"}}\n\n'
                f"Include EVERY date from {start_date} to {end_date}. Use realistic temperatures in Celsius "
                f"based on {city_name}'s actual climate for these months."
            )}],
            temperature=0.3,
        )
        content = (resp.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM seasonal weather failed for %s: %s", city_name, e)
        return None


def check_weather_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: get weather forecast for destination. Returns partial state update."""
    start = time.time()

    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    start_date = req.get("start_date")
    end_date = req.get("end_date")
    if not dest:
        return {
            "weather": None,
            "agent_decisions": [{
                "agent_name": "weather_check",
                "action": "forecast",
                "reasoning": "No destination — skipping weather check.",
                "result_summary": "Skipped",
                "tokens_used": 0,
                "latency_ms": 0,
            }],
        }

    # ── Geocode the city (multi-strategy) ──────────────────────────────────
    lat, lon = _geocode_city(dest)
    if lat is None or lon is None:
        # Ultimate fallback: Delhi coords (better than crashing)
        lat, lon = 28.6, 77.2
        logger.warning("Could not geocode %s; using Delhi coords as last resort", dest)

    start_str = start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date)
    end_str = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)

    # ── Calculate trip duration to decide strategy ─────────────────────────
    try:
        sd = start_date if isinstance(start_date, date) else date.fromisoformat(str(start_date)[:10])
        ed = end_date if isinstance(end_date, date) else date.fromisoformat(str(end_date)[:10])
        trip_days = (ed - sd).days + 1
    except Exception:
        trip_days = 5

    today = date.today()
    try:
        days_until_start = (sd - today).days
    except Exception:
        days_until_start = 0

    forecast: dict[str, Any] = {}
    summary: str = ""
    reasoning_parts: list[str] = []
    tokens_used = 0

    # ── Strategy 1: Open-Meteo (free, no key, 16-day forecast) ────────────
    try:
        from app.api.open_meteo import get_forecast as open_meteo_forecast
        from app.api.open_meteo import get_weather_summary as open_meteo_summary

        om_forecast = open_meteo_forecast(lat, lon, days=16)
        # Filter to trip dates only
        for dk in sorted(om_forecast.keys()):
            if start_str <= dk <= end_str:
                forecast[dk] = om_forecast[dk]

        if forecast:
            summary = open_meteo_summary(lat, lon, start_str, end_str)
            reasoning_parts.append(
                f"Open-Meteo API returned {len(forecast)}-day forecast for {dest} "
                f"(lat={lat:.2f}, lon={lon:.2f}). Free real-time weather data."
            )
    except Exception as e:
        logger.warning("Open-Meteo failed for %s: %s", dest, e)

    # ── Strategy 2: OpenWeatherMap (if Open-Meteo missed dates) ───────────
    if not forecast and days_until_start < 5:
        try:
            client = WeatherClient()
            owm_forecast = client.get_forecast(lat, lon, days=7)
            owm_summary = client.get_weather_summary(lat, lon, start_str, end_str)

            if owm_forecast:
                forecast.update(owm_forecast)
            if owm_summary and owm_summary != "No forecast available.":
                summary = owm_summary
                reasoning_parts.append(
                    f"OpenWeatherMap forecast for {dest} (lat={lat:.2f}, lon={lon:.2f})."
                )
        except Exception as e:
            logger.warning("OpenWeatherMap failed: %s", e)

    # ── Strategy 3: LLM seasonal weather (for trips > 16 days out) ────────
    if not forecast:
        llm_result = _llm_seasonal_weather(dest, start_str, end_str)
        if llm_result:
            llm_forecast = llm_result.get("forecast", {})
            llm_summary = llm_result.get("summary", "")

            for date_key, weather_data in llm_forecast.items():
                if date_key not in forecast:
                    forecast[date_key] = weather_data

            if not summary or summary == "No forecast available.":
                summary = llm_summary

            reasoning_parts.append(
                f"Used GPT-4o-mini seasonal weather for {dest} "
                f"({trip_days}-day trip, dates > 16 days out)."
            )
            tokens_used = 200
        else:
            if not summary or summary == "No forecast available.":
                summary = (
                    f"Weather data unavailable for {dest} ({start_str} to {end_str}). "
                    f"Please check local weather forecasts closer to your travel dates."
                )
            reasoning_parts.append(
                f"Could not retrieve weather for {dest}; generic advisory provided."
            )

    latency_ms = int((time.time() - start) * 1000)
    decision = {
        "agent_name": "weather_check",
        "action": "forecast",
        "reasoning": " ".join(reasoning_parts) or f"Retrieved weather for {dest}.",
        "result_summary": summary[:100] if summary else "No data",
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    return {"weather": {"forecast": forecast, "summary": summary}, "agent_decisions": [decision]}
