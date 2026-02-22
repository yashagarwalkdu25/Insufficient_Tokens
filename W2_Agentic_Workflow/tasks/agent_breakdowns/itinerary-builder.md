# Itinerary Builder Agent Breakdown

## Role
Creates the complete day-by-day trip itinerary with timings, costs, and tips.

## File
`app/graph/nodes/itinerary_builder.py`

## Model
GPT-4o (complex generation task, needs quality)

## Inputs
- Selected flight, hotel, activities
- weather_forecast, festivals_events, local_tips
- trip_request (dates, style, preferences)

## Outputs
- `trip`: Trip model with DayPlan[] containing ItineraryItem[]
- `agent_reasoning`: scheduling decisions

## Logic
1. GPT-4o generates day-by-day plan following rules:
   - Day 1: lighter (arrival)
   - Last day: lighter (departure)
   - Outdoor early, avoid midday heat
   - Temples early morning, markets evening
   - Include meals + travel durations
2. Weather-aware: no outdoor during rain
3. Festival-aware: include must-see events
4. Tips injected inline
5. Per-day and total cost calculated

## Structured Output
Uses Pydantic model enforcement:
- Trip → DayPlan[] → ItineraryItem[]
- Each item has: start_time, end_time, type, title, location, cost, booking_url

## Task Reference
TASK-08
