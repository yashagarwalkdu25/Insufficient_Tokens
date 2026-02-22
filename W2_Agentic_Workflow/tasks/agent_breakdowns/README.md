# Agent Breakdowns

Detailed task breakdown for each of the 13 agents in YATRA AI.

## Agents by Category

### Orchestration
- [Supervisor Agent](supervisor.md) - Routes requests, activates agents, monitors quality

### Input Processing
- [Intent Parser](intent-parser.md) - NL query → structured TripRequest
- [Destination Recommender](destination-recommender.md) - Suggests destinations when not specified

### Data Fetching (Parallel)
- [Flight Search](flight-search.md) - Finds flights via Amadeus + fallbacks
- [Hotel Search](hotel-search.md) - Finds hotels via LiteAPI + fallbacks
- [Activity Search](activity-search.md) - Finds activities via Google Places + curated
- [Weather Check](weather-check.md) - Gets forecast via OpenWeatherMap + fallback

### Enrichment (Conditional)
- [Local Intel](local-intel.md) - Reddit tips + curated + AI hidden gems
- [Festival Check](festival-check.md) - Events during trip dates

### Optimization & Generation
- [Budget Optimizer](budget-optimizer.md) - Scores, selects, allocates budget
- [Itinerary Builder](itinerary-builder.md) - Creates day-by-day plan
- [Vibe Scorer](vibe-scorer.md) - Trip-preference match scoring

### Feedback
- [Feedback Handler](feedback-handler.md) - Processes changes, triggers selective re-plan
