"""
Fallback booking URL generators when primary APIs fail.
All URLs are valid search pages (Skyscanner, MakeMyTrip, Booking, IRCTC, RedBus).
"""
from urllib.parse import quote_plus


def generate_skyscanner_flight_url(origin_iata: str, dest_iata: str, date_str: str) -> str:
    """Skyscanner flight search URL. date_str: YYYY-MM-DD."""
    return (
        f"https://www.skyscanner.co.in/transport/flights/{origin_iata.lower()}/{dest_iata.lower()}/{date_str}/"
    )


def generate_makemytrip_flight_url(origin_iata: str, dest_iata: str, date_str: str) -> str:
    """MakeMyTrip flight search URL."""
    return (
        f"https://www.makemytrip.com/flights/{origin_iata.lower()}-{dest_iata.lower()}-flight-tickets.html?"
        f"tripType=O&paxType=A&intl=false&cabinClass=E&itinerary={origin_iata}-{dest_iata}-{date_str}"
    )


def generate_booking_hotel_url(city_name: str, checkin: str, checkout: str) -> str:
    """Booking.com hotel search. checkin/checkout: YYYY-MM-DD."""
    city = quote_plus(city_name)
    return f"https://www.booking.com/searchresults.html?ss={city}&checkin={checkin}&checkout={checkout}&group_adults=1"


def generate_makemytrip_hotel_url(city_name: str, checkin: str, checkout: str) -> str:
    """MakeMyTrip hotel search."""
    city = quote_plus(city_name)
    return f"https://www.makemytrip.com/hotels/{city}-hotels.html?checkin={checkin}&checkout={checkout}"


def generate_goibibo_hotel_url(city_name: str, checkin: str, checkout: str) -> str:
    """Goibibo hotel search."""
    city = quote_plus(city_name)
    return f"https://www.goibibo.com/hotels/{city}-hotels/?checkin={checkin}&checkout={checkout}"


def generate_irctc_url(origin_station: str, dest_station: str, date_str: str) -> str:
    """IRCTC train search. Opens search page with origin/dest/date."""
    return (
        "https://www.irctc.co.in/nget/train-search?"
        f"fromStationName={quote_plus(origin_station)}&toStationName={quote_plus(dest_station)}&dateOfJourney={date_str}"
    )


def generate_redbus_url(origin_city: str, dest_city: str, date_str: str) -> str:
    """RedBus bus search. date_str: DD-MM-YYYY for RedBus."""
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        redbus_date = dt.strftime("%d-%m-%Y")
    except Exception:
        redbus_date = date_str
    o = quote_plus(origin_city)
    d = quote_plus(dest_city)
    return f"https://www.redbus.in/bus-tickets/{o}-to-{d}?date={redbus_date}"


def generate_makemytrip_bus_url(origin_city: str, dest_city: str, date_str: str) -> str:
    """MakeMyTrip bus search."""
    o = quote_plus(origin_city)
    d = quote_plus(dest_city)
    return f"https://www.makemytrip.com/bus-tickets/{o}-to-{d}.html?date={date_str}"


def generate_makemytrip_train_url(origin_city: str, dest_city: str, date_str: str) -> str:
    """MakeMyTrip train search."""
    o = quote_plus(origin_city)
    d = quote_plus(dest_city)
    return f"https://www.makemytrip.com/railways/{o}-to-{d}.html?date={date_str}"
