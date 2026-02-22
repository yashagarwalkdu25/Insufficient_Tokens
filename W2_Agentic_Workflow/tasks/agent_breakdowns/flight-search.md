# Flight Search Agent Breakdown

## Role
Searches for outbound and return flights, scores options, selects best within budget.

## File
`app/graph/nodes/flight_search.py`

## Model
None (pure API calls + algorithmic scoring)

## Inputs
- `trip_request`: origin, destination, dates, num_travelers, budget

## Outputs
- `flight_options`: all found flights
- `selected_outbound_flight`: best outbound
- `selected_return_flight`: best return
- `agent_reasoning`: decision log

## Logic
1. Calculate per-way transport budget
2. Call Amadeus API for outbound flights
3. Call Amadeus API for return flights
4. If Amadeus fails → generate Skyscanner + MakeMyTrip URLs
5. Score flights: price(35%) + duration(25%) + direct bonus(20%) + time(10%) + airline(10%)
6. Select best within budget

## Fallback Chain
Amadeus → Skyscanner URL → MakeMyTrip URL → "Search manually" message

## Source Tagging
- Amadeus results: source="amadeus", verified=True
- URL fallbacks: source="url_redirect", verified=False

## Task Reference
TASK-06
