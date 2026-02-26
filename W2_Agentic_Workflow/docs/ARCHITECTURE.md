# TripSaathi — Agent Architecture

> How the AI agents plan your trip: from raw query to day-by-day itinerary.

---

## Table of Contents

1. [Overview](#overview)
2. [Graph Flow](#graph-flow)
3. [Agent Nodes](#agent-nodes)
4. [State Schema](#state-schema)
5. [AI Travel Negotiator](#ai-travel-negotiator)
6. [Human-in-the-Loop (HITL) Checkpoints](#human-in-the-loop-hitl-checkpoints)
7. [Streaming & Resumption](#streaming--resumption)
8. [Fallback & Resilience Strategy](#fallback--resilience-strategy)

---

## Overview

TripSaathi is built on **LangGraph** — a stateful, graph-based orchestration framework. The planning pipeline is a directed graph of specialised AI agents that run sequentially, in parallel, or in loops depending on the task.

Key design principles:

- **Parallel research** — flights, hotels, activities, and weather are fetched simultaneously via LangGraph `Send()` fan-out
- **Deterministic negotiation** — bundle scoring is algorithmic (no LLM required); LLM is optional for trade-off text only
- **Multi-stage validation** — feasibility checks + hallucination detection before the itinerary reaches the user
- **Graceful degradation** — every agent has a fallback (demo data, heuristics, Tavily web search) when primary APIs fail
- **HITL at key decisions** — the user approves destination, bundle selection, and final itinerary

---

## Graph Flow

```
User Query
    │
    ▼
┌─────────────┐
│  supervisor │  ── classifies intent (plan / modify / conversation)
└──────┬──────┘
       │
       ├──► conversation_handler ──► END   (Q&A, no replanning)
       ├──► feedback_handler ──► [re-route to search or optimizer]
       │
       ▼
┌──────────────┐
│ intent_parser│  ── extracts destination, dates, budget, interests
└──────┬───────┘
       │
       ├──► clarification ──► END          (missing info detected)
       ├──► destination_recommender ──► approval_gate  (no destination given)
       │
       ▼
┌──────────────────┐
│ search_dispatcher│  ── fan-out trigger (pass-through node)
└──────┬───────────┘
       │  [parallel via Send()]
       ├──► flight_search
       ├──► hotel_search
       ├──► activity_search
       └──► weather_check
                │
                ▼
        search_aggregator
                │
                ▼
┌──────────────────────┐
│ enrichment_dispatcher│  ── fan-out trigger
└──────┬───────────────┘
       │  [parallel via Send()]
       ├──► local_intel
       └──► festival_check
                │
                ▼
       enrichment_aggregator
                │
                ▼  [conditional: use_negotiator?]
       ┌────────┴────────┐
       │                 │
       ▼                 ▼
  negotiator        approval_gate   (negotiator skipped if disabled)
       │
       ▼
feasibility_validator
       │
       ├──► negotiator   (loop back on failure, max 2 retries)
       │
       ▼
  approval_gate ──► END   (pauses for user input)
       │
       ▼  [after user approves]
budget_optimizer
       │
       ▼
itinerary_builder
       │
       ▼
response_validator
       │
       ▼
  vibe_scorer
       │
       ▼
  approval_gate ──► END   (itinerary review checkpoint)
```

---

## Agent Nodes

### Orchestration

| Node | Role | LLM |
|------|------|-----|
| `supervisor` | Classifies intent (plan / modify / conversation), sets `active_agents` | GPT-4o-mini |
| `intent_parser` | Extracts `TripRequest` (destination, dates, budget, traveller type, interests) from raw text | GPT-4o / heuristic fallback |
| `destination_recommender` | Suggests 3 destinations when none is specified; triggers HITL approval | GPT-4o-mini / fallback |
| `approval_gate` | HITL checkpoint manager — pauses graph and waits for user input | None |
| `feedback_handler` | Classifies modification requests; determines which agents need to re-run | GPT-4o-mini |
| `conversation_handler` | Answers questions about the trip without triggering replanning | GPT-4o-mini |
| `clarification` | Detects missing trip details and asks a follow-up question | GPT-4o-mini |

---

### Search Agents (run in parallel)

| Node | Data Sources | Fallback |
|------|-------------|---------|
| `flight_search` | Amadeus API → Tavily web search | Fare calculator heuristic; skips flights for trips < 200 km |
| `hotel_search` | LiteAPI → Tavily web search | Demo hotel data |
| `activity_search` | Google Places API → Tavily | Demo activity data |
| `weather_check` | Open-Meteo → OpenWeatherMap → Tavily | Static seasonal forecast |

---

### Enrichment Agents (run in parallel)

| Node | Data Sources | Output |
|------|-------------|--------|
| `local_intel` | Reddit → Tavily | Local tips, hidden gems |
| `festival_check` | Tavily (date-aware search) | Festivals and events during trip dates |

---

### Negotiation Pipeline

| Node | Role | LLM |
|------|------|-----|
| `negotiator` | Generates 3 bundles (Budget Saver, Best Value, Experience Max) using deterministic scoring | Optional GPT-4o-mini for trade-off text |
| `feasibility_validator` | Validates daily schedule feasibility; auto-fixes over-packed days; loops back to negotiator on failure (max 2 retries) | None |

---

### Optimisation & Generation Pipeline

| Node | Role | LLM |
|------|------|-----|
| `budget_optimizer` | Selects best transport / hotel / activities within budget; builds `BudgetTracker` | GPT-4o-mini |
| `itinerary_builder` | Generates day-by-day itinerary with timings, costs, and descriptions | GPT-4o |
| `response_validator` | Cross-validates itinerary against raw search results; flags hallucinations | GPT-4o-mini |
| `vibe_scorer` | Scores trip match 0–100 against user preferences; generates tagline | GPT-4o-mini |

---

## State Schema

The entire pipeline shares a single `TravelPlannerState` TypedDict. Key fields:

```
User context
  user_id, session_id, raw_query

Trip request
  trip_request       → { destination, start_date, end_date, budget, traveller_type, interests, ... }
  intent_type        → "plan" | "modify" | "conversation"
  current_stage      → stage tracking string
  active_agents      → list of agent names to run

HITL control
  requires_approval  → bool
  approval_type      → "destination" | "research" | "itinerary" | "clarification"
  user_feedback      → user's modification or clarification text

Search results  [deduplicated lists]
  flight_options, ground_transport_options
  hotel_options
  activity_options
  weather
  local_tips, hidden_gems, events

Selected options
  selected_outbound_flight, selected_return_flight
  selected_hotel
  selected_activities
  budget_tracker

Generated output
  trip               → { destination, days: [...], total_cost, ... }
  vibe_score         → { overall_score, tagline, dimension_scores }
  destination_options
  conversation_response
  validation_issues

Negotiator
  use_negotiator     → bool (user opt-in)
  bundles            → [BundleChoice × 3]
  selected_bundle_id → "budget_saver" | "best_value" | "experience_max"
  what_if_delta      → cumulative budget adjustment
  what_if_history
  negotiation_log
  feasibility_passed, feasibility_issues

System
  agent_decisions    → transparency log of every agent action
  errors
```

**Custom reducer:** All list fields use `_dedupe_reducer` — on parallel fan-out, partial states are merged and deduplicated by `id` / `name` / `title` rather than concatenated, preventing duplicate search results.

---

## AI Travel Negotiator

The negotiator runs after all research is complete and before the itinerary is built. It generates three distinct bundles so the user can compare trade-offs before committing.

### Bundle Types

| Bundle | Optimises For |
|--------|--------------|
| **Budget Saver** | Lowest total cost |
| **Best Value** | Highest composite score within budget |
| **Experience Max** | Highest experience score, up to +10% over budget |

### Scoring Algorithm (fully deterministic)

```
For each (transport × stay × activity_subset) combination:

  cost_score        = f(total_cost / budget)     — heavy penalty for over-budget
  experience_score  = stay_quality (0–30)
                    + activity_richness (0–40)
                    + transport_comfort (0–20)
                    + variety_bonus (0–10)
  convenience_score = f(travel_time, transfers, schedule_density, booking_links)

  final_score = weighted_sum(cost, experience, convenience)
```

LLM is called once (GPT-4o-mini) to generate human-readable trade-off bullets per bundle. If the LLM call fails, rule-based fallback bullets are used.

### Feasibility Validation

After bundle generation, `feasibility_validator` checks:
- Daily activity hours ≤ 10 h/day
- Buffer time ≥ 60 min/day
- Transport duration < 24 h

If a bundle fails, the longest activity is auto-removed and the check retries. After 2 failures the bundle is passed through anyway to avoid blocking the pipeline.

### What-If Budget Adjustments

Users can adjust budget by ±₹5K–₹10K (or any custom amount). `apply_what_if()` increments `what_if_delta`, clears the negotiator cache, and re-runs only the negotiator + feasibility validator — skipping the expensive research phase.

---

## Human-in-the-Loop (HITL) Checkpoints

The graph pauses at three points and waits for explicit user approval before continuing.

```
Checkpoint 1 — Destination Selection
  Trigger : destination_recommender sets requires_approval=True
  UI      : Radio buttons to pick from 3 recommended destinations
  Resume  : Graph continues to search_dispatcher with chosen destination

Checkpoint 2 — Bundle Selection  (only when use_negotiator=True)
  Trigger : negotiator + feasibility_validator complete
  UI      : Bundle cards (Budget Saver / Best Value / Experience Max)
  Resume  : Graph continues to budget_optimizer with selected bundle

Checkpoint 3 — Itinerary Review
  Trigger : vibe_scorer completes; approval_gate sets approval_type="itinerary"
  UI      : "Approve & Export" button on dashboard → review card
  Resume  : Approval opens share/QR modal; Modify opens chat sidebar
```

**Resumption mechanism:**
```python
runner.resume(session_id, user_feedback=None, approval=True)
# Sets requires_approval=False in state
# Graph continues from the MemorySaver checkpoint
```

---

## Streaming & Resumption

```
GraphRunner.stream(query, session_id, user_id)
  → yields (node_name, partial_state) tuples as each node completes
  → UI renders live timeline with progress bar
  → Final state persisted to SQLite via WorkingMemoryManager

GraphRunner.resume(session_id, feedback, approval)
  → Loads checkpointed state from SQLite
  → Patches state with user_feedback / requires_approval=False
  → Re-invokes graph from last checkpoint (MemorySaver)

GraphRunner.chat(message, session_id)
  → Fast-path: calls conversation_handler_node directly
  → No graph traversal — instant Q&A response
```

**Conversation memory** is stored separately in `ConversationMemoryManager` and compressed every 5 messages to keep context window manageable.

---

## Fallback & Resilience Strategy

Every agent is designed to never block the pipeline:

| Layer | Primary | Fallback 1 | Fallback 2 |
|-------|---------|-----------|-----------|
| Flights | Amadeus API | Tavily web search | Fare heuristic / skip |
| Hotels | LiteAPI | Tavily web search | Demo hotel data |
| Activities | Google Places | Tavily web search | Demo activity data |
| Weather | Open-Meteo | OpenWeatherMap | Seasonal static forecast |
| Local intel | Reddit API | Tavily web search | Empty list (non-blocking) |
| Trade-off text | GPT-4o-mini | Rule-based bullets | — |
| Intent parsing | GPT-4o | GPT-4o-mini | Regex heuristic |
| Negotiator bundles | Algorithmic scoring | - | — |

If all fallbacks fail, the agent logs the error to `state["errors"]` and returns an empty result — the pipeline continues with whatever data is available.
