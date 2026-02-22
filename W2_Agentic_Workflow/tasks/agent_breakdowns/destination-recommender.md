# Destination Recommender Agent Breakdown

## Role
When user doesn't specify a destination, recommends 3 options with reasoning.

## File
`app/graph/nodes/destination_recommender.py`

## Model
GPT-4o-mini

## Inputs
- `trip_request.preferences` (style, interests, budget)
- `trip_request.start_date` / `end_date` (for seasonal filtering)

## Outputs
- `destination_options`: list of 3 city dicts with name, reasoning, match_score
- `requires_approval`: True
- `approval_type`: "destination"

## Logic
1. Filter india_cities.py by:
   - Style match (city type tags vs preferences)
   - Season suitability (best_months includes trip month)
   - Budget feasibility
2. GPT-4o-mini ranks top 3 with personalized reasoning
3. Triggers HITL Checkpoint #1

## Task Reference
TASK-07
