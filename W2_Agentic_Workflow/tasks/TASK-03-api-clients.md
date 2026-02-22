# TASK-03: API Client Layer

## PR Title: `feat: API clients for flights, hotels, activities, weather, Reddit, directions, ground transport`

## Priority: P0 (Required by all search agents)

## Summary
Build all external API clients with retry logic, error handling, 2-layer caching (in-memory + SQLite), and fallback URL generation.

## Scope

### 1. Base API Client (app/api/base.py)
- Abstract base class `BaseAPIClient` with:
  - httpx.AsyncClient management (context manager)
  - Tenacity retry: 3 attempts, exponential backoff, retry on timeout/connect errors
  - Error classification: APIError, RateLimitError, AuthenticationError, NotFoundError
  - Request logging
- `CachedAPIClient(BaseAPIClient)` with:
  - L1: in-memory dict cache (per-process)
  - L2: SQLite api_cache table (persistent)
  - Cache key: MD5(endpoint + sorted params)
  - TTL-based expiry (configurable per client)
  - `get_cached(endpoint, params)` → check L1 → L2 → API call → write both

### 2. Amadeus Client (app/api/amadeus_client.py)
- OAuth2 token management with auto-refresh
- `search_flights(origin, dest, date, return_date, adults, class, max_results, max_price) → list[FlightOption]`
- IATA code normalization (city name → code)
- Response parser: Amadeus JSON → FlightOption models
- Duration parser: ISO 8601 (PT2H30M) → minutes
- Booking URL generator: Skyscanner deep links
- Source tagging: source="amadeus", verified=True

### 3. LiteAPI Client (app/api/liteapi_client.py)
- `search_hotels(dest, checkin, checkout, guests, max_results) → list[HotelOption]`
- Response parser → HotelOption models
- Price normalization to INR
- Source tagging: source="liteapi", verified=True

### 4. Google Places Client (app/api/google_places.py)
- `search_activities(location, interests, radius_km) → list[Activity]`
- `get_place_details(place_id) → Activity`
- Category mapping: Google types → our categories
- **Extract opening_hours**: parse Google's `regularOpeningHours` → dict[str, str] (e.g., {"Monday": "09:00-18:00"})
- **Extract contact info**: phone (internationalPhoneNumber), address (formattedAddress), website
- Source tagging: source="google_places", verified=True

### 4b. Google Directions Client (app/api/google_directions.py)
- `GoogleDirectionsClient(CachedAPIClient)`
- Uses Google Directions API: `https://maps.googleapis.com/maps/api/directions/json`
- `get_travel_time(origin_lat, origin_lng, dest_lat, dest_lng, mode="driving") → dict`:
  - Returns: {duration_minutes: int, distance_km: float, mode: str}
  - Modes: "driving", "walking", "transit"
- `get_travel_times_batch(locations: list[tuple[float,float]]) → list[dict]`:
  - Given ordered list of (lat,lng), returns travel times between consecutive pairs
  - Used by itinerary builder to add travel durations between activities
- **Fallback**: `estimate_travel_time(origin_lat, origin_lng, dest_lat, dest_lng) → dict`:
  - Uses haversine distance formula
  - Estimates: driving ~40 km/h in city, walking ~5 km/h, auto-rickshaw ~25 km/h
  - Returns same dict format as API version
  - Used when Google Directions API key is not configured
- Cache TTL: 86400 (24 hours — routes don't change)

### 5. Weather Client (app/api/weather_client.py)
- `get_forecast(city, num_days) → list[WeatherDay]`
- 5-day forecast from OpenWeatherMap
- Temperature in Celsius, rain probability
- Weather warnings (extreme heat, heavy rain, etc.)
- Fallback: seasonal averages from india_cities.py

### 6. Reddit Client (app/api/reddit_client.py)
- OAuth2 client credentials flow
- `search_travel_tips(destination, subreddits, limit) → list[LocalTip]`
- Subreddits: travel, india, incredibleindia, solotravel, backpacking
- Post parser → LocalTip models with category detection
- Rate limit awareness (respect Reddit API limits)
- Source tagging: source="reddit", verified=False

### 7. Booking Link Generator (app/api/booking_links.py)
Fallback URL generators when APIs fail:
- `generate_skyscanner_url(origin, dest, date) → str`
- `generate_makemytrip_flight_url(origin, dest, date) → str`
- `generate_makemytrip_hotel_url(dest, checkin, checkout) → str`
- `generate_booking_com_url(dest, checkin, checkout) → str`
- `generate_google_maps_url(lat, lon) → str`
- **`generate_irctc_url(origin_station, dest_station, date) → str`** — redirects to IRCTC train search (no deep link possible, opens search page)
- **`generate_redbus_url(origin_city, dest_city, date) → str`** — RedBus search URL for bus tickets
- **`generate_makemytrip_bus_url(origin_city, dest_city, date) → str`** — MakeMyTrip bus search
- **`generate_makemytrip_train_url(origin_city, dest_city, date) → str`** — MakeMyTrip train search

All URLs must be tested and working. Ground transport URLs are critical for budget trips where bus/train is the primary mode.

## Acceptance Criteria
- [ ] Each client works with valid API keys (manual test)
- [ ] Each client returns empty list (not crash) when API key missing
- [ ] Each client returns empty list (not crash) on API timeout
- [ ] Retry logic triggers on 429/timeout (visible in debug logs)
- [ ] L1 cache returns same data on second call (no API hit)
- [ ] L2 cache survives process restart (SQLite persistence)
- [ ] All returned models have correct source and verified fields
- [ ] Booking link URLs are valid and open correct pages
- [ ] Amadeus IATA normalization handles 30+ Indian cities
- [ ] Reddit client respects rate limits
- [ ] Google Places returns opening_hours and phone/address when available
- [ ] Google Directions returns travel time between two coordinates
- [ ] Haversine fallback returns reasonable estimates when Directions API key missing
- [ ] IRCTC, RedBus, MakeMyTrip bus/train URLs are valid and open correct search pages

## Dependencies
- TASK-01 (config, database, Pydantic models)

## Estimated Files: 9 (added google_directions.py, expanded booking_links.py)
## Estimated LOC: ~1150
