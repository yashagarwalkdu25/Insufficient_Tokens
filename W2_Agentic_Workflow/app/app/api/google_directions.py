"""
Google Directions API for travel time between locations.
Haversine-based estimate_travel_time is the DEFAULT when no API key is configured.
"""
import math
from typing import Any

import httpx

from app.config import get_settings

# Approximate speeds (km/h) for fallback
SPEED_DRIVING = 40.0
SPEED_WALKING = 5.0
SPEED_AUTO = 25.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371  # Earth radius km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def estimate_travel_time(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    mode: str = "driving",
) -> dict[str, Any]:
    """
    Haversine-based travel time estimate (DEFAULT when Directions API key missing).
    Returns: {"duration_minutes": int, "distance_km": float, "mode": str}
    """
    km = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    if mode == "walking":
        speed = SPEED_WALKING
    elif mode == "transit":
        speed = SPEED_AUTO
    else:
        speed = SPEED_DRIVING
    duration_h = km / speed if speed else 0
    duration_min = int(round(duration_h * 60))
    return {"duration_minutes": max(1, duration_min), "distance_km": round(km, 2), "mode": mode}


class GoogleDirectionsClient:
    """Directions API + haversine fallback."""

    def __init__(self):
        self.timeout = 10.0

    def get_travel_time(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str = "driving",
    ) -> dict[str, Any]:
        """API call if key available; else estimate_travel_time (haversine)."""
        settings = get_settings()
        key = settings.GOOGLE_DIRECTIONS_KEY or settings.GOOGLE_PLACES_KEY
        if not key:
            return estimate_travel_time(origin_lat, origin_lng, dest_lat, dest_lng, mode)
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{origin_lat},{origin_lng}",
            "destination": f"{dest_lat},{dest_lng}",
            "mode": mode,
            "key": key,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
        except Exception:
            return estimate_travel_time(origin_lat, origin_lng, dest_lat, dest_lng, mode)
        routes = data.get("routes", [])
        if not routes:
            return estimate_travel_time(origin_lat, origin_lng, dest_lat, dest_lng, mode)
        leg = routes[0].get("legs", [{}])[0]
        duration_sec = leg.get("duration", {}).get("value", 0)
        distance_m = leg.get("distance", {}).get("value", 0)
        return {
            "duration_minutes": max(1, duration_sec // 60),
            "distance_km": round(distance_m / 1000, 2),
            "mode": mode,
        }

    def get_travel_times_batch(
        self,
        locations: list[tuple[float, float]],
    ) -> list[dict[str, Any]]:
        """Given ordered (lat, lng) pairs, return travel time dicts between consecutive pairs."""
        out = []
        for i in range(len(locations) - 1):
            a, b = locations[i], locations[i + 1]
            out.append(
                self.get_travel_time(a[0], a[1], b[0], b[1], mode="driving")
            )
        return out
