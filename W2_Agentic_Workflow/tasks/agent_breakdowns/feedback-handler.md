# Feedback Handler Agent Breakdown

## Role
Processes user feedback/modifications and triggers selective re-planning.

## File
`app/graph/nodes/feedback_handler.py`

## Model
GPT-4o-mini (classification + modification)

## Inputs
- `user_feedback`: natural language feedback text
- Current state (full)

## Outputs
- Updated `trip_request` (if preferences changed)
- `is_replanning`: True
- Routing info: which agents need re-running

## Logic
1. GPT-4o-mini classifies feedback:
   - "change hotel" → hotel_change
   - "make it cheaper" → budget_change
   - "add more adventure" → activity_change
   - "flight delayed" → disruption
2. Impact assessment using dependency graph:
   - hotel_change → re-run: hotel_search, budget_optimizer, itinerary_builder, vibe_scorer
   - budget_change → re-run: budget_optimizer, itinerary_builder, vibe_scorer
   - activity_change → re-run: activity_search, budget_optimizer, itinerary_builder, vibe_scorer
3. Update trip_request based on feedback
4. Route back to appropriate pipeline stage

## Selective Re-planning
Key efficiency: only affected agents re-run.
Unaffected search results (e.g., weather, flights) are preserved.

## Task Reference
TASK-08
