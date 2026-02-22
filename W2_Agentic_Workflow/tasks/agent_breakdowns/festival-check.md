# Festival Check Agent Breakdown

## Role
Checks for festivals and events during trip dates that may affect the experience.

## File
`app/graph/nodes/festival_check.py`

## Model
None (pure database lookup)

## Inputs
- `trip_request`: destination, start_date, end_date

## Outputs
- `festivals_events`: list of Event with impact assessments
- `agent_reasoning`: decision log

## Logic
1. Query india_festivals.py for date range overlap
2. Filter by city (or "All India" events)
3. Classify impact: positive (must-see), caution (crowds), avoid (disruptions)
4. Generate recommendations per event

## Impact
Festival data influences:
- Budget optimizer: price spikes during festivals
- Itinerary builder: include must-see events, avoid disruptions
- User warnings: book early for high-crowd periods

## Task Reference
TASK-07
