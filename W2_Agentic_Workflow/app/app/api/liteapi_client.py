"""
LiteAPI client for hotel search.
/data/hotels for real hotel data (names, addresses, coordinates, stars).
/data/rates for pricing (may return empty on free tier).
Falls back to star-rating-based price estimates when rates unavailable.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings
from app.models.accommodation import HotelOption

logger = logging.getLogger(__name__)

BASE_URL = "https://api.liteapi.travel/v3.0"

# Price estimates per night based on star rating (INR)
_STAR_PRICE_MAP = {
    1: 800,
    1.5: 1000,
    2: 1500,
    2.5: 2000,
    3: 3000,
    3.5: 4500,
    4: 6000,
    4.5: 9000,
    5: 15000,
}


class LiteAPIClient:
    """Hotel search with API key in X-API-Key header."""

    def search_hotels(
        self,
        city_name: str,
        checkin_date: str,
        checkout_date: str,
        adults: int = 1,
        max_results: int = 8,
    ) -> list[HotelOption]:
        """Search hotels via LiteAPI. Returns real hotel data with estimated prices."""
        settings = get_settings()
        if not settings.LITEAPI_KEY:
            return []
        headers = {"X-API-Key": settings.LITEAPI_KEY}

        # Step 1: Get hotel metadata (names, addresses, coords, stars)
        try:
            with httpx.Client(timeout=12.0) as client:
                r = client.get(
                    f"{BASE_URL}/data/hotels",
                    params={"countryCode": "IN", "cityName": city_name},
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning("LiteAPI hotel search failed for %s: %s", city_name, e)
            return []

        hotels = data.get("data", []) or data.get("hotels", [])
        if not hotels:
            return []

        # Filter out deleted hotels
        active_hotels = [
            h for h in hotels
            if not h.get("deletedAt") and h.get("name")
        ]
        if not active_hotels:
            active_hotels = hotels  # fallback to all if filter removes everything

        ids = []
        for h in active_hotels[:max_results]:
            hid = h.get("id") or h.get("hotelId")
            if hid:
                ids.append(str(hid))

        # Step 2: Try to get rates (may fail on free tier)
        rates_by_id: dict[str, dict] = {}
        if ids:
            try:
                with httpx.Client(timeout=12.0) as client:
                    r2 = client.get(
                        f"{BASE_URL}/data/rates",
                        params={
                            "hotelIds": ",".join(ids),
                            "checkin": checkin_date,
                            "checkout": checkout_date,
                            "adults": adults,
                        },
                        headers=headers,
                    )
                    if r2.status_code == 200 and r2.content:
                        rates_data = r2.json()
                        for rate in rates_data.get("data", []) or rates_data.get("rates", []):
                            hid = rate.get("hotelId") or rate.get("id")
                            if hid:
                                rates_by_id[str(hid)] = rate
                        if rates_by_id:
                            logger.info("LiteAPI rates returned %d prices", len(rates_by_id))
            except Exception as e:
                logger.info("LiteAPI rates unavailable (free tier): %s", e)

        # Step 3: Build HotelOption list
        return self._build_options(
            active_hotels[:max_results], rates_by_id, checkin_date, checkout_date,
        )

    def _build_options(
        self,
        hotels: list[dict],
        rates_by_id: dict[str, dict],
        checkin: str,
        checkout: str,
    ) -> list[HotelOption]:
        try:
            d1 = datetime.strptime(checkin, "%Y-%m-%d")
            d2 = datetime.strptime(checkout, "%Y-%m-%d")
            nights = max(1, (d2 - d1).days)
        except Exception:
            nights = 1

        from app.api.booking_links import generate_booking_hotel_url
        city = hotels[0].get("city", "") if hotels else ""

        out = []
        for h in hotels:
            hid = str(h.get("id") or h.get("hotelId", ""))
            name = h.get("name", "Hotel")

            # Address
            addr = ""
            if isinstance(h.get("address"), str):
                addr = h["address"]
            elif isinstance(h.get("address"), dict):
                addr = h["address"].get("line1") or h["address"].get("full") or ""

            # Coordinates
            lat = h.get("latitude") or (h.get("location") or {}).get("latitude")
            lon = h.get("longitude") or (h.get("location") or {}).get("longitude")

            # Star rating
            stars = h.get("stars") or h.get("starRating") or 3

            # Price: try real rate first, fall back to star-based estimate
            rate = rates_by_id.get(hid, {})
            api_price = float(
                rate.get("price", {}).get("total", 0)
                or rate.get("totalPrice", 0)
                or 0
            )
            if api_price > 0:
                total_price = api_price
                price_per_night = total_price / nights
                price_source = "api"
            else:
                # Estimate from star rating
                price_per_night = _STAR_PRICE_MAP.get(
                    stars, _STAR_PRICE_MAP.get(round(stars), 3000)
                )
                total_price = price_per_night * nights
                price_source = "estimated"

            # Contact info
            phone = h.get("phone") or (h.get("contact") or {}).get("phone")

            # Booking URL
            booking_url = (
                rate.get("bookingUrl")
                or h.get("url")
                or generate_booking_hotel_url(city or name, checkin, checkout)
            )

            # Image
            main_photo = h.get("main_photo")
            images = h.get("images") or []
            image_url = main_photo or (images[0].get("url") if images else None)

            # User rating
            rating = h.get("rating")

            out.append(
                HotelOption(
                    name=name,
                    address=addr or None,
                    latitude=float(lat) if lat is not None else None,
                    longitude=float(lon) if lon is not None else None,
                    star_rating=stars,
                    price_per_night=price_per_night,
                    total_price=total_price,
                    currency="INR",
                    amenities=h.get("amenities", []) or [],
                    booking_url=booking_url,
                    image_url=image_url,
                    phone=phone,
                    email=h.get("email"),
                    contact_info=f"{addr}" if addr else None,
                    check_in_time=h.get("checkInTime"),
                    check_out_time=h.get("checkOutTime"),
                    source=price_source,
                    verified=price_source == "api",
                )
            )
        return out[:8]
