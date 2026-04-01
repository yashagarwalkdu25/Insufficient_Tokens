🚀 Week 3 MCP Feature Plan

Trust Score + Conflict Detection (Easy but Killer Edge)

⸻

🎯 Objective

Enhance existing cross-source tools to provide:
	•	Trust Score (confidence of result)
	•	Signal Summary (agree / disagree / missing)
	•	Conflict Detection (explicit contradictions between sources)

Goal: Upgrade from “data aggregation” → intelligent reasoning system

⸻

🧠 Core Idea

Instead of just returning data:
	•	Normalize all outputs into signals
	•	Compare signals across sources
	•	Detect agreement vs contradiction
	•	Compute a transparent trust score

⸻

📦 Phase 1 — Output Schema (LOCK THIS FIRST)

Add the following fields to all cross-source tools:

Applies to:
	•	cross_reference_signals
	•	generate_research_brief
	•	portfolio_risk_report
	•	earnings_verdict

{
  "trust_score": 78,
  "signal_summary": {
    "confirmations": 3,
    "contradictions": 1,
    "missing": 2
  },
  "conflicts": [
    {
      "topic": "sentiment_vs_fundamentals",
      "status": "contradiction",
      "sources": ["BSE Filing", "GNews"],
      "details": "Fundamentals improved but sentiment stayed negative."
    }
  ],
  "evidence_matrix": [
    {
      "signal": "price_trend",
      "status": "confirmed",
      "sources": ["Angel One", "yfinance"]
    },
    {
      "signal": "news_sentiment",
      "status": "contradicted",
      "sources": ["GNews", "Finnhub"]
    }
  ]
}


⸻

🔍 Phase 2 — Signal Normalization Layer

Why

Raw API outputs are messy → normalize into standard signals

⸻

Example Signals

PS1 (Research)
	•	price_trend
	•	volume_spike
	•	fundamental_strength
	•	news_sentiment
	•	macro_support
	•	filing_health

PS2 (Portfolio)
	•	sector_concentration
	•	mf_overlap
	•	macro_sensitivity
	•	sentiment_shift

PS3 (Earnings)
	•	earnings_beat_miss
	•	post_results_reaction
	•	shareholding_change
	•	guidance_sentiment

⸻

Signal Format

{
  "name": "news_sentiment",
  "value": "negative",
  "confidence": 0.7,
  "sources": ["GNews", "Finnhub"],
  "source_values": {
    "GNews": "negative",
    "Finnhub": "neutral"
  }
}


⸻

⚔️ Phase 3 — Conflict Detection Engine

Core Logic

For each signal:

Condition	Status
Sources agree	confirmed
Sources disagree	contradicted
Only one source	weakly_supported
Missing expected data	missing


⸻

Key Contradiction Rules

1. Price vs Sentiment
	•	Price ↓
	•	Sentiment positive
→ contradiction

⸻

2. Fundamentals vs Sentiment
	•	Revenue/profit ↑
	•	Sentiment negative
→ contradiction

⸻

3. Earnings vs Market Reaction (🔥 best demo)
	•	Earnings beat
	•	Stock falls
→ contradiction

⸻

4. Macro vs Sector
	•	Macro favorable
	•	Sector weak
→ contradiction

⸻

Conflict Output Example

{
  "topic": "earnings_vs_price",
  "status": "contradiction",
  "sources": ["BSE Filing", "NSE"],
  "details": "Company beat earnings but stock dropped 3%."
}


⸻

📊 Phase 4 — Trust Score Engine

Design Principles
	•	Simple
	•	Explainable
	•	Deterministic (NO LLM scoring)

⸻

Formula

Start with:

base = 50

Adjust:
	•	+10 → per confirmed signal
	•	-12 → per contradiction
	•	-5 → per missing signal
	•	+5 → multi-source agreement

Clamp:

0 ≤ score ≤ 100


⸻

Example

50 + (3×10) - (1×12) - (1×5) + (2×5)
= 73


⸻

Add Explanation

"trust_score_reasoning": [
  "Price trend confirmed by Angel One and yfinance",
  "News sentiment conflicted across sources",
  "No recent filing available"
]


⸻

🧱 Phase 5 — Shared Module Design

Create reusable modules:

src/
 ├── cross_source/
 │   ├── signal_normalizer.py
 │   ├── conflict_detector.py
 │   ├── trust_scorer.py


⸻

Responsibilities

signal_normalizer.py
	•	Convert API responses → signals

conflict_detector.py
	•	Detect:
	•	confirmations
	•	contradictions
	•	missing signals

trust_scorer.py
	•	Compute:
	•	trust_score
	•	signal_summary
	•	reasoning

⸻

🔌 Phase 6 — Integration Points

Start with HIGH IMPACT tools

Priority 1
	•	cross_reference_signals
	•	earnings_verdict

Priority 2
	•	portfolio_risk_report
	•	generate_research_brief

⸻

🖥️ Phase 7 — UI / Output Display

Show clearly:

Trust Score

Trust Score: 78 / 100

Signal Summary

✔ Confirmed: 3  
⚠ Contradicted: 1  
❌ Missing: 1

Conflicts
	•	“Earnings beat but stock dropped”
	•	“Strong fundamentals but negative sentiment”

⸻

🎬 Phase 8 — Demo Strategy

Best Demo (PS3 🔥)
	•	Company beats earnings
	•	Stock drops
	•	System shows contradiction
	•	Trust score = medium (not blindly high)

⸻

Alternative Demo (PS1)
	•	Mixed signals across:
	•	price
	•	news
	•	filings
→ show trust + conflicts

⸻

Auth Demo Combo
	•	Free user → 403
	•	Upgrade → access
	•	Show reasoning output

⸻

⏱️ 2-Day Implementation Plan

Day 1
	•	Define schema
	•	Build signal normalization
	•	Implement conflict detection
	•	Implement trust scoring

⸻

Day 2
	•	Integrate into:
	•	cross_reference_signals
	•	earnings_verdict
	•	Add UI / output formatting
	•	Prepare demo scenarios

⸻

⚠️ What NOT to Do
	•	❌ Don’t use LLM for scoring
	•	❌ Don’t overcomplicate formula
	•	❌ Don’t implement for all tools first
	•	❌ Don’t build ML models

⸻

🏆 Final Pitch

“Our MCP server doesn’t just aggregate financial data. It evaluates agreement across sources, detects contradictions, and assigns a transparent trust score to every insight.”

⸻

✅ Implementation Order
	1.	Signal Normalizer
	2.	Conflict Detector
	3.	Trust Scorer
	4.	Apply to:
	•	cross_reference_signals
	•	earnings_verdict

⸻

🚀 Outcome

You transform your system from:

❌ API wrapper
➡️
✅ Intelligent financial reasoning engine

⸻

This is your edge.
:::