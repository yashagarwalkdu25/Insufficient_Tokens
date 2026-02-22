"""Conversation handler: answer questions about itinerary without re-planning."""
import json
import logging
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def conversation_handler_node(state: dict[str, Any]) -> dict[str, Any]:
    """Handle general conversation and questions about the itinerary."""
    start_t = time.time()
    message = (state.get("user_feedback") or state.get("raw_query") or "").strip()
    trip = state.get("trip")
    
    reasoning_parts = []
    tokens_used = 0
    response = "I can help you with your trip planning!"
    
    settings = get_settings()
    if settings.has_openai and message and trip:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Prepare context about current trip
            dest = trip.get("destination", "?")
            origin = trip.get("origin", "?")
            start_date = trip.get("start_date", "?")
            end_date = trip.get("end_date", "?")
            total_cost = trip.get("total_cost", 0)
            days = trip.get("days", [])
            
            # Build compact trip summary for context
            trip_summary = f"""Current Trip Plan:
- Destination: {dest}
- Origin: {origin}
- Dates: {start_date} to {end_date}
- Total Budget: ₹{total_cost:,.0f}
- Days: {len(days)}

Day-by-day summary:
"""
            for day in days[:5]:  # First 5 days only
                day_num = day.get("day_number", 1)
                day_title = day.get("title", f"Day {day_num}")
                items = day.get("items", [])
                trip_summary += f"\nDay {day_num} - {day_title}: {len(items)} activities\n"
                for item in items[:3]:  # First 3 items per day
                    trip_summary += f"  - {item.get('time', '?')}: {item.get('title', '?')} (₹{item.get('cost', 0)})\n"
            
            r = client.chat.completions.create(
                model=settings.GPT4O_MINI_MODEL,
                messages=[
                    {"role": "system", "content": f"""You are TripSaathi, a friendly Indian travel assistant. Answer the user's question about their trip concisely and helpfully.

{trip_summary}

Rules:
- Be conversational and warm
- Refer to specific parts of their itinerary when relevant
- If asked about costs, cite the specific amounts
- If asked about timing, reference the schedule
- If you don't have the info, be honest
- Keep responses under 3-4 sentences unless asked for details"""},
                    {"role": "user", "content": message},
                ],
                temperature=0.7,
            )
            response = (r.choices[0].message.content or "").strip()
            tokens_used = getattr(r.usage, "total_tokens", 0) if hasattr(r, "usage") else 0
            reasoning_parts.append(f"LLM answered question about itinerary")
            
        except Exception as e:
            logger.warning(f"Conversation handler LLM failed: {e}")
            response = f"I see you're asking about your trip to {trip.get('destination', '?')}. Your itinerary is ready! Feel free to modify it using the chat."
            reasoning_parts.append(f"Fallback response: {str(e)}")
    elif not trip:
        response = "You don't have an itinerary yet. Let's plan your perfect trip! Just describe where you want to go."
        reasoning_parts.append("No trip in state")
    else:
        response = "I'm here to help! Ask me anything about your trip or request modifications."
        reasoning_parts.append("No OpenAI key or message")
    
    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "conversation_handler",
        "action": "answer_question",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": response[:100],
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    
    # Store response in state for UI to display
    return {
        "current_stage": "conversation_done",
        "agent_decisions": [decision],
        "conversation_response": response,
    }
