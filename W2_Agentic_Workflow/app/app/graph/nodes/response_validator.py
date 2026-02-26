"""Response validator agent: cross-reference the itinerary against real search data to catch hallucinations."""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

BUDGET_OVERRUN_THRESHOLD = 1.20  # 20 % over budget
COST_DRIFT_RATIO = 3.0  # flag if itinerary cost > 3× the search-result price


def _normalize(name: str) -> str:
    """Lowercase, strip, collapse whitespace for fuzzy matching."""
    return " ".join(name.lower().split())


def _build_activity_index(selected_activities: list[dict]) -> dict[str, dict]:
    """Map normalised activity names to their search-result dicts."""
    index: dict[str, dict] = {}
    for act in selected_activities:
        name = act.get("name") or ""
        if name:
            index[_normalize(name)] = act
    return index


def validate_response_node(state: dict[str, Any]) -> dict[str, Any]:
    """Validate the built itinerary against search results and budget constraints."""
    start_t = time.time()
    trip = state.get("trip")
    selected_activities = state.get("selected_activities") or []
    trip_request = state.get("trip_request") or {}
    budget = float(trip_request.get("budget") or 0)

    issues: list[str] = []
    warnings: list[str] = []
    reasoning_parts: list[str] = []
    activities_checked = 0
    activities_unmatched = 0
    cost_anomalies = 0

    if not trip:
        reasoning_parts.append("No trip in state — nothing to validate.")
        latency_ms = int((time.time() - start_t) * 1000)
        return {
            "validation_issues": ["No itinerary to validate."],
            "agent_decisions": [{
                "agent_name": "response_validator",
                "action": "validate",
                "reasoning": "No trip present in state.",
                "result_summary": "Skipped — no trip",
                "tokens_used": 0,
                "latency_ms": latency_ms,
            }],
        }

    act_index = _build_activity_index(selected_activities)
    days = trip.get("days") or [] if isinstance(trip, dict) else []

    for day in days:
        day_num = day.get("day_number", "?")
        for item in day.get("items", []):
            item_type = item.get("item_type", "")
            title = item.get("title") or ""
            cost = item.get("cost", 0)

            if cost is not None and cost < 0:
                msg = f"Day {day_num}: '{title}' has a negative cost (₹{cost})."
                issues.append(msg)
                cost_anomalies += 1

            if item_type != "activity":
                continue

            activities_checked += 1
            norm_title = _normalize(title)

            matched_act = act_index.get(norm_title)
            if matched_act is None:
                for search_name, search_act in act_index.items():
                    if search_name in norm_title or norm_title in search_name:
                        matched_act = search_act
                        break

            if matched_act is None and selected_activities:
                activities_unmatched += 1
                issues.append(
                    f"Day {day_num}: activity '{title}' was not found in search results — possible hallucination."
                )
                continue

            if matched_act:
                search_price = float(matched_act.get("price") or 0)
                itin_cost = float(cost or 0)
                if search_price > 0 and itin_cost > search_price * COST_DRIFT_RATIO:
                    cost_anomalies += 1
                    issues.append(
                        f"Day {day_num}: '{title}' costs ₹{itin_cost:,.0f} in itinerary vs ₹{search_price:,.0f} from search (>{COST_DRIFT_RATIO:.0f}× drift)."
                    )

    total_cost = trip.get("total_cost", 0) if isinstance(trip, dict) else 0
    if budget > 0 and total_cost > budget * BUDGET_OVERRUN_THRESHOLD:
        overrun_pct = ((total_cost - budget) / budget) * 100
        msg = (
            f"Total itinerary cost ₹{total_cost:,.0f} exceeds budget ₹{budget:,.0f} "
            f"by {overrun_pct:.0f}% (threshold is {int((BUDGET_OVERRUN_THRESHOLD - 1) * 100)}%)."
        )
        warnings.append(msg)
        issues.append(msg)

    if activities_unmatched > 0:
        warnings.append(
            f"{activities_unmatched} activit{'y' if activities_unmatched == 1 else 'ies'} "
            f"could not be matched to search results — review recommended."
        )

    if cost_anomalies > 0:
        warnings.append(f"{cost_anomalies} cost anomal{'y' if cost_anomalies == 1 else 'ies'} detected in the itinerary.")

    if not issues:
        reasoning_parts.append(
            f"Validated {activities_checked} activities — all matched search results with reasonable costs."
        )
    else:
        reasoning_parts.append(
            f"Validated {activities_checked} activities: {len(issues)} issue(s) found "
            f"({activities_unmatched} unmatched, {cost_anomalies} cost anomalies)."
        )

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "response_validator",
        "action": "validate",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"{len(issues)} issue(s), {activities_checked} activities checked",
        "tokens_used": 0,
        "latency_ms": latency_ms,
    }

    existing_warnings = state.get("budget_warnings") or []
    merged_warnings = existing_warnings + warnings

    return {
        "validation_issues": issues,
        "budget_warnings": merged_warnings,
        "current_stage": "validation_done",
        "agent_decisions": [decision],
    }
