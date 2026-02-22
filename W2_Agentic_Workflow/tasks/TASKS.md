# YATRA AI - Master Task List

## Overview
12 independent tasks, each can be a separate PR. Execute in dependency order.

---

## Dependency Graph

```
TASK-01 (Project Setup)
  ├── TASK-02 (Static Data)
  ├── TASK-03 (API Clients)
  ├── TASK-04 (Memory Layer)
  │
  ├── TASK-05 (LangGraph Core) ← depends on TASK-01, TASK-04
  │     ├── TASK-06 (Search Agents) ← depends on TASK-03, TASK-05
  │     ├── TASK-07 (Enrichment Agents) ← depends on TASK-02, TASK-03, TASK-05
  │     └── TASK-08 (Optimization Agents) ← depends on TASK-05, TASK-06, TASK-07
  │
  ├── TASK-09 (Streamlit UI) ← depends on TASK-02, TASK-05, TASK-08
  ├── TASK-10 (Export & Sharing) ← depends on TASK-01, TASK-08
  │
  ├── TASK-11 (Demo Scenarios) ← depends on ALL above
  └── TASK-12 (Documentation) ← can start early, finalize last
```

---

## Task Summary

| ID | Title | Priority | Depends On | Est. Files | Est. LOC |
|----|-------|----------|------------|-----------|---------|
| TASK-01 | Project Setup & Foundation | P0 | None | ~15 | ~850 |
| TASK-02 | Static Data & Curated DBs | P0 | TASK-01 | 4 | ~1000 |
| TASK-03 | API Client Layer (+Directions, Ground Transport) | P0 | TASK-01 | 9 | ~1150 |
| TASK-04 | Memory & Context Mgmt | P0 | TASK-01 | 4 | ~500 |
| TASK-05 | LangGraph Core | P0 | TASK-01, 04 | 5 | ~700 |
| TASK-06 | Search Agents (+Ground Transport, Contact Info) | P1 | TASK-03, 05 | 4 | ~650 |
| TASK-07 | Enrichment Agents | P1 | TASK-02, 03, 05 | 5 | ~450 |
| TASK-08 | Optimization Agents (+Travel Times, Hours Validation) | P1 | TASK-05, 06, 07 | 12 | ~1400 |
| TASK-09 | Streamlit UI (+Travel Duration, Contact Info Display) | P1 | TASK-02, 05, 08 | 14 | ~1900 |
| TASK-10 | Export & Sharing | P2 | TASK-01, 08 | 7 | ~700 |
| TASK-11 | Demo Scenarios | P2 | ALL | 4 | ~800 |
| TASK-12 | Documentation | P2 | ALL (start early) | 4 | ~500 |
| **TOTAL** | | | | **~87** | **~10600** |

---

## Execution Order (Recommended)

### Sprint 1: Foundation (Can all run in parallel)
1. **TASK-01** - Project Setup & Foundation
2. **TASK-02** - Static Data (after TASK-01 models done)
3. **TASK-03** - API Clients (after TASK-01 config done)
4. **TASK-04** - Memory Layer (after TASK-01 database done)

### Sprint 2: Core Pipeline
5. **TASK-05** - LangGraph Core (after TASK-01 + TASK-04)
6. **TASK-06** - Search Agents (after TASK-03 + TASK-05)
7. **TASK-07** - Enrichment Agents (after TASK-02 + TASK-05)

### Sprint 3: Intelligence + UI
8. **TASK-08** - Optimization Agents (after TASK-05 + 06 + 07)
9. **TASK-09** - Streamlit UI (after TASK-08)

### Sprint 4: Polish & Submit
10. **TASK-10** - Export & Sharing (after TASK-08)
11. **TASK-11** - Demo Scenarios (after ALL)
12. **TASK-12** - Documentation (start early, finalize last)

---

## Agent → Task Mapping

| Agent | Task |
|-------|------|
| Supervisor | TASK-05 |
| Intent Parser | TASK-08 |
| Destination Recommender | TASK-07 |
| Flight Search | TASK-06 |
| Hotel Search | TASK-06 |
| Activity Search | TASK-06 |
| Weather Check | TASK-06 |
| Local Intel | TASK-07 |
| Festival Check | TASK-07 |
| Budget Optimizer | TASK-08 |
| Itinerary Builder | TASK-08 |
| Vibe Scorer | TASK-08 |
| Feedback Handler | TASK-08 |

---

## PR Strategy

Each task = 1 PR. Merge in dependency order.

```
PR #1:  TASK-01 → main
PR #2:  TASK-02 → main (after PR #1)
PR #3:  TASK-03 → main (after PR #1)
PR #4:  TASK-04 → main (after PR #1)
PR #5:  TASK-05 → main (after PR #1, #4)
PR #6:  TASK-06 → main (after PR #3, #5)
PR #7:  TASK-07 → main (after PR #2, #3, #5)
PR #8:  TASK-08 → main (after PR #5, #6, #7)
PR #9:  TASK-09 → main (after PR #2, #5, #8)
PR #10: TASK-10 → main (after PR #1, #8)
PR #11: TASK-11 → main (after all)
PR #12: TASK-12 → main (after all)
```

## Branch Naming
```
feat/task-01-project-setup
feat/task-02-static-data
feat/task-03-api-clients
feat/task-04-memory-layer
feat/task-05-langgraph-core
feat/task-06-search-agents
feat/task-07-enrichment-agents
feat/task-08-optimization-agents
feat/task-09-streamlit-ui
feat/task-10-export-sharing
feat/task-11-demo-scenarios
docs/task-12-documentation
```
