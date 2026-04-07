"""Deterministic cross-source trust scoring (signals → conflicts → score)."""
from __future__ import annotations

from typing import Any, Literal

from .conflict_detector import append_narrative_conflicts, build_evidence_and_conflicts
from .trust_scorer import build_trust_payload

Context = Literal["research", "earnings", "portfolio"]


def compute_trust_envelope(
    signals: list[dict[str, Any]] | None,
    *,
    context: Context,
    extra_contradiction_strings: list[str] | None = None,
) -> dict[str, Any]:
    """
    Returns trust_score, signal_summary, conflicts, evidence_matrix, trust_score_reasoning.
    Safe with empty or None signals (high missing penalty).
    """
    evidence_matrix, cross_conflicts, _ = build_evidence_and_conflicts(signals, context)
    conflicts = append_narrative_conflicts(cross_conflicts, extra_contradiction_strings)
    return build_trust_payload(evidence_matrix, conflicts)


__all__ = ["compute_trust_envelope", "Context"]
