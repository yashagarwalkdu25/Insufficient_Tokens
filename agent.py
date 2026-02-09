"""Agentic RAG pipeline for claim verification.

Flow:
  1. Extract / normalise the claim
  2. Retrieve from vector KB  →  rerank
  3. If evidence insufficient  →  web search (trusted + fact-checkers)
  4. Index new web evidence into KB (ever-growing)
  5. Combine all evidence  →  LLM verdict with citations
  6. Return structured result
"""
from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from openai import OpenAI
from config import (
    OPENAI_API_KEY, LLM_MODEL, LLM_TEMPERATURE,
    TOP_K_RETRIEVAL, TOP_K_RERANK, VERDICTS,
)
from vector_store import VectorStore
from reranker import Reranker
from web_search import search_web, search_trusted, search_fact_checkers

logger = logging.getLogger(__name__)

# ── Data classes ──────────────────────────────────────────────────────
@dataclass
class Evidence:
    text: str
    source: str
    score: float = 0.0
    origin: str = "kb"  # "kb" | "web" | "fact_check"

@dataclass
class VerificationResult:
    claim: str
    verdict: str
    confidence: float
    reasoning: str
    evidence: list[Evidence] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


# ── Agent ─────────────────────────────────────────────────────────────
class ClaimVerifier:
    """Agentic RAG claim verification pipeline."""

    def __init__(self):
        self.vs = VectorStore()
        self.reranker = Reranker()
        self.llm = OpenAI(api_key=OPENAI_API_KEY)

    # ── public API ────────────────────────────────────────────────────
    def verify(self, raw_claim: str) -> VerificationResult:
        """End-to-end claim verification with agentic decision loop."""
        steps: list[str] = []
        all_evidence: list[Evidence] = []

        # Step 1 — Normalise claim
        steps.append("Step 1: Normalising claim…")
        claim = self._normalise_claim(raw_claim)
        steps.append(f"  → Normalised: \"{claim}\"")

        # Step 2 — KB retrieval + rerank
        steps.append("Step 2: Retrieving from knowledge base…")
        kb_evidence = self._retrieve_kb(claim)
        all_evidence.extend(kb_evidence)
        steps.append(f"  → Found {len(kb_evidence)} KB evidence(s)")

        # Step 3 — Decide: enough evidence?
        enough = self._has_enough_evidence(claim, kb_evidence)
        if not enough:
            # Step 3a — Web search (trusted sources)
            steps.append("Step 3: KB insufficient → searching trusted news…")
            web_ev = self._search_and_index(claim, search_fn=search_trusted)
            all_evidence.extend(web_ev)
            steps.append(f"  → Found {len(web_ev)} web evidence(s)")

            # Step 3b — Fact-checker search
            steps.append("Step 4: Searching fact-checkers…")
            fc_ev = self._search_and_index(claim, search_fn=search_fact_checkers)
            all_evidence.extend(fc_ev)
            steps.append(f"  → Found {len(fc_ev)} fact-check evidence(s)")

            # Step 3c — Broad web if still thin
            if len(all_evidence) < 2:
                steps.append("Step 5: Still thin → broad web search…")
                broad_ev = self._search_and_index(claim, search_fn=search_web)
                all_evidence.extend(broad_ev)
                steps.append(f"  → Found {len(broad_ev)} broad evidence(s)")
        else:
            steps.append("Step 3: Sufficient KB evidence — skipping web search.")

        # Step 4 — Deduplicate
        all_evidence = self._deduplicate(all_evidence)

        # Step 5 — Final rerank across all evidence
        if all_evidence:
            steps.append(f"Step 6: Reranking {len(all_evidence)} total evidence(s)…")
            all_evidence = self._rerank_evidence(claim, all_evidence)

        # Step 6 — LLM verdict
        steps.append("Step 7: Generating verdict with LLM…")
        result = self._generate_verdict(claim, all_evidence)
        result.steps = steps
        return result

    # ── private helpers ───────────────────────────────────────────────
    def _normalise_claim(self, raw: str) -> str:
        """Use LLM to extract a clean, verifiable claim."""
        resp = self.llm.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": (
                    "Extract a single, clear, verifiable factual claim from the "
                    "user's input. Output ONLY the claim, nothing else. "
                    "If the input is already a clean claim, return it as-is."
                )},
                {"role": "user", "content": raw},
            ],
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip().strip('"')

    def _retrieve_kb(self, claim: str) -> list[Evidence]:
        """Retrieve from vector store and rerank."""
        hits = self.vs.query(claim, top_k=TOP_K_RETRIEVAL)
        if not hits:
            return []
        # Bump access counts
        for h in hits:
            self.vs.increment_access(h["id"])
        # Rerank
        reranked = self.reranker.rerank(claim, hits, top_k=TOP_K_RERANK)
        return [
            Evidence(text=h["text"], source=h["source"],
                     score=h.get("rerank_score", h.get("score", 0)), origin="kb")
            for h in reranked
        ]

    def _has_enough_evidence(self, claim: str, evidence: list[Evidence]) -> bool:
        """Quick LLM check: is the KB evidence sufficient?"""
        if len(evidence) < 2:
            return False
        ctx = "\n".join(f"- {e.text} (score={e.score:.2f})" for e in evidence[:5])
        resp = self.llm.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": (
                    "You decide if the provided evidence is SUFFICIENT to verify "
                    "the claim. Answer ONLY 'yes' or 'no'."
                )},
                {"role": "user", "content": f"Claim: {claim}\n\nEvidence:\n{ctx}"},
            ],
            max_tokens=5,
        )
        answer = resp.choices[0].message.content.strip().lower()
        return answer.startswith("yes")

    def _search_and_index(self, claim: str, search_fn) -> list[Evidence]:
        """Run a web search, index results into KB, return Evidence list."""
        results = search_fn(claim)
        evidence = []
        docs_to_index = []
        for r in results:
            snippet = r.get("snippet", "")
            url = r.get("url", "")
            title = r.get("title", "")
            if not snippet:
                continue
            evidence.append(Evidence(
                text=snippet, source=url,
                score=0.0, origin="web" if "fact" not in str(search_fn) else "fact_check",
            ))
            docs_to_index.append({
                "text": snippet,
                "source": url,
                "details": title,
            })
        # Index into KB (ever-growing knowledge base)
        if docs_to_index:
            self.vs.add_documents_batch(docs_to_index)
        return evidence

    def _rerank_evidence(self, claim: str, evidence: list[Evidence]) -> list[Evidence]:
        """Rerank all evidence using cross-encoder."""
        candidates = [{"text": e.text, "source": e.source, "origin": e.origin}
                      for e in evidence]
        reranked = self.reranker.rerank(claim, candidates, top_k=TOP_K_RERANK)
        return [
            Evidence(text=r["text"], source=r["source"],
                     score=r.get("rerank_score", 0), origin=r.get("origin", "web"))
            for r in reranked
        ]

    def _deduplicate(self, evidence: list[Evidence]) -> list[Evidence]:
        """Remove near-duplicate evidence by source URL."""
        seen_sources: set[str] = set()
        seen_texts: set[str] = set()
        unique = []
        for e in evidence:
            text_key = e.text[:100].lower()
            if e.source in seen_sources or text_key in seen_texts:
                continue
            seen_sources.add(e.source)
            seen_texts.add(text_key)
            unique.append(e)
        return unique

    def _generate_verdict(self, claim: str, evidence: list[Evidence]) -> VerificationResult:
        """Use LLM to produce final verdict with citations."""
        if not evidence:
            return VerificationResult(
                claim=claim,
                verdict="Not Enough Evidence",
                confidence=0.0,
                reasoning="No supporting or contradicting evidence was found in the "
                          "knowledge base or on the web.",
                evidence=[],
            )

        evidence_block = ""
        for i, e in enumerate(evidence, 1):
            evidence_block += (
                f"[{i}] (Source: {e.source}, Origin: {e.origin}, "
                f"Relevance: {e.score:.2f})\n{e.text}\n\n"
            )

        system_prompt = f"""You are a rigorous fact-checking assistant. Analyse the claim against the provided evidence and produce a JSON response.

RULES:
- You MUST cite sources using [1], [2], etc. matching the evidence numbers.
- You MUST NOT fabricate any sources or evidence.
- If evidence is contradictory, explain both sides.
- If evidence is insufficient, verdict MUST be "Not Enough Evidence".
- Allowed verdicts: {', '.join(VERDICTS)}

OUTPUT FORMAT (strict JSON):
{{
  "verdict": "<one of the allowed verdicts>",
  "confidence": <float 0-1>,
  "reasoning": "<detailed reasoning with [N] citations>"
}}"""

        user_msg = f"CLAIM: {claim}\n\nEVIDENCE:\n{evidence_block}"

        resp = self.llm.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1000,
            response_format={"type": "json_object"},
        )

        raw = resp.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"verdict": "Not Enough Evidence", "confidence": 0.0,
                    "reasoning": raw}

        return VerificationResult(
            claim=claim,
            verdict=data.get("verdict", "Not Enough Evidence"),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
            evidence=evidence,
        )
