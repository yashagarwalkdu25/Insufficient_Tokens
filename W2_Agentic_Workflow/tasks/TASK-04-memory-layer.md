# TASK-04: Memory & Context Management Layer

## PR Title: `feat: 3-tier memory system with context compression`

## Priority: P0 (Required by Supervisor and all agents)

## Summary
Implement the 3-tier memory hierarchy (working, conversation, user profile) with token-efficient context compression.

## Scope

### 1. Working Memory (app/memory/working_memory.py)
Manages current trip session state:
- `WorkingMemoryManager` class
- `save_state(session_id, state_dict)` → serialize to JSON, save to trip_sessions
- `load_state(session_id) → dict | None` → deserialize from trip_sessions
- `update_state(session_id, partial_update)` → merge partial update into existing state
- `get_state_slice(session_id, fields: list[str]) → dict` → return only requested fields (token efficiency)
- Auto-save on every state change (called by graph runner)
- State versioning: track which fields changed

### 2. Conversation Memory (app/memory/conversation_memory.py)
Manages chat history with compression:
- `ConversationMemoryManager` class
- `add_message(session_id, role, content, metadata)` → save to conversation_history
- `get_recent_messages(session_id, limit=10) → list[dict]`
- `get_compressed_history(session_id) → str` → returns:
  - Last 3 messages: full text
  - Older messages: content_summary field (pre-compressed)
  - Total token count tracked
- `compress_message(content) → str` → uses GPT-4o-mini to summarize long messages to ~50 tokens
- Compression triggers when message token_count > 200
- `get_key_decisions(session_id) → list[str]` → extract user decisions (approvals, rejections, preferences stated)

### 3. User Profile (app/memory/user_profile.py)
Learns user preferences over time:
- `UserProfileManager` class
- `get_profile(user_id) → UserProfile | None`
- `update_profile_from_trip(user_id, trip_request, trip)` → after trip completion:
  - Update preferred_style (most frequent)
  - Update budget_range (rolling average)
  - Append to past_destinations
  - Update home_city (most common origin)
  - Merge dietary/accessibility needs
- `get_personalization_context(user_id) → str` → returns short prompt snippet:
  "User prefers adventure travel, usually budgets ₹10-15K, from Delhi, vegetarian"
- `clear_profile(user_id)` → reset learned data

### 4. Context Compressor (app/memory/context_compressor.py)
Token-efficient data passing between agents:
- `compress_for_agent(full_state, agent_name) → dict` → returns ONLY fields this agent needs:
  ```
  AGENT_CONTEXT_MAP = {
    "intent_parser": ["user_query"],
    "flight_search": ["trip_request.origin", "trip_request.destination", "trip_request.start_date", "trip_request.end_date", "trip_request.preferences.num_travelers"],
    "budget_optimizer": ["flight_options_summary", "hotel_options_summary", "activities_summary", "trip_request.total_budget", "trip_request.preferences.travel_style"],
    "itinerary_builder": ["selected_flight", "selected_hotel", "selected_activities", "weather_summary", "festivals_summary", "local_tips_summary", "trip_request"],
    ...
  }
  ```
- `summarize_search_results(results: list) → str` → "5 flights found, cheapest ₹3,200 IndiGo, best ₹4,100 Vistara direct"
- `summarize_weather(forecast: list) → str` → "25-32°C, sunny, no rain expected"
- `estimate_tokens(text: str) → int` → rough token count (len/4)
- Token budget enforcement: if context exceeds agent's max, compress further

## Acceptance Criteria
- [ ] Working memory: save state → kill process → load state returns same data
- [ ] Conversation memory: 20 messages added, get_compressed_history returns <2000 tokens
- [ ] Compression: 500-word message compressed to <100 words summary
- [ ] User profile: after 3 mock trips, profile reflects correct preferred_style
- [ ] Context compressor: flight_search agent receives only trip_request fields, not hotel data
- [ ] Token estimation: within 20% of actual tiktoken count
- [ ] get_key_decisions extracts "user approved budget" from conversation
- [ ] All SQLite operations use parameterized queries (no SQL injection)

## Dependencies
- TASK-01 (database, config)

## Estimated Files: 4
## Estimated LOC: ~500
