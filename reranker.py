"""Cross-encoder reranker for precision retrieval."""
from __future__ import annotations
from sentence_transformers import CrossEncoder
from config import RERANKER_MODEL, TOP_K_RERANK, MIN_RELEVANCE_SCORE


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
        """
        if not candidates:
            return []
        pairs = [(claim, c["text"]) for c in candidates]
        scores = self._model.predict(pairs)
        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)
        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        # Filter by minimum relevance
        filtered = [c for c in ranked if c["rerank_score"] >= MIN_RELEVANCE_SCORE]
        if not filtered:
            # If nothing passes threshold, return top results anyway with flag
            for c in ranked[:top_k]:
                c["low_confidence"] = True
            return ranked[:top_k]
        return filtered[:top_k]
