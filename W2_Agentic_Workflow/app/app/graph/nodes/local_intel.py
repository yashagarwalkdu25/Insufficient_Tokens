"""Local intel agent: Reddit + Tavily web search. No hardcoded curated data."""
import json
import logging
import time
from typing import Any

from app.api.reddit_client import RedditClient
from app.api.tavily_client import TavilySearchClient
from app.config import get_settings
from app.models.local_intel import LocalTip, HiddenGem

logger = logging.getLogger(__name__)


def _tip_to_dict(t: Any) -> dict:
    if hasattr(t, "model_dump"):
        return t.model_dump()
    return t if isinstance(t, dict) else {"title": str(t), "content": "", "category": "travel", "source_platform": "web", "source": "web", "verified": False}


def _gem_to_dict(g: Any) -> dict:
    if hasattr(g, "model_dump"):
        return g.model_dump()
    return g if isinstance(g, dict) else {"name": str(g), "description": "", "category": "nature", "source": "web", "verified": False}


def gather_local_intel_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: gather tips, hidden gems from Reddit + Tavily web search."""
    start_t = time.time()

    req = state.get("trip_request") or {}
    dest = (req.get("destination") or "").strip()
    interests = req.get("interests") or []
    if not dest:
        return {
            "local_tips": [],
            "hidden_gems": [],
            "agent_decisions": [{
                "agent_name": "local_intel",
                "action": "gather",
                "reasoning": "No destination — skipping local intel.",
                "result_summary": "Skipped",
                "tokens_used": 0,
                "latency_ms": 0,
            }],
        }

    tips: list[Any] = []
    gems: list[Any] = []
    reasoning_parts: list[str] = []

    # Strategy 1: Reddit tips
    try:
        client = RedditClient()
        reddit_tips = client.search_travel_tips(dest, limit=5)
        for t in reddit_tips:
            tips.append(LocalTip(title=t.title, content=t.content, category="travel", source_platform="reddit", source_url=t.source_url, upvotes=t.upvotes, source="api", verified=True))
        if reddit_tips:
            reasoning_parts.append(f"Reddit: found {len(reddit_tips)} tips from travel subreddits.")
    except Exception:
        reasoning_parts.append("Reddit API unavailable.")

    # Strategy 2: Tavily web search for local tips and hidden gems
    if not tips:
        try:
            tavily = TavilySearchClient()
            if tavily.available:
                tavily_tips = tavily.search_local_tips(dest)
                if tavily_tips:
                    for tt in tavily_tips:
                        tips.append(LocalTip(
                            title=tt.get("title", "Travel tip"),
                            content=tt.get("content", ""),
                            category="travel",
                            source_platform="web",
                            source_url=tt.get("url"),
                            source="tavily_web",
                            verified=False,
                        ))
                    reasoning_parts.append(f"Tavily web search found {len(tavily_tips)} local tips for {dest}.")
        except Exception as e:
            reasoning_parts.append(f"Tavily local tips search failed ({e}).")

    if not tips and not gems:
        reasoning_parts.append(f"No local tips or hidden gems found for {dest} from any source.")

    latency_ms = int((time.time() - start_t) * 1000)
    decision = {
        "agent_name": "local_intel",
        "action": "gather",
        "reasoning": " ".join(reasoning_parts),
        "result_summary": f"{len(tips)} tips, {len(gems)} gems for {dest}",
        "tokens_used": 0,
        "latency_ms": latency_ms,
    }
    return {
        "local_tips": [_tip_to_dict(t) for t in tips],
        "hidden_gems": [_gem_to_dict(g) for g in gems],
        "agent_decisions": [decision],
    }
