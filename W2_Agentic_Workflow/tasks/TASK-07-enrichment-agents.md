# TASK-07: Enrichment Agent Nodes (Local Intel, Festival Check, Destination Recommender)

## PR Title: `feat: enrichment agents for local tips, festivals, and destination recommendations`

## Priority: P1 (Enriches the plan with unique value)

## Summary
Implement the enrichment agents that add local intelligence, festival awareness, and destination recommendations to the trip plan.

## Scope

### 1. Local Intel Node (app/graph/nodes/local_intel.py)
- `gather_local_intel_node(state) → dict`
- Input: trip_request (destination, interests)
- Process:
  1. Get curated tips from local_tips_db.py (always available)
  2. Get curated hidden gems
  3. If Reddit API configured → search Reddit for destination tips
  4. Use GPT-4o-mini to:
     a. Summarize and categorize Reddit tips
     b. Generate 3 additional hidden gems based on tips + interests
     c. Tag AI-generated gems: source="llm", verified=False
  5. Sort by relevance score
- Output: local_tips, hidden_gems
- Prompt: app/prompts/local_intel.py

### 2. Festival Check Node (app/graph/nodes/festival_check.py)
- `check_festivals_node(state) → dict`
- Input: trip_request (destination, start_date, end_date)
- Process:
  1. Query india_festivals.py for date range + city overlap
  2. Flag events by impact: positive (must-see), caution (crowds), avoid (disruptions)
  3. Generate recommendations for each event
- Output: festivals_events
- No LLM needed (pure database lookup)

### 3. Destination Recommender Node (app/graph/nodes/destination_recommender.py)
- `recommend_destination_node(state) → dict`
- Input: trip_request (preferences, budget, dates) with destination=None
- Process:
  1. Filter india_cities.py by:
     - Travel style match (city.type tags vs preferences)
     - Season suitability (best_months includes trip month)
     - Budget feasibility
  2. Use GPT-4o-mini to rank top 3 and explain why each fits
  3. Set requires_approval=True, approval_type="destination"
- Output: destination_options (list of 3), requires_approval=True
- This triggers HITL Checkpoint #1

### 4. Prompts
- app/prompts/local_intel.py: Prompt for hidden gem generation from tips
- app/prompts/destination_recommender.py: Prompt for destination ranking

## Acceptance Criteria
- [ ] Local intel returns curated tips even without Reddit API key
- [ ] Reddit tips are categorized correctly (food, safety, transport, etc.)
- [ ] AI-generated gems tagged source="llm", verified=False
- [ ] Festival check finds Ganga Aarti for any Rishikesh trip
- [ ] Festival check flags Diwali as "caution" impact
- [ ] Destination recommender returns 3 options when destination=None
- [ ] Destination recommender sets requires_approval=True
- [ ] Each agent logs AgentDecision

## Dependencies
- TASK-01 (models)
- TASK-02 (static data: festivals, tips, cities)
- TASK-03 (Reddit client)
- TASK-05 (LangGraph state)

## Estimated Files: 3 nodes + 2 prompts
## Estimated LOC: ~450
