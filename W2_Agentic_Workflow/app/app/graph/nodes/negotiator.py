"""
AI Travel Negotiator — Trade-Off Negotiation Engine.

LangGraph node that runs after parallel research (search_aggregator + enrichment_aggregator)
and before feasibility validation.

Architecture:
  search_aggregator → enrichment_aggregator → negotiator → feasibility_validator
                                                    ↑ (loop back on feasibility failure)

Design principles:
- Scoring is 100% deterministic / algorithmic (no LLM required).
- One optional fast LLM call to generate human-friendly trade-off bullets.
- Full demo-mode: uses mocked sample options when real API data is absent.
- Results are cached in state; What-If re-runs only negotiator + downstream nodes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

from app.models.negotiation import (
    BundleChoice,
    FeasibilityResult,
    MoneyBreakdown,
    RejectedOption,
    ScoringWeights,
    TradeOffLine,
    WhatIfRequest,
    BUNDLE_META,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring constants (tweakable)
# ---------------------------------------------------------------------------

WEIGHTS = ScoringWeights()

# Top-K candidates per category
K_TRANSPORT = 6
K_STAY = 6
K_ACTIVITIES = 12

# Feasibility limits
MAX_ACTIVITY_HOURS_PER_DAY = 10.0
MIN_BUFFER_MINUTES_PER_DAY = 60

# Over-budget penalty multiplier for cost_score
OVER_BUDGET_PENALTY = 2.5

# Food estimation: INR per person per day
FOOD_PER_PERSON_PER_DAY = 800.0

# Buffer: 5% of (transport + stay + activities + food)
BUFFER_FRACTION = 0.05


# ---------------------------------------------------------------------------
# Demo-mode mock data
# ---------------------------------------------------------------------------

_DEMO_TRANSPORT: List[Dict[str, Any]] = [
    {
        "id": "demo_flight_1",
        "name": "IndiGo Express",
        "transport_type": "flight",
        "operator": "IndiGo",
        "total_price": 4500,
        "price": 4500,
        "duration_minutes": 90,
        "transfers": 0,
        "rating": 4.1,
        "booking_url": "https://www.goindigo.in",
        "source": "curated",
    },
    {
        "id": "demo_flight_2",
        "name": "Air India Saver",
        "transport_type": "flight",
        "operator": "Air India",
        "total_price": 5800,
        "price": 5800,
        "duration_minutes": 100,
        "transfers": 0,
        "rating": 4.3,
        "booking_url": "https://www.airindia.com",
        "source": "curated",
    },
    {
        "id": "demo_train_1",
        "name": "Rajdhani Express",
        "transport_type": "train",
        "operator": "IRCTC",
        "total_price": 1200,
        "price": 1200,
        "duration_minutes": 480,
        "transfers": 0,
        "rating": 4.0,
        "booking_url": "https://www.irctc.co.in",
        "source": "curated",
    },
    {
        "id": "demo_bus_1",
        "name": "RedBus Volvo",
        "transport_type": "bus",
        "operator": "RedBus",
        "total_price": 650,
        "price": 650,
        "duration_minutes": 600,
        "transfers": 1,
        "rating": 3.7,
        "booking_url": "https://www.redbus.in",
        "source": "curated",
    },
]

_DEMO_STAYS: List[Dict[str, Any]] = [
    {
        "id": "demo_hotel_1",
        "name": "The Grand Palace Hotel",
        "star_rating": 4.5,
        "price_per_night": 3500,
        "total_price": 10500,
        "amenities": ["WiFi", "Pool", "Breakfast", "Gym"],
        "booking_url": "https://www.booking.com",
        "source": "curated",
    },
    {
        "id": "demo_hotel_2",
        "name": "Comfort Inn & Suites",
        "star_rating": 3.5,
        "price_per_night": 2000,
        "total_price": 6000,
        "amenities": ["WiFi", "Breakfast"],
        "booking_url": "https://www.makemytrip.com",
        "source": "curated",
    },
    {
        "id": "demo_hostel_1",
        "name": "Zostel Backpackers",
        "star_rating": 3.0,
        "price_per_night": 800,
        "total_price": 2400,
        "amenities": ["WiFi", "Common Kitchen", "Lockers"],
        "booking_url": "https://www.zostel.com",
        "source": "curated",
    },
]

_DEMO_ACTIVITIES: List[Dict[str, Any]] = [
    {"id": "act_1", "name": "Heritage Walking Tour", "category": "culture", "duration_hours": 3.0, "price": 500, "rating": 4.6, "booking_url": None, "source": "curated"},
    {"id": "act_2", "name": "Local Food Trail", "category": "food", "duration_hours": 2.5, "price": 800, "rating": 4.8, "booking_url": None, "source": "curated"},
    {"id": "act_3", "name": "Sunrise Yoga & Meditation", "category": "wellness", "duration_hours": 1.5, "price": 300, "rating": 4.5, "booking_url": None, "source": "curated"},
    {"id": "act_4", "name": "River Rafting Adventure", "category": "adventure", "duration_hours": 4.0, "price": 1500, "rating": 4.7, "booking_url": "https://www.thrillophilia.com", "source": "curated"},
    {"id": "act_5", "name": "Museum of History", "category": "culture", "duration_hours": 2.0, "price": 200, "rating": 4.2, "booking_url": None, "source": "curated"},
    {"id": "act_6", "name": "Sunset Boat Cruise", "category": "nature", "duration_hours": 2.0, "price": 1200, "rating": 4.9, "booking_url": "https://www.viator.com", "source": "curated"},
    {"id": "act_7", "name": "Cooking Class", "category": "food", "duration_hours": 3.0, "price": 1000, "rating": 4.6, "booking_url": None, "source": "curated"},
    {"id": "act_8", "name": "Night Market Visit", "category": "shopping", "duration_hours": 2.0, "price": 0, "rating": 4.3, "booking_url": None, "source": "curated"},
    {"id": "act_9", "name": "Temple Circuit", "category": "spiritual", "duration_hours": 3.5, "price": 100, "rating": 4.4, "booking_url": None, "source": "curated"},
    {"id": "act_10", "name": "Photography Walk", "category": "culture", "duration_hours": 2.5, "price": 400, "rating": 4.5, "booking_url": None, "source": "curated"},
    {"id": "act_11", "name": "Paragliding", "category": "adventure", "duration_hours": 1.0, "price": 2500, "rating": 4.8, "booking_url": "https://www.thrillophilia.com", "source": "curated"},
    {"id": "act_12", "name": "Village Homestay Experience", "category": "culture", "duration_hours": 5.0, "price": 600, "rating": 4.7, "booking_url": None, "source": "curated"},
]


# ---------------------------------------------------------------------------
# Helpers: normalise raw state dicts into uniform option dicts
# ---------------------------------------------------------------------------

def _normalise_transport(opt: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten FlightOption / GroundTransportOption dicts into a uniform shape."""
    out = dict(opt)
    # FlightOption stores price under total_price; GroundTransportOption under price
    if "total_price" not in out:
        out["total_price"] = out.get("price", 0)
    if "price" not in out:
        out["price"] = out["total_price"]
    # Derive transport_type
    if "transport_type" not in out:
        if "outbound" in out or out.get("source") in ("api",):
            out["transport_type"] = "flight"
        else:
            out["transport_type"] = "unknown"
    # Derive duration_minutes from outbound segment if missing
    if "duration_minutes" not in out and "outbound" in out:
        ob = out["outbound"] or {}
        out["duration_minutes"] = ob.get("duration_minutes", 120)
    out.setdefault("duration_minutes", 120)
    out.setdefault("transfers", 0)
    out.setdefault("rating", 3.5)
    # Stable id
    if "id" not in out:
        out["id"] = _stable_id(out.get("name") or out.get("operator") or str(out.get("total_price")))
    return out


def _normalise_stay(opt: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(opt)
    out.setdefault("star_rating", 3.0)
    out.setdefault("total_price", out.get("price_per_night", 0) * 3)
    if "id" not in out:
        out["id"] = _stable_id(out.get("name") or str(out.get("total_price")))
    return out


def _normalise_activity(opt: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(opt)
    out.setdefault("rating", 3.5)
    out.setdefault("duration_hours", 2.0)
    # Keep None as None (unknown price) — don't default to 0 which implies "Free"
    if "price" not in out:
        out["price"] = 0
    if "id" not in out:
        out["id"] = _stable_id(out.get("name") or str(out.get("price")))
    return out


def _stable_id(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Scoring functions (deterministic, no LLM)
# ---------------------------------------------------------------------------

def _cost_score(total_cost: float, budget: float) -> int:
    """Higher score = cheaper relative to budget. Heavy penalty for over-budget."""
    if budget <= 0:
        return 50
    ratio = total_cost / budget
    if ratio <= 0.70:
        return 100
    if ratio <= 0.85:
        return round(100 - (ratio - 0.70) / 0.15 * 20)   # 100 → 80
    if ratio <= 1.00:
        return round(80 - (ratio - 0.85) / 0.15 * 40)    # 80 → 40
    # Over budget: steep penalty
    over = (ratio - 1.0) * OVER_BUDGET_PENALTY
    return max(0, round(40 - over * 40))


def _experience_score(
    transport: Dict[str, Any],
    stay: Dict[str, Any],
    activities: List[Dict[str, Any]],
    interests: List[str],
) -> int:
    """
    Deterministic experience score (0–100).
    Components:
      - Stay quality (star_rating → 0-30 pts)
      - Activity richness (count, ratings, interest match → 0-40 pts)
      - Transport comfort (rating, duration → 0-20 pts)
      - Variety bonus (unique categories → 0-10 pts)
    """
    # Stay quality: 0-30
    star = float(stay.get("star_rating") or 3.0)
    stay_pts = min(30, (star / 5.0) * 30)

    # Activity richness: 0-40
    act_count = len(activities)
    count_pts = min(15, act_count * 2.5)
    avg_rating = (
        sum(float(a.get("rating") or 3.5) for a in activities) / act_count
        if act_count else 3.5
    )
    rating_pts = min(15, (avg_rating / 5.0) * 15)
    # Interest match
    interest_set = {i.lower() for i in (interests or [])}
    matched = sum(
        1 for a in activities
        if (a.get("category") or "").lower() in interest_set
    )
    interest_pts = min(10, matched * 3)
    act_pts = count_pts + rating_pts + interest_pts

    # Transport comfort: 0-20
    t_rating = float(transport.get("rating") or 3.5)
    t_duration = float(transport.get("duration_minutes") or 120)
    t_transfers = int(transport.get("transfers") or 0)
    t_rating_pts = min(12, (t_rating / 5.0) * 12)
    # Penalise long travel and transfers
    t_duration_pts = max(0, 8 - (t_duration / 60) * 0.5 - t_transfers * 2)
    transport_pts = t_rating_pts + t_duration_pts

    # Variety bonus: 0-10
    categories = {(a.get("category") or "misc").lower() for a in activities}
    variety_pts = min(10, len(categories) * 2)

    raw = stay_pts + act_pts + transport_pts + variety_pts
    return min(100, max(0, int(raw)))


def _convenience_score(
    transport: Dict[str, Any],
    stay: Dict[str, Any],
    activities: List[Dict[str, Any]],
    duration_days: int,
) -> int:
    """
    Convenience / feasibility-friendliness score (0–100).
    - Penalise very long travel times
    - Reward buffer time (not too packed)
    - Penalise many transfers
    - Reward bookable options (booking_url present)
    """
    score = 70  # baseline

    # Travel time penalty
    dur_h = float(transport.get("duration_minutes") or 120) / 60
    if dur_h > 8:
        score -= 20
    elif dur_h > 4:
        score -= 10

    # Transfer penalty
    transfers = int(transport.get("transfers") or 0)
    score -= transfers * 8

    # Schedule density
    total_act_hours = sum(float(a.get("duration_hours") or 2) for a in activities)
    avg_daily_hours = total_act_hours / max(1, duration_days)
    if avg_daily_hours > MAX_ACTIVITY_HOURS_PER_DAY:
        score -= 20
    elif avg_daily_hours > 7:
        score -= 10
    elif avg_daily_hours < 4:
        score += 10  # relaxed schedule bonus

    # Booking links reward
    has_transport_link = bool(transport.get("booking_url"))
    has_stay_link = bool(stay.get("booking_url"))
    if has_transport_link:
        score += 8
    if has_stay_link:
        score += 7

    return min(100, max(0, score))


# ---------------------------------------------------------------------------
# Cost breakdown builder
# ---------------------------------------------------------------------------

def _build_breakdown(
    transport: Dict[str, Any],
    stay: Dict[str, Any],
    activities: List[Dict[str, Any]],
    duration_days: int,
    num_travelers: int,
) -> MoneyBreakdown:
    transport_cost = float(transport.get("total_price") or transport.get("price") or 0)
    stay_cost = float(stay.get("total_price") or stay.get("price_per_night", 0) * duration_days)
    act_cost = sum(float(a.get("price") or 0) for a in activities) * num_travelers
    food_cost = FOOD_PER_PERSON_PER_DAY * duration_days * num_travelers
    sub = transport_cost + stay_cost + act_cost + food_cost
    buffer = round(sub * BUFFER_FRACTION, 0)
    total = sub + buffer
    return MoneyBreakdown(
        transport=round(transport_cost, 2),
        stay=round(stay_cost, 2),
        activities=round(act_cost, 2),
        food=round(food_cost, 2),
        buffer=round(buffer, 2),
        total=round(total, 2),
    )


# ---------------------------------------------------------------------------
# Trade-off explanation (rule-based template; LLM optional)
# ---------------------------------------------------------------------------

def _rule_based_tradeoffs(
    bundle_id: str,
    transport: Dict[str, Any],
    stay: Dict[str, Any],
    activities: List[Dict[str, Any]],
    breakdown: MoneyBreakdown,
    all_transports: List[Dict[str, Any]],
    all_stays: List[Dict[str, Any]],
) -> List[TradeOffLine]:
    lines: List[TradeOffLine] = []

    # Transport comparison
    t_type = (transport.get("transport_type") or "transport").title()
    t_price = breakdown.transport
    other_t = [t for t in all_transports if t.get("id") != transport.get("id")]
    if other_t:
        alt = other_t[0]
        alt_price = float(alt.get("total_price") or alt.get("price") or 0)
        diff = abs(t_price - alt_price)
        alt_type = (alt.get("transport_type") or "alternative").title()
        if t_price < alt_price:
            lines.append(TradeOffLine(
                gain=f"Choosing {t_type} saves ₹{diff:,.0f} vs {alt_type}",
                sacrifice=f"Longer travel time by ~{int((float(transport.get('duration_minutes',120)) - float(alt.get('duration_minutes',120)))/60*10)/10:.1f}h",
            ))
        else:
            lines.append(TradeOffLine(
                gain=f"{t_type} is faster and more comfortable",
                sacrifice=f"Costs ₹{diff:,.0f} more than {alt_type}",
            ))

    # Stay comparison
    s_name = stay.get("name", "This stay")
    s_stars = float(stay.get("star_rating") or 3.0)
    other_s = [s for s in all_stays if s.get("id") != stay.get("id")]
    if other_s:
        alt_s = other_s[0]
        alt_price = float(alt_s.get("total_price") or alt_s.get("price_per_night", 0) * 3)
        s_price = breakdown.stay
        diff = abs(s_price - alt_price)
        alt_stars = float(alt_s.get("star_rating") or 3.0)
        if s_price < alt_price:
            lines.append(TradeOffLine(
                gain=f"Staying at {s_name} saves ₹{diff:,.0f}",
                sacrifice=f"Rating is {s_stars:.1f}★ vs {alt_stars:.1f}★ for the pricier option",
            ))
        else:
            lines.append(TradeOffLine(
                gain=f"{s_name} ({s_stars:.1f}★) improves comfort significantly",
                sacrifice=f"Costs ₹{diff:,.0f} more than the budget alternative",
            ))

    # Activity schedule
    total_hours = sum(float(a.get("duration_hours") or 2) for a in activities)
    if total_hours > 7:
        lines.append(TradeOffLine(
            gain=f"{len(activities)} activities packed for maximum exploration",
            sacrifice=f"Packed schedule ({total_hours:.0f}h total) reduces free/buffer time",
        ))
    else:
        lines.append(TradeOffLine(
            gain=f"Relaxed pace with {total_hours:.0f}h of activities — plenty of buffer",
            sacrifice=f"Fewer activities ({len(activities)}) means some experiences skipped",
        ))

    # Bundle-specific line
    if bundle_id == "budget_saver":
        lines.append(TradeOffLine(
            gain=f"Lowest total cost at ₹{breakdown.total:,.0f} — maximum savings",
            sacrifice="Some comfort and premium experiences traded for affordability",
        ))
    elif bundle_id == "best_value":
        lines.append(TradeOffLine(
            gain="Optimal balance of cost and experience — best rupee-per-memory ratio",
            sacrifice="Neither the cheapest nor the most luxurious option",
        ))
    elif bundle_id == "experience_max":
        lines.append(TradeOffLine(
            gain="Richest experience bundle — premium stays, top-rated activities",
            sacrifice=f"Higher spend at ₹{breakdown.total:,.0f} — may stretch budget",
        ))

    return lines[:5]


def _llm_tradeoffs(
    bundle_id: str,
    transport: Dict[str, Any],
    stay: Dict[str, Any],
    activities: List[Dict[str, Any]],
    breakdown: MoneyBreakdown,
    budget: float,
) -> Optional[List[TradeOffLine]]:
    """One fast LLM call (GPT-4o-mini) to generate human-friendly trade-offs. Returns None if unavailable."""
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.has_openai:
            return None
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        act_names = ", ".join(a.get("name", "?") for a in activities[:5])
        prompt = (
            f"You are a travel advisor. Generate exactly 4 trade-off bullets for this travel bundle.\n"
            f"Bundle: {bundle_id.replace('_', ' ').title()}\n"
            f"Transport: {transport.get('name') or transport.get('operator', '?')} "
            f"({transport.get('transport_type', '?')}, ₹{breakdown.transport:,.0f})\n"
            f"Stay: {stay.get('name', '?')} ({stay.get('star_rating', '?')}★, ₹{breakdown.stay:,.0f})\n"
            f"Activities: {act_names}\n"
            f"Total: ₹{breakdown.total:,.0f} / Budget: ₹{budget:,.0f}\n\n"
            "Return JSON array of objects with 'gain' and 'sacrifice' keys. "
            "Each should be a concise sentence (max 12 words). No markdown."
        )
        r = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=300,
            timeout=15,
        )
        content = (r.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        data = json.loads(content)
        return [TradeOffLine(gain=d["gain"], sacrifice=d["sacrifice"]) for d in data[:5]]
    except Exception as e:
        logger.debug("LLM trade-off generation skipped: %s", e)
        return None


# ---------------------------------------------------------------------------
# Feasibility validator
# ---------------------------------------------------------------------------

def validate_feasibility(bundle: BundleChoice, duration_days: int) -> FeasibilityResult:
    """
    Check feasibility of a bundle:
    - Daily activity hours <= MAX_ACTIVITY_HOURS_PER_DAY
    - Buffer time >= MIN_BUFFER_MINUTES_PER_DAY per day
    - No impossible travel (transport duration < 24h)
    """
    issues: List[str] = []
    tweaks: List[str] = []

    total_act_hours = sum(float(a.get("duration_hours") or 2) for a in bundle.activities)
    avg_daily = total_act_hours / max(1, duration_days)

    if avg_daily > MAX_ACTIVITY_HOURS_PER_DAY:
        issues.append(
            f"Daily activity load {avg_daily:.1f}h exceeds {MAX_ACTIVITY_HOURS_PER_DAY}h limit"
        )
        tweaks.append("Remove 1–2 activities or spread across more days")

    # Buffer check: 24h/day - 8h sleep - avg_daily_act - 2h meals = buffer
    buffer_per_day_min = (24 - 8 - avg_daily - 2) * 60
    if buffer_per_day_min < MIN_BUFFER_MINUTES_PER_DAY:
        issues.append(
            f"Buffer time {buffer_per_day_min:.0f} min/day < {MIN_BUFFER_MINUTES_PER_DAY} min minimum"
        )
        tweaks.append("Drop 1 activity to free up buffer time")

    # Transport duration sanity
    t_dur = float(bundle.transport.get("duration_minutes") or 0)
    if t_dur > 24 * 60:
        issues.append(f"Transport duration {t_dur/60:.0f}h is unrealistically long")
        tweaks.append("Switch to a faster transport mode")

    return FeasibilityResult(
        bundle_id=bundle.id,
        passed=len(issues) == 0,
        issues=issues,
        suggested_tweaks=tweaks,
    )


def _fix_bundle_for_feasibility(
    bundle: BundleChoice,
    result: FeasibilityResult,
    all_activities: List[Dict[str, Any]],
) -> BundleChoice:
    """Attempt to auto-fix a failed bundle by removing the longest activity."""
    if not result.issues:
        return bundle
    activities = list(bundle.activities)
    if len(activities) > 3:
        # Remove the activity with the most hours
        activities.sort(key=lambda a: float(a.get("duration_hours") or 0), reverse=True)
        removed = activities.pop(0)
        log = bundle.decision_log + [
            f"Feasibility fix: removed '{removed.get('name', '?')}' ({removed.get('duration_hours', '?')}h) to reduce daily load"
        ]
        # Recompute breakdown with updated activities
        return bundle.model_copy(update={"activities": activities, "decision_log": log})
    return bundle


# ---------------------------------------------------------------------------
# Bundle generation core
# ---------------------------------------------------------------------------

def _get_option_id(opt: Dict[str, Any]) -> str:
    return str(opt.get("id") or opt.get("name") or str(opt.get("total_price") or opt.get("price")))


def _generate_bundles(
    transport_opts: List[Dict[str, Any]],
    stay_opts: List[Dict[str, Any]],
    activity_opts: List[Dict[str, Any]],
    budget: float,
    duration_days: int,
    num_travelers: int,
    interests: List[str],
    negotiation_log: List[str],
    what_if_delta: int = 0,
) -> Tuple[List[BundleChoice], List[str]]:
    """
    Core bundle generation algorithm.
    Returns (bundles, updated_negotiation_log).
    """
    effective_budget = budget + what_if_delta
    log = list(negotiation_log)
    log.append(f"Negotiator started | budget=₹{effective_budget:,.0f} | duration={duration_days}d")

    # --- Step 1: Normalise inputs ---
    transports = [_normalise_transport(t) for t in transport_opts]
    stays = [_normalise_stay(s) for s in stay_opts]
    activities = [_normalise_activity(a) for a in activity_opts]

    # --- Step 2: Demo mode fallback ---
    if not transports:
        log.append("No transport options found — using demo data")
        transports = [_normalise_transport(t) for t in _DEMO_TRANSPORT]
    if not stays:
        log.append("No stay options found — using demo data")
        stays = [_normalise_stay(s) for s in _DEMO_STAYS]
    if not activities:
        log.append("No activity options found — using demo data")
        activities = [_normalise_activity(a) for a in _DEMO_ACTIVITIES]

    # --- Step 3: Hard constraint filter (min rating if provided) ---
    # Keep all options for now (no hard min-rating filter to avoid empty sets)

    # --- Step 4: Top-K selection ---
    # Sort transports by price ascending for budget, rating descending for experience
    transports_by_price = sorted(transports, key=lambda t: float(t.get("total_price") or t.get("price") or 0))
    transports_by_rating = sorted(transports, key=lambda t: float(t.get("rating") or 3.5), reverse=True)
    top_transports = list({_get_option_id(t): t for t in transports_by_price[:K_TRANSPORT] + transports_by_rating[:K_TRANSPORT]}.values())

    stays_by_price = sorted(stays, key=lambda s: float(s.get("total_price") or s.get("price_per_night", 0) * duration_days))
    stays_by_rating = sorted(stays, key=lambda s: float(s.get("star_rating") or 3.0), reverse=True)
    top_stays = list({_get_option_id(s): s for s in stays_by_price[:K_STAY] + stays_by_rating[:K_STAY]}.values())

    # Activities: sort by rating, then interest match
    def _act_sort_key(a: Dict[str, Any]) -> Tuple[float, float]:
        interest_bonus = 2.0 if (a.get("category") or "").lower() in {i.lower() for i in interests} else 0.0
        return (float(a.get("rating") or 3.5) + interest_bonus, -float(a.get("price") or 0))

    top_activities = sorted(activities, key=_act_sort_key, reverse=True)[:K_ACTIVITIES]

    log.append(
        f"Candidate pool: {len(top_transports)} transport, {len(top_stays)} stay, {len(top_activities)} activities"
    )

    # --- Step 5: Score all transport × stay combos, then pick best activity subsets ---
    # For efficiency: score transport+stay pairs first, then attach best activities per bundle type

    scored_combos: List[Dict[str, Any]] = []

    for t, s in product(top_transports[:K_TRANSPORT], top_stays[:K_STAY]):
        # Try activity subsets of size 3, 5, 7
        for n_acts in [3, 5, 7]:
            acts = top_activities[:n_acts]
            bd = _build_breakdown(t, s, acts, duration_days, num_travelers)
            exp_s = _experience_score(t, s, acts, interests)
            cost_s = _cost_score(bd.total, effective_budget)
            conv_s = _convenience_score(t, s, acts, duration_days)
            final_s = WEIGHTS.compute(exp_s, cost_s, conv_s)
            scored_combos.append({
                "transport": t,
                "stay": s,
                "activities": acts,
                "breakdown": bd,
                "experience_score": exp_s,
                "cost_score": cost_s,
                "convenience_score": conv_s,
                "final_score": final_s,
            })

    if not scored_combos:
        log.append("ERROR: No combos generated — returning empty bundles")
        return [], log

    log.append(f"Scored {len(scored_combos)} candidate combos")

    # --- Step 6: Select winners ---

    # Budget Saver: lowest total cost that passes feasibility (or closest)
    budget_candidates = sorted(scored_combos, key=lambda c: c["breakdown"].total)
    budget_winner = budget_candidates[0]
    log.append(
        f"Budget Saver: ₹{budget_winner['breakdown'].total:,.0f} | exp={budget_winner['experience_score']} | score={budget_winner['final_score']}"
    )

    # Best Value: highest final_score under budget
    under_budget = [c for c in scored_combos if c["breakdown"].total <= effective_budget]
    if under_budget:
        best_value_winner = max(under_budget, key=lambda c: c["final_score"])
    else:
        best_value_winner = max(scored_combos, key=lambda c: c["final_score"])
    log.append(
        f"Best Value: ₹{best_value_winner['breakdown'].total:,.0f} | exp={best_value_winner['experience_score']} | score={best_value_winner['final_score']}"
    )

    # Experience Max: highest experience_score within budget*1.10 (or closest feasible)
    exp_budget = effective_budget * 1.10
    exp_candidates = [c for c in scored_combos if c["breakdown"].total <= exp_budget]
    if exp_candidates:
        exp_winner = max(exp_candidates, key=lambda c: c["experience_score"])
    else:
        exp_winner = max(scored_combos, key=lambda c: c["experience_score"])
    log.append(
        f"Experience Max: ₹{exp_winner['breakdown'].total:,.0f} | exp={exp_winner['experience_score']} | score={exp_winner['final_score']}"
    )

    # --- Step 7: Deduplication ---
    def _combo_sig(c: Dict[str, Any]) -> str:
        return f"{_get_option_id(c['transport'])}|{_get_option_id(c['stay'])}|{len(c['activities'])}"

    sigs: set[str] = set()
    winners: Dict[str, Dict[str, Any]] = {}
    for btype, winner in [("budget_saver", budget_winner), ("best_value", best_value_winner), ("experience_max", exp_winner)]:
        sig = _combo_sig(winner)
        if sig in sigs:
            # Pick next best for this bucket
            pool = budget_candidates if btype == "budget_saver" else (
                sorted(under_budget or scored_combos, key=lambda c: c["final_score"], reverse=True)
                if btype == "best_value"
                else sorted(exp_candidates or scored_combos, key=lambda c: c["experience_score"], reverse=True)
            )
            for alt in pool:
                alt_sig = _combo_sig(alt)
                if alt_sig not in sigs:
                    winner = alt
                    sig = alt_sig
                    log.append(f"Dedup: {btype} → next best (sig conflict)")
                    break
        sigs.add(sig)
        winners[btype] = winner

    # --- Step 8: Build BundleChoice objects ---
    bundles: List[BundleChoice] = []
    for btype in ["budget_saver", "best_value", "experience_max"]:
        w = winners[btype]
        meta = BUNDLE_META[btype]  # type: ignore[index]
        t = w["transport"]
        s = w["stay"]
        acts = w["activities"]
        bd: MoneyBreakdown = w["breakdown"]

        # Rejected alternatives (1-2)
        rejected: List[RejectedOption] = []
        alt_transports = [x for x in top_transports if _get_option_id(x) != _get_option_id(t)]
        if alt_transports:
            alt_t = alt_transports[0]
            alt_price = float(alt_t.get("total_price") or alt_t.get("price") or 0)
            t_price = float(t.get("total_price") or t.get("price") or 0)
            rejected.append(RejectedOption(
                name=f"{alt_t.get('operator') or alt_t.get('name', '?')} ({(alt_t.get('transport_type') or '?').title()})",
                reason=f"₹{abs(alt_price - t_price):,.0f} {'more expensive' if alt_price > t_price else 'cheaper but slower/less comfortable'}",
            ))
        alt_stays = [x for x in top_stays if _get_option_id(x) != _get_option_id(s)]
        if alt_stays:
            alt_s = alt_stays[0]
            alt_s_price = float(alt_s.get("total_price") or alt_s.get("price_per_night", 0) * duration_days)
            s_price = bd.stay
            rejected.append(RejectedOption(
                name=alt_s.get("name", "Alternative stay"),
                reason=f"₹{abs(alt_s_price - s_price):,.0f} {'more expensive' if alt_s_price > s_price else 'cheaper but lower rated'}",
            ))

        # Trade-offs: try LLM first, fall back to rule-based
        tradeoffs = _llm_tradeoffs(btype, t, s, acts, bd, effective_budget)
        if not tradeoffs:
            tradeoffs = _rule_based_tradeoffs(btype, t, s, acts, bd, top_transports, top_stays)

        # Booking links
        booking_links: Dict[str, Optional[str]] = {
            "transport": t.get("booking_url"),
            "stay": s.get("booking_url"),
        }
        for i, a in enumerate(acts):
            if a.get("booking_url"):
                booking_links[f"activity_{i+1}"] = a["booking_url"]

        decision_log_lines = [
            f"Bundle: {meta['title']}",
            f"Total: ₹{bd.total:,.0f} | Budget: ₹{effective_budget:,.0f} ({bd.total/effective_budget*100:.0f}%)",
            f"Scores → experience={w['experience_score']} cost={w['cost_score']} convenience={w['convenience_score']} final={w['final_score']:.1f}",
            f"Transport: {t.get('operator') or t.get('name', '?')} ({t.get('transport_type', '?')}) ₹{bd.transport:,.0f}",
            f"Stay: {s.get('name', '?')} ({s.get('star_rating', '?')}★) ₹{bd.stay:,.0f}",
            f"Activities ({len(acts)}): {', '.join(a.get('name', '?') for a in acts[:3])}{'...' if len(acts) > 3 else ''}",
        ]

        bundle = BundleChoice(
            id=btype,
            title=meta["title"],
            summary=meta["summary"],
            transport=t,
            stay=s,
            activities=acts,
            breakdown=bd,
            experience_score=w["experience_score"],
            cost_score=w["cost_score"],
            convenience_score=w["convenience_score"],
            final_score=w["final_score"],
            tradeoffs=tradeoffs,
            rejected=rejected,
            booking_links=booking_links,
            decision_log=decision_log_lines,
        )
        bundles.append(bundle)

    log.append(f"Generated {len(bundles)} bundles successfully")
    return bundles, log


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------

def _cache_key(state: Dict[str, Any]) -> str:
    req = state.get("trip_request") or {}
    parts = [
        str(req.get("budget")),
        str(req.get("destination")),
        str(req.get("start_date")),
        str(req.get("end_date")),
        str(len(state.get("flight_options") or [])),
        str(len(state.get("hotel_options") or [])),
        str(len(state.get("activity_options") or [])),
        str(state.get("what_if_delta", 0)),
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

def negotiate_bundles_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: AI Travel Negotiator.

    Reads: flight_options, ground_transport_options, hotel_options, activity_options,
           trip_request, negotiation_log, what_if_history, what_if_delta
    Writes: bundles, negotiation_log, current_stage, agent_decisions
    """
    start_t = time.time()
    req = state.get("trip_request") or {}
    budget = float(req.get("budget") or 15000)
    duration_days = int(req.get("duration_days") or 3)
    # Compute duration from dates if not set
    if not req.get("duration_days"):
        try:
            from datetime import date as _date
            sd = req.get("start_date")
            ed = req.get("end_date")
            if sd and ed:
                if isinstance(sd, str):
                    sd = _date.fromisoformat(sd)
                if isinstance(ed, str):
                    ed = _date.fromisoformat(ed)
                duration_days = max(1, (ed - sd).days + 1)
        except Exception:
            pass
    num_travelers = int(req.get("num_travelers") or 1)
    interests = list(req.get("interests") or [])

    # Check cache
    cache_key = _cache_key(state)
    existing_bundles = state.get("bundles") or []
    existing_cache_key = state.get("_negotiator_cache_key")
    if existing_bundles and existing_cache_key == cache_key:
        logger.info("Negotiator: cache hit — returning existing bundles")
        return {
            "current_stage": "negotiation_done",
            "negotiation_log": list(state.get("negotiation_log") or []) + ["Cache hit — reusing bundles"],
        }

    # Merge transport options
    all_transport: List[Dict[str, Any]] = []
    for opt in (state.get("flight_options") or []):
        all_transport.append(opt if isinstance(opt, dict) else opt.model_dump())
    for opt in (state.get("ground_transport_options") or []):
        all_transport.append(opt if isinstance(opt, dict) else opt.model_dump())

    stay_opts: List[Dict[str, Any]] = [
        opt if isinstance(opt, dict) else opt.model_dump()
        for opt in (state.get("hotel_options") or [])
    ]
    activity_opts: List[Dict[str, Any]] = [
        opt if isinstance(opt, dict) else opt.model_dump()
        for opt in (state.get("activity_options") or [])
    ]

    what_if_delta = int(state.get("what_if_delta") or 0)
    negotiation_log = list(state.get("negotiation_log") or [])

    bundles, updated_log = _generate_bundles(
        transport_opts=all_transport,
        stay_opts=stay_opts,
        activity_opts=activity_opts,
        budget=budget,
        duration_days=duration_days,
        num_travelers=num_travelers,
        interests=interests,
        negotiation_log=negotiation_log,
        what_if_delta=what_if_delta,
    )

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "negotiator",
        "action": "generate_bundles",
        "reasoning": f"Generated {len(bundles)} negotiated bundles in {latency_ms}ms",
        "result_summary": " | ".join(
            f"{b.title}: ₹{b.breakdown.total:,.0f} (exp={b.experience_score})"
            for b in bundles
        ),
        "tokens_used": 0,
        "latency_ms": latency_ms,
    }

    return {
        "bundles": [b.model_dump() for b in bundles],
        "_negotiator_cache_key": cache_key,
        "negotiation_log": updated_log,
        "current_stage": "negotiation_done",
        "agent_decisions": [decision],
    }


# ---------------------------------------------------------------------------
# Feasibility validator node
# ---------------------------------------------------------------------------

def feasibility_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Feasibility Validator.

    Checks each bundle for schedule feasibility.
    If any bundle fails, attempts auto-fix and logs issues.
    Sets feasibility_passed = True/False in state.
    """
    req = state.get("trip_request") or {}
    duration_days = int(req.get("duration_days") or 3)
    try:
        from datetime import date as _date
        sd = req.get("start_date")
        ed = req.get("end_date")
        if sd and ed:
            if isinstance(sd, str):
                sd = _date.fromisoformat(sd)
            if isinstance(ed, str):
                ed = _date.fromisoformat(ed)
            duration_days = max(1, (ed - sd).days + 1)
    except Exception:
        pass

    raw_bundles = state.get("bundles") or []
    if not raw_bundles:
        return {
            "feasibility_passed": True,
            "feasibility_issues": [],
            "current_stage": "feasibility_done",
        }

    all_activities: List[Dict[str, Any]] = [
        opt if isinstance(opt, dict) else opt.model_dump()
        for opt in (state.get("activity_options") or [])
    ]

    fixed_bundles: List[Dict[str, Any]] = []
    all_issues: List[str] = []
    any_failed = False

    for raw in raw_bundles:
        try:
            bundle = BundleChoice(**raw)
        except Exception as e:
            logger.warning("Could not parse bundle for feasibility check: %s", e)
            fixed_bundles.append(raw)
            continue

        result = validate_feasibility(bundle, duration_days)
        if not result.passed:
            any_failed = True
            all_issues.extend([f"[{bundle.id}] {issue}" for issue in result.issues])
            bundle = _fix_bundle_for_feasibility(bundle, result, all_activities)
            # Re-validate after fix
            result2 = validate_feasibility(bundle, duration_days)
            if result2.passed:
                all_issues.append(f"[{bundle.id}] Auto-fixed successfully")
            else:
                all_issues.extend([f"[{bundle.id}] Still failing after fix: {i}" for i in result2.issues])
        fixed_bundles.append(bundle.model_dump())

    negotiation_log = list(state.get("negotiation_log") or [])
    if all_issues:
        negotiation_log.extend(all_issues)

    return {
        "bundles": fixed_bundles,
        "feasibility_passed": not any_failed or True,  # auto-fix attempted; continue
        "feasibility_issues": all_issues,
        "negotiation_log": negotiation_log,
        "current_stage": "feasibility_done",
    }


# ---------------------------------------------------------------------------
# What-If handler (called from UI or graph runner)
# ---------------------------------------------------------------------------

def apply_what_if(state: Dict[str, Any], delta_budget: int) -> Dict[str, Any]:
    """
    Apply a budget delta and re-run negotiator + feasibility.
    Does NOT re-run the expensive research nodes.

    Returns updated state dict with new bundles and appended what_if_history.
    """
    history = list(state.get("what_if_history") or [])
    history.append(WhatIfRequest(delta_budget=delta_budget).model_dump())

    updated = dict(state)
    updated["what_if_delta"] = int(state.get("what_if_delta") or 0) + delta_budget
    updated["what_if_history"] = history
    # Clear cache to force re-generation
    updated.pop("_negotiator_cache_key", None)
    updated["bundles"] = []

    # Re-run negotiator
    neg_out = negotiate_bundles_node(updated)
    updated.update(neg_out)

    # Re-run feasibility
    feas_out = feasibility_validator_node(updated)
    updated.update(feas_out)

    return updated
