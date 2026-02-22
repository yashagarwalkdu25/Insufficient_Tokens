# YATRA AI - Execution Flow

## High-Level Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER ARRIVES                              │
│                    (Streamlit app loads)                          │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SESSION INIT                                   │
│  • get_or_create_user(session_id) → SQLite users table           │
│  • Load user_profile if returning user                           │
│  • Restore last trip_session if exists                           │
│  • Initialize LangGraph runner (sync mode)                       │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                  ONBOARDING SCREEN                                │
│                                                                  │
│  Option A: Interactive Form           Option B: Free Text        │
│  ┌─────────────────────────┐         ┌────────────────────────┐  │
│  │ Destination [autocomplete]│       │ "Plan a 4-day solo     │  │
│  │ Traveler [Solo/Family/...]│       │  trip to Rishikesh     │  │
│  │ Budget [₹ slider]        │       │  under 15K from Delhi  │  │
│  │ Dates [calendar picker]  │       │  next weekend"         │  │
│  │ Interests [tag pills]    │       └────────────────────────┘  │
│  │ Style [Budget/Mid/Luxury]│                                    │
│  └─────────────────────────┘                                     │
│                                                                  │
│              [  🚀 Plan My Trip  ]                                │
└─────────────────────────┬────────────────────────────────────────┘
                          │ User submits
                          ▼
╔══════════════════════════════════════════════════════════════════╗
║                    SUPERVISOR AGENT                              ║
║              (GPT-4o-mini, ~2K tokens)                          ║
║                                                                  ║
║  Classifies intent:                                              ║
║   • "Plan a trip..."     → PLANNING SUBGRAPH                    ║
║   • "Change the hotel"   → MODIFICATION SUBGRAPH                ║
║   • "What's the weather?" → CONVERSATION SUBGRAPH               ║
║                                                                  ║
║  Decides conditional activation:                                 ║
║   • Day trip? → skip flight search                              ║
║   • Budget < ₹5K/day? → skip luxury sources                    ║
║   • No Reddit key? → skip Reddit, use curated                  ║
╚══════════════════╦══════════════╦════════════════╦═══════════════╝
                   │              │                │
     ┌─────────────┘              │                └──────────────┐
     ▼                            ▼                               ▼
 PLANNING              MODIFICATION                    CONVERSATION
 SUBGRAPH              SUBGRAPH                        SUBGRAPH
 (new trip)            (edit existing)                  (Q&A only)
```

---

## Planning Subgraph (Detailed)

```
═══════════════════════════════════════════════════════════════════
 PHASE 1: INTENT PARSING
═══════════════════════════════════════════════════════════════════

User Input (form or text)
       │
       ▼
┌─────────────────────────────────────────┐
│         INTENT PARSER                    │
│         (GPT-4o, ~3K tokens)            │
│                                          │
│  Input: raw query OR form data           │
│  Process:                                │
│    1. Extract structured fields          │
│    2. Resolve relative dates             │
│    3. Estimate budget if missing         │
│    4. Detect ambiguity                   │
│  Output: TripRequest (Pydantic)          │
│                                          │
│  Ambiguous? ──────► CLARIFICATION LOOP   │
│    "For how many days?"                  │
│    "What's your budget range?"           │
│    User responds → re-parse              │
│                                          │
│  No destination? ──► DEST RECOMMENDER    │
└────────────┬──────────────┬──────────────┘
             │              │
     Has destination    No destination
             │              │
             │              ▼
             │   ┌──────────────────────────┐
             │   │  DESTINATION RECOMMENDER  │
             │   │  (GPT-4o-mini, ~1.5K)    │
             │   │                          │
             │   │  Analyzes: style, budget, │
             │   │  dates, interests         │
             │   │  Returns: 3 options with  │
             │   │  reasoning                │
             │   └──────────┬───────────────┘
             │              │
             │              ▼
             │   ┌──────────────────────────┐
             │   │  🛑 HITL CHECKPOINT #1   │
             │   │  "Choose destination"     │
             │   │  [Rishikesh] [Manali]     │
             │   │  [Darjeeling]             │
             │   │  User picks one → update  │
             │   └──────────┬───────────────┘
             │              │
             └──────┬───────┘
                    │ TripRequest validated
                    ▼
═══════════════════════════════════════════════════════════════════
 PHASE 2: PARALLEL SEARCH (Fan-out)
═══════════════════════════════════════════════════════════════════

Supervisor activates relevant agents:

┌──────────────┐ ┌─────────────┐ ┌──────────────┐ ┌─────────────┐
│  TRANSPORT   │ │   HOTEL     │ │  ACTIVITY    │ │  WEATHER    │
│  SEARCH      │ │   SEARCH    │ │   SEARCH     │ │   CHECK     │
│              │ │             │ │              │ │             │
│ Flights:     │ │ LiteAPI     │ │ Google       │ │ OpenWeather │
│ Amadeus API  │ │ +phone,email│ │ Places API   │ │ Map API     │
│    ↓ fail    │ │ +address    │ │ +opening_hrs │ │    ↓ fail   │
│ Skyscanner   │ │    ↓ fail   │ │ +phone,addr  │ │ Seasonal DB │
│    ↓ fail    │ │ Booking.com │ │    ↓ fail    │ │             │
│ MakeMyTrip   │ │    ↓ fail   │ │ Curated DB   │ │             │
│              │ │ MakeMyTrip  │ │ (with hours) │ │             │
│ Ground:      │ │             │ │    ↓ fail    │ │             │
│ IRCTC(train) │ │             │ │ GPT suggest  │ │             │
│ RedBus(bus)  │ │             │ │ (tagged AI)  │ │             │
│ MMT train/bus│ │             │ │              │ │             │
│              │ │             │ │              │ │             │
│ try/except   │ │ try/except  │ │ try/except   │ │ try/except  │
│ isolated     │ │ isolated    │ │ isolated     │ │ isolated    │
└──────┬───────┘ └──────┬──────┘ └──────┬───────┘ └──────┬──────┘
       │                │               │                │
       └────────────────┴───────┬───────┴────────────────┘
                                │ Fan-in (custom reducer)
                                ▼
                    ┌───────────────────────┐
                    │  SUPERVISOR QUALITY   │
                    │  CHECK                │
                    │                       │
                    │  All returned data?   │
                    │  Yes → continue       │
                    │  Partial → warn user  │
                    │  Empty → fallback     │
                    └───────────┬───────────┘
                               │
                               ▼
═══════════════════════════════════════════════════════════════════
 PHASE 3: ENRICHMENT (Conditional, Parallel)
═══════════════════════════════════════════════════════════════════

Only if supervisor decides it adds value:

┌───────────────────┐  ┌───────────────────┐
│    LOCAL INTEL     │  │  FESTIVAL CHECK   │
│                    │  │                   │
│ Reddit API search  │  │ Curated festival  │
│    ↓ fail          │  │ DB lookup by      │
│ Curated tips DB    │  │ destination +     │
│    ↓ always        │  │ travel dates      │
│ GPT-4o hidden gems │  │                   │
│ (tagged "AI")      │  │ Impact analysis:  │
│                    │  │ positive/negative │
│ Source tagging on  │  │ for each event    │
│ every tip/gem      │  │                   │
└────────┬──────────┘  └────────┬──────────┘
         └──────────┬───────────┘
                    │
                    ▼
═══════════════════════════════════════════════════════════════════
 PHASE 4: HITL CHECKPOINT #2 — Research Review
═══════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────┐
│                    RESEARCH SUMMARY UI                        │
│                                                              │
│  "Here's what I found for your Rishikesh trip:"              │
│                                                              │
│  ✈️  5 flights (cheapest ₹3,200, best value ₹4,100)          │
│  🏨 8 hotels (₹500 - ₹2,500/night range)                    │
│  🎯 12 activities matching your interests                    │
│  🌤️  Weather: 25-32°C, no rain expected                      │
│  💰 Budget feasibility: ✅ Within ₹15,000                    │
│  🎉 Holi festival during your dates!                         │
│                                                              │
│  [✅ Looks good, continue]                                    │
│  [💰 Adjust budget] → slider → re-runs budget-affected agents│
│  [🔄 Different options] → text → selective re-search          │
└──────────────────────────┬───────────────────────────────────┘
                           │ User approves
                           ▼
═══════════════════════════════════════════════════════════════════
 PHASE 5: BUDGET OPTIMIZATION
═══════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────┐
│              BUDGET OPTIMIZER                                 │
│              (GPT-4o-mini, ~2.5K tokens)                    │
│                                                              │
│  Input: all search results + budget + travel style           │
│                                                              │
│  Step 1: Allocate budget by category                         │
│    Backpacker: Transport 25% | Stay 25% | Food 25% |        │
│                Activities 15% | Buffer 10%                   │
│                                                              │
│  Step 2: Score each option                                   │
│    score = price(35%) + quality(25%) + convenience(20%)      │
│            + preference_fit(20%)                             │
│                                                              │
│  Step 3: Select best combo within budget                     │
│    If over budget → generate trade-off suggestions:          │
│    "Bus (₹800) vs flight (₹3,200) saves ₹2,400"            │
│                                                              │
│  Step 4: Build BudgetTracker                                 │
│    {transport: {allocated, spent, remaining}, ...}           │
│                                                              │
│  ⚠️  ANTI-HALLUCINATION: Only selects from API results       │
│  Every selection: source="api", verified=true                │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
═══════════════════════════════════════════════════════════════════
 PHASE 6: ITINERARY BUILDING
═══════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────┐
│              ITINERARY BUILDER                                │
│              (GPT-4o, ~4K tokens)                            │
│                                                              │
│  Input: selected items + weather + festivals + tips          │
│                                                              │
│  Step 0 — TRAVEL TIME PRE-COMPUTATION:                       │
│   • Google Directions API → exact time between locations     │
│   • Fallback: haversine distance × speed estimate            │
│     (driving ~40km/h, walking ~5km/h, auto ~25km/h)         │
│   • Result: travel_duration_to_next + travel_mode on items   │
│                                                              │
│  Step 1 — OPENING HOURS VALIDATION:                          │
│   • Check each activity's opening_hours dict                 │
│   • Conflict? → reschedule to valid time slot                │
│   • Closed on scheduled day? → swap to different day         │
│   • Log all validation changes in AgentDecision              │
│                                                              │
│  Step 2 — Scheduling rules:                                  │
│   • Day 1: lighter (arrival buffer)                          │
│   • Last day: lighter (departure buffer)                     │
│   • Outdoor activities: morning (avoid midday heat)          │
│   • Temple visits: early morning                             │
│   • Markets/shopping: evening                                │
│   • Meal slots: 8am breakfast, 1pm lunch, 8pm dinner        │
│   • Travel durations between locations INCLUDED as items     │
│     (e.g., "🚗 25 min auto ride to next stop")              │
│                                                              │
│  Step 3 — Weather integration:                               │
│   • Rain forecast → move outdoor indoor or reschedule        │
│   • Extreme heat → schedule indoor for 12-3pm               │
│                                                              │
│  Step 4 — CONTACT INFO ATTACHMENT:                           │
│   • Each ItineraryItem gets phone/address from source data   │
│   • Hotel: phone + email + check-in time                     │
│   • Activity: phone + address + opening hours display        │
│                                                              │
│  Step 5 — Festival integration:                              │
│   • Positive: add to itinerary                               │
│   • Negative (closures): avoid affected areas                │
│                                                              │
│  Output: Trip { days: DayPlan[], total_cost, ... }           │
│  Each ItineraryItem: travel_duration_to_next, contact_info   │
│  Structured output via Pydantic model                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
═══════════════════════════════════════════════════════════════════
 PHASE 7: VIBE SCORING
═══════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────┐
│              VIBE SCORER                                      │
│              (GPT-4o-mini, ~1.5K tokens)                    │
│                                                              │
│  Input: final itinerary + user preferences                   │
│                                                              │
│  Output:                                                     │
│    overall_score: 87                                         │
│    breakdown: {adventure: 92, culture: 78, relaxation: 65}   │
│    tagline: "Your spiritual adventure awaits!"               │
│    perfect_matches: ["Rafting → adventure vibe"]             │
│    considerations: ["Limited nightlife options"]              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
═══════════════════════════════════════════════════════════════════
 PHASE 8: HITL CHECKPOINT #3 — Final Review (Interactive)
═══════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────┐
│                 TRIP DASHBOARD                                │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  Rishikesh Solo Adventure  │ Vibe: 87% 🎯 │ [Share] │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  [📅 Itinerary] [🗺️ Map] [💰 Budget] [🕵️ Tips] [🤖 AI Log]  │
│                                                              │
│  Itinerary Tab (Editable):                                   │
│  ┌─Day 1 ─────────────────────────────────────────────┐     │
│  │ 6:00 AM  Bus from Delhi     ₹800  [Swap] [Book]   │     │
│  │          📞 RedBus: 1800-XXX-XXXX                  │     │
│  │          ⏱️ 🚌 6hr to Rishikesh                    │     │
│  │ 2:00 PM  Check-in Zostel    ₹700  [Swap] [Book]   │     │
│  │          📞 +91-XXXXX | 📍 Laxman Jhula Road      │     │
│  │          ⏱️ 🚗 10 min auto ride                    │     │
│  │ 4:00 PM  Lakshman Jhula     Free  [Remove]        │     │
│  │          🕐 Open 6AM-9PM | 📍 Ram Jhula Road      │     │
│  │          ⏱️ 🚶 15 min walk                         │     │
│  │ 7:00 PM  Dinner at Chotiwala₹200  [Swap]          │     │
│  │          📞 +91-XXXXX | 🕐 Open 8AM-10PM          │     │
│  │                         [+ Add Activity]           │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  [✅ Approve & Export]  [🔄 Modify via Chat]  [🔃 Start Over] │
└─────────────┬────────────────────┬───────────────────────────┘
              │                    │
     User approves          User modifies
              │                    │
              ▼                    ▼
        PHASE 10           MODIFICATION
        (Export)            SUBGRAPH
```

---

## Modification Subgraph

```
═══════════════════════════════════════════════════════════════════
 MODIFICATION FLOW (User says "change hotel to cheaper")
═══════════════════════════════════════════════════════════════════

User feedback (text or UI action)
       │
       ▼
┌──────────────────────────────────────────┐
│          CHANGE ANALYZER                  │
│          (Supervisor, GPT-4o-mini)       │
│                                          │
│  Categorizes change:                     │
│   • hotel_change                         │
│   • budget_change                        │
│   • date_change                          │
│   • activity_change                      │
│   • disruption (flight delayed)          │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│          IMPACT ASSESSOR                  │
│                                          │
│  Dependency graph lookup:                │
│                                          │
│  hotel_change →                          │
│    RE-RUN: hotel_search,                 │
│            budget_optimizer,             │
│            itinerary_builder,            │
│            vibe_scorer                   │
│    KEEP:   flights, weather, tips        │
│                                          │
│  flight_delay →                          │
│    RE-RUN: itinerary_builder (Day 1),    │
│            vibe_scorer                   │
│    KEEP:   everything else               │
│                                          │
│  budget_change →                         │
│    RE-RUN: budget_optimizer,             │
│            itinerary_builder,            │
│            vibe_scorer                   │
│    KEEP:   search results, enrichment    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│       SELECTIVE RE-RUN                    │
│                                          │
│  Only affected agents execute            │
│  (saves time + tokens)                   │
│                                          │
│  Unaffected state preserved in           │
│  working memory                          │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│          DIFF GENERATOR                   │
│                                          │
│  "Here's what changed:"                  │
│  • Hotel: Zostel (₹800) → Moustache     │
│    (₹500) — saved ₹900 total            │
│  • Day 2 schedule adjusted               │
│  • Budget: ₹14,200 → ₹13,300            │
└──────────────────┬───────────────────────┘
                   │
                   ▼
            Back to HITL #3
            (Dashboard with diff highlighted)
```

---

## Conversation Subgraph

```
═══════════════════════════════════════════════════════════════════
 CONVERSATION FLOW (User asks "what's the weather like?")
═══════════════════════════════════════════════════════════════════

User question
       │
       ▼
┌──────────────────────────────────────────┐
│          SUPERVISOR classifies            │
│          intent = "conversation"          │
│                                          │
│  Routes to conversation handler          │
│  Provides: question + relevant state     │
│  slice (weather data, trip details)      │
│                                          │
│  GPT-4o-mini answers from state          │
│  No agents re-run                        │
│  No state mutation                       │
└──────────────────┬───────────────────────┘
                   │
                   ▼
             Response shown
             in chat sidebar
```

---

## Export Flow

```
═══════════════════════════════════════════════════════════════════
 PHASE 10: EXPORT & SHARING
═══════════════════════════════════════════════════════════════════

User clicks [Approve & Export]
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                    SHARE MODAL                                │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 📄 PDF   │  │ 📋 JSON  │  │ 🌐 HTML  │  │ 🔗 Share │    │
│  │ Download │  │ Download │  │ Download │  │  Link    │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │          │
│       ▼              ▼              ▼              ▼          │
│  WeasyPrint     Pydantic       Jinja2         SQLite        │
│  + Jinja2       .model_dump    template       shared_trips  │
│  template       → JSON         + inline CSS   table +       │
│  + QR codes                    + JS           short URL     │
│  per booking                                  + QR code     │
│  link                                                        │
│                                                              │
│                    [QR Code]                                 │
│                    Scan to view trip                          │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Flow: State Through Agents

```
TripRequest (from intent parser)
     │
     ├──► flight_options: list[FlightOption]           (from transport search)
     ├──► ground_transport_options: list[GroundTransportOption]  (train/bus from transport search)
     ├──► hotel_options: list[HotelOption]              (with phone, email, address)
     ├──► activity_options: list[Activity]               (with opening_hours, phone, address)
     ├──► weather: WeatherForecast                       (from weather check)
     ├──► local_tips: list[LocalTip]                     (from local intel)
     ├──► hidden_gems: list[HiddenGem]                   (from local intel)
     ├──► events: list[Event]                            (from festival check)
     │
     ▼ (Budget Optimizer selects from above — including flight vs train/bus trade-off)
     │
     ├──► selected_outbound_flight: FlightOption | GroundTransportOption
     ├──► selected_return_flight: FlightOption | GroundTransportOption
     ├──► selected_hotel: HotelOption
     ├──► selected_activities: list[Activity]
     ├──► budget_tracker: BudgetTracker
     │
     ▼ (Itinerary Builder: computes travel times + validates hours + arranges)
     │
     ├──► trip: Trip { days: DayPlan[], total_cost }
     │         Each ItineraryItem has:
     │           travel_duration_to_next (min), travel_mode_to_next
     │           contact_info (phone/address), opening_hours validated
     │
     ▼ (Vibe Scorer evaluates)
     │
     └──► vibe_score: VibeScore { overall, breakdown, tagline }
```

---

## Memory & Persistence Flow

```
┌─────────────────────────────────────────────────────────┐
│                    RUNTIME                               │
│                                                         │
│  L1 CACHE (dict)     WORKING MEMORY (state dict)       │
│  ┌──────────────┐    ┌─────────────────────────┐       │
│  │ flight:DEL→GOI│   │ trip_request             │       │
│  │ hotel:GOI     │   │ flight_options           │       │
│  │ weather:GOI   │   │ selected_hotel           │       │
│  │ (TTL-based)   │   │ trip                     │       │
│  └───────┬──────┘    │ vibe_score               │       │
│          │           │ agent_decisions           │       │
│          │           └────────────┬──────────────┘       │
│          │                        │                      │
└──────────┼────────────────────────┼──────────────────────┘
           │ miss                   │ every state change
           ▼                        ▼
┌─────────────────────────────────────────────────────────┐
│                    SQLITE                                │
│                                                         │
│  api_cache          trip_sessions       users            │
│  ┌────────────┐    ┌──────────────┐   ┌──────────────┐  │
│  │ key        │    │ session_id   │   │ id           │  │
│  │ value (JSON)│   │ state (JSON) │   │ session_id   │  │
│  │ expires_at │    │ stage        │   │ display_name │  │
│  │ created_at │    │ updated_at   │   │ created_at   │  │
│  └────────────┘    └──────────────┘   └──────────────┘  │
│                                                         │
│  conversation_history    agent_decisions   user_profiles │
│  ┌──────────────────┐  ┌──────────────┐ ┌────────────┐  │
│  │ session + msgs   │  │ agent + why  │ │ preferences│  │
│  │ compressed older │  │ per session  │ │ learned    │  │
│  └──────────────────┘  └──────────────┘ └────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Error Recovery Flow

```
API Call Attempt
       │
       ▼
┌─ Tenacity Retry (3x, exponential backoff) ─┐
│                                              │
│  Attempt 1 → timeout/error                   │
│  Attempt 2 → timeout/error                   │
│  Attempt 3 → timeout/error                   │
│                                              │
└──────────────┬───────────────────────────────┘
               │ All retries exhausted
               ▼
┌─ Fallback Chain ──────────────────────────────┐
│                                                │
│  Primary API failed → try Fallback #1          │
│  Fallback #1 failed → try Fallback #2          │
│  All failed → use curated/static data          │
│  No static data → return empty + warning       │
│                                                │
│  Every fallback result tagged:                 │
│    source="fallback_url" or source="curated"   │
└──────────────┬─────────────────────────────────┘
               │
               ▼
        Agent returns result
        (possibly partial)
        + warning in agent_decisions
```

---

## Task Execution Order

```
SPRINT 1: Foundation (Parallel)
────────────────────────────────
  TASK-01 ──► Project Setup (config, DB, models)
  TASK-02 ──► Static Data (cities, festivals, activities)
  TASK-03 ──► API Clients (Amadeus, LiteAPI, Google, etc.)
  TASK-04 ──► Memory Layer (working, conversation, profile)

SPRINT 2: Core Pipeline (Sequential)
────────────────────────────────
  TASK-05 ──► LangGraph Core (state, supervisor, graph builder)
  TASK-06 ──► Search Agents (flight, hotel, activity, weather)
  TASK-07 ──► Enrichment Agents (local intel, festivals, dest recommender)

SPRINT 3: Intelligence + UI (Sequential)
────────────────────────────────
  TASK-08 ──► Optimization Agents (intent, budget, itinerary, vibe, feedback)
  TASK-09 ──► Streamlit UI (all 14 components)

SPRINT 4: Polish (Parallel)
────────────────────────────────
  TASK-10 ──► Export & Sharing (PDF, JSON, HTML, QR, links)
  TASK-11 ──► Demo Scenarios (3 sample trips + tests)
  TASK-12 ──► Documentation (README, architecture, CLAUDE.md)
```
