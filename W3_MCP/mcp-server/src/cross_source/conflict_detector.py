"""Build evidence matrix, cross-topic conflicts, and missing-signal counts."""
from __future__ import annotations

from typing import Any, Literal

from .signal_normalizer import group_by_logical, normalize_rows

Context = Literal["research", "earnings", "portfolio"]

EXPECTED: dict[Context, list[str]] = {
    "research": ["price_trend", "fundamental_strength", "news_sentiment", "macro_support"],
    "earnings": [
        "earnings_beat_miss",
        "post_results_reaction",
        "shareholding_change",
        "guidance_sentiment",
    ],
    "portfolio": [
        "sector_concentration",
        "mf_overlap",
        "macro_sensitivity",
        "sentiment_shift",
    ],
}


def _aggregate_status(rows: list[dict[str, Any]]) -> tuple[str, list[str], dict[str, str]]:
    """Return matrix status, source list, source->polarity (last wins per source)."""
    by_src: dict[str, str] = {}
    for r in rows:
        by_src[r["source"]] = r["polarity"]
    sources = list(by_src.keys())
    polarities = list(by_src.values())
    non_neutral = [p for p in polarities if p != "neutral"]
    if len(sources) == 0:
        return "missing", [], {}
    if len(sources) == 1:
        return "weakly_supported", sources, by_src
    uniq = set(non_neutral) if non_neutral else {"neutral"}
    if len(uniq) > 1:
        return "contradicted", sources, by_src
    return "confirmed", sources, by_src


def _polarity_map(groups: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """Dominant polarity per logical signal (first non-neutral row in group)."""
    out: dict[str, str] = {}
    for name, rows in groups.items():
        for r in rows:
            if r["polarity"] != "neutral":
                out[name] = r["polarity"]
                break
        else:
            out[name] = rows[0]["polarity"] if rows else "neutral"
    return out


def _cross_topic_research(pm: dict[str, str], sources_hint: dict[str, list[str]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    pt, ns, fs = pm.get("price_trend"), pm.get("news_sentiment"), pm.get("fundamental_strength")
    if pt == "bearish" and ns == "bullish":
        conflicts.append(
            {
                "topic": "price_vs_sentiment",
                "status": "contradiction",
                "sources": _merge_sources(sources_hint, "price_trend", "news_sentiment"),
                "details": "Price trend is negative while news sentiment reads positive.",
            }
        )
    if fs == "bullish" and ns == "bearish":
        conflicts.append(
            {
                "topic": "sentiment_vs_fundamentals",
                "status": "contradiction",
                "sources": _merge_sources(sources_hint, "fundamental_strength", "news_sentiment"),
                "details": "Fundamentals skew positive but news sentiment is negative.",
            }
        )
    return conflicts


def _cross_topic_earnings(pm: dict[str, str], sources_hint: dict[str, list[str]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    em, pr = pm.get("earnings_beat_miss"), pm.get("post_results_reaction")
    if em == "bullish" and pr == "bearish":
        conflicts.append(
            {
                "topic": "earnings_vs_price",
                "status": "contradiction",
                "sources": _merge_sources(sources_hint, "earnings_beat_miss", "post_results_reaction"),
                "details": "Earnings outcome skews positive but price reaction is negative.",
            }
        )
    if em == "bearish" and pr == "bullish":
        conflicts.append(
            {
                "topic": "earnings_vs_price",
                "status": "contradiction",
                "sources": _merge_sources(sources_hint, "earnings_beat_miss", "post_results_reaction"),
                "details": "Earnings miss or weak print but price moved up — expectations may be priced in.",
            }
        )
    return conflicts


def _cross_topic_portfolio(pm: dict[str, str], sources_hint: dict[str, list[str]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    macro, sector = pm.get("macro_sensitivity"), pm.get("sector_concentration")
    # macro favorable (bullish) but portfolio/sector stress (bearish concentration signal)
    if macro == "bullish" and sector == "bearish":
        conflicts.append(
            {
                "topic": "macro_vs_sector",
                "status": "contradiction",
                "sources": _merge_sources(sources_hint, "macro_sensitivity", "sector_concentration"),
                "details": "Macro backdrop looks supportive but portfolio shows concentration or sector stress.",
            }
        )
    return conflicts


def _merge_sources(
    hint: dict[str, list[str]], *logical_names: str
) -> list[str]:
    seen: list[str] = []
    for ln in logical_names:
        for s in hint.get(ln, []):
            if s not in seen:
                seen.append(s)
    return seen[:8] if seen else ["multiple"]


def _remap_portfolio_logical(normalized: list[dict[str, Any]]) -> None:
    """Risk crew often emits research-style logical names; map into portfolio matrix."""
    for r in normalized:
        ln = r.get("logical_name")
        if ln == "macro_support":
            r["logical_name"] = "macro_sensitivity"
        elif ln == "news_sentiment":
            r["logical_name"] = "sentiment_shift"


def build_evidence_and_conflicts(
    signals: list[dict[str, Any]] | None,
    context: Context,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """
    Returns evidence_matrix, structured conflicts (cross-topic only here),
    missing_expected_count.
    """
    normalized = normalize_rows(signals)
    if context == "portfolio":
        _remap_portfolio_logical(normalized)
    groups = group_by_logical(normalized)
    expected = EXPECTED[context]
    evidence_matrix: list[dict[str, Any]] = []
    sources_hint: dict[str, list[str]] = {}

    for logical in expected:
        rows = groups.get(logical, [])
        sources_hint[logical] = list({r["source"] for r in rows})
        if not rows:
            evidence_matrix.append(
                {
                    "signal": logical,
                    "status": "missing",
                    "sources": [],
                }
            )
            continue
        status, srcs, by_src = _aggregate_status(rows)
        source_values = {s: by_src[s] for s in srcs}
        evidence_matrix.append(
            {
                "signal": logical,
                "status": status,
                "sources": srcs,
                "source_values": source_values,
            }
        )

    pm = _polarity_map(groups)
    if context == "research":
        cross = _cross_topic_research(pm, sources_hint)
    elif context == "earnings":
        cross = _cross_topic_earnings(pm, sources_hint)
    else:
        cross = _cross_topic_portfolio(pm, sources_hint)

    missing_count = sum(1 for row in evidence_matrix if row["status"] == "missing")
    return evidence_matrix, cross, missing_count


def append_narrative_conflicts(
    base: list[dict[str, Any]],
    extra_strings: list[str] | None,
) -> list[dict[str, Any]]:
    if not extra_strings:
        return list(base)
    out = list(base)
    for i, text in enumerate(extra_strings):
        if not text or not str(text).strip():
            continue
        topic = "narrative" if i == 0 else f"narrative_{i}"
        out.append(
            {
                "topic": topic,
                "status": "contradiction",
                "sources": ["cross_source"],
                "details": str(text).strip(),
            }
        )
    return out
