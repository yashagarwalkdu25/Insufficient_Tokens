"""Local intel agent: Reddit + Tavily web search + LLM extraction for hidden gems."""
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


def _extract_gems_with_llm(dest: str, raw_results: list[dict]) -> list[HiddenGem]:
    """Use GPT to extract structured hidden gems from raw Tavily search results."""
    settings = get_settings()
    if not settings.has_openai or not raw_results:
        return []

    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    combined_text = "\n\n".join(
        f"[{i+1}] {r.get('title','')}\n{r.get('content','')}"
        for i, r in enumerate(raw_results[:6])
    )

    prompt = f"""You are a local travel expert for {dest}, India.
From the search results below, extract 4-6 specific hidden gems, lesser-known spots, or off-the-beaten-path experiences.

Rules:
- Each gem must be a real, specific place or experience (not generic advice)
- Focus on spots locals love but tourists often miss
- Include a pro tip for each gem
- Assign a confidence score 0.0–1.0 based on how specific and credible the source is
- Category must be one of: nature, food, culture, adventure, heritage, spiritual, market, viewpoint

Return ONLY a JSON array, no markdown:
[
  {{
    "name": "Place or experience name",
    "description": "1-2 sentence description of what it is",
    "why_special": "Why locals love it / what makes it unique",
    "pro_tip": "Practical insider tip (best time, how to get there, what to order, etc.)",
    "category": "nature",
    "confidence": 0.85
  }}
]

Search results:
{combined_text}"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1200,
        )
        raw = resp.choices[0].message.content or "[]"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        gems = []
        for item in parsed:
            if not item.get("name"):
                continue
            gems.append(HiddenGem(
                name=item["name"],
                description=item.get("description", ""),
                why_special=item.get("why_special"),
                pro_tip=item.get("pro_tip"),
                category=item.get("category", "culture"),
                confidence=float(item.get("confidence", 0.75)),
                source="llm",
                verified=False,
            ))
        return gems
    except Exception as e:
        logger.warning("LLM gem extraction failed: %s", e)
        return []


def gather_local_intel_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: gather tips and hidden gems from Reddit + Tavily + LLM extraction."""
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
        reddit_client = RedditClient()
        reddit_tips = reddit_client.search_travel_tips(dest, limit=5)
        for t in reddit_tips:
            tips.append(LocalTip(
                title=t.title,
                content=t.content,
                category="travel",
                source_platform="reddit",
                source_url=t.source_url,
                upvotes=t.upvotes,
                source="api",
                verified=True,
            ))
        if reddit_tips:
            reasoning_parts.append(f"Reddit: found {len(reddit_tips)} tips from travel subreddits.")
    except Exception:
        reasoning_parts.append("Reddit API unavailable.")

    # Strategy 2: Tavily web search for local tips
    tavily_gem_results: list[dict] = []
    try:
        tavily = TavilySearchClient()
        if tavily.available:
            if not tips:
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
                    reasoning_parts.append(f"Tavily: found {len(tavily_tips)} local tips for {dest}.")

            # Always search for hidden gems separately
            tavily_gem_results = tavily.search_hidden_gems(dest, interests)
            if tavily_gem_results:
                reasoning_parts.append(f"Tavily: found {len(tavily_gem_results)} raw gem results for {dest}.")
    except Exception as e:
        reasoning_parts.append(f"Tavily search failed ({e}).")

    # Strategy 3: LLM extraction of structured hidden gems from raw Tavily results
    if tavily_gem_results:
        try:
            llm_gems = _extract_gems_with_llm(dest, tavily_gem_results)
            gems.extend(llm_gems)
            if llm_gems:
                reasoning_parts.append(f"LLM extracted {len(llm_gems)} hidden gems from web results.")
        except Exception as e:
            reasoning_parts.append(f"LLM gem extraction failed ({e}).")

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
