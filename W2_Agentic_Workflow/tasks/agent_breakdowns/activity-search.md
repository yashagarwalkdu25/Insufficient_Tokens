# Activity Search Agent Breakdown

## Role
Finds activities and things to do at the destination, merges API + curated data.

## File
`app/graph/nodes/activity_search.py`

## Model
None (pure API calls + database lookup)

## Inputs
- `trip_request`: destination, interests, num_days, style

## Outputs
- `activities`: all found activities
- `selected_activities`: top picks (2-3 per day)
- `agent_reasoning`: decision log

## Logic
1. Search Google Places for activities matching interests
2. Load curated activities from india_activities.py
3. Deduplicate by name similarity
4. Score by relevance to user interests
5. Select top activities (2-3 per day of trip)

## Source Tagging
- Google Places: source="google_places", verified=True
- Curated: source="curated", verified=True
- Both have real coordinates and booking URLs

## Task Reference
TASK-06
