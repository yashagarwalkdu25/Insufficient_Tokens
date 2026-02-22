# TASK-06: Search Agent Nodes (Flight, Hotel, Activity, Weather)

## PR Title: `feat: search agent nodes for flights, ground transport, hotels, activities, and weather`

## Priority: P1 (Core pipeline - produces the data everything else depends on)

## Summary
Implement the 4 parallel search agent nodes that fetch real-time data from external APIs with fallback handling, source tagging, and quality validation.

## Scope

### 1. Transport Search Node (app/graph/nodes/flight_search.py)
- `search_flights_node(state) → dict`
- Input: trip_request (origin, destination, dates, travelers, budget)
- Process:
  1. Calculate transport budget allocation
  2. Determine transport modes based on distance + budget:
     - Distance > 500km OR luxury style → search flights
     - Distance < 500km OR backpacker style → search ground transport (train/bus) as PRIMARY
     - Always search both when budget allows, let budget optimizer choose
  3. **Flight search**: Amadeus → Skyscanner URLs → MakeMyTrip URLs as FlightOption
  4. **Ground transport search**: generate GroundTransportOption entries:
     - IRCTC URL (train), RedBus URL (bus), MakeMyTrip train/bus URLs
     - Estimated prices from curated data (Delhi→Rishikesh bus ~₹500-800, train ~₹300-600)
     - Duration estimates from curated data or Google Directions API
     - source="curated" for estimated prices, source="fallback_url" for URL-only
  5. Score all options using calculate_score() method
  6. Return both flight_options AND ground_transport_options
- Output: flight_options, ground_transport_options, selected_outbound_flight, selected_return_flight
- Decision logging: "Found X flights and Y bus/train options, cheapest flight ₹Z, cheapest bus ₹W"
- Error handling: API failure returns empty + warning, does NOT crash pipeline

### 2. Hotel Search Node (app/graph/nodes/hotel_search.py)
- `search_hotels_node(state) → dict`
- Input: trip_request (destination, dates, budget, style)
- Process:
  1. Calculate accommodation budget
  2. Search via LiteAPI
  3. **Extract contact info from API response**: phone, email, address, check_in_time, check_out_time
  4. If LiteAPI fails → generate Booking.com + MakeMyTrip URLs
  5. Score hotels: price (30%), rating (25%), location (20%), amenities (15%), reviews (10%)
  6. Select best within budget per style (backpacker→hostels, luxury→5-star)
- Output: hotel_options, selected_hotel
- Every HotelOption MUST include: phone (str or None), email (str or None), address (str or None)
- Source tagging on every option

### 3. Activity Search Node (app/graph/nodes/activity_search.py)
- `search_activities_node(state) → dict`
- Input: trip_request (destination, interests, num_days, style)
- Process:
  1. Search Google Places for activities matching interests
  2. **Extract opening_hours** from Google Places response (regularOpeningHours → dict)
  3. **Extract contact info**: phone (internationalPhoneNumber), address (formattedAddress)
  4. Merge with curated activities from india_activities.py (curated data includes opening_hours and contact)
  5. Deduplicate by name/location
  6. Score by relevance to interests
  7. Select top activities (2-3 per day)
- Output: activities, selected_activities
- Every Activity MUST include: opening_hours (dict or None), phone (str or None), address (str or None)
- Curated items: source="curated", verified=True
- Google items: source="google_places", verified=True

### 4. Weather Check Node (app/graph/nodes/weather_check.py)
- `check_weather_node(state) → dict`
- Input: trip_request (destination, dates)
- Process:
  1. Get forecast from OpenWeatherMap
  2. If API fails → use seasonal data from india_cities.py
  3. Generate weather warnings (extreme heat, monsoon, cold)
  4. Flag days unsuitable for outdoor activities
- Output: weather_forecast (list[WeatherDay])

### 5. LLM Prompts (app/prompts/)
- No LLM calls needed for search agents (pure API calls)
- But each agent must produce structured AgentDecision for transparency

## Acceptance Criteria
- [ ] Flight search returns results with valid API keys
- [ ] Flight search returns Skyscanner URLs when Amadeus fails
- [ ] **Ground transport search returns train/bus options with IRCTC/RedBus URLs**
- [ ] **Budget trips (backpacker + short distance) prioritize ground transport over flights**
- [ ] Hotel search returns results or fallback URLs
- [ ] **Hotel results include phone/email/address when available from API**
- [ ] Activity search merges API + curated without duplicates
- [ ] **Activity results include opening_hours and phone/address when available**
- [ ] Weather returns forecast or seasonal fallback
- [ ] All results have correct source and verified fields
- [ ] Each agent logs AgentDecision with reasoning
- [ ] Empty API keys → graceful fallback, no crash
- [ ] API timeout → retry 3x → fallback, no crash
- [ ] Selected items are within budget allocation

## Dependencies
- TASK-01 (models)
- TASK-03 (API clients)
- TASK-05 (LangGraph state, graph builder registers these nodes)

## Estimated Files: 4 nodes + 0 prompts
## Estimated LOC: ~650
