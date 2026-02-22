"""Local intel agent: Reddit + curated tips + LLM-generated hidden gems."""
import json
import logging
import time
from typing import Any

from app.api.reddit_client import RedditClient
from app.config import get_settings
from app.data.local_tips_db import get_tips, get_hidden_gems
from app.models.local_intel import LocalTip, HiddenGem

logger = logging.getLogger(__name__)


def _tip_to_dict(t: Any) -> dict:
    if hasattr(t, "model_dump"):
        return t.model_dump()
    return t if isinstance(t, dict) else {"title": str(t), "content": "", "category": "travel", "source_platform": "curated", "source": "curated", "verified": True}


def _gem_to_dict(g: Any) -> dict:
    if hasattr(g, "model_dump"):
        return g.model_dump()
    return g if isinstance(g, dict) else {"name": str(g), "description": "", "category": "nature", "source": "curated", "verified": True}


def _llm_hidden_gems(dest: str, interests: list[str]) -> list[dict]:
    """Use GPT-4o-mini to generate AI-powered hidden gems."""
    settings = get_settings()
    if not settings.has_openai:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        r = client.chat.completions.create(
            model=settings.GPT4O_MINI_MODEL,
            messages=[{"role": "user", "content": f"""Generate 3 hidden gem recommendations for {dest}, India that most tourists miss.
Traveler interests: {', '.join(interests) if interests else 'general exploration'}

Return JSON array:
[{{"name": "...", "description": "2-3 sentences", "why_special": "what makes it unique", "pro_tip": "insider advice", "category": "nature/culture/food/adventure", "best_time": "when to visit"}}]

Be specific to {dest}. Include real lesser-known places, not mainstream tourist spots."""}],
            temperature=0.7,
        )
        content = (r.choices[0].message.content or "").strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        logger.warning("LLM hidden gems failed: %s", e)
        return []


def gather_local_intel_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: gather tips, hidden gems from Reddit + curated DB + LLM."""
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

    # ── Reddit tips ────────────────────────────────────────────────────────
    try:
        client = RedditClient()
        reddit_tips = client.search_travel_tips(dest, limit=5)
        for t in reddit_tips:
            tips.append(LocalTip(title=t.title, content=t.content, category="travel", source_platform="reddit", source_url=t.source_url, upvotes=t.upvotes, source="api", verified=True))
        if reddit_tips:
            reasoning_parts.append(f"Reddit: found {len(reddit_tips)} tips from travel subreddits.")
    except Exception:
        reasoning_parts.append("Reddit API unavailable; using curated tips only.")

    # ── Curated tips + gems ────────────────────────────────────────────────
    curated_tips = get_tips(dest)
    for t in curated_tips:
        tips.append(LocalTip(title=t["title"], content=t["content"], category=t.get("category", "travel"), source_platform="curated", source="curated", verified=True))
    curated_gems = get_hidden_gems(dest)
    for g in curated_gems:
        gems.append(HiddenGem(name=g["name"], description=g["description"], why_special=g.get("why_special"), pro_tip=g.get("pro_tip"), category=g.get("category", "nature"), latitude=g.get("latitude"), longitude=g.get("longitude"), source="curated", verified=True))
    reasoning_parts.append(f"Curated DB: {len(curated_tips)} tips, {len(curated_gems)} gems for {dest}.")

    # ── LLM-generated hidden gems ──────────────────────────────────────────
    llm_gems = _llm_hidden_gems(dest, interests)
    for g in llm_gems:
        gems.append(HiddenGem(
            name=g.get("name", "Hidden Gem"),
            description=g.get("description", ""),
            why_special=g.get("why_special"),
            pro_tip=g.get("pro_tip"),
            category=g.get("category", "nature"),
            source="llm",
            verified=False,
        ))
    if llm_gems:
        reasoning_parts.append(f"LLM generated {len(llm_gems)} AI hidden gems (unverified, tagged source=llm).")

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
