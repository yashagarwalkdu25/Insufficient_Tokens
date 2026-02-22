# TASK-02: Static Data & Curated Databases

## PR Title: `feat: India cities, festivals, curated tips, and activity databases`

## Priority: P0 (Required by search agents and enrichment agents)

## Summary
Create all static/curated data files that serve as fallback when APIs are unavailable and as enrichment data for the planning pipeline.

## Scope

### 1. India Cities Database (app/data/india_cities.py)
Dictionary of 20+ Indian cities with:
- name, state, IATA code, latitude, longitude
- type tags (spiritual, adventure, beach, cultural, etc.)
- best_months, avoid_months (seasonal awareness)
- timezone
- nearest_airport (if different from city)
- permit_required (bool) - for Ladakh, Arunachal, etc.
- permit_details (str) - processing time, where to apply

Cities: Delhi, Mumbai, Bangalore, Chennai, Kolkata, Hyderabad, Goa, Jaipur, Rishikesh, Varanasi, Kerala/Kochi, Manali, Ladakh/Leh, Udaipur, Shimla, Darjeeling, Amritsar, Agra, Jodhpur, Andaman/Port Blair

Also include **ground transport estimates** between popular city pairs:
- Dict of (origin, destination) → {bus_price_range: str, train_price_range: str, bus_duration_hours: float, train_duration_hours: float}
- Cover at least 15 popular routes: Delhi→Rishikesh, Delhi→Jaipur, Delhi→Agra, Delhi→Manali, Mumbai→Goa, Mumbai→Pune, Bangalore→Mysore, etc.

Helper functions:
- `get_city_data(name) → dict | None`
- `get_iata_code(name) → str`
- `get_city_coordinates(name) → tuple[float, float] | None`
- `search_cities(query) → list[dict]` (fuzzy match)
- `get_cities_by_type(type_tag) → list[dict]`
- `get_ground_transport_estimate(origin, destination) → dict | None`

### 2. India Festivals Database (app/data/india_festivals.py)
List of 15+ major festivals/events with:
- name, description, event_type, impact (positive/caution/avoid)
- city (or "All India"), start_date, end_date
- impact_description, recommendation
- expected_crowds, booking_advice
- is_must_see, best_experience_tip

Include: Diwali, Holi, Durga Puja, Ganesh Chaturthi, Eid, Christmas/New Year (Goa), Pushkar Fair, Kumbh Mela, Ganga Aarti (daily Rishikesh/Varanasi), International Yoga Day, Republic Day, Onam, Pongal, Navratri

Also daily/recurring events (Ganga Aarti, weekly markets).

Helper functions:
- `get_events_for_dates(start, end, city=None) → list[Event]`
- `get_city_events(city) → list[Event]`

### 3. Curated Activities (app/data/india_activities.py)
Per-city curated activity lists (at least 8 cities, 5-10 activities each):
- name, description, category, estimated_cost, duration_minutes
- latitude, longitude, booking_url (real URLs)
- best_time, tips
- **opening_hours: dict[str, str]** (e.g., {"Monday": "06:00-18:00"}) — include for all attractions with fixed hours (monuments, museums, temples with timings)
- **phone: str or None** — official contact number or booking office number where available
- **address: str** — full address for each activity
- source="curated", verified=True

### 4. Curated Local Tips (app/data/local_tips_db.py)
Per-city tips (at least 5 cities, 4-8 tips each) covering:
- Food, Safety, Transport, Money, Culture, Photography, Timing
- Each with title, content, category, upvotes (curated score), relevance_score

Per-city hidden gems (at least 5 cities, 2-3 gems each):
- name, why_special, best_time, pro_tip, confidence_score
- latitude, longitude (real coordinates)

Helper functions:
- `get_curated_tips(city) → list[LocalTip]`
- `get_hidden_gems(city) → list[HiddenGem]`

## Acceptance Criteria
- [ ] All city IATA codes are valid
- [ ] All coordinates are real (verified against Google Maps)
- [ ] All booking URLs are real, working links
- [ ] **All curated activities include opening_hours where applicable** (monuments, museums close by 5-6 PM)
- [ ] **All curated activities include address field**
- [ ] **Phone numbers included where available** (tourism offices, booking contacts)
- [ ] Festival dates cover 2025-2026
- [ ] `get_events_for_dates()` correctly finds overlapping events
- [ ] `search_cities("rishikesh")` returns correct result
- [ ] Every curated item has source="curated", verified=True
- [ ] At least 20 cities, 15 festivals, 50 activities, 30 tips, 15 gems

## Dependencies
- TASK-01 (Pydantic models for LocalTip, HiddenGem, Event, Activity)

## Estimated Files: 4
## Estimated LOC: ~1000
