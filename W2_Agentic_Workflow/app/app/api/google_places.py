"""
Google Places API (New) client for activities and restaurants.
Extracts opening_hours, phone, address. Returns Activity/Restaurant with source=api, verified=True.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.models.activity import Activity, Restaurant

PLACES_BASE = "https://places.googleapis.com/v1"


def _parse_opening_hours(periods: list[dict] | None) -> dict[str, str] | None:
    """Convert regularOpeningHours.periods to dict e.g. {'Monday': '09:00-18:00'}."""
    if not periods:
        return None
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out = {}
    for i, p in enumerate(periods):
        if i >= 7:
            break
        open_t = p.get("open", {}).get("hour", 0) or 0
        open_m = p.get("open", {}).get("minute", 0) or 0
        close_t = p.get("close", {}).get("hour", 18) or 18
        close_m = p.get("close", {}).get("minute", 0) or 0
        out[day_names[i]] = f"{open_t:02d}:{open_m:02d}-{close_t:02d}:{close_m:02d}"
    return out if out else None


class GooglePlacesClient:
    """Places API (New) with text search. Uses GOOGLE_PLACES_KEY."""

    def __init__(self):
        self.timeout = 10.0

    def _request(self, url: str, body: dict) -> dict:
        settings = get_settings()
        if not settings.GOOGLE_PLACES_KEY:
            return {}
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.GOOGLE_PLACES_KEY,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, json=body, headers=headers)
                r.raise_for_status()
                return r.json()
        except Exception:
            return {}

    def search_activities(
        self,
        query: str,
        latitude: float,
        longitude: float,
        radius_m: int = 5000,
        max_results: int = 10,
    ) -> list[Activity]:
        """Text search for activities; returns list[Activity] with opening_hours, phone, address."""
        url = f"{PLACES_BASE}/places:searchText"
        body = {
            "textQuery": query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_m,
                }
            },
            "maxResultCount": max_results,
        }
        data = self._request(url, body)
        places = data.get("places", [])
        out = []
        for p in places:
            try:
                loc = p.get("location", {}) or {}
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                addr = p.get("formattedAddress") or p.get("address", {}).get("formattedAddress")
                phone = p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber")
                hours = _parse_opening_hours(p.get("regularOpeningHours", {}).get("periods"))
                price = 0
                if p.get("priceLevel"):
                    price = {"INEXPENSIVE": 200, "MODERATE": 500, "EXPENSIVE": 1500}.get(
                        p["priceLevel"], 500
                    )
                out.append(
                    Activity(
                        name=p.get("displayName", {}).get("text", "Place"),
                        description=p.get("editorialSummary", {}).get("text") if isinstance(p.get("editorialSummary"), dict) else None,
                        category=query[:50],
                        duration_hours=2.0,
                        price=price,
                        currency="INR",
                        latitude=lat,
                        longitude=lng,
                        rating=p.get("rating"),
                        address=addr,
                        booking_url=p.get("websiteUri"),
                        opening_hours=hours,
                        phone=phone,
                        best_time=None,
                        source="api",
                        verified=True,
                    )
                )
            except Exception:
                continue
        return out

    def search_restaurants(
        self,
        latitude: float,
        longitude: float,
        radius_m: int = 2000,
        max_results: int = 5,
    ) -> list[Restaurant]:
        """Search for restaurants near location."""
        url = f"{PLACES_BASE}/places:searchText"
        body = {
            "textQuery": "restaurants food",
            "locationBias": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_m,
                }
            },
            "maxResultCount": max_results,
        }
        data = self._request(url, body)
        places = data.get("places", [])
        out = []
        for p in places:
            try:
                loc = p.get("location", {}) or {}
                addr = p.get("formattedAddress") or (p.get("address", {}) or {}).get("formattedAddress")
                phone = p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber")
                hours = _parse_opening_hours(p.get("regularOpeningHours", {}).get("periods"))
                price_level = p.get("priceLevel")
                out.append(
                    Restaurant(
                        name=p.get("displayName", {}).get("text", "Restaurant"),
                        cuisine="Various",
                        price_level=price_level,
                        rating=p.get("rating"),
                        address=addr,
                        latitude=loc.get("latitude"),
                        longitude=loc.get("longitude"),
                        phone=phone,
                        opening_hours=hours,
                        source="api",
                        verified=True,
                    )
                )
            except Exception:
                continue
        return out
