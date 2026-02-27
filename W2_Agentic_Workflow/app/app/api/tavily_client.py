"""Tavily web search client for real-time travel data retrieval.

Used as the primary fallback when specialized APIs (Amadeus, LiteAPI, Google Places, etc.)
fail or are unavailable. Returns structured search results from the web.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class TavilySearchClient:
    """Wrapper around the Tavily Search API for travel-related web searches."""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.TAVILY_API_KEY
        self._available = bool(self._api_key)

    @property
    def available(self) -> bool:
        return self._available

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        topic: str = "general",
    ) -> dict[str, Any]:
        """Run a Tavily web search and return results.

        Returns dict with keys: answer (str), results (list of dicts with title/url/content).
        Returns empty dict on failure.
        """
        if not self._available:
            logger.warning("Tavily API key not configured; skipping web search")
            return {}

        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=self._api_key)
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=include_answer,
                topic=topic,
            )
            return response
        except Exception as e:
            logger.warning("Tavily search failed for '%s': %s", query, e)
            return {}

    def search_hotels(self, destination: str, checkin: str, checkout: str, style: str = "midrange") -> list[dict]:
        """Search for real hotel options via Tavily, then parse with LLM."""
        query = f"best {style} hotels in {destination} India prices per night {checkin} booking"
        result = self.search(query, max_results=5, search_depth="advanced")
        if not result:
            return []

        answer = result.get("answer", "")
        raw_results = result.get("results", [])
        raw_text = f"Answer: {answer}\n"
        for r in raw_results:
            raw_text += f"- {r.get('title', '')}: {r.get('content', '')[:200]}\n"

        settings = get_settings()
        if settings.has_openai and raw_text.strip():
            try:
                import json as _json
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                r = client.chat.completions.create(
                    model=settings.GPT4O_MINI_MODEL,
                    messages=[
                        {"role": "system", "content": (
                            "Extract hotel information from search results. Return a JSON array of hotels. "
                            "Each hotel: {\"name\": \"...\", \"price_per_night\": 0, \"star_rating\": 0, "
                            "\"description\": \"...\", \"location\": \"...\"}. "
                            "Estimate realistic INR price_per_night from context. "
                            f"Style: {style}. Use realistic Indian hotel prices."
                        )},
                        {"role": "user", "content": raw_text[:2000]},
                    ],
                    temperature=0.2,
                )
                content = (r.choices[0].message.content or "").strip()
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()
                parsed = _json.loads(content)
                if isinstance(parsed, list):
                    hotels = []
                    for i, h in enumerate(parsed[:5]):
                        booking_url = raw_results[i].get("url", "") if i < len(raw_results) else ""
                        hotels.append({
                            "name": h.get("name", "Hotel"),
                            "price_per_night": float(h.get("price_per_night", 0)),
                            "star_rating": h.get("star_rating"),
                            "description": h.get("description", "")[:200],
                            "location": h.get("location", destination),
                            "booking_url": booking_url,
                            "source": "tavily_web",
                            "verified": False,
                        })
                    if hotels:
                        return hotels
            except Exception as e:
                logger.warning("LLM hotel parsing failed: %s", e)

        hotels = []
        for r in raw_results:
            hotels.append({
                "name": r.get("title", "Hotel"),
                "description": r.get("content", "")[:200],
                "booking_url": r.get("url", ""),
                "source": "tavily_web",
                "verified": False,
            })
        return hotels

    def search_flights(self, origin: str, destination: str, date: str) -> list[dict]:
        """Search for real flight options via Tavily."""
        query = f"flights from {origin} to {destination} India {date} prices airlines"
        result = self.search(query, max_results=5, search_depth="advanced")
        if not result:
            return []

        flights = []
        results = result.get("results", [])

        for r in results:
            flights.append({
                "title": r.get("title", "Flight"),
                "content": r.get("content", "")[:200],
                "booking_url": r.get("url", ""),
                "source": "tavily_web",
                "verified": False,
            })

        return flights

    def search_activities(self, destination: str, interests: list[str] | None = None) -> list[dict]:
        """Search for real activities via Tavily, then parse with LLM into structured data."""
        interest_str = ", ".join(interests) if interests else "sightseeing attractions"
        query = f"top attractions things to do in {destination} India {interest_str} entry fees timings"
        result = self.search(query, max_results=8, search_depth="advanced")
        if not result:
            return []

        answer = result.get("answer", "")
        raw_results = result.get("results", [])
        raw_text = f"Answer: {answer}\n"
        for r in raw_results:
            raw_text += f"- {r.get('title', '')}: {r.get('content', '')[:250]}\n"

        settings = get_settings()
        if settings.has_openai and raw_text.strip():
            try:
                import json as _json
                from openai import OpenAI
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                r = client.chat.completions.create(
                    model=settings.GPT4O_MINI_MODEL,
                    messages=[
                        {"role": "system", "content": (
                            f"Extract individual attractions/activities in {destination} from search results. "
                            "Return a JSON array. Each item: "
                            "{\"name\": \"Actual Place Name\", \"description\": \"1-2 sentences\", "
                            "\"category\": \"monument/temple/market/restaurant/park/museum/adventure/other\", "
                            "\"price\": 0, \"duration_hours\": 2, \"opening_hours\": \"...\"}. "
                            "Use realistic Indian prices in INR (entry fees, costs). "
                            "Extract 8-12 SPECIFIC, NAMED places — NOT web page titles. "
                            "Include a mix: 2-3 restaurants, major attractions, markets, hidden gems."
                        )},
                        {"role": "user", "content": raw_text[:3000]},
                    ],
                    temperature=0.3,
                )
                content = (r.choices[0].message.content or "").strip()
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()
                parsed = _json.loads(content)
                if isinstance(parsed, list):
                    activities = []
                    for a in parsed[:12]:
                        activities.append({
                            "name": a.get("name", "Activity"),
                            "description": a.get("description", ""),
                            "category": a.get("category", "general"),
                            "price": float(a.get("price", 0)),
                            "duration_hours": float(a.get("duration_hours", 2)),
                            "opening_hours": a.get("opening_hours"),
                            "currency": "INR",
                            "source": "tavily_web",
                            "verified": False,
                        })
                    if activities:
                        return activities
            except Exception as e:
                logger.warning("LLM activity parsing failed: %s", e)

        activities = []
        for r in raw_results:
            activities.append({
                "name": r.get("title", "Activity"),
                "description": r.get("content", "")[:300],
                "url": r.get("url", ""),
                "source": "tavily_web",
                "verified": False,
            })
        return activities

    def search_weather(self, destination: str, start_date: str, end_date: str) -> dict[str, Any]:
        """Search for weather information via Tavily."""
        query = f"weather forecast {destination} India {start_date} to {end_date} temperature conditions"
        result = self.search(query, max_results=3, search_depth="basic")
        if not result:
            return {}

        return {
            "answer": result.get("answer", ""),
            "sources": [{"title": r.get("title"), "url": r.get("url")} for r in result.get("results", [])],
            "source": "tavily_web",
        }

    def search_local_tips(self, destination: str) -> list[dict]:
        """Search for local travel tips and hidden gems via Tavily."""
        query = f"local travel tips hidden gems {destination} India insider advice what tourists miss"
        result = self.search(query, max_results=5, search_depth="advanced")
        if not result:
            return []

        tips = []
        results = result.get("results", [])

        for r in results:
            tips.append({
                "title": r.get("title", "Tip"),
                "content": r.get("content", "")[:300],
                "url": r.get("url", ""),
                "source": "tavily_web",
                "verified": False,
            })

        return tips

    def search_hidden_gems(self, destination: str, interests: list[str] | None = None) -> list[dict]:
        """Search for hidden gems and lesser-known spots via Tavily."""
        interest_str = ", ".join(interests[:3]) if interests else "nature, culture, food"
        query = (
            f"hidden gems lesser known places {destination} India off beaten path "
            f"secret spots locals recommend {interest_str} underrated"
        )
        result = self.search(query, max_results=6, search_depth="advanced")
        if not result:
            return []
        return [
            {
                "title": r.get("title", "Hidden Gem"),
                "content": r.get("content", "")[:400],
                "url": r.get("url", ""),
                "source": "tavily_web",
            }
            for r in result.get("results", [])
        ]

    def search_festivals(self, destination: str, start_date: str, end_date: str) -> list[dict]:
        """Search for festivals and events via Tavily."""
        query = f"festivals events celebrations in {destination} India between {start_date} and {end_date}"
        result = self.search(query, max_results=5, search_depth="advanced")
        if not result:
            return []

        events = []
        results = result.get("results", [])

        for r in results:
            events.append({
                "name": r.get("title", "Event"),
                "description": r.get("content", "")[:300],
                "url": r.get("url", ""),
                "source": "tavily_web",
                "verified": False,
            })

        return events

    def search_transport_prices(self, origin: str, destination: str) -> dict[str, Any]:
        """Search for transport prices between cities via Tavily."""
        query = f"travel from {origin} to {destination} India flight train bus prices 2025"
        result = self.search(query, max_results=5, search_depth="advanced")
        if not result:
            return {}

        return {
            "answer": result.get("answer", ""),
            "sources": [
                {"title": r.get("title"), "content": r.get("content", "")[:200], "url": r.get("url")}
                for r in result.get("results", [])
            ],
            "source": "tavily_web",
        }
