"""
OpenWeatherMap 5-day forecast client.
Returns daily summary (temp_min, temp_max, condition, rain_probability).
No hardcoded fallback data — returns empty when API key missing or call fails.
"""
from typing import Any

import httpx

from app.config import get_settings


class WeatherClient:
    """OpenWeatherMap forecast; returns empty dict when key missing or API fails."""

    def __init__(self):
        self.timeout = 10.0

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 5,
    ) -> dict[str, Any]:
        """Return dict keyed by date with temp_min, temp_max, condition, rain_probability."""
        settings = get_settings()
        if not settings.OPENWEATHERMAP_KEY:
            return {}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.get(
                    "https://api.openweathermap.org/data/2.5/forecast",
                    params={
                        "lat": latitude,
                        "lon": longitude,
                        "appid": settings.OPENWEATHERMAP_KEY,
                        "units": "metric",
                        "cnt": days * 8,
                    },
                )
                r.raise_for_status()
                data = r.json()
        except Exception:
            return {}

        list_ = data.get("list", [])
        by_date: dict[str, Any] = {}
        for item in list_:
            dt_str = item.get("dt_txt", "")[:10]
            if not dt_str:
                continue
            if dt_str not in by_date:
                by_date[dt_str] = {
                    "temp_min": item.get("main", {}).get("temp"),
                    "temp_max": item.get("main", {}).get("temp"),
                    "condition": (item.get("weather", [{}])[0].get("main") or "Clear"),
                    "rain_probability": int(item.get("pop", 0) * 100),
                }
            else:
                t = item.get("main", {}).get("temp")
                if t is not None:
                    by_date[dt_str]["temp_min"] = min(by_date[dt_str]["temp_min"], t)
                    by_date[dt_str]["temp_max"] = max(by_date[dt_str]["temp_max"], t)
        return by_date

    def get_weather_summary(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> str:
        """Human-readable weather summary for the date range."""
        f = self.get_forecast(latitude, longitude, days=10)
        parts = []
        for date_key in sorted(f.keys()):
            if start_date <= date_key <= end_date:
                w = f[date_key]
                parts.append(
                    f"{date_key}: {w.get('temp_min', '?')}-{w.get('temp_max', '?')}°C, "
                    f"{w.get('condition', '')}, rain {w.get('rain_probability', 0)}%"
                )
        return " | ".join(parts) if parts else "No forecast available."
