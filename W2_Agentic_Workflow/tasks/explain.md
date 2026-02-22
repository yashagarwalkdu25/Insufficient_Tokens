# YATRA AI - Complete Architecture & Workflow Explanation

## Solving: AI League #2 - Agentic Workflow Building (Travel Planning Agent)

---

## 1. WHAT WE'RE BUILDING

**YATRA AI** (Your AI Travel & Routing Assistant) — A user-first, interactive, multi-agent travel planning system. Not a chatbot. An intelligent travel dashboard where users can plan, customize, and share complete trip itineraries powered by 13 AI agents collaborating in real-time.

### Problem → Solution Mapping

| Problem Statement Requirement | Our Solution |
|-------------------------------|-------------|
| Understand traveler intent | Intent Parser (GPT-4o) + Clarification Loop |
| Multi-agent workflow | 13 agents orchestrated by Supervisor via LangGraph |
| Real-world data | Amadeus (flights), LiteAPI (hotels), Google Places (activities), OpenWeatherMap |
| Smart decision-making | Budget Optimizer with scoring algo + trade-off reasoning |
| Transparency | Agent decision log stored in SQLite, viewable in UI |
| Human-in-the-loop | 3 checkpoints: destination, budget review, final approval |
| Actionable outputs | Booking links, QR codes, maps, contact info (phone/address) |
| Dynamic re-planning | Modification Subgraph: change analyzer → impact assessor → selective re-run |
| Travel duration between stops | Google Directions API + haversine fallback on every itinerary item |
| Opening hours validation | Google Places hours captured → itinerary builder validates scheduling |
| Train/bus transport | IRCTC, RedBus, MakeMyTrip ground transport URLs for budget trips |
| Contact info on bookings | Phone, email, address extracted from APIs → shown in UI + PDF |
| **Bonus: Visual itinerary** | Folium interactive map with day-wise color-coded routes + travel time labels |
| **Bonus: Local insider tips** | Reddit API + curated DB + GPT-4o hidden gems |
| Downloadable output | PDF (with QR codes), JSON, HTML export |
| No hallucinations | Source tagging on every data model, post-processing validation |

---

## 2. TECH STACK

```
Orchestration    : LangGraph 0.2+ (synchronous mode)
LLM (Complex)    : OpenAI GPT-4o (intent parsing, itinerary building)
LLM (Fast)       : OpenAI GPT-4o-mini (supervisor, optimization, scoring)
UI Framework     : Streamlit 1.40+
Database         : SQLite (users, sessions, cache, decisions)
Maps             : Folium + streamlit-folium
Charts           : Plotly
PDF Export       : WeasyPrint + Jinja2
QR Codes         : qrcode library
HTTP Client      : httpx + tenacity (retry with backoff)
Validation       : Pydantic v2
Scraping         : httpx + BeautifulSoup4
```

### External APIs

| API | Purpose | Fallback |
|-----|---------|----------|
| Amadeus Self-Service | Flight search | Skyscanner/MakeMyTrip URL generation |
| LiteAPI/Nuitee | Hotel search (with phone/email/address) | Booking.com/MakeMyTrip URL generation |
| Google Places | Activities, restaurants, opening hours, contact info | Curated activity database |
| Google Directions | Travel time between locations | Haversine distance-based estimation |
| OpenWeatherMap | Weather forecast | Seasonal averages database |
| Reddit API | Local travel tips | Curated tips database |
| IRCTC / RedBus (URLs) | Train/bus booking links | MakeMyTrip ground transport URLs |

---

## 3. ARCHITECTURE OVERVIEW

### 3.1 Three Subgraphs

The system has **three subgraphs** managed by a **Supervisor Agent**:

```
USER INPUT
    │
    ▼
SUPERVISOR (classifies intent)
    │
    ├── "Plan a trip to Goa"     → PLANNING SUBGRAPH
    ├── "Change hotel to cheaper" → MODIFICATION SUBGRAPH
    └── "What's the weather?"     → CONVERSATION SUBGRAPH
```

**Planning Subgraph**: Full pipeline for new trips (intent → search → optimize → build → approve).

**Modification Subgraph**: Targeted changes to existing plans (analyze change → identify affected agents → re-run only those → show diff).

**Conversation Subgraph**: Q&A about the current trip without triggering re-planning.

### 3.2 Memory Hierarchy

```
WORKING MEMORY     → Current trip state (LangGraph state dict)
                     Lives in memory during session, persisted to SQLite on every change

CONVERSATION MEMORY → Chat history with compression
                     Last 3 messages: full text
                     Older: GPT-4o-mini generated summary
                     Stored in SQLite conversation_history table

USER PROFILE        → Learned preferences across sessions
                     Preferred style, budget range, home city, past destinations
                     Updated after each completed trip
                     Stored in SQLite user_profiles table
```

### 3.3 Data Persistence (SQLite)

```
users               → id, session_id, display_name, timestamps
user_profiles       → preferences learned over time
trip_sessions       → full state snapshot (JSON), status, stage
conversation_history→ messages with compressed summaries
agent_decisions     → reasoning log per agent per session
api_cache           → L2 persistent cache with TTL
```

**Why SQLite**: Zero config, single file, survives server restarts, sufficient for hackathon scale, can migrate to Postgres later.

### 3.4 Caching Strategy

```
L1: In-memory Python dict (fastest, lost on restart)
L2: SQLite api_cache table (persistent, survives restart)

Read path:  L1 hit? → return. L1 miss? → L2 hit? → return + write L1. L2 miss? → API call → write L1 + L2.

TTL by data type:
  Flights    : 30 minutes (prices change frequently)
  Hotels     : 1 hour
  Weather    : 2 hours
  Places     : 24 hours
  Static data: No expiry
```

---

## 4. AGENT WORKFLOW (Detailed)

### Phase 1: User Input & Intent Parsing

```
User arrives → Onboarding screen with:
  • Destination autocomplete
  • Traveler type cards (Solo/Couple/Family/Group)
  • Budget slider
  • Date picker
  • Interest tags
  • OR free-text box

User submits → Supervisor classifies → routes to Planning Subgraph

Intent Parser (Agent 1, GPT-4o):
  • Extracts: destination, origin, dates, budget, style, interests
  • If ambiguous → Clarification Loop asks user specific questions
  • If no destination → Destination Recommender suggests 3 options → HITL #1
  • Output: validated TripRequest (Pydantic model)
```

### Phase 2: Parallel Research (Conditional Activation)

The Supervisor decides which agents to activate:

```
Condition                    → Agents Activated
Day trip / same city         → Skip Flight Search
Budget < ₹5000/day          → Skip luxury hotel sources
No Reddit API key            → Skip Reddit, use curated tips only
Destination not in India     → Skip India-specific data
```

Activated agents run in parallel (LangGraph fan-out):

```
┌──────────────┐ ┌─────────────┐ ┌──────────────┐ ┌─────────────┐
│ Transport    │ │ Hotel       │ │ Activity     │ │ Weather     │
│ Search       │ │ Search      │ │ Search       │ │ Check       │
│ (Agent 4)    │ │ (Agent 5)   │ │ (Agent 6)    │ │ (Agent 7)   │
│              │ │             │ │              │ │             │
│ Flights +    │ │ Returns:    │ │ Returns:     │ │             │
│ Train/Bus    │ │ phone,email │ │ opening_hours│ │             │
│ options      │ │ address     │ │ phone,address│ │             │
└──────┬───────┘ └──────┬──────┘ └──────┬───────┘ └──────┬──────┘
       │ try/except      │ try/except    │ try/except     │ try/except
       │ each agent      │ isolated      │ failure doesn't│ affect others
       └─────────────────┴───────┬───────┴────────────────┘
                                 │ fan-in
                                 ▼
                    Quality Check by Supervisor
                    "Did all agents return valid data?"
                    Failed? → Activate fallback source
```

Each agent has a **fallback chain**:
- Flights: Amadeus → Skyscanner URLs → MakeMyTrip URLs → "Search manually"
- **Ground Transport**: IRCTC URLs (train) → RedBus URLs (bus) → MakeMyTrip train/bus URLs → curated price estimates
- Hotels: LiteAPI (with phone/email/address) → Booking.com URLs → MakeMyTrip URLs → Curated list
- Activities: Google Places (with opening_hours + contact) → Curated DB → GPT-4o suggestions (tagged "AI suggested")
- Weather: OpenWeatherMap → Seasonal averages from static DB

**Transport mode selection**: For distances < 500km or backpacker style, ground transport (train/bus) is searched as PRIMARY alongside flights. Budget optimizer picks the best option based on price vs travel time trade-off.

### Phase 3: Enrichment (Conditional)

Only if supervisor decides it adds value (destination known, APIs available):

```
┌─────────────────┐  ┌─────────────────┐
│ Local Intel     │  │ Festival Check  │
│ (Agent 8)       │  │ (Agent 9)       │
│ Reddit + Curated│  │ Curated DB      │
│ + GPT-4o gems   │  │                 │
└────────┬────────┘  └────────┬────────┘
         └──────────┬─────────┘
                    ▼
```

### Phase 4: HITL Checkpoint #2 — Research Review

```
UI shows user:
  "Here's what I found for your Rishikesh trip:"
  • 5 flights (cheapest ₹3,200, best value ₹4,100)
  • 8 hotels (₹500-₹2,500/night range)
  • 12 activities matching your interests
  • Weather: 25-32°C, no rain expected
  • Budget feasibility: ✅ Within ₹15,000

User options:
  [Looks good, continue] → proceed to optimization
  [Adjust budget]        → slider, re-runs affected agents
  [Different options]    → feedback text, selective re-search
```

### Phase 5: Budget Optimization

```
Budget Optimizer (Agent 10, GPT-4o-mini):
  Input: all search results + budget constraints
  Process:
    1. Score each option: price_score(35%) + quality_score(25%) + convenience_score(20%) + fit_score(20%)
    2. Select best combination within budget
    3. If over budget: suggest trade-offs with reasoning
       "Choosing bus (₹800) over flight (₹3,200) saves ₹2,400 for better activities"
    4. Allocate budget by category based on travel style
  Output: selected flight, hotel, activities + budget_tracker

  Anti-hallucination: ONLY selects from API-returned options
  Every selection tagged: source="api", verified=true
```

### Phase 6: Itinerary Building

```
Itinerary Builder (Agent 11, GPT-4o):
  Input: selected items + weather + festivals + local tips
  Process:
    1. PRE-COMPUTE TRAVEL TIMES between all activity locations:
       - Google Directions API → exact driving/walking/transit time
       - Fallback: haversine distance × speed estimate (driving ~40km/h, walking ~5km/h)
       - Each ItineraryItem gets: travel_duration_to_next (minutes), travel_mode_to_next
    2. Arrange activities respecting:
       - Travel times between locations (now with real data)
       - OPENING HOURS VALIDATION: check each activity's opening_hours dict
         against scheduled time — reschedule if conflict, swap days if closed
       - Weather (no outdoor in rain/heat)
       - Temple visits early morning
       - Markets/shopping in evening
    3. Add meal recommendations from local tips
    4. Add travel duration display: "🚗 25 min auto ride" between items
    5. ATTACH CONTACT INFO to each item: phone, address from source Activity/Hotel
    6. Include local tips inline
  Output: Trip model with DayPlan[] → ItineraryItem[]
    Each ItineraryItem includes:
      - travel_duration_to_next: int (minutes) or None
      - travel_mode_to_next: str ("auto","walk","bus","train") or None
      - contact_info: str (phone + address) or None

  Structured output enforced via Pydantic model
  Every item must reference an API-sourced activity or be tagged source="llm"
  Opening hours validated — no scheduling during closed hours
```

### Phase 7: Vibe Scoring

```
Vibe Scorer (Agent 12, GPT-4o-mini):
  Input: final itinerary + user preferences
  Output:
    overall_score: 87%
    breakdown: {adventure: 92%, culture: 78%, relaxation: 65%}
    tagline: "Your spiritual adventure awaits!"
    perfect_matches: ["Rafting matches your adventure vibe"]
    considerations: ["Limited nightlife options"]
```

### Phase 8: HITL Checkpoint #3 — Final Review (Interactive Dashboard)

```
Full Trip Dashboard with tabs:
  📅 Itinerary   → Editable day cards with Swap/Add/Remove buttons
  🗺️ Map         → Interactive Folium map with day-wise routes
  💰 Budget      → Pie chart + per-day bar chart + sliders
  🕵️ Tips        → Insider tips, hidden gems, festivals
  📊 AI Reasoning → Decision log: why each choice was made

User can:
  ✅ [Approve & Export] → proceed to export
  🔄 [Modify via chat] → "make it cheaper" → Modification Subgraph
  ✏️ [Edit directly]   → click Swap/Add/Remove in itinerary
  🔃 [Start Over]      → clear and re-plan
```

### Phase 9: Plan Customization (Interactive)

When user clicks [Swap Flight]:
1. Modal shows all flight_options from state
2. User picks alternative
3. System recalculates: budget → itinerary timing → vibe score
4. Shows diff: "Flight changed. Saved ₹800. Day 1 arrival now 2pm."

When user clicks [+ Add Activity]:
1. Activity browser filtered by destination + day availability
2. System checks: time slot available? budget impact?
3. If over budget → suggests: "Remove X to fit this in"
4. Adds to itinerary, auto-updates everything

Budget slider adjustment:
1. Budget Optimizer re-runs with new total
2. Shows suggestions: "Downgrade hotel to save ₹700/night"
3. User cherry-picks which suggestions to accept

### Phase 10: Export & Sharing

```
PDF Export (WeasyPrint + Jinja2):
  • Cover page: title, dates, vibe score, tagline
  • Day-by-day pages: times, locations, costs, tips
  • Budget summary: pie chart + breakdown table
  • Booking links page: each with QR code
  • Map snapshot: static image from Folium
  • Hidden gems appendix

JSON Export: Full trip state, re-importable

HTML Export: Self-contained single file, works offline

QR Code Sharing:
  • Trip overview QR → shareable link to view trip
  • Per-booking QRs → direct booking site links
  • In-app QR modal for quick mobile sharing

Shareable Link:
  • Unique trip_id stored in SQLite
  • URL: app/?id=<trip_id>
  • Recipient sees read-only view
```

---

## 5. MODIFICATION SUBGRAPH (Dynamic Re-planning)

When user says "change hotel to cheaper" or "my flight got delayed":

```
CHANGE ANALYZER (Supervisor)
  "What did user ask to change?"
  → Categorizes: hotel_change / budget_change / date_change / activity_change / disruption
       │
       ▼
IMPACT ASSESSOR
  "What agents/data are affected?"
  Uses dependency graph:
    hotel_change → re-run: hotel_search, budget_optimizer, itinerary_builder, vibe_scorer
    flight_delay → re-run: itinerary_builder (Day 1 only), vibe_scorer
    budget_change → re-run: budget_optimizer, itinerary_builder, vibe_scorer
  Preserves: unaffected search results (flight data, weather, tips)
       │
       ▼
SELECTIVE RE-RUN
  Only affected agents execute (saves time + tokens)
       │
       ▼
DIFF GENERATOR
  "Here's what changed:"
  • Hotel: Zostel (₹800) → Hostel Moustache (₹500) — saved ₹900 total
  • Day 2 schedule adjusted: check-in time changed
  • Budget: ₹14,200 → ₹13,300 (₹900 saved)
       │
       ▼
Back to HITL Checkpoint #3
```

---

## 6. TOKEN MANAGEMENT

```
Agent              │ Model       │ Max Tokens │ Strategy
Supervisor         │ GPT-4o-mini │ 2,000      │ Routing only, minimal context
Intent Parser      │ GPT-4o      │ 3,000      │ Full query + format instructions
Dest. Recommender  │ GPT-4o-mini │ 1,500      │ Preferences summary only
Budget Optimizer   │ GPT-4o-mini │ 2,500      │ Summarized search results (not raw)
Itinerary Builder  │ GPT-4o      │ 4,000      │ Selected items + weather summary
Vibe Scorer        │ GPT-4o-mini │ 1,500      │ Itinerary summary + preferences
Local Intel AI     │ GPT-4o-mini │ 2,000      │ Tips context + interests
Feedback Handler   │ GPT-4o-mini │ 1,500      │ Feedback + affected state slice
Change Analyzer    │ GPT-4o-mini │ 1,500      │ User message + state summary
Clarification      │ GPT-4o-mini │ 1,000      │ Ambiguous fields only

Context compression: Each agent receives ONLY the state fields it needs,
with API data summarized to key metrics (not raw JSON).
```

---

## 7. ERROR RECOVERY

| Failure | Recovery |
|---------|----------|
| API timeout | Tenacity retry (3x, exponential backoff) → fallback source → curated data |
| API returns empty | Warning to user + use curated data + tag as "limited data" |
| All APIs down | Curated data + GPT-4o suggestions (tagged "AI suggested") |
| OpenAI down | Error screen: "AI service unavailable, try again shortly" |
| Over budget | Budget optimizer suggests trade-offs, user decides |
| Ambiguous query | Clarification loop asks specific questions |
| Browser refresh | State restored from SQLite, resume from last checkpoint |
| Server restart | State restored from SQLite |
| Hallucination | Post-processing strips any data not from API sources |

---

## 8. ANTI-HALLUCINATION STRATEGY

Every Pydantic data model includes:
```python
source: Literal["api", "curated", "llm"]  # Where did this data come from?
verified: bool                              # Was it verified against real data?
```

Rules:
1. Hotels, flights, prices → MUST be `source="api"` or `source="curated"`, `verified=True`
2. Activity suggestions from GPT → `source="llm"`, `verified=False`, shown with badge
3. Itinerary builder receives ONLY verified data
4. Post-processing validation strips any hotel name / price not in original API response
5. Display: unverified items shown with "AI suggested" indicator

---

## 9. DIRECTORY STRUCTURE

```
yatra-ai/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Streamlit entry point
│   ├── config.py                   # Pydantic settings
│   ├── database.py                 # SQLite setup + models
│   │
│   ├── models/                     # Pydantic data models
│   │   ├── user.py                 # TripRequest, UserPreferences
│   │   ├── transport.py            # FlightOption, FlightSegment
│   │   ├── accommodation.py        # HotelOption
│   │   ├── activity.py             # Activity, Restaurant
│   │   ├── budget.py               # BudgetTracker
│   │   ├── trip.py                 # Trip, DayPlan, ItineraryItem
│   │   ├── local_intel.py          # LocalTip, HiddenGem
│   │   └── events.py               # Event, VibeScore
│   │
│   ├── api/                        # External API clients
│   │   ├── base.py                 # BaseAPIClient with retry + cache
│   │   ├── amadeus_client.py       # Flights
│   │   ├── liteapi_client.py       # Hotels (with phone/email/address)
│   │   ├── google_places.py        # Activities (with opening_hours + contact)
│   │   ├── google_directions.py    # Travel time between locations + haversine fallback
│   │   ├── weather_client.py       # Weather
│   │   ├── reddit_client.py        # Local tips
│   │   └── booking_links.py        # URL generators: Skyscanner/MMT/Booking/IRCTC/RedBus
│   │
│   ├── graph/                      # LangGraph implementation
│   │   ├── state.py                # TravelPlannerState
│   │   ├── supervisor.py           # Supervisor routing logic
│   │   ├── nodes/
│   │   │   ├── intent_parser.py
│   │   │   ├── destination_recommender.py
│   │   │   ├── flight_search.py
│   │   │   ├── hotel_search.py
│   │   │   ├── activity_search.py
│   │   │   ├── weather_check.py
│   │   │   ├── local_intel.py
│   │   │   ├── festival_check.py
│   │   │   ├── budget_optimizer.py
│   │   │   ├── itinerary_builder.py
│   │   │   ├── vibe_scorer.py
│   │   │   ├── approval_gate.py
│   │   │   └── feedback_handler.py
│   │   ├── edges.py                # Conditional routing
│   │   ├── builder.py              # Graph construction
│   │   └── runner.py               # Execution with streaming
│   │
│   ├── memory/                     # Memory management
│   │   ├── working_memory.py       # Current session state
│   │   ├── conversation_memory.py  # Compressed chat history
│   │   ├── user_profile.py         # Learned preferences
│   │   └── context_compressor.py   # Token-efficient summaries
│   │
│   ├── prompts/                    # LLM prompt templates
│   │   ├── intent_parser.py
│   │   ├── supervisor.py
│   │   ├── budget_optimizer.py
│   │   ├── itinerary_builder.py
│   │   ├── vibe_scorer.py
│   │   └── feedback_handler.py
│   │
│   ├── ui/                         # Streamlit UI components
│   │   ├── components/
│   │   │   ├── onboarding.py       # Trip input form
│   │   │   ├── planning_progress.py# Animated agent progress
│   │   │   ├── trip_dashboard.py   # Main results view
│   │   │   ├── itinerary_editor.py # Editable day cards
│   │   │   ├── map_view.py         # Folium interactive map
│   │   │   ├── budget_view.py      # Charts + sliders
│   │   │   ├── local_tips_view.py  # Tips + gems + events
│   │   │   ├── vibe_score_view.py  # Vibe match display
│   │   │   ├── reasoning_view.py   # Agent decision log
│   │   │   ├── share_modal.py      # QR code + export buttons
│   │   │   ├── chat_sidebar.py     # Modification chat
│   │   │   └── approval_section.py # HITL review UI
│   │   └── styles.py               # Custom CSS
│   │
│   ├── export/                     # Export generators
│   │   ├── pdf_generator.py        # WeasyPrint PDF with QR codes
│   │   ├── json_exporter.py        # JSON state export
│   │   ├── html_exporter.py        # Self-contained HTML
│   │   ├── qr_generator.py         # QR code generation
│   │   └── templates/
│   │       └── itinerary.html      # Jinja2 PDF template
│   │
│   ├── data/                       # Static/curated data
│   │   ├── india_cities.py         # IATA codes, coordinates
│   │   ├── india_activities.py     # Curated activities per city
│   │   ├── india_festivals.py      # Festival calendar
│   │   └── local_tips_db.py        # Fallback tips
│   │
│   └── utils/
│       ├── scoring.py              # Option scoring functions
│       ├── validators.py           # Data validation
│       └── formatters.py           # Display formatting
│
├── tests/
├── demo/scenarios/                 # 3 sample trip JSONs
├── .env.example
├── requirements.txt
└── README.md
```

---

## 10. DELIVERABLES CHECKLIST

| # | Deliverable | How We Cover It |
|---|------------|-----------------|
| 1 | Working demo | Streamlit app with interactive dashboard |
| 2 | Solo backpacking sample | Rishikesh, ₹15K, adventure+spiritual |
| 3 | Family vacation sample | Goa, ₹60K, kid-friendly beaches |
| 4 | Weekend getaway sample | Jaipur from Delhi, mid-range, culture |
| 5 | Architecture diagram | Mermaid/ASCII in README + explain.md |
| 6 | Agent roles & responsibilities | 13 agents documented |
| 7 | Data sources & APIs | 7 APIs (+ IRCTC/RedBus URLs) + curated DBs |
| 8 | Workflow orchestration | LangGraph with 3 subgraphs |
| 9 | Decision-making process | Scoring algorithms + LLM reasoning |
| 10 | HITL integration | 3 checkpoints + interactive editing |
| 11 | Technical explanation | This document + README |
| 12 | **Bonus: Interactive map** | Folium with day-wise color routes |
| 13 | **Bonus: Local tips** | Reddit + curated + AI hidden gems |
| 14 | PDF export | WeasyPrint with QR codes |
| 15 | Shareable plans | QR codes + shareable links |

---

## 11. GAP CLOSURE — ZERO GAPS WITH PROBLEM STATEMENT

Every requirement from the problem statement is fully addressed:

| Requirement | Implementation | Files |
|---|---|---|
| **Travel duration between stops** | Google Directions API for exact driving/walking/transit time. Haversine-based estimation as fallback when API key unavailable. Every ItineraryItem has `travel_duration_to_next` (minutes) and `travel_mode_to_next` (auto/walk/bus/train). Displayed as "🚗 25 min" badges in itinerary + map labels. | `api/google_directions.py`, `graph/nodes/itinerary_builder.py`, `ui/components/itinerary_editor.py` |
| **Opening hours validation** | Google Places extracts `regularOpeningHours` → stored as `opening_hours: dict[str, str]` on Activity. Curated DB also includes hours. Itinerary builder validates: no scheduling during closed hours, no visits on closed days. Conflicts trigger automatic rescheduling. UI shows "Open 9AM-6PM" or "Closed on Mondays" warnings. | `api/google_places.py`, `graph/nodes/activity_search.py`, `graph/nodes/itinerary_builder.py` |
| **Train/bus transport options** | Ground transport searched alongside flights for budget trips (distance < 500km or backpacker style). GroundTransportOption model with estimated prices from curated data. URL generators: IRCTC (trains), RedBus (buses), MakeMyTrip bus/train. Budget optimizer weighs flight vs bus/train (price vs time trade-off with reasoning). | `models/transport.py`, `api/booking_links.py`, `graph/nodes/flight_search.py` |
| **Contact info on all bookings** | Hotels: phone, email, address, check-in/check-out times from LiteAPI. Activities: phone, address from Google Places. Every ItineraryItem carries `contact_info`. Surfaced in: itinerary editor (📞 line), map popups, PDF export (booking links page with QR + contact). | `models/accommodation.py`, `models/activity.py`, `models/trip.py`, `ui/components/itinerary_editor.py` |
| **Booking-ready actionable outputs** | Every flight/hotel/activity has `booking_url` linking to booking platform. QR codes per booking link in PDF. Fallback URL generators for Skyscanner, MakeMyTrip, Booking.com, IRCTC, RedBus. Contact info for direct phone booking. One-click-to-book links throughout UI and exports. | `api/booking_links.py`, `export/pdf_generator.py`, `export/qr_generator.py` |
