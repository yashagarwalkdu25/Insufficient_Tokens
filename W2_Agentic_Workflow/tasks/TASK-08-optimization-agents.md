# TASK-08: Optimization & Generation Agents (Budget, Itinerary, Vibe, Feedback)

## PR Title: `feat: budget optimizer, itinerary builder, vibe scorer, and feedback handler`

## Priority: P1 (Core pipeline - produces the final trip plan)

## Summary
Implement the agents that process search results into an optimized, scored, reviewable trip plan.

## Scope

### 1. Intent Parser Node (app/graph/nodes/intent_parser.py)
- `parse_intent_node(state) → dict`
- Uses GPT-4o with structured output (Pydantic)
- Extracts: destination, origin, dates, budget, style, interests, traveler type
- Handles relative dates ("next weekend", "this Friday")
- Handles budget estimation when not specified
- If ambiguous (missing critical info) → set requires_approval=True, approval_type="clarification"
- Prompt: app/prompts/intent_parser.py

### 2. Budget Optimizer Node (app/graph/nodes/budget_optimizer.py)
- `optimize_budget_node(state) → dict`
- Input: all search results (flight_options + ground_transport_options + hotel_options + activity_options) + trip_request (budget, style)
- Process:
  1. Calculate budget allocation by category (from TripRequest.get_budget_allocation)
  2. Score each flight, **ground transport (train/bus)**, hotel, activity using weighted scoring
  3. **Flight vs Ground Transport trade-off**: compare flights and ground transport options on same route
     - Score both: price(35%) + time(25%) + comfort(20%) + fit(20%)
     - Generate explicit reasoning: "Bus (₹800, 6hrs) vs Flight (₹3,200, 1hr) — bus saves ₹2,400, adds 5hr travel time"
     - Backpacker style → weight price higher. Luxury → weight comfort/time higher.
  4. Select best combination that fits total budget:
     - Try ideal selections first
     - If over budget: identify cheapest swaps with best value retention
     - Generate trade-off reasoning for every swap
  5. Build BudgetTracker with allocated, spent, remaining per category
  6. Generate warnings if over budget or tight
- Output: selected_outbound_flight (can be FlightOption or GroundTransportOption), selected_return_flight, selected_hotel, selected_activities, budget_tracker, budget_warnings
- CRITICAL: Only select from API-returned or curated options. No invented options.
- Prompt: app/prompts/budget_optimizer.py (for trade-off reasoning)

### 3. Itinerary Builder Node (app/graph/nodes/itinerary_builder.py)
- `build_itinerary_node(state) → dict`
- Input: selected items + weather + festivals + tips + trip_request
- Uses GPT-4o with structured output
- Process:
  1. **Pre-compute travel times** between all selected activity locations:
     - Use GoogleDirectionsClient.get_travel_times_batch() if API key available
     - Fallback: haversine distance estimation (estimate_travel_time())
     - Store as travel_duration_to_next and travel_mode_to_next on each ItineraryItem
  2. Create day-by-day plan following scheduling rules:
     - Day 1: lighter (account for arrival)
     - Last day: lighter (departure buffer)
     - Outdoor activities early (avoid midday heat)
     - Temple visits: early morning
     - Markets: evening
     - Include meal times
     - **Include travel duration between consecutive activities** (e.g., "🚗 25 min auto ride")
  3. **Validate against opening hours**:
     - For each activity with opening_hours data, verify the scheduled time falls within open hours
     - If conflict: reschedule to a valid time slot or swap with another activity
     - If closed on scheduled day (e.g., Monday closures): move to different day
     - Log validation results in AgentDecision
  4. Integrate weather warnings (no outdoor in rain)
  5. Inject festival activities (if positive impact)
  6. Add local tips inline
  7. **Attach contact info** to each ItineraryItem from the source Activity/Hotel data (phone, address)
  8. Calculate per-day and total costs
- Output: trip (Trip model with DayPlan[] and ItineraryItem[])
- Each ItineraryItem includes: travel_duration_to_next, travel_mode_to_next, contact_info
- Prompt: app/prompts/itinerary_builder.py

### 4. Vibe Scorer Node (app/graph/nodes/vibe_scorer.py)
- `score_vibe_node(state) → dict`
- Input: trip + trip_request.preferences + activities
- Process:
  1. Algorithm: score activities against interest tags
  2. GPT-4o-mini: generate tagline, perfect matches, considerations
  3. Calculate breakdown by category
- Output: vibe_score (VibeScore model)
- Prompt: app/prompts/vibe_scorer.py

### 5. Approval Gate Node (app/graph/nodes/approval_gate.py)
- `approval_gate_node(state) → dict`
- Sets requires_approval=True, approval_type="itinerary"
- Pauses execution (returns state for UI to display)
- No LLM call, pure state management

### 6. Feedback Handler Node (app/graph/nodes/feedback_handler.py)
- `handle_feedback_node(state) → dict`
- Input: user_feedback text + current state
- Uses GPT-4o-mini to classify what changed
- Determines which agents need re-running (dependency graph)
- Updates trip_request based on feedback
- Output: updated trip_request, is_replanning=True
- Prompt: app/prompts/feedback_handler.py

### 7. All Prompts
- app/prompts/intent_parser.py
- app/prompts/budget_optimizer.py
- app/prompts/itinerary_builder.py
- app/prompts/vibe_scorer.py
- app/prompts/feedback_handler.py
- app/prompts/supervisor.py

## Acceptance Criteria
- [ ] Intent parser extracts correct data from "4-day solo trip to Rishikesh under 15K from Delhi next weekend"
- [ ] Intent parser handles relative dates correctly
- [ ] Budget optimizer stays within total budget
- [ ] Budget optimizer generates trade-off reasoning
- [ ] Budget optimizer ONLY selects from provided options (no hallucination)
- [ ] Itinerary has correct number of days matching trip dates
- [ ] Itinerary accounts for arrival/departure on first/last day
- [ ] Itinerary doesn't schedule outdoor activities during rain
- [ ] **Itinerary includes travel duration (minutes) between consecutive activities**
- [ ] **Itinerary validates activities against opening hours (no scheduling during closed hours)**
- [ ] **Each ItineraryItem has contact_info (phone/address) when available from source data**
- [ ] **Ground transport options (train/bus) are considered alongside flights for budget trips**
- [ ] Vibe score returns 0-100 with breakdown
- [ ] Feedback handler correctly identifies "change hotel" → re-run hotel_search + budget + itinerary
- [ ] Approval gate sets correct state for HITL pause
- [ ] All agents log AgentDecision

## Dependencies
- TASK-01 (models)
- TASK-05 (LangGraph state, edges)
- TASK-06 (search results to optimize)
- TASK-07 (enrichment data for itinerary)

## Estimated Files: 6 nodes + 6 prompts = 12
## Estimated LOC: ~1400
