"""Cross-encoder reranker for precision retrieval with source credibility."""
from __future__ import annotations
from urllib.parse import urlparse
from sentence_transformers import CrossEncoder
from config import (
    RERANKER_MODEL, TOP_K_RERANK, MIN_RELEVANCE_SCORE,
    SOURCE_CREDIBILITY, CREDIBILITY_BOOST_FACTOR
)


class Reranker:
    """Reranks candidate documents using a cross-encoder model."""

    def __init__(self):
        self._model = CrossEncoder(RERANKER_MODEL, max_length=512)

    def rerank(self, claim: str, candidates: list[dict],
               top_k: int = TOP_K_RERANK) -> list[dict]:
        """Rerank candidates by cross-encoder relevance to the claim.

        Each candidate dict must have a 'text' key.
        Returns top_k candidates sorted by reranker score, with
        'rerank_score' added to each dict.
        Returns EMPTY list if no candidate meets the minimum relevance threshold.
        """
        if not candidates:
            return []
        pairs = [(claim, c["text"]) for c in candidates]
        scores = self._model.predict(pairs)
        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)
        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        # Filter by minimum relevance — return nothing if all irrelevant
        filtered = [c for c in ranked if c["rerank_score"] >= MIN_RELEVANCE_SCORE]
        return filtered[:top_k]

    def rerank_with_credibility(self, claim: str, candidates: list[dict],
                                 top_k: int = TOP_K_RERANK) -> list[dict]:
        """Multi-stage reranking with source credibility scoring.

        Pipeline:
        1. Cross-encoder scoring (relevance)
        2. Source credibility lookup
        3. Combined scoring: relevance + credibility boost
        4. Sort by final score

        Args:
            claim: The claim to verify
            candidates: List of dicts with 'text', 'source', 'origin' keys
            top_k: Number of results to return

        Returns:
            Top-K candidates with 'rerank_score', 'credibility_score', 'final_score'
        """
        if not candidates:
            return []

        # Stage 1: Cross-encoder relevance scoring
        pairs = [(claim, c["text"]) for c in candidates]
        relevance_scores = self._model.predict(pairs)

        # Stage 2: Source credibility scoring
        for i, candidate in enumerate(candidates):
            relevance = float(relevance_scores[i])
            candidate["rerank_score"] = relevance

            # Extract domain from source URL
            source_url = candidate.get("source", "")
            domain = self._extract_domain(source_url)

            # Lookup credibility score
            credibility = SOURCE_CREDIBILITY.get(domain, 0.5)  # Default: 0.5 (neutral)
            candidate["credibility_score"] = credibility
            candidate["domain"] = domain

            # Stage 3: Combined scoring
            # Formula: final_score = relevance + (credibility * boost_factor)
            credibility_boost = (credibility - 0.5) * CREDIBILITY_BOOST_FACTOR
            final_score = relevance + credibility_boost
            candidate["final_score"] = final_score

        # Stage 4: Sort by final score
        ranked = sorted(candidates, key=lambda x: x["final_score"], reverse=True)

        # Filter by minimum relevance — return nothing if all irrelevant
        filtered = [c for c in ranked if c["rerank_score"] >= MIN_RELEVANCE_SCORE]
        if not filtered:
            return []

        # Enforce source diversity (max 2 from same domain)
        diverse_results = self._enforce_diversity(filtered, max_per_domain=2)

        return diverse_results[:top_k]

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _enforce_diversity(self, candidates: list[dict], max_per_domain: int = 2) -> list[dict]:
        """Ensure source diversity by limiting results from same domain.

        Args:
            candidates: Sorted list of candidates
            max_per_domain: Maximum results from same domain

        Returns:
            Filtered list with enforced diversity
        """
        domain_counts: dict[str, int] = {}
        diverse_results = []

        for candidate in candidates:
            domain = candidate.get("domain", "")
            count = domain_counts.get(domain, 0)

            if count < max_per_domain:
                diverse_results.append(candidate)
                domain_counts[domain] = count + 1

        return diverse_results
