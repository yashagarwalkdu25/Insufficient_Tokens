# Local Intel Agent Breakdown

## Role
Gathers insider tips from Reddit and curated sources, generates AI hidden gems.

## File
`app/graph/nodes/local_intel.py`

## Model
GPT-4o-mini (for hidden gem generation from tips)

## Inputs
- `trip_request`: destination, interests

## Outputs
- `local_tips`: list of LocalTip (categorized, scored)
- `hidden_gems`: list of HiddenGem (curated + AI-generated)
- `agent_reasoning`: decision log

## Logic
1. Load curated tips from local_tips_db.py (always available)
2. Load curated hidden gems
3. If Reddit configured → search travel subreddits
4. GPT-4o-mini: analyze tips → extract 3 hidden gems
5. AI gems tagged: source="llm", verified=False
6. Sort all by relevance score

## Source Tagging
- Curated: source="curated", verified=True
- Reddit: source="reddit", verified=False
- AI-generated: source="llm", verified=False (shown with badge in UI)

## Task Reference
TASK-07
