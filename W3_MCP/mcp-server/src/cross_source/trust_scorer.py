"""Deterministic trust score from evidence matrix and conflicts (no LLM).

Penalties use structured cross-topic conflicts plus matrix contradictions.
LLM narrative strings appended as topic=narrative* are shown in the UI but do
not reduce the score (they often say \"no contradictions\", which is not a
data conflict).

Weakly_supported rows (single source per dimension) get partial credit so
aligned single-source research is not stuck at baseline minus false penalties.
"""
from __future__ import annotations

from typing import Any


def _scoring_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exclude narrative bullets — those are summaries, not detected conflicts."""
    out: list[dict[str, Any]] = []
    for c in conflicts:
        topic = str(c.get("topic") or "")
        if topic.startswith("narrative"):
            continue
        out.append(c)
    return out


def _signal_summary(
    evidence_matrix: list[dict[str, Any]], conflicts: list[dict[str, Any]]
) -> dict[str, int]:
    confirmations = sum(1 for r in evidence_matrix if r.get("status") == "confirmed")
    # Intra-signal multi-source disagreement
    contradicted_rows = sum(1 for r in evidence_matrix if r.get("status") == "contradicted")
    missing = sum(1 for r in evidence_matrix if r.get("status") == "missing")
    scoring_n = len(_scoring_conflicts(conflicts)) + contradicted_rows
    return {
        "confirmations": confirmations,
        "contradictions": scoring_n,
        "missing": missing,
    }


def _trust_numeric(
    evidence_matrix: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> int:
    base = 50
    n_confirm = sum(1 for r in evidence_matrix if r.get("status") == "confirmed")
    n_multi = sum(
        1
        for r in evidence_matrix
        if r.get("status") == "confirmed" and len(r.get("sources") or []) >= 2
    )
    n_weak = sum(1 for r in evidence_matrix if r.get("status") == "weakly_supported")
    n_missing = sum(1 for r in evidence_matrix if r.get("status") == "missing")
    contradicted_rows = sum(1 for r in evidence_matrix if r.get("status") == "contradicted")
    n_conflict_events = len(_scoring_conflicts(conflicts)) + contradicted_rows
    # Single-source dimensions still carry evidence; multi-source confirmation adds more.
    score = (
        base
        + 10 * n_confirm
        + 5 * n_multi
        + 5 * n_weak
        - 12 * n_conflict_events
        - 5 * n_missing
    )
    return max(0, min(100, int(round(score))))


def _reasoning_lines(
    evidence_matrix: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    for r in evidence_matrix:
        sig = r.get("signal", "")
        st = r.get("status", "")
        srcs = r.get("sources") or []
        if st == "confirmed" and srcs:
            lines.append(f"{sig} confirmed across {', '.join(srcs[:3])}")
        elif st == "contradicted" and srcs:
            lines.append(f"{sig} conflicted across sources ({', '.join(srcs[:3])})")
        elif st == "weakly_supported":
            lines.append(f"{sig} supported by a single source only")
        elif st == "missing":
            lines.append(f"No recent signal for {sig}")
    for c in conflicts[:6]:
        d = c.get("details") or ""
        if d:
            lines.append(d)
    return lines[:12]


def build_trust_payload(
    evidence_matrix: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "trust_score": _trust_numeric(evidence_matrix, conflicts),
        "signal_summary": _signal_summary(evidence_matrix, conflicts),
        "conflicts": conflicts,
        "evidence_matrix": evidence_matrix,
        "trust_score_reasoning": _reasoning_lines(evidence_matrix, conflicts),
    }
