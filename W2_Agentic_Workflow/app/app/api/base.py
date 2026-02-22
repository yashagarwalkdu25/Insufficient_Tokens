"""
Base API client with retry and logging.
Sync-only (httpx.Client) for Streamlit compatibility.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.database import get_db

logger = logging.getLogger(__name__)


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
)
def _get_with_retry(
    client: httpx.Client,
    url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Perform GET with retry on timeout and 5xx."""
    params = params or {}
    headers = headers or {}
    start = time.time()
    resp = client.get(url, params=params, headers=headers)
    latency_ms = int((time.time() - start) * 1000)
    logger.info("API request url=%s status=%s latency_ms=%s", url, resp.status_code, latency_ms)
    if resp.status_code >= 500:
        resp.raise_for_status()
    if resp.status_code == 429:
        raise httpx.HTTPStatusError("Rate limited", request=resp.request, response=resp)
    resp.raise_for_status()
    return resp.json()


class BaseAPIClient:
    """Sync HTTP client with retry and timeout."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def _get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        headers = headers or {}
        with httpx.Client(timeout=self.timeout) as client:
            return _get_with_retry(client, url, params=params, headers=headers)

    def _post(
        self,
        url: str,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        headers = headers or {}
        start = time.time()
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, data=data, headers=headers)
        latency_ms = int((time.time() - start) * 1000)
        logger.info("API POST url=%s status=%s latency_ms=%s", url, resp.status_code, latency_ms)
        resp.raise_for_status()
        return resp.json()


def _make_cache_key(*args: Any) -> str:
    """Deterministic hash from arguments for cache key."""
    payload = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class CachedAPIClient(BaseAPIClient):
    """L1 (in-memory) + L2 (SQLite) cache."""

    _l1_cache: dict[str, tuple[Any, float]] = {}

    def _cached_get(
        self,
        cache_key: str,
        url: str,
        params: Optional[dict[str, Any]],
        ttl: int,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        import time as t
        now = t.time()
        if cache_key in self._l1_cache:
            data, expiry = self._l1_cache[cache_key]
            if now < expiry:
                return data
            del self._l1_cache[cache_key]

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT response_json, expires_at FROM api_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row:
                from datetime import datetime
                expires_at = row["expires_at"]
                if expires_at:
                    exp = datetime.fromisoformat(expires_at)
                    if exp.timestamp() > now:
                        data = json.loads(row["response_json"])
                        self._l1_cache[cache_key] = (data, now + ttl)
                        return data
            data = self._get(url, params=params, headers=headers)
            from datetime import datetime, timedelta
            expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO api_cache (cache_key, response_json, created_at, expires_at) VALUES (?, ?, CURRENT_TIMESTAMP, ?)",
                (cache_key, json.dumps(data, default=str), expires_at),
            )
            conn.commit()
            self._l1_cache[cache_key] = (data, now + ttl)
            return data
        finally:
            conn.close()
