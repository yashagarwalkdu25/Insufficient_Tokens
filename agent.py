"""Agentic RAG pipeline for claim verification.

Flow:
  1. Extract / normalise the claim with type classification
  2. Retrieve from vector KB  →  multi-stage rerank
  3. If evidence insufficient  →  web search (trusted + fact-checkers)
  4. Index new web evidence into KB (ever-growing)
  5. Combine all evidence  →  LLM verdict with citations
  6. Return structured result

Improvements:
  - Claim type classification (factual vs opinion vs mixed)
  - Context isolation with session IDs
  - Multi-stage reranking with source credibility
  - Better error handling and user feedback
"""
from __future__ import annotations
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
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
    session_id: str = ""
    claim_type: str = ""  # FACTUAL, OPINION, MIXED, AMBIGUOUS
    original_claim: str = ""  # User's raw input


# ── Agent ─────────────────────────────────────────────────────────────
class ClaimVerifier:
    """Agentic RAG claim verification pipeline."""

    def __init__(self):
        self.vs = VectorStore()
        self.reranker = Reranker()
        self.llm = OpenAI(api_key=OPENAI_API_KEY)
        self.current_session_id: Optional[str] = None

    # ── public API ────────────────────────────────────────────────────
    def verify(self, raw_claim: str) -> VerificationResult:
        """End-to-end claim verification with agentic decision loop.

        Args:
            raw_claim: User's raw input text

        Returns:
            VerificationResult with verdict, evidence, and reasoning
        """
        # Generate new session ID for context isolation
        self.current_session_id = str(uuid.uuid4())
        steps: list[str] = []
        all_evidence: list[Evidence] = []

        # Step 1 — Classify and normalise claim
        steps.append("Step 1: Classifying and normalising claim…")
        claim_data = self._extract_and_classify_claim(raw_claim)

        # Handle non-factual claims
        if claim_data["type"] == "OPINION":
            return VerificationResult(
                claim=raw_claim,
                verdict="Not Verifiable",
                confidence=0.0,
                reasoning="This appears to be a subjective opinion or personal preference "
                          "(e.g., 'best', 'worst', 'most beautiful'). Opinions cannot be "
                          "fact-checked as they are not objectively verifiable.",
                evidence=[],
                steps=steps,
                session_id=self.current_session_id,
                claim_type="OPINION",
                original_claim=raw_claim,
            )

        if claim_data["type"] == "AMBIGUOUS":
            return VerificationResult(
                claim=raw_claim,
                verdict="Not Enough Evidence",
                confidence=0.0,
                reasoning="The claim is too ambiguous or unclear to verify. Please rephrase "
                          "with more specific, verifiable details.",
                evidence=[],
                steps=steps,
                session_id=self.current_session_id,
                claim_type="AMBIGUOUS",
                original_claim=raw_claim,
            )

        claim = claim_data["claim"]
        claim_type = claim_data["type"]
        steps.append(f"  → Type: {claim_type}")
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

            # Small delay between DDG searches to avoid rate-limiting
            time.sleep(2)

            # Step 3b — Fact-checker search
            steps.append("Step 4: Searching fact-checkers…")
            fc_ev = self._search_and_index(claim, search_fn=search_fact_checkers)
            all_evidence.extend(fc_ev)
            steps.append(f"  → Found {len(fc_ev)} fact-check evidence(s)")

            # Step 3c — Broad web if still thin (count only relevant evidence)
            relevant_so_far = [e for e in all_evidence if e.score > 0.0 or e.origin != "kb"]
            if len(relevant_so_far) < 2:
                time.sleep(2)
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
        result.session_id = self.current_session_id
        result.claim_type = claim_type
        result.original_claim = raw_claim
        return result

    # ── private helpers ───────────────────────────────────────────────
    def _extract_and_classify_claim(self, raw: str) -> dict:
        """Extract and classify claim type using LLM.

        Returns:
            dict with keys: type (FACTUAL/OPINION/MIXED/AMBIGUOUS), claim (extracted text)
        """
        system_prompt = """You are a claim classification expert. Your job is to:
1. Classify the claim as: FACTUAL, OPINION, MIXED, or AMBIGUOUS
2. Extract the core VERIFIABLE factual claim (if any)
3. Preserve ALL factual elements, even incorrect ones — do NOT correct them

CLASSIFICATION RULES:

FACTUAL: Contains objective, verifiable statements (even if false)
- "The Earth is flat" → FACTUAL, claim: "The Earth is flat"
- "COVID-19 vaccines are safe" → FACTUAL, claim: "COVID-19 vaccines are safe"
- "India is a company" → FACTUAL, claim: "India is a company" (factually wrong but verifiable)
- "Water boils at 50°C" → FACTUAL, claim: "Water boils at 50°C" (wrong but verifiable)

OPINION: Purely subjective preferences or value judgments with NO factual component
- "Minecraft is the best game" → OPINION (subjective, no factual part)
- "Pizza tastes better than burgers" → OPINION
- "Blue is the prettiest color" → OPINION

MIXED: Contains BOTH a verifiable factual part AND a subjective part
- "Minecraft is the best 2D game" → MIXED, claim: "Minecraft is a 2D game"
  (Extract factual: "Minecraft is a 2D game". Discard subjective: "best")
- "India is the biggest company" → MIXED, claim: "India is a company"
  (Extract factual: "India is a company". Discard subjective: "biggest")
- "The beautiful Earth is flat" → MIXED, claim: "The Earth is flat"
  (Extract factual: "The Earth is flat". Discard subjective: "beautiful")

AMBIGUOUS: Too vague, no clear claim, or needs clarification
- "It's true" → AMBIGUOUS
- "They said so" → AMBIGUOUS
- "Something happened" → AMBIGUOUS

IMPORTANT:
- Do NOT correct factual errors in the claim — extract them as-is for verification
- For MIXED, extract ONLY the factual/verifiable part
- For OPINION, return the original input as the claim
- For AMBIGUOUS, return the original input as the claim

Output ONLY valid JSON:
{
  "type": "FACTUAL" | "OPINION" | "MIXED" | "AMBIGUOUS",
  "claim": "extracted verifiable claim (preserve factual errors)",
  "reasoning": "brief explanation"
}"""

        user_msg = f"Input: {raw}"

        try:
            resp = self.llm.chat.completions.create(
                model=LLM_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=300,
                response_format={"type": "json_object"},
            )

            result = json.loads(resp.choices[0].message.content.strip())

            # Validate and normalize
            claim_type = result.get("type", "AMBIGUOUS").upper()
            if claim_type not in ["FACTUAL", "OPINION", "MIXED", "AMBIGUOUS"]:
                claim_type = "AMBIGUOUS"

            return {
                "type": claim_type,
                "claim": result.get("claim", raw).strip().strip('"'),
                "reasoning": result.get("reasoning", ""),
            }

        except Exception as e:
            logger.error(f"Claim classification failed: {e}")
            # Fallback: treat as factual and try to extract
            return {
                "type": "FACTUAL",
                "claim": raw.strip(),
                "reasoning": "Classification failed, treating as factual",
            }

    def _retrieve_kb(self, claim: str) -> list[Evidence]:
        """Retrieve from vector store and rerank.

        Only returns evidence that passes the relevance threshold.
        Only bumps access count on actually relevant results.
        """
        hits = self.vs.query(claim, top_k=TOP_K_RETRIEVAL)
        if not hits:
            return []
        # Rerank FIRST — filters out irrelevant results
        reranked = self.reranker.rerank(claim, hits, top_k=TOP_K_RERANK)
        if not reranked:
            return []
        # Only bump access counts for relevant results
        for h in reranked:
            self.vs.increment_access(h["id"])
        return [
            Evidence(text=h["text"], source=h["source"],
                     score=h.get("rerank_score", h.get("score", 0)), origin="kb")
            for h in reranked
        ]

    def _has_enough_evidence(self, claim: str, evidence: list[Evidence]) -> bool:
        """Check if KB evidence is sufficient — both quantity AND quality.

        Returns False if:
        - Fewer than 2 pieces of evidence
        - Average relevance score is too low
        - LLM says evidence is insufficient
        """
        # Need at least 2 pieces of evidence
        if len(evidence) < 2:
            return False

        # Check quality: average score must be positive and meaningful
        avg_score = sum(e.score for e in evidence) / len(evidence)
        if avg_score < 1.0:
            return False

        # LLM sufficiency check
        ctx = "\n".join(f"- {e.text} (relevance_score={e.score:.2f})" for e in evidence[:5])
        resp = self.llm.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": (
                    "You decide if the provided evidence is SUFFICIENT and RELEVANT "
                    "to verify the claim. The evidence must DIRECTLY address the claim. "
                    "Answer ONLY 'yes' or 'no'."
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
        """Rerank all evidence using multi-stage reranking with source credibility.

        Args:
            claim: The claim to verify
            evidence: List of evidence to rerank

        Returns:
            Top-K reranked evidence with credibility-adjusted scores
        """
        candidates = [{"text": e.text, "source": e.source, "origin": e.origin}
                      for e in evidence]
        # Use enhanced reranker with credibility scoring
        reranked = self.reranker.rerank_with_credibility(claim, candidates, top_k=TOP_K_RERANK)
        return [
            Evidence(text=r["text"], source=r["source"],
                     score=r.get("final_score", r.get("rerank_score", 0)),
                     origin=r.get("origin", "web"))
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
        """Use LLM to produce final verdict with citations.

        Filters out irrelevant evidence (negative scores) before sending to LLM.
        Always calls the LLM — even with no evidence, the LLM can verify
        mathematical, definitional, or widely-known factual claims.
        """
        # Filter out evidence with negative or very low relevance scores
        relevant_evidence = [e for e in evidence if e.score > 0.0]

        if relevant_evidence:
            evidence_block = ""
            for i, e in enumerate(relevant_evidence, 1):
                evidence_block += (
                    f"[{i}] (Source: {e.source}, Origin: {e.origin}, "
                    f"Relevance: {e.score:.2f})\n{e.text}\n\n"
                )

            system_prompt = f"""You are a rigorous fact-checking assistant. Analyse the claim against the provided evidence and produce a JSON response.

RULES:
- You MUST cite sources using [1], [2], etc. matching the evidence numbers.
- You MUST NOT fabricate any sources or evidence.
- ONLY use evidence that DIRECTLY addresses the specific claim. Ignore tangentially related evidence.
- If evidence is contradictory, explain both sides.
- If evidence is insufficient or does not directly address the claim, verdict MUST be "Not Enough Evidence".
- Do NOT draw conclusions from evidence that is about a different topic.
- Allowed verdicts: {', '.join(VERDICTS)}

IMPORTANT: Each piece of evidence has a relevance score. Higher scores mean the evidence is more relevant to the claim. Be skeptical of low-scoring evidence.

OUTPUT FORMAT (strict JSON):
{{
  "verdict": "<one of the allowed verdicts>",
  "confidence": <float 0-1>,
  "reasoning": "<detailed reasoning with [N] citations>"
}}"""

            user_msg = f"CLAIM: {claim}\n\nEVIDENCE:\n{evidence_block}"
        else:
            # No retrieved evidence — let the LLM use its own knowledge
            system_prompt = f"""You are a rigorous fact-checking assistant. No external evidence was found for this claim from the knowledge base or web searches.

RULES:
- If the claim is a mathematical fact, unit conversion, logical tautology, or widely-known definition that you can verify with certainty, provide a verdict based on your knowledge.
- For such verifiable-by-reasoning claims, clearly state that no external sources were found but the claim can be verified through direct reasoning.
- If the claim requires external evidence that you do not have (e.g., recent events, statistics, specific incidents), verdict MUST be "Not Enough Evidence".
- Do NOT fabricate sources or citations. Do NOT invent evidence.
- Allowed verdicts: {', '.join(VERDICTS)}

OUTPUT FORMAT (strict JSON):
{{
  "verdict": "<one of the allowed verdicts>",
  "confidence": <float 0-1>,
  "reasoning": "<explanation — state clearly if verified by reasoning alone vs. needing external evidence>"
}}"""

            user_msg = f"CLAIM: {claim}\n\nNO EXTERNAL EVIDENCE AVAILABLE."

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
            evidence=relevant_evidence,
        )
