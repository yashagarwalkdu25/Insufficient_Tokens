# Vibe Scorer Agent Breakdown

## Role
Calculates how well the final trip matches the user's stated preferences and energy.

## File
`app/graph/nodes/vibe_scorer.py`

## Model
GPT-4o-mini (creative task, fast model sufficient)

## Inputs
- `trip`: final itinerary
- `trip_request.preferences`: interests, style, vibe
- `selected_activities`: what was included

## Outputs
- `vibe_score`: VibeScore model
  - overall_score (0-100)
  - breakdown by category
  - perfect_matches list
  - considerations list
  - tagline (8 words max)
  - vibe_emoji

## Logic
1. Algorithm: score activities against interest tags
   - Adventure activities found → adventure score
   - Cultural sites found → culture score
   - etc.
2. GPT-4o-mini: generate creative tagline, matches, considerations
3. Combine into VibeScore model

## Task Reference
TASK-08
