# Hotel Search Agent Breakdown

## Role
Searches for accommodation options, scores by style fit, selects best within budget.

## File
`app/graph/nodes/hotel_search.py`

## Model
None (pure API calls + algorithmic scoring)

## Inputs
- `trip_request`: destination, dates, budget, travel_style

## Outputs
- `hotel_options`: all found hotels
- `selected_hotel`: best match
- `agent_reasoning`: decision log

## Logic
1. Calculate accommodation budget
2. Call LiteAPI for hotels
3. If LiteAPI fails → generate Booking.com + MakeMyTrip URLs
4. Score: price(30%) + rating(25%) + location(20%) + amenities(15%) + reviews(10%)
5. Filter by style (backpacker→hostels, luxury→5-star)
6. Select best within budget

## Fallback Chain
LiteAPI → Booking.com URL → MakeMyTrip URL → Curated hotel list

## Task Reference
TASK-06
