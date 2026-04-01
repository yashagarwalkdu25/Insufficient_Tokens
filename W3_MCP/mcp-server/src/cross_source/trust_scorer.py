"""Deterministic trust score from evidence matrix and conflicts (no LLM).

Penalty uses len(conflicts) plus per-matrix-row contradicted count (intra-source
disagreement); narrative strings are already folded into conflicts.
"""
from __future__ import annotations

from typing import Any

# Scoring uses matrix row statuses + len(conflicts); narrative strings add conflicts only (no double -12 for same row).


def _signal_summary(
    evidence_matrix: list[dict[str, Any]], conflicts: list[dict[str, Any]]
) -> dict[str, int]:
    confirmations = sum(1 for r in evidence_matrix if r.get("status") == "confirmed")
    # Intra-signal multi-source disagreement
    contradicted_rows = sum(1 for r in evidence_matrix if r.get("status") == "contradicted")
    missing = sum(1 for r in evidence_matrix if r.get("status") == "missing")
    return {
        "confirmations": confirmations,
        "contradictions": len(conflicts) + contradicted_rows,
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
    n_missing = sum(1 for r in evidence_matrix if r.get("status") == "missing")
    contradicted_rows = sum(1 for r in evidence_matrix if r.get("status") == "contradicted")
    n_conflict_events = len(conflicts) + contradicted_rows
    score = base + 10 * n_confirm + 5 * n_multi - 12 * n_conflict_events - 5 * n_missing
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
