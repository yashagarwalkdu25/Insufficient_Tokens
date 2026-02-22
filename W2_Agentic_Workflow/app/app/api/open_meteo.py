"""Open-Meteo weather API client — completely free, no API key needed.

Provides 16-day weather forecast with daily temperature, precipitation,
wind speed, and weather condition codes. Works globally.

API docs: https://open-meteo.com/en/docs
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes → human-readable condition
_WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 16,
) -> dict[str, Any]:
    """Fetch daily weather forecast from Open-Meteo.

    Returns dict keyed by date (YYYY-MM-DD):
        {
            "2026-03-15": {
                "temp_min": 18.5,
                "temp_max": 32.1,
                "condition": "Partly cloudy",
                "rain_probability": 20,
                "precipitation_mm": 0.5,
                "wind_speed_max": 15.2,
                "weather_code": 2
            },
            ...
        }
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "precipitation_sum",
            "weathercode",
            "windspeed_10m_max",
        ]),
        "forecast_days": min(days, 16),
        "timezone": "Asia/Kolkata",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(BASE_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("Open-Meteo API failed: %s", e)
        return {}

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    rain_prob = daily.get("precipitation_probability_max", [])
    precip = daily.get("precipitation_sum", [])
    codes = daily.get("weathercode", [])
    wind = daily.get("windspeed_10m_max", [])

    forecast: dict[str, Any] = {}
    for i, date_str in enumerate(dates):
        code = codes[i] if i < len(codes) else 0
        forecast[date_str] = {
            "temp_min": temp_min[i] if i < len(temp_min) else None,
            "temp_max": temp_max[i] if i < len(temp_max) else None,
            "condition": _WMO_CODES.get(code, "Unknown"),
            "rain_probability": rain_prob[i] if i < len(rain_prob) else 0,
            "precipitation_mm": precip[i] if i < len(precip) else 0,
            "wind_speed_max": wind[i] if i < len(wind) else None,
            "weather_code": code,
        }

    logger.info(
        "Open-Meteo returned %d-day forecast for (%.2f, %.2f)",
        len(forecast), latitude, longitude,
    )
    return forecast


def get_weather_summary(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> str:
    """Return a human-readable weather summary for the trip date range."""
    fc = get_forecast(latitude, longitude, days=16)

    parts = []
    for date_key in sorted(fc.keys()):
        if start_date <= date_key <= end_date:
            w = fc[date_key]
            parts.append(
                f"{date_key}: {w.get('temp_min', '?')}-{w.get('temp_max', '?')}C, "
                f"{w.get('condition', '')}, rain {w.get('rain_probability', 0)}%"
            )

    if not parts:
        return "No forecast available for the requested dates."
    return " | ".join(parts)
