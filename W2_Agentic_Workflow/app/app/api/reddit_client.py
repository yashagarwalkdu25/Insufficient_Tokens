"""
Reddit API client for travel tips (OAuth2 script app).
Returns list[LocalTip] with source=api, verified=True.
No API key → return empty list (graceful skip).
"""
from __future__ import annotations

import base64
from typing import Any

import httpx

from app.config import get_settings
from app.models.local_intel import LocalTip

SUBREDDITS = ["IndiaTravel", "solotravel", "travel", "backpacking", "IncredibleIndia"]


class RedditClient:
    """OAuth2 client_credentials; search travel tips."""

    def __init__(self):
        self.timeout = 10.0
        self._token: str | None = None

    def _get_token(self) -> str | None:
        settings = get_settings()
        if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
            return None
        if self._token:
            return self._token
        creds = base64.b64encode(
            f"{settings.REDDIT_CLIENT_ID}:{settings.REDDIT_CLIENT_SECRET}".encode()
        ).decode()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    data={"grant_type": "client_credentials"},
                    headers={
                        "Authorization": f"Basic {creds}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                r.raise_for_status()
                data = r.json()
                self._token = data.get("access_token")
                return self._token
        except Exception:
            return None

    def search_travel_tips(self, destination: str, limit: int = 10) -> list[LocalTip]:
        """Search subreddits for destination; filter >5 upvotes; return list[LocalTip]."""
        token = self._get_token()
        if not token:
            return []
        out = []
        headers = {"Authorization": f"Bearer {token}", "User-Agent": "TripSaathi/1.0"}
        query = destination.replace(" ", "%20")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                for sub in SUBREDDITS[:3]:
                    r = client.get(
                        f"https://oauth.reddit.com/r/{sub}/search",
                        params={"q": query, "limit": min(limit, 10), "restrict_sr": "true", "sort": "relevance"},
                        headers=headers,
                    )
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    for child in data.get("data", {}).get("children", [])[:5]:
                        post = child.get("data", {})
                        if post.get("ups", 0) < 5:
                            continue
                        title = post.get("title", "")[:200]
                        content = (post.get("selftext") or "")[:500]
                        if not title and not content:
                            continue
                        permalink = post.get("permalink", "")
                        url = f"https://reddit.com{permalink}" if permalink else None
                        out.append(
                            LocalTip(
                                title=title,
                                content=content,
                                category="travel",
                                source_platform="reddit",
                                source_url=url,
                                upvotes=post.get("ups", 0),
                                source="api",
                                verified=True,
                            )
                        )
        except Exception:
            pass
        return out[:limit]
