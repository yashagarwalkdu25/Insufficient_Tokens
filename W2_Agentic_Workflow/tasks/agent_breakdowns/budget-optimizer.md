# Budget Optimizer Agent Breakdown

## Role
Scores all options, selects best combination within budget, generates trade-off reasoning.

## File
`app/graph/nodes/budget_optimizer.py`

## Model
GPT-4o-mini (for trade-off reasoning text)

## Inputs
- All search results (flights, hotels, activities)
- `trip_request`: total_budget, travel_style
- `weather_forecast` (for activity feasibility)

## Outputs
- `selected_outbound_flight`, `selected_return_flight`
- `selected_hotel`
- `selected_activities`
- `budget_tracker`: BudgetTracker model
- `budget_warnings`: list of warnings
- `agent_reasoning`: detailed trade-off decisions

## Logic
1. Get budget allocation by category (from TripRequest.get_budget_allocation)
2. Score each option using weighted scoring
3. Try ideal combination → check if within budget
4. If over → identify cheapest swaps with best value retention
5. GPT-4o-mini generates human-readable trade-off reasoning
6. Build BudgetTracker with per-category tracking
7. Generate warnings if tight or over budget

## Anti-Hallucination
CRITICAL: Only selects from API-returned options. Never invents options.
All selections reference existing FlightOption/HotelOption/Activity objects.

## Task Reference
TASK-08
