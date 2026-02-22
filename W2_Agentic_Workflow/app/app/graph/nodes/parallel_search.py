"""
DEPRECATED: Parallel search is now handled by the LangGraph graph structure itself.

Individual search agents (flight_search, hotel_search, activity_search, weather_check)
are separate LangGraph nodes that run IN PARALLEL via Send() fan-out from the
search_dispatcher node.

Similarly, enrichment agents (local_intel, festival_check) run in parallel via
Send() fan-out from the enrichment_dispatcher node.

This file is kept for backward compatibility only.
"""
