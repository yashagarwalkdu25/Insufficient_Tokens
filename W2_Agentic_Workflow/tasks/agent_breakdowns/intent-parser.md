# Intent Parser Agent Breakdown

## Role
Converts natural language travel queries into structured TripRequest Pydantic models.

## File
`app/graph/nodes/intent_parser.py`

## Model
GPT-4o (needs accuracy for date parsing, budget estimation, style detection)

## Inputs
- `user_query`: raw natural language string
- User profile context (if available)

## Outputs
- `trip_request`: TripRequest model with all fields
- `requires_approval`: True if ambiguous (missing destination or dates)
- `approval_type`: "clarification" if ambiguous

## Logic
1. Build prompt with today's date, format instructions, India-specific rules
2. Call GPT-4o with structured output
3. Extract JSON → validate with Pydantic
4. Handle relative dates ("next weekend" → actual dates)
5. Estimate budget if not specified (based on style)
6. Detect travel style from keywords
7. If critical fields missing → set requires_approval for clarification

## Prompt
`app/prompts/intent_parser.py` — includes:
- Date parsing rules (relative → absolute)
- Budget estimation table by style
- Indian destination recognition
- Vibe/energy extraction

## Anti-Hallucination
- Structured output enforced via Pydantic
- Dates validated against calendar
- Budget clamped to reasonable range (₹1K-₹10L)

## Task Reference
TASK-08
