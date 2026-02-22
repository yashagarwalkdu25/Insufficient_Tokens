"""Intent parser: extract TripRequest from raw_query (GPT or heuristic)."""
import json
import time
from datetime import date, timedelta
from typing import Any

from dateutil.parser import parse as date_parse

from app.config import get_settings
from app.data.india_cities import search_cities
from app.models.user import TripRequest


def _heuristic_parse(raw: str) -> dict[str, Any]:
    """Simple heuristic: look for city names and numbers."""
    raw_lower = raw.lower()
    dest = ""
    
    # Extended city list with better matching
    city_keywords = {
        "rishikesh": "Rishikesh",
        "goa": "Goa",
        "jaipur": "Jaipur",
        "manali": "Manali",
        "varanasi": "Varanasi",
        "delhi": "Delhi",
        "mumbai": "Mumbai",
        "kerala": "Kochi",
        "munnar": "Munnar",
        "kochi": "Kochi",
        "udaipur": "Udaipur",
        "agra": "Agra",
        "darjeeling": "Darjeeling",
        "shimla": "Shimla",
        "amritsar": "Amritsar",
        "jodhpur": "Jodhpur",
        "pushkar": "Pushkar",
        "pondicherry": "Pondicherry",
        "pondy": "Pondicherry",
        "coorg": "Coorg",
        "hampi": "Hampi",
        "leh": "Leh",
        "ladakh": "Leh",
    }
    
    # Find the first matching city
    for keyword, city_name in city_keywords.items():
        if keyword in raw_lower:
            dest = city_name
            break
    
    origin = "Delhi"
    if "mumbai" in raw_lower and "from" in raw_lower:
        origin = "Mumbai"
    elif "bangalore" in raw_lower and "from" in raw_lower:
        origin = "Delhi"
    
    budget = 15000
    for word in raw.split():
        if "k" in word.lower() or "000" in word:
            try:
                budget = int(word.replace("k", "000").replace("K", "000").replace(",", ""))
                if budget < 1000:
                    budget *= 1000
                break
            except ValueError:
                pass
    
    start = date.today() + timedelta(days=7)
    end = start + timedelta(days=2)
    if "weekend" in raw_lower:
        end = start + timedelta(days=1)
    if "week" in raw_lower or "4 day" in raw_lower or "4-day" in raw_lower:
        end = start + timedelta(days=3)
    if "5 day" in raw_lower or "5-day" in raw_lower:
        end = start + timedelta(days=4)
    
    style = "backpacker"
    if "luxury" in raw_lower:
        style = "luxury"
    elif "mid" in raw_lower or "midrange" in raw_lower:
        style = "balanced"
    
    interests = []
    if "adventure" in raw_lower or "rafting" in raw_lower or "trekking" in raw_lower:
        interests.append("adventure")
    if "spiritual" in raw_lower or "yoga" in raw_lower or "temple" in raw_lower:
        interests.append("spiritual")
    if "culture" in raw_lower or "heritage" in raw_lower:
        interests.append("culture")
    if "beach" in raw_lower:
        interests.append("beaches")
    
    return {
        "destination": dest,  # Empty string if no match
        "origin": origin,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "budget": float(budget),
        "currency": "INR",
        "traveler_type": "solo",
        "travel_style": style,
        "interests": interests or ["adventure"],
        "num_travelers": 1,
        "special_requirements": None,
    }


def parse_intent_node(state: dict[str, Any]) -> dict[str, Any]:
    """Parse raw_query into trip_request; use GPT if available else heuristic."""
    start = time.time()
    raw = (state.get("raw_query") or "").strip()
    if not raw:
        return {"current_stage": "intent_parsed", "agent_decisions": []}

    req_dict = None
    settings = get_settings()
    if settings.has_openai:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Build valid cities list for the LLM prompt
            valid_cities = list(search_cities(""))  # Get all cities
            city_names = [c.get("name", "") for c in valid_cities[:20]]  # Use first 20 for prompt
            
            r = client.chat.completions.create(
                model=settings.GPT4O_MODEL,
                messages=[
                    {"role": "system", "content": f"""Extract travel plan from the user message. Return only valid JSON with keys: destination (city), origin (city), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), budget (number), currency (INR), traveler_type (solo/couple/family/group), travel_style (backpacker/budget/balanced/luxury), interests (array of strings), num_travelers (number), special_requirements (string or null).

IMPORTANT: 
- Use FULL city names from this list ONLY: {', '.join(city_names)}
- If user says 'SA', interpret as 'South Africa' is NOT in India - ask for clarification or default to a popular Indian city
- NEVER use abbreviations or short forms for destination/origin
- Use today's date if not specified; for 'next weekend' use next Saturday-Sunday
- Budget in INR
- If destination is unclear, leave it empty for recommendation

Example valid destinations: Rishikesh, Goa, Jaipur, Manali, Varanasi, Delhi, Mumbai, Kochi, Udaipur"""},
                    {"role": "user", "content": raw},
                ],
            )
            content = (r.choices[0].message.content or "").strip()
            if content:
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()
                req_dict = json.loads(content)
                
                # Validate and normalize destination name
                dest = (req_dict.get("destination") or "").strip()
                if dest:
                    # Try exact match first
                    matched_cities = search_cities(dest)
                    if matched_cities:
                        # Use the first matched city's canonical name
                        req_dict["destination"] = matched_cities[0].get("name", dest)
                    elif len(dest) < 4:  # Likely an abbreviation
                        # Clear it so recommender runs
                        req_dict["destination"] = ""
                
                for k in ("start_date", "end_date"):
                    if isinstance(req_dict.get(k), str):
                        req_dict[k] = date_parse(req_dict[k]).date().isoformat()
        except Exception:
            pass
    if not req_dict:
        req_dict = _heuristic_parse(raw)
    if isinstance(req_dict.get("start_date"), date):
        req_dict["start_date"] = req_dict["start_date"].isoformat()
    if isinstance(req_dict.get("end_date"), date):
        req_dict["end_date"] = req_dict["end_date"].isoformat()
    
    # Final validation: ensure destination is valid or empty
    dest = (req_dict.get("destination") or "").strip()
    if dest and len(dest) < 4:  # Likely abbreviation
        req_dict["destination"] = ""  # Let recommender handle it
    
    try:
        tr = TripRequest(
            destination=req_dict.get("destination", ""),  # Empty if unclear
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
    decision = {"agent_name": "intent_parser", "action": "parse", "reasoning": f"Parsed query: {raw[:100]}", "result_summary": f"Destination: {dest_result}", "tokens_used": 0, "latency_ms": latency_ms}
    return {
        "trip_request": trip_request,
        "current_stage": "intent_parsed",
        "agent_decisions": [decision],
    }
