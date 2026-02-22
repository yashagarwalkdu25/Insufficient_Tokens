"""
Curated Indian festivals and events for trip planning.
Used for festival_check agent and date recommendations.
"""
from datetime import date
from typing import Any

FESTIVALS: list[dict[str, Any]] = [
    {
        "name": "Diwali",
        "description": "Festival of lights; major Hindu festival across India.",
        "typical_month": 11,
        "date_range": None,
        "locations": ["All India"],
        "impact": "positive",
        "recommendation": "Vibrant celebrations, lit-up cities. Book accommodation early; prices spike.",
        "price_impact": "high",
    },
    {
        "name": "Holi",
        "description": "Festival of colors; spring celebration.",
        "typical_month": 3,
        "date_range": None,
        "locations": ["North India", "Mathura", "Vrindavan", "Jaipur"],
        "impact": "positive",
        "recommendation": "Great time to visit — street celebrations. Wear clothes you don't mind staining.",
        "price_impact": "moderate",
    },
    {
        "name": "Navratri",
        "description": "Nine nights of dance and devotion; especially big in Gujarat and Maharashtra.",
        "typical_month": 10,
        "date_range": None,
        "locations": ["Gujarat", "Mumbai", "All India"],
        "impact": "positive",
        "recommendation": "Dandiya and Garba nights. Join local events for authentic experience.",
        "price_impact": "moderate",
    },
    {
        "name": "Durga Puja",
        "description": "Bengal's biggest festival; elaborate pandals and celebrations.",
        "typical_month": 10,
        "date_range": None,
        "locations": ["Kolkata", "West Bengal"],
        "impact": "positive",
        "recommendation": "Peak time to visit Kolkata — stunning pandals and cultural events.",
        "price_impact": "high",
    },
    {
        "name": "Ganesh Chaturthi",
        "description": "Elephant god festival; huge in Maharashtra.",
        "typical_month": 9,
        "date_range": None,
        "locations": ["Mumbai", "Pune", "Maharashtra"],
        "impact": "positive",
        "recommendation": "Processions and immersions. Expect crowds and road closures.",
        "price_impact": "moderate",
    },
    {
        "name": "Eid ul-Fitr",
        "description": "Islamic festival marking end of Ramadan.",
        "typical_month": 4,
        "date_range": None,
        "locations": ["All India"],
        "impact": "positive",
        "recommendation": "Feast and community celebrations. Some shops may close briefly.",
        "price_impact": "none",
    },
    {
        "name": "Christmas & New Year (Goa)",
        "description": "Peak season in Goa with parties and beach events.",
        "typical_month": 12,
        "date_range": (12, 25, 1, 5),
        "locations": ["Goa"],
        "impact": "positive",
        "recommendation": "Great time for beaches and nightlife. Book months in advance; prices very high.",
        "price_impact": "high",
    },
    {
        "name": "Pushkar Camel Fair",
        "description": "World's largest camel fair; cultural and livestock fair.",
        "typical_month": 11,
        "date_range": None,
        "locations": ["Pushkar", "Rajasthan"],
        "impact": "positive",
        "recommendation": "Unique experience — book Pushkar accommodation early. Prices triple.",
        "price_impact": "high",
    },
    {
        "name": "Rath Yatra",
        "description": "Chariot festival; major in Puri, Odisha.",
        "typical_month": 7,
        "date_range": None,
        "locations": ["Puri", "Odisha"],
        "impact": "positive",
        "recommendation": "Massive crowds. Plan transport and stay in advance.",
        "price_impact": "moderate",
    },
    {
        "name": "Onam",
        "description": "Harvest festival of Kerala; flower carpets and boat races.",
        "typical_month": 9,
        "date_range": None,
        "locations": ["Kerala"],
        "impact": "positive",
        "recommendation": "Best time to experience Kerala culture. Snake boat races are spectacular.",
        "price_impact": "moderate",
    },
    {
        "name": "Pongal",
        "description": "Tamil harvest festival; four-day celebration.",
        "typical_month": 1,
        "date_range": None,
        "locations": ["Tamil Nadu"],
        "impact": "positive",
        "recommendation": "Traditional rituals and feasts. Some businesses closed.",
        "price_impact": "none",
    },
    {
        "name": "Republic Day",
        "description": "National holiday with parade in Delhi.",
        "typical_month": 1,
        "date_range": (1, 26, 1, 26),
        "locations": ["Delhi", "All India"],
        "impact": "positive",
        "recommendation": "Delhi parade is spectacular. Heavy security; book viewing in advance.",
        "price_impact": "moderate",
    },
    {
        "name": "Kumbh Mela",
        "description": "Mass Hindu pilgrimage; rotates between Prayagraj, Haridwar, Nashik, Ujjain.",
        "typical_month": 1,
        "date_range": None,
        "locations": ["Prayagraj", "Haridwar", "Nashik", "Ujjain"],
        "impact": "positive",
        "recommendation": "Once-in-lifetime experience but extreme crowds. Plan logistics carefully.",
        "price_impact": "high",
    },
    {
        "name": "Hemis Festival",
        "description": "Ladakh's most famous monastery festival; mask dances.",
        "typical_month": 7,
        "date_range": None,
        "locations": ["Leh", "Ladakh"],
        "impact": "positive",
        "recommendation": "Peak season for Ladakh. Permits and accommodation book early.",
        "price_impact": "high",
    },
    {
        "name": "Hornbill Festival",
        "description": "Nagaland's festival of festivals; tribal culture and music.",
        "typical_month": 12,
        "date_range": (12, 1, 12, 10),
        "locations": ["Kohima", "Nagaland"],
        "impact": "positive",
        "recommendation": "Inner Line Permit required. Book flights and stay well in advance.",
        "price_impact": "high",
    },
]


def get_festivals_for_dates(
    destination: str,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """
    Return festivals that overlap with the trip dates and are relevant to the destination.
    destination can be city name or "All India".
    """
    out = []
    dest_lower = destination.lower() if destination else ""
    sm, sd = start_date.month, start_date.day
    em, ed = end_date.month, end_date.day

    for f in FESTIVALS:
        locs = f.get("locations", [])
        in_dest = "all india" in dest_lower or any(
            dest_lower in loc.lower() or loc.lower() in dest_lower for loc in locs
        )
        if not in_dest:
            continue
        month = f.get("typical_month")
        if not month:
            continue
        # Simple overlap: festival month overlaps trip
        if start_date.month <= month <= end_date.month:
            out.append(f)
        elif start_date.month > end_date.month and (month >= start_date.month or month <= end_date.month):
            out.append(f)
    return out
