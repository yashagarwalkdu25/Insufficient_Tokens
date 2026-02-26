"""Intent parser: extract TripRequest from raw_query (GPT or heuristic)."""
import json
import logging
import re
import time
from datetime import date, timedelta
from typing import Any

from dateutil.parser import parse as date_parse

from app.config import get_settings
from app.data.india_cities import search_cities, INDIA_CITIES
from app.models.user import TripRequest

logger = logging.getLogger(__name__)


def _extract_destination_heuristic(raw: str) -> tuple[str, str]:
    """Extract destination and origin from raw text using pattern matching.

    Returns (destination, origin). Either may be empty.
    """
    raw_lower = raw.lower()

    dest = ""
    origin = ""

    to_pattern = re.search(r'\bto\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\s*[,.]|\s+(?:from|for|under|budget|with|in|on|\d)|\s*$)', raw, re.IGNORECASE)
    if to_pattern:
        dest = to_pattern.group(1).strip().title()

    from_pattern = re.search(r'\bfrom\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\s*[,.]|\s+(?:to|for|under|budget|with|in|on|\d)|\s*$)', raw, re.IGNORECASE)
    if from_pattern:
        origin = from_pattern.group(1).strip().title()

    if not dest:
        for city_name in INDIA_CITIES:
            if city_name.lower() in raw_lower:
                if city_name.lower() != origin.lower():
                    dest = city_name
                    break

    if not origin:
        origin = "Delhi"

    return dest, origin


def _heuristic_parse(raw: str) -> dict[str, Any]:
    """Parse trip details from raw text without LLM."""
    raw_lower = raw.lower()

    dest, origin = _extract_destination_heuristic(raw)

    budget = 15000
    for word in raw.split():
        cleaned = word.replace(",", "").replace("₹", "")
        if "k" in cleaned.lower() or "000" in cleaned:
            try:
                num = int(cleaned.lower().replace("k", "000"))
                if num < 1000:
                    num *= 1000
                budget = num
                break
            except ValueError:
                pass

    start = date.today() + timedelta(days=7)
    end = start + timedelta(days=2)
    if "weekend" in raw_lower:
        end = start + timedelta(days=1)
    for n in range(2, 15):
        if f"{n} day" in raw_lower or f"{n}-day" in raw_lower:
            end = start + timedelta(days=n - 1)
            break
    if "week" in raw_lower and "weekend" not in raw_lower:
        end = start + timedelta(days=6)

    style = "backpacker"
    if "luxury" in raw_lower:
        style = "luxury"
    elif "mid" in raw_lower or "midrange" in raw_lower:
        style = "balanced"

    traveler_type = "solo"
    if "family" in raw_lower:
        traveler_type = "family"
    elif "couple" in raw_lower:
        traveler_type = "couple"
    elif "group" in raw_lower or "friends" in raw_lower:
        traveler_type = "group"

    interests: list[str] = []
    interest_map = {
        "adventure": ["adventure", "rafting", "trekking", "paragliding", "bungee"],
        "spiritual": ["spiritual", "yoga", "temple", "meditation", "ashram"],
        "culture": ["culture", "heritage", "history", "museum", "fort"],
        "beaches": ["beach", "sea", "ocean", "coast"],
        "nature": ["nature", "hills", "mountains", "valley", "scenic"],
        "food": ["food", "culinary", "cuisine", "street food"],
        "wildlife": ["wildlife", "safari", "jungle", "national park"],
        "shopping": ["shopping", "market", "bazaar"],
    }
    for interest, keywords in interest_map.items():
        if any(kw in raw_lower for kw in keywords):
            interests.append(interest)

    return {
        "destination": dest,
        "origin": origin,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "budget": float(budget),
        "currency": "INR",
        "traveler_type": traveler_type,
        "travel_style": style,
        "interests": interests or ["adventure"],
        "num_travelers": 1,
        "special_requirements": None,
    }


def parse_intent_node(state: dict[str, Any]) -> dict[str, Any]:
    """Parse raw_query into trip_request; use GPT if available else heuristic."""
    start = time.time()

    existing_req = state.get("trip_request") or {}
    existing_dest = (existing_req.get("destination") or "").strip()
    if existing_dest:
        latency_ms = int((time.time() - start) * 1000)
        return {
            "trip_request": existing_req,
            "current_stage": "intent_parsed",
            "agent_decisions": [{
                "agent_name": "intent_parser",
                "action": "skip",
                "reasoning": f"Trip request already has destination '{existing_dest}' — skipping re-parse.",
                "result_summary": f"Destination: {existing_dest}",
                "tokens_used": 0,
                "latency_ms": latency_ms,
            }],
        }

    raw = (state.get("raw_query") or "").strip()
    if not raw:
        return {"current_stage": "intent_parsed", "agent_decisions": []}

    req_dict = None
    settings = get_settings()
    if settings.has_openai:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            today = date.today().isoformat()

            r = client.chat.completions.create(
                model=settings.GPT4O_MODEL,
                messages=[
                    {"role": "system", "content": f"""Extract travel plan from the user message. Return only valid JSON with keys: destination (city name), origin (city name), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), budget (number), currency (INR), traveler_type (solo/couple/family/group), travel_style (backpacker/budget/balanced/luxury), interests (array of strings), num_travelers (number), special_requirements (string or null).

IMPORTANT:
- Accept ANY valid Indian city or town as destination — not limited to popular tourist cities.
- Use the FULL city/town name exactly as the user wrote it (properly capitalized).
- If the user mentions "from X to Y", X is origin and Y is destination.
- Today's date is {today}. For 'next weekend' use next Saturday-Sunday.
- Budget in INR. Default to 15000 if not specified.
- If destination is genuinely unclear or not mentioned at all, leave it as empty string.
- Do NOT leave destination empty if the user clearly named a city/town — even if it's a small or uncommon place."""},
                    {"role": "user", "content": raw},
                ],
            )
            content = (r.choices[0].message.content or "").strip()
            if content:
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()
                req_dict = json.loads(content)

                for k in ("start_date", "end_date"):
                    if isinstance(req_dict.get(k), str):
                        req_dict[k] = date_parse(req_dict[k]).date().isoformat()
        except Exception as exc:
            logger.warning("LLM intent parsing failed: %s", exc)

    if not req_dict:
        req_dict = _heuristic_parse(raw)

    if isinstance(req_dict.get("start_date"), date):
        req_dict["start_date"] = req_dict["start_date"].isoformat()
    if isinstance(req_dict.get("end_date"), date):
        req_dict["end_date"] = req_dict["end_date"].isoformat()

    try:
        tr = TripRequest(
            destination=req_dict.get("destination", ""),
            origin=req_dict.get("origin", "Delhi"),
            start_date=date.fromisoformat(str(req_dict.get("start_date", date.today()))[:10]),
            end_date=date.fromisoformat(str(req_dict.get("end_date", date.today() + timedelta(days=2)))[:10]),
            budget=float(req_dict.get("budget", 15000)),
            currency=req_dict.get("currency", "INR"),
            traveler_type=req_dict.get("traveler_type", "solo"),
            travel_style=req_dict.get("travel_style", "backpacker"),
            interests=req_dict.get("interests", []),
            num_travelers=int(req_dict.get("num_travelers", 1)),
            special_requirements=req_dict.get("special_requirements"),
        )
        trip_request = tr.model_dump()
        for k in ("start_date", "end_date"):
            v = trip_request.get(k)
            if hasattr(v, "isoformat"):
                trip_request[k] = v.isoformat()
    except Exception:
        trip_request = _heuristic_parse(raw)

    latency_ms = int((time.time() - start) * 1000)
    dest_result = trip_request.get('destination') or "To be recommended"
    decision = {
        "agent_name": "intent_parser",
        "action": "parse",
        "reasoning": f"Parsed query: {raw[:100]}",
        "result_summary": f"Destination: {dest_result}",
        "tokens_used": 0,
        "latency_ms": latency_ms,
    }
    return {
        "trip_request": trip_request,
        "current_stage": "intent_parsed",
        "agent_decisions": [decision],
    }
