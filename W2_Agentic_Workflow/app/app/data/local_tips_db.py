"""
Curated local tips and hidden gems per city.
Used by local_intel agent when Reddit API is unavailable or to supplement.
"""
from typing import Any

# Structure: city -> { tips: list[dict], hidden_gems: list[dict] }
LOCAL_DATA: dict[str, dict[str, list[dict[str, Any]]]] = {
    "Rishikesh": {
        "tips": [
            {
                "title": "Shared autos from Rishikesh station",
                "content": "Shared autos from Rishikesh bus/rail area to Laxman Jhula cost ₹10-20 per person. Don't pay more than ₹30 for a full auto.",
                "category": "transport",
            },
            {
                "title": "Rafting season",
                "content": "Rafting runs Sep–Jun. Monsoon (Jul–Aug) is usually closed. Book with registered operators; check for life jackets.",
                "category": "safety",
            },
            {
                "title": "ATM and cash",
                "content": "ATMs are available in Rishikesh town and Tapovan. Laxman Jhula area has fewer ATMs; carry some cash.",
                "category": "money",
            },
            {
                "title": "Ganga Aarti timing",
                "content": "Parmarth Niketan aarti is around 6 PM. Reach 15–20 min early for a good spot. Free; donation optional.",
                "category": "culture",
            },
            {
                "title": "Yoga and meditation",
                "content": "Many ashrams offer drop-in classes. Parmarth and Sivananda are popular. Donation-based or nominal fee.",
                "category": "culture",
            },
        ],
        "hidden_gems": [
            {
                "name": "Kunjapuri Temple at sunrise",
                "description": "Hilltop temple with 360° views of the Himalayas and Ganges valley.",
                "why_special": "Less crowded than Neelkanth; stunning sunrise and Garhwal range visibility.",
                "pro_tip": "Leave by 4:30 AM from Rishikesh; shared jeeps go from Laxman Jhula. Dress warm.",
                "category": "spiritual",
                "latitude": 30.1789,
                "longitude": 78.4333,
            },
            {
                "name": "Rajaji National Park (near Rishikesh)",
                "description": "Wildlife sanctuary with elephants, tigers, and birdlife; safari by jeep.",
                "why_special": "Easily combined with Rishikesh; less known than Corbett.",
                "pro_tip": "Book safari in advance. Best in winter (Nov–Mar).",
                "category": "nature",
                "latitude": 30.0833,
                "longitude": 78.0833,
            },
            {
                "name": "Vashishta Cave",
                "description": "Small cave by the Ganges where sage Vashishta meditated; very peaceful.",
                "why_special": "Quiet spot away from main ghats; locals meditate here.",
                "pro_tip": "Visit early morning. Remove shoes; minimal fee.",
                "category": "spiritual",
                "latitude": 30.1025,
                "longitude": 78.2980,
            },
        ],
    },
    "Goa": {
        "tips": [
            {
                "title": "Two-wheeler rental",
                "content": "Rent a scooter or bike (₹300–500/day) for North Goa. Have a valid license; helmet mandatory.",
                "category": "transport",
            },
            {
                "title": "Beach shack billing",
                "content": "Beach shacks often have minimum consumption. Confirm prices for fish and drinks before ordering.",
                "category": "food",
            },
            {
                "title": "Sunset vs sunrise beaches",
                "content": "West coast = sunset (Baga, Calangute, Anjuna). For sunrise, head to the eastern side or backwaters.",
                "category": "culture",
            },
            {
                "title": "Monsoon (Jun–Sep)",
                "content": "Many shacks and water sports close. Great for greenery, rain, and lower prices; swimming can be risky.",
                "category": "safety",
            },
            {
                "title": "SIM and connectivity",
                "content": "Jio/Airtel work well in towns. Some beaches have patchy signal. Cafes have Wi-Fi.",
                "category": "money",
            },
        ],
        "hidden_gems": [
            {
                "name": "Butterfly Beach (South Goa)",
                "description": "Small cove reachable by boat from Palolem or Agonda; clear water and quiet.",
                "why_special": "Less commercial; good snorkeling and dolphin sightings.",
                "pro_tip": "Take the morning boat; afternoon can get crowded. Carry water and snacks.",
                "category": "nature",
                "latitude": 15.0019,
                "longitude": 74.0176,
            },
            {
                "name": "Fontainhas (Panjim)",
                "description": "Latin quarter with colorful Portuguese-era houses and galleries.",
                "why_special": "Walking heritage area; great for photography and cafés.",
                "pro_tip": "Go early morning for soft light. Joseph's Bakery for local snacks.",
                "category": "culture",
                "latitude": 15.4989,
                "longitude": 73.8278,
            },
            {
                "name": "Netravali Bubble Lake",
                "description": "Natural bubbling spring in South Goa forest; surreal and lesser-visited.",
                "why_special": "Unique natural phenomenon; off the main tourist trail.",
                "pro_tip": "Hire a local guide; combine with Netravali wildlife sanctuary.",
                "category": "nature",
                "latitude": 15.1167,
                "longitude": 74.2333,
            },
        ],
    },
    "Jaipur": {
        "tips": [
            {
                "title": "Amber Fort timing",
                "content": "Opens 8 AM. Go early to avoid crowds and heat. Elephant ride is optional (book at gate).",
                "category": "transport",
            },
            {
                "title": "Rickshaws and haggling",
                "content": "Fix price before boarding. From railway station to Hawa Mahal area: around ₹80–120 for auto.",
                "category": "transport",
            },
            {
                "title": "Markets and fixed price",
                "content": "Bapu Bazaar, Johari Bazaar: bargaining expected. Government emporiums have fixed prices.",
                "category": "money",
            },
            {
                "title": "Summer heat",
                "content": "Apr–Jun is very hot. Plan indoor sites (museums, City Palace) midday; forts early or late.",
                "category": "safety",
            },
            {
                "title": "Composite ticket",
                "content": "Rajasthan tourism composite ticket covers multiple monuments; can save money for 2-day visits.",
                "category": "money",
            },
        ],
        "hidden_gems": [
            {
                "name": "Panna Meena Ka Kund",
                "description": "Stepwell near Amber Fort; symmetrical steps and great for photography.",
                "why_special": "Less crowded than the fort; Instagram-famous geometry.",
                "pro_tip": "Visit just after sunrise or before sunset. Free entry.",
                "category": "culture",
                "latitude": 26.9856,
                "longitude": 75.8522,
            },
            {
                "name": "Nahargarh Biological Park",
                "description": "Zoo and rescue center on the way to Nahargarh; good for families.",
                "why_special": "Views of Jaipur from the hills; tigers and leopards.",
                "pro_tip": "Combine with Nahargarh Fort. Open 10–5:30.",
                "category": "nature",
                "latitude": 26.9350,
                "longitude": 75.8150,
            },
            {
                "name": "Jawahar Kala Kendra",
                "description": "Arts center designed by Charles Correa; galleries, theater, and café.",
                "why_special": "Modern architecture; local art and performances.",
                "pro_tip": "Check schedule for evening performances. Café is a good break from heritage tours.",
                "category": "culture",
                "latitude": 26.8600,
                "longitude": 75.7980,
            },
        ],
    },
}


def get_tips(city: str) -> list[dict[str, Any]]:
    """Return curated tips for the city."""
    for k, v in LOCAL_DATA.items():
        if k.lower() == city.strip().lower():
            return list(v.get("tips", []))
    return []


def get_hidden_gems(city: str) -> list[dict[str, Any]]:
    """Return curated hidden gems for the city."""
    for k, v in LOCAL_DATA.items():
        if k.lower() == city.strip().lower():
            return list(v.get("hidden_gems", []))
    return []
