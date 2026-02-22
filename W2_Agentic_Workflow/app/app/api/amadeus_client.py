"""
Amadeus Self-Service API client for flight search.
Uses test API base URL. Returns list[FlightOption] with source=api, verified=True.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.api.base import CachedAPIClient, _make_cache_key
from app.config import get_settings
from app.models.transport import FlightOption, FlightSegment

BASE_URL = "https://test.api.amadeus.com"


class AmadeusClient(CachedAPIClient):
    """OAuth2 + flight search with caching."""

    def __init__(self):
        super().__init__(timeout=10.0)
        self._token: str | None = None
        self._token_expiry: float = 0

    def _ensure_token(self) -> str:
        import time
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        settings = get_settings()
        if not settings.AMADEUS_CLIENT_ID or not settings.AMADEUS_CLIENT_SECRET:
            raise ValueError("Amadeus credentials not configured")
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{BASE_URL}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.AMADEUS_CLIENT_ID,
                    "client_secret": settings.AMADEUS_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 1799)
        return self._token

    def search_flights(
        self,
        origin_iata: str,
        destination_iata: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        max_results: int = 5,
    ) -> list[FlightOption]:
        """Search flights; return list[FlightOption]. Empty list on missing key or API error."""
        settings = get_settings()
        if not settings.has_amadeus:
            return []
        try:
            self._ensure_token()
        except Exception:
            return []

        url = f"{BASE_URL}/v2/shopping/flight-offers"
        params: dict[str, Any] = {
            "originLocationCode": origin_iata.upper(),
            "destinationLocationCode": destination_iata.upper(),
            "departureDate": departure_date,
            "adults": adults,
            "max": max_results,
        }
        if return_date:
            params["returnDate"] = return_date

        cache_key = _make_cache_key("amadeus_flights", url, params)
        ttl = settings.FLIGHT_CACHE_TTL
        headers = {"Authorization": f"Bearer {self._ensure_token()}"}
        try:
            raw = self._cached_get(cache_key, url, params, ttl, headers=headers)
        except Exception:
            return []

        return self._parse_offers(raw)

    def _parse_offers(self, data: dict) -> list[FlightOption]:
        offers = data.get("data") or []
        out = []
        for o in offers[:5]:
            try:
                segs = o.get("itineraries", [{}])[0].get("segments", [])
                if not segs:
                    continue
                s = segs[0]
                dep = s.get("departure", {})
                arr = s.get("arrival", {})
                dep_time = dep.get("at", "")[:19].replace("T", " ")
                arr_time = arr.get("at", "")[:19].replace("T", " ")
                try:
                    dep_dt = datetime.fromisoformat(dep_time.replace(" ", "T"))
                    arr_dt = datetime.fromisoformat(arr_time.replace(" ", "T"))
                except Exception:
                    continue
                duration_min = int((arr_dt - dep_dt).total_seconds() / 60)
                outbound = FlightSegment(
                    airline=s.get("carrierCode", ""),
                    flight_number=s.get("number", ""),
                    departure_airport=dep.get("iataCode", ""),
                    arrival_airport=arr.get("iataCode", ""),
                    departure_time=dep_dt,
                    arrival_time=arr_dt,
                    duration_minutes=duration_min,
                )
                return_seg = None
                if len(o.get("itineraries", [])) > 1:
                    ret_segs = o["itineraries"][1].get("segments", [])
                    if ret_segs:
                        r = ret_segs[0]
                        rdep = r.get("departure", {})
                        rarr = r.get("arrival", {})
                        rdep_dt = datetime.fromisoformat(rdep.get("at", "")[:19].replace("T", "T"))
                        rarr_dt = datetime.fromisoformat(rarr.get("at", "")[:19].replace("T", "T"))
                        return_seg = FlightSegment(
                            airline=r.get("carrierCode", ""),
                            flight_number=r.get("number", ""),
                            departure_airport=rdep.get("iataCode", ""),
                            arrival_airport=rarr.get("iataCode", ""),
                            departure_time=rdep_dt,
                            arrival_time=rarr_dt,
                            duration_minutes=int((rarr_dt - rdep_dt).total_seconds() / 60),
                        )
                price = float(o.get("price", {}).get("grandTotal", 0))
                currency = o.get("price", {}).get("currency", "INR")
                # Convert common currencies to INR
                if currency == "EUR":
                    price = round(price * 93, 2)  # 1 EUR ≈ 93 INR
                    currency = "INR"
                elif currency == "USD":
                    price = round(price * 83, 2)  # 1 USD ≈ 83 INR
                    currency = "INR"
                elif currency == "GBP":
                    price = round(price * 105, 2)
                    currency = "INR"
                out.append(
                    FlightOption(
                        outbound=outbound,
                        return_segment=return_seg,
                        total_price=price,
                        currency=currency,
                        booking_url=None,
                        source="api",
                        verified=True,
                    )
                )
            except Exception:
                continue
        return out
