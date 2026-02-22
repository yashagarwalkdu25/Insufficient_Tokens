# TASK-05: LangGraph Core (State, Supervisor, Builder, Runner)

## PR Title: `feat: LangGraph state machine, supervisor agent, graph builder and runner`

## Priority: P0 (Core orchestration - all agents plug into this)

## Summary
Build the LangGraph state machine, supervisor routing agent, graph construction with conditional edges, and the synchronous execution runner with streaming support.

## Scope

### 1. State Definition (app/graph/state.py)
- `AgentDecision(TypedDict)`: agent, action, reasoning, result, timestamp
- `WeatherDay(TypedDict)`: date, temp_min, temp_max, condition, rain_probability, warning
- `TravelPlannerState(TypedDict)`: Complete state with all fields:
  - Input: user_query
  - Parsed: trip_request
  - Search results: flight_options, hotel_options, ground_transport_options, activities, restaurants, weather_forecast (using Annotated[list, add] for parallel merge)
  - Enrichment: local_tips, hidden_gems, festivals_events, vibe_score
  - Selections: selected_outbound_flight, selected_return_flight, selected_hotel, selected_activities
  - Budget: budget_tracker, budget_warnings
  - Output: trip
  - Control: current_stage, requires_approval, approval_type, user_feedback, is_replanning
  - Transparency: agent_reasoning (Annotated[list, add]), errors, warnings
  - Supervisor: supervisor_route, active_agents (list of agents to run)
- `create_initial_state(user_query) → TravelPlannerState` with all defaults
- Custom reducer for deduplication (not raw operator.add)

### 2. Supervisor Agent (app/graph/supervisor.py)
- `classify_intent(user_message, current_state) → str`: Returns one of:
  - "new_trip" → Planning subgraph
  - "modify" → Modification subgraph
  - "question" → Conversation subgraph
  - "approve" → Export
  - "reject_with_feedback" → Feedback handler
  - "reset" → Clear state
- `decide_active_agents(trip_request) → list[str]`: Conditional activation:
  - Day trip → skip flight_search
  - No Reddit key → skip reddit, use curated
  - Destination unknown → add destination_recommender
- `check_agent_quality(agent_name, output) → bool`: Validate agent output is non-empty, within expected ranges
- `get_fallback_agent(agent_name) → str`: Map failed agent to fallback
- Uses GPT-4o-mini for intent classification, rule-based for the rest

### 3. Conditional Edges (app/graph/edges.py)
- `route_after_intent(state) → str`: Check if destination known → "research" or "recommend_destination"
- `route_after_approval(state) → str`: "approved" → END, "rejected" → "handle_feedback"
- `should_enrich(state) → str`: Check if enrichment agents should run
- `route_supervisor(state) → str`: Based on supervisor_route field
- `route_after_modification(state) → str`: Back to appropriate checkpoint

### 4. Graph Builder (app/graph/builder.py)
- `build_travel_graph() → CompiledGraph`:
  - Add all nodes (13 agents)
  - Entry point: supervisor routing
  - Fan-out: intent → parallel search (conditional agents)
  - Fan-in: search results → enrichment (conditional)
  - Sequential: budget → itinerary → vibe → approval
  - Conditional edges for approval outcome
  - Feedback loop: feedback → selective re-run → back to approval
  - Compile with sync execution (NOT async)
- `get_travel_graph() → CompiledGraph` singleton

### 5. Graph Runner (app/graph/runner.py)
- `TravelPlannerRunner` class:
  - `run(user_query) → TravelPlannerState`: Synchronous full execution
  - `stream(user_query) → Generator[dict, None, None]`: Yields progress updates:
    - `{"type": "node_start", "node": "search_flights", "message": "Searching flights..."}`
    - `{"type": "node_end", "node": "search_flights", "preview": "Found 5 flights"}`
    - `{"type": "complete", "state": final_state}`
  - `handle_approval(approved, feedback) → TravelPlannerState`: Process user decision
  - `handle_modification(change_request) → TravelPlannerState`: Selective re-planning
  - Auto-saves state to SQLite via working memory after each node
  - Token tracking: count tokens used per agent

CRITICAL: Use synchronous .invoke() and .stream() methods ONLY. No asyncio.run() in Streamlit context.

## Acceptance Criteria
- [ ] Graph compiles without errors
- [ ] Supervisor correctly classifies 5 test intents (new trip, modify, question, approve, reset)
- [ ] Conditional agent activation: day trip skips flight search
- [ ] Parallel search nodes execute concurrently (fan-out works)
- [ ] Fan-in correctly merges results from parallel nodes
- [ ] Custom reducer prevents duplicate entries in lists
- [ ] Streaming yields correct progress events for each node
- [ ] State persisted to SQLite after each node execution
- [ ] Feedback loop correctly routes back to budget optimizer
- [ ] Token count tracked per agent in agent_decisions table
- [ ] No asyncio.run() calls anywhere in the codebase

## Dependencies
- TASK-01 (models, config, database)
- TASK-04 (memory layer for state persistence)

## Estimated Files: 5
## Estimated LOC: ~700
