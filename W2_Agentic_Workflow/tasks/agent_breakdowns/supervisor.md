# Supervisor Agent Breakdown

## Role
Central orchestrator that classifies user intent, routes to subgraphs, decides which agents to activate, monitors quality, and manages fallbacks.

## File
`app/graph/supervisor.py`

## Model
GPT-4o-mini (fast routing decisions, ~2000 token budget)

## Inputs
- User message (current turn)
- Current state (stage, existing data)
- Conversation history summary

## Outputs
- `supervisor_route`: "new_trip" | "modify" | "question" | "approve" | "reject_with_feedback" | "reset"
- `active_agents`: list of agent names to activate

## Logic
1. Classify intent using GPT-4o-mini (or rule-based for simple cases)
2. Based on trip_request, decide conditional agent activation:
   - Day trip → skip flight_search
   - No Reddit key → skip reddit
   - Destination unknown → add destination_recommender
3. After each agent returns, validate output quality
4. If agent failed → activate fallback source

## Key Decisions
- Uses GPT-4o-mini (not 4o) to save tokens — routing is a simple classification
- Rule-based fallback if LLM fails
- Quality check is algorithmic (non-empty, valid ranges), not LLM-based

## Task Reference
TASK-05
