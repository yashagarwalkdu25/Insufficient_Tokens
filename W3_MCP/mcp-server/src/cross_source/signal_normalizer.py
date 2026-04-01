"""Map raw tool signal rows to logical signal names and polarity labels."""
from __future__ import annotations

from typing import Any

# Threshold aligned with heuristic tools (e.g. sentiment buckets)
POLARITY_EPS = 0.15

# signal_type (lowercase keys) -> canonical logical name
_SIGNAL_TYPE_TO_LOGICAL: dict[str, str] = {
    "price": "price_trend",
    "price_trend": "price_trend",
    "fundamental": "fundamental_strength",
    "fundamentals": "fundamental_strength",
    "fundamental_strength": "fundamental_strength",
    "sentiment": "news_sentiment",
    "news": "news_sentiment",
    "news_sentiment": "news_sentiment",
    "macro": "macro_support",
    "macro_support": "macro_support",
    "earnings": "earnings_beat_miss",
    "earnings_beat_miss": "earnings_beat_miss",
    "beat_miss": "earnings_beat_miss",
    "market_reaction": "post_results_reaction",
    "post_results": "post_results_reaction",
    "post_results_reaction": "post_results_reaction",
    "shareholding": "shareholding_change",
    "shareholding_change": "shareholding_change",
    "fii": "shareholding_change",
    "guidance": "guidance_sentiment",
    "guidance_sentiment": "guidance_sentiment",
    "sector": "sector_concentration",
    "sector_concentration": "sector_concentration",
    "concentration": "sector_concentration",
    "mf_overlap": "mf_overlap",
    "overlap": "mf_overlap",
    "macro_sensitivity": "macro_sensitivity",
    "sentiment_shift": "sentiment_shift",
    "portfolio_stress": "portfolio_stress",
    "risk": "portfolio_stress",
}


def direction_to_polarity(direction: float | None) -> str:
    if direction is None:
        return "neutral"
    try:
        d = float(direction)
    except (TypeError, ValueError):
        return "neutral"
    if d > POLARITY_EPS:
        return "bullish"
    if d < -POLARITY_EPS:
        return "bearish"
    return "neutral"


def logical_name_for_row(row: dict[str, Any]) -> str:
    raw = (row.get("signal_type") or "").strip().lower().replace(" ", "_")
    if raw in _SIGNAL_TYPE_TO_LOGICAL:
        return _SIGNAL_TYPE_TO_LOGICAL[raw]
    if raw:
        return raw
    return "unknown"


def normalize_rows(signals: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return enriched rows: logical_name, polarity, source, confidence, direction."""
    if not signals:
        return []
    out: list[dict[str, Any]] = []
    for row in signals:
        if not isinstance(row, dict):
            continue
        src = str(row.get("source") or "unknown")
        direction = row.get("direction")
        logical = logical_name_for_row(row)
        pol = direction_to_polarity(direction if isinstance(direction, (int, float)) else None)
        conf = row.get("confidence")
        try:
            c = float(conf) if conf is not None else 0.5
        except (TypeError, ValueError):
            c = 0.5
        out.append(
            {
                "logical_name": logical,
                "polarity": pol,
                "source": src,
                "confidence": max(0.0, min(1.0, c)),
                "direction": float(direction) if isinstance(direction, (int, float)) else 0.0,
                "evidence": str(row.get("evidence") or ""),
            }
        )
    return out


def group_by_logical(normalized: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    g: dict[str, list[dict[str, Any]]] = {}
    for r in normalized:
        name = r["logical_name"]
        if name == "unknown":
            continue
        g.setdefault(name, []).append(r)
    return g
