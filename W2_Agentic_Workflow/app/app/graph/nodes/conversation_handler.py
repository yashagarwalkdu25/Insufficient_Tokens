"""Conversation handler: answer questions about itinerary without re-planning. No hardcoded responses."""
import json
import logging
import time
from typing import Any

from app.config import get_settings
from app.api.tavily_client import TavilySearchClient
from app.memory.conversation_memory import ConversationMemoryManager

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are TripSaathi, a warm and knowledgeable Indian travel assistant with a friendly, conversational personality. Think of yourself as the traveler's best friend who happens to know everything about their trip.

{trip_summary}

YOUR CAPABILITIES:
1. **Itinerary Q&A** — Answer any question about the trip by referencing the exact data above (costs, timings, hotel names, activity details, etc.)
2. **Clarification** — When the user's request is vague (e.g., "change it", "make it better", "that one"), ask a specific follow-up: "What would you like me to change? The hotel, activities, dates, or budget?"
3. **Suggest alternatives** — When asked to adjust something (e.g., "make it cheaper", "I want more adventure"), suggest 2-3 concrete changes with estimated savings or cost differences based on the actual itinerary items.
4. **Price questions** — Break down costs per day, per category, or compare items. Always cite the exact INR amounts from the itinerary.
5. **Timing & logistics** — Reference the schedule, travel durations between activities, and suggest adjustments if things seem rushed or too slow.
6. **Packing advice** — Based on the destination, season, and planned activities, give practical packing suggestions.
7. **Visa & documents** — Provide general visa/document guidance for the destination (domestic vs. international).
8. **Safety tips** — Share relevant safety advice for the destination and travel style.
9. **Food & culture** — Recommend local dishes, cultural etiquette, and must-try experiences based on the destination.
10. **Weather context** — Use the weather summaries from the itinerary to give practical advice.

RESPONSE STYLE:
- Be conversational and warm — use a friendly tone like a travel buddy, not a robot
- Reference specific parts of their itinerary by name, time, and cost
- Keep answers concise (3-5 sentences) unless the user asks for details
- Use INR for all prices
- If you genuinely don't have the information, say so honestly and suggest where they might find it
- When suggesting changes, be specific: "You could swap [Activity X at ₹Y] for [Alternative at ₹Z] and save ₹W"
- Sprinkle in local flavor — mention a local phrase, a hidden gem, or a pro tip when relevant
- If the user seems to want a modification to the plan (not just information), let them know they can use the "modify" feature or tell you exactly what to change"""


def _build_trip_summary(trip: dict[str, Any]) -> str:
    """Build a comprehensive trip summary for the LLM context."""
    dest = trip.get("destination", "?")
    origin = trip.get("origin", "?")
    start_date = trip.get("start_date", "?")
    end_date = trip.get("end_date", "?")
    total_cost = trip.get("total_cost", 0)
    travel_style = trip.get("travel_style", "balanced")
    traveler_type = trip.get("traveler_type", "solo")
    days = trip.get("days", [])

    summary = f"""CURRENT TRIP PLAN:
- Destination: {dest}
- Origin: {origin}
- Dates: {start_date} to {end_date}
- Duration: {len(days)} days
- Travel Style: {travel_style.title()}
- Traveler Type: {traveler_type.title()}
- Total Cost: ₹{total_cost:,.0f}

DETAILED DAY-BY-DAY ITINERARY:
"""

    for day in days:
        day_num = day.get("day_number", 1)
        day_title = day.get("title", f"Day {day_num}")
        day_date = day.get("date", "")
        day_cost = day.get("day_cost", 0)
        weather = day.get("weather_summary", "")
        tip = day.get("tip_of_the_day", "")
        items = day.get("items", [])

        summary += f"\n--- Day {day_num}: {day_title} ({day_date}) — Day cost: ₹{day_cost:,.0f} ---\n"
        if weather:
            summary += f"  Weather: {weather}\n"

        for item in items:
            time_str = item.get("time", "?")
            end_time = item.get("end_time", "")
            title = item.get("title", "?")
            item_type = item.get("item_type", "")
            cost = item.get("cost", 0)
            desc = item.get("description", "")
            location = item.get("location", "")
            travel_dur = item.get("travel_duration_to_next")
            travel_mode = item.get("travel_mode_to_next")
            contact = item.get("contact_info", "")

            time_label = time_str
            if end_time:
                time_label += f"–{end_time}"

            line = f"  {time_label} [{item_type}] {title}"
            if cost:
                line += f" — ₹{cost:,.0f}"
            if location:
                line += f" @ {location}"
            summary += line + "\n"

            if desc:
                summary += f"    → {desc[:150]}\n"
            if contact:
                summary += f"    Contact: {contact}\n"
            if travel_dur:
                summary += f"    ~{travel_dur} min to next by {travel_mode or 'auto'}\n"

        if tip:
            summary += f"  💡 Tip: {tip}\n"

    return summary


def conversation_handler_node(state: dict[str, Any]) -> dict[str, Any]:
    """Handle general conversation and questions about the itinerary."""
    start_t = time.time()
    message = (state.get("user_feedback") or state.get("raw_query") or "").strip()
    trip = state.get("trip")

    reasoning_parts = []
    tokens_used = 0
    response = ""

    conv_context = ""
    try:
        conv_context = ConversationMemoryManager().get_context_for_agent(state.get("session_id", ""))
    except Exception as e:
        logger.warning("Failed to load conversation context: %s", e)

    settings = get_settings()
    if settings.has_openai and message and trip:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            trip_summary = _build_trip_summary(trip)
            system_content = _SYSTEM_PROMPT.format(trip_summary=trip_summary)
            if conv_context:
                system_content += f"\n\nCONVERSATION HISTORY:\n{conv_context}"

            r = client.chat.completions.create(
                model=settings.GPT4O_MINI_MODEL,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": message},
                ],
                temperature=0.7,
            )
            response = (r.choices[0].message.content or "").strip()
            tokens_used = getattr(r.usage, "total_tokens", 0) if hasattr(r, "usage") else 0
            reasoning_parts.append("LLM answered question about itinerary")

        except Exception as e:
            logger.warning("Conversation handler LLM failed: %s", e)
            reasoning_parts.append(f"LLM failed: {str(e)}")

    if not response and message:
        try:
            tavily = TavilySearchClient()
            if tavily.available:
                dest = trip.get("destination", "") if trip else ""
                search_query = f"{message} {dest} India travel" if dest else f"{message} India travel"
                result = tavily.search(search_query, max_results=3)
                if result and result.get("answer"):
                    response = result["answer"]
                    reasoning_parts.append("Tavily web search answered the question")
        except Exception as e:
            logger.warning("Tavily conversation search failed: %s", e)
            reasoning_parts.append(f"Tavily search failed: {str(e)}")

    if not response:
        if not trip:
            response = "You don't have an itinerary yet. Let's plan your perfect trip! Just describe where you want to go."
        elif not settings.has_openai:
            response = "I need an OpenAI API key to answer questions. Please configure it in your .env file."
        else:
            response = "I wasn't able to process your question. Please try rephrasing or use the modify feature to make changes."
        reasoning_parts.append("No response generated from any source")

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "conversation_handler",
        "action": "answer_question",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": response[:100],
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }

    return {
        "current_stage": "conversation_done",
        "agent_decisions": [decision],
        "conversation_response": response,
    }
