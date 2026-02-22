# TASK-01: Project Setup & Foundation

## PR Title: `feat: project scaffolding, config, and data models`

## Priority: P0 (Blocker - everything depends on this)

## Summary
Set up the complete project structure, dependencies, environment configuration, Pydantic data models, and SQLite database schema. This is the foundation every other task depends on.

## Scope

### 1. Project Structure
Create the full directory tree:
```
yatra-ai/
├── app/__init__.py
├── app/config.py
├── app/database.py
├── app/models/__init__.py
├── app/models/user.py
├── app/models/transport.py
├── app/models/accommodation.py
├── app/models/activity.py
├── app/models/budget.py
├── app/models/trip.py
├── app/models/local_intel.py
├── app/models/events.py
├── app/api/__init__.py
├── app/graph/__init__.py
├── app/graph/nodes/__init__.py
├── app/prompts/__init__.py
├── app/memory/__init__.py
├── app/ui/__init__.py
├── app/ui/components/__init__.py
├── app/export/__init__.py
├── app/export/templates/
├── app/data/__init__.py
├── app/utils/__init__.py
├── tests/__init__.py
├── demo/scenarios/
├── .env.example
├── .gitignore
├── requirements.txt
└── pyproject.toml
```

### 2. Configuration (app/config.py)
- Pydantic Settings class loading from .env
- All API keys: OpenAI, Amadeus, LiteAPI, Google Places, Google Directions, OpenWeatherMap, Reddit
- App config: debug, log_level, cache_ttl
- LangSmith config (optional)
- Property helpers: has_amadeus, has_hotels, has_places, has_directions, has_weather, has_reddit
- Validation: OpenAI key required, others optional with graceful degradation
- GOOGLE_DIRECTIONS_KEY (optional, same key as Google Places if Directions API enabled)

### 3. SQLite Database (app/database.py)
Tables:
- `users`: id (UUID), session_id, display_name, created_at, last_active
- `user_profiles`: user_id (FK), preferred_style, budget_range_low/high, home_city, dietary_restrictions (JSON), accessibility_needs (JSON), past_destinations (JSON), updated_at
- `trip_sessions`: id (UUID), user_id (FK), query, state_snapshot (JSON), stage, status (enum: planning|reviewing|approved|exported|abandoned), timestamps
- `conversation_history`: id, session_id (FK), role, content, content_summary, token_count, metadata (JSON), created_at
- `agent_decisions`: id, session_id (FK), agent_name, action, reasoning, input_summary, output_summary, tokens_used, latency_ms, created_at
- `api_cache`: cache_key (PK), endpoint, response_data (JSON), ttl_seconds, created_at, expires_at

Functions:
- `init_db()` - create tables if not exist
- `get_or_create_user(session_id)` - returns user record
- `save_trip_session(session_id, state)` - persist state
- `load_trip_session(session_id)` - restore state
- `save_conversation_message(...)` - store message
- `get_conversation_history(session_id, limit)` - retrieve messages
- `save_agent_decision(...)` - log agent reasoning
- `cache_get(key)` / `cache_set(key, data, ttl)` - L2 cache ops

### 4. Pydantic Data Models
All models must include `source` and `verified` fields for anti-hallucination:

**user.py**: TravelStyle(Enum), TravelerType(Enum), TransportPreference(Enum), PacePreference(Enum), UserPreferences(BaseModel), TripRequest(BaseModel) with computed fields (num_days, budget_per_day, get_budget_allocation)

**transport.py**: TransportType(Enum: flight/train/bus), FlightClass(Enum), FlightSegment(BaseModel), FlightOption(BaseModel) with scoring method calculate_score(), GroundTransportOption(BaseModel) with transport_type, operator, departure_time, arrival_time, duration_minutes, price, booking_url, source, verified — used for train/bus options

**accommodation.py**: HotelOption(BaseModel) with name, price_per_night, rating, amenities, booking_url, phone, email, address, contact_info, check_in_time, check_out_time, source, verified

**activity.py**: Activity(BaseModel) with name, description, category, duration, cost, location, lat/lon, booking_url, phone, address, opening_hours (dict[str, str] — day→"9:00-18:00"), best_time, source, verified. Restaurant(BaseModel) with phone, address, opening_hours

**budget.py**: BudgetTracker(BaseModel) with total_budget, allocated (dict), spent (dict), remaining, warnings, is_over_budget computed field

**trip.py**: ItineraryItemType(Enum), ItineraryItem(BaseModel) with travel_duration_to_next (minutes, int|None — travel time to next activity), travel_mode_to_next (str|None — "auto","walk","bus","train"), contact_info (str|None — phone/address for bookings), DayPlan(BaseModel), Trip(BaseModel) with title, destination, days, estimated_cost, booking_links

**local_intel.py**: TipSource(Enum), TipCategory(Enum), LocalTip(BaseModel), HiddenGem(BaseModel)

**events.py**: EventType(Enum), EventImpact(Enum), Event(BaseModel), VibeScore(BaseModel)

### 5. Dependencies (requirements.txt)
```
langchain>=0.3.0
langchain-openai>=0.2.0
langgraph>=0.2.0
streamlit>=1.40.0
streamlit-folium>=0.22.0
httpx>=0.27.0
tenacity>=9.0.0
pydantic>=2.9.0
pydantic-settings>=2.5.0
folium>=0.18.0
plotly>=5.24.0
weasyprint>=62.0
jinja2>=3.1.0
beautifulsoup4>=4.12.0
qrcode>=7.4.0
python-dotenv>=1.0.0
python-dateutil>=2.9.0
pytest>=8.3.0
```

### 6. Environment (.env.example)
All API keys with descriptions and defaults.

## Acceptance Criteria
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `python -c "from app.config import settings"` works with .env
- [ ] `python -c "from app.database import init_db; init_db()"` creates yatra.db with all tables
- [ ] All Pydantic models can be instantiated with sample data
- [ ] Every model with external data has `source` and `verified` fields
- [ ] .gitignore excludes .env, __pycache__, *.db, .venv
- [ ] Config gracefully handles missing optional API keys (has_* properties return False)

## Dependencies
None (this is the foundation)

## Estimated Files: ~15
## Estimated LOC: ~800
