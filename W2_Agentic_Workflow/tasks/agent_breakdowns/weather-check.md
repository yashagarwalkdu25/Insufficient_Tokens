# Weather Check Agent Breakdown

## Role
Gets weather forecast for trip dates to inform itinerary scheduling.

## File
`app/graph/nodes/weather_check.py`

## Model
None (pure API call)

## Inputs
- `trip_request`: destination, start_date, end_date

## Outputs
- `weather_forecast`: list of WeatherDay per trip day
- `agent_reasoning`: decision log

## Logic
1. Call OpenWeatherMap 5-day forecast
2. If API fails → use seasonal data from india_cities.py
3. Generate warnings: extreme heat (>40°C), heavy rain (>70% chance), cold (<5°C)
4. Flag days unsuitable for outdoor activities

## Impact
Weather data influences:
- Itinerary builder: no outdoor activities during rain
- Activity scheduling: early morning in hot weather
- Packing suggestions

## Task Reference
TASK-06
