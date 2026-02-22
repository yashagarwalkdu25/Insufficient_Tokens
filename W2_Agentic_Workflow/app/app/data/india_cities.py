"""
Curated database of Indian cities for TripSaathi.
Real coordinates and IATA codes; used for autocomplete and destination logic.
"""
from __future__ import annotations

from typing import Any

# Structure: name, state, iata_code, latitude, longitude, best_season, avoid_season,
# known_for, budget_range, permit_required, permit_info, nearby_airport
INDIA_CITIES: dict[str, dict[str, Any]] = {
    "Delhi": {
        "name": "Delhi",
        "state": "Delhi",
        "iata_code": "DEL",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "best_season": [10, 11, 2, 3],
        "avoid_season": [5, 6, 7],
        "known_for": ["history", "culture", "food", "shopping", "monuments"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹8000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "DEL",
    },
    "Mumbai": {
        "name": "Mumbai",
        "state": "Maharashtra",
        "iata_code": "BOM",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "best_season": [11, 12, 1, 2],
        "avoid_season": [5, 6, 7],
        "known_for": ["beaches", "nightlife", "bollywood", "gateway"],
        "budget_range": {
            "backpacker": "₹1000-₹2500/day",
            "midrange": "₹4000-₹8000/day",
            "luxury": "₹10000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "BOM",
    },
    "Goa": {
        "name": "Goa",
        "state": "Goa",
        "iata_code": "GOI",
        "latitude": 15.2993,
        "longitude": 74.1240,
        "best_season": [11, 12, 1, 2],
        "avoid_season": [5, 6, 7],
        "known_for": ["beaches", "nightlife", "water sports", "food"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹8000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "GOI",
    },
    "Jaipur": {
        "name": "Jaipur",
        "state": "Rajasthan",
        "iata_code": "JAI",
        "latitude": 26.9124,
        "longitude": 75.7873,
        "best_season": [10, 11, 2, 3],
        "avoid_season": [5, 6],
        "known_for": ["culture", "forts", "heritage", "photography"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹8000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "JAI",
    },
    "Rishikesh": {
        "name": "Rishikesh",
        "state": "Uttarakhand",
        "iata_code": "DED",
        "latitude": 30.0869,
        "longitude": 78.2676,
        "best_season": [2, 3, 4, 9, 10, 11],
        "avoid_season": [6, 7, 8],
        "known_for": ["yoga", "adventure", "spiritual", "rafting"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹2500-₹5000/day",
            "luxury": "₹6000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "DED",
    },
    "Manali": {
        "name": "Manali",
        "state": "Himachal Pradesh",
        "iata_code": "KULLU",
        "latitude": 32.2396,
        "longitude": 77.1887,
        "best_season": [3, 4, 5, 9, 10],
        "avoid_season": [7, 8],
        "known_for": ["mountains", "adventure", "snow", "trekking"],
        "budget_range": {
            "backpacker": "₹1000-₹2500/day",
            "midrange": "₹3500-₹7000/day",
            "luxury": "₹9000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "KULLU",
    },
    "Varanasi": {
        "name": "Varanasi",
        "state": "Uttar Pradesh",
        "iata_code": "VNS",
        "latitude": 25.3176,
        "longitude": 82.9739,
        "best_season": [10, 11, 2, 3],
        "avoid_season": [5, 6],
        "known_for": ["spiritual", "culture", "temples", "ganga"],
        "budget_range": {
            "backpacker": "₹600-₹1500/day",
            "midrange": "₹2500-₹5000/day",
            "luxury": "₹6000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "VNS",
    },
    "Udaipur": {
        "name": "Udaipur",
        "state": "Rajasthan",
        "iata_code": "UDR",
        "latitude": 24.5854,
        "longitude": 73.7125,
        "best_season": [9, 10, 11, 2, 3],
        "avoid_season": [5, 6],
        "known_for": ["culture", "lakes", "palaces", "romantic"],
        "budget_range": {
            "backpacker": "₹1000-₹2500/day",
            "midrange": "₹3500-₹7000/day",
            "luxury": "₹9000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "UDR",
    },
    "Agra": {
        "name": "Agra",
        "state": "Uttar Pradesh",
        "iata_code": "AGR",
        "latitude": 27.1767,
        "longitude": 78.0081,
        "best_season": [10, 11, 2, 3],
        "avoid_season": [5, 6],
        "known_for": ["taj mahal", "heritage", "monuments"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹7000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "AGR",
    },
    "Darjeeling": {
        "name": "Darjeeling",
        "state": "West Bengal",
        "iata_code": "IXB",
        "latitude": 27.0410,
        "longitude": 88.2663,
        "best_season": [3, 4, 5, 9, 10],
        "avoid_season": [6, 7, 8],
        "known_for": ["tea", "mountains", "toy train", "nature"],
        "budget_range": {
            "backpacker": "₹1000-₹2500/day",
            "midrange": "₹3500-₹6000/day",
            "luxury": "₹8000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "IXB",
    },
    "Shimla": {
        "name": "Shimla",
        "state": "Himachal Pradesh",
        "iata_code": "SLV",
        "latitude": 31.1048,
        "longitude": 77.1734,
        "best_season": [3, 4, 5, 9, 10],
        "avoid_season": [7, 8],
        "known_for": ["mountains", "colonial", "nature", "family"],
        "budget_range": {
            "backpacker": "₹1000-₹2500/day",
            "midrange": "₹3500-₹7000/day",
            "luxury": "₹9000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "SLV",
    },
    "Munnar": {
        "name": "Munnar",
        "state": "Kerala",
        "iata_code": "COK",
        "latitude": 10.0889,
        "longitude": 77.0595,
        "best_season": [9, 10, 11, 12, 1],
        "avoid_season": [5, 6, 7],
        "known_for": ["tea", "nature", "hills", "photography"],
        "budget_range": {
            "backpacker": "₹1000-₹2500/day",
            "midrange": "₹3500-₹6000/day",
            "luxury": "₹8000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "COK",
    },
    "Kochi": {
        "name": "Kochi",
        "state": "Kerala",
        "iata_code": "COK",
        "latitude": 9.9312,
        "longitude": 76.2673,
        "best_season": [9, 10, 11, 12, 1, 2],
        "avoid_season": [5, 6],
        "known_for": ["backwaters", "culture", "food", "history"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹8000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "COK",
    },
    "Hampi": {
        "name": "Hampi",
        "state": "Karnataka",
        "iata_code": "BLR",
        "latitude": 15.3350,
        "longitude": 76.4600,
        "best_season": [10, 11, 12, 1, 2],
        "avoid_season": [5, 6],
        "known_for": ["ruins", "history", "culture", "photography"],
        "budget_range": {
            "backpacker": "₹600-₹1500/day",
            "midrange": "₹2500-₹5000/day",
            "luxury": "₹6000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "BLR",
    },
    "Leh": {
        "name": "Leh",
        "state": "Ladakh",
        "iata_code": "IXL",
        "latitude": 34.1526,
        "longitude": 77.5771,
        "best_season": [5, 6, 7, 8, 9],
        "avoid_season": [11, 12, 1, 2],
        "known_for": ["mountains", "adventure", "biking", "monasteries"],
        "budget_range": {
            "backpacker": "₹1500-₹3500/day",
            "midrange": "₹5000-₹10000/day",
            "luxury": "₹12000+/day",
        },
        "permit_required": True,
        "permit_info": "Inner Line Permit (ILP) required for certain areas. Apply online or at Leh office.",
        "nearby_airport": "IXL",
    },
    "Amritsar": {
        "name": "Amritsar",
        "state": "Punjab",
        "iata_code": "ATQ",
        "latitude": 31.6340,
        "longitude": 74.8723,
        "best_season": [10, 11, 2, 3],
        "avoid_season": [5, 6],
        "known_for": ["golden temple", "culture", "food", "history"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹7000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "ATQ",
    },
    "Jodhpur": {
        "name": "Jodhpur",
        "state": "Rajasthan",
        "iata_code": "JDH",
        "latitude": 26.2389,
        "longitude": 73.0243,
        "best_season": [10, 11, 2, 3],
        "avoid_season": [5, 6],
        "known_for": ["forts", "blue city", "culture", "photography"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹8000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "JDH",
    },
    "Pushkar": {
        "name": "Pushkar",
        "state": "Rajasthan",
        "iata_code": "JAI",
        "latitude": 26.4897,
        "longitude": 74.5511,
        "best_season": [10, 11, 2, 3],
        "avoid_season": [5, 6],
        "known_for": ["camel fair", "spiritual", "lakes", "culture"],
        "budget_range": {
            "backpacker": "₹600-₹1500/day",
            "midrange": "₹2500-₹5000/day",
            "luxury": "₹6000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "JAI",
    },
    "Pondicherry": {
        "name": "Pondicherry",
        "state": "Puducherry",
        "iata_code": "PNY",
        "latitude": 11.9416,
        "longitude": 79.8083,
        "best_season": [10, 11, 12, 1, 2],
        "avoid_season": [5, 6],
        "known_for": ["beaches", "french colony", "ashram", "cycling"],
        "budget_range": {
            "backpacker": "₹800-₹2000/day",
            "midrange": "₹3000-₹6000/day",
            "luxury": "₹7000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "PNY",
    },
    "Coorg": {
        "name": "Coorg",
        "state": "Karnataka",
        "iata_code": "BLR",
        "latitude": 12.3375,
        "longitude": 75.8069,
        "best_season": [9, 10, 11, 12, 1, 2],
        "avoid_season": [5, 6, 7],
        "known_for": ["coffee", "nature", "trekking", "waterfalls"],
        "budget_range": {
            "backpacker": "₹1000-₹2500/day",
            "midrange": "₹3500-₹7000/day",
            "luxury": "₹9000+/day",
        },
        "permit_required": False,
        "permit_info": "",
        "nearby_airport": "BLR",
    },
}


def get_city(name: str) -> Any:
    """Get city data by exact or normalized name."""
    key = name.strip()
    for k, v in INDIA_CITIES.items():
        if k.lower() == key.lower():
            return dict(v)
    return None


def search_cities(query: str) -> list[dict[str, Any]]:
    """Fuzzy search cities by name or state."""
    q = query.strip().lower()
    if not q:
        return []
    out = []
    for name, data in INDIA_CITIES.items():
        if q in name.lower() or q in data.get("state", "").lower():
            out.append(dict(data))
    return out


def get_cities_for_interests(interests: list[str]) -> list[dict[str, Any]]:
    """Return cities that match given interest tags."""
    if not interests:
        return list(INDIA_CITIES.values())
    interest_set = {s.lower().strip() for s in interests}
    out = []
    for data in INDIA_CITIES.values():
        known = {k.lower() for k in data.get("known_for", [])}
        if interest_set & known:
            out.append(dict(data))
    return out


def get_cities_by_budget(style: str) -> list[dict[str, Any]]:
    """Return cities (all have budget_range; filter by style if needed)."""
    style = (style or "midrange").lower()
    if style not in ("backpacker", "midrange", "luxury"):
        return list(INDIA_CITIES.values())
    return [dict(d) for d in INDIA_CITIES.values()]
