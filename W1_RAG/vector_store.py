"""ChromaDB vector store for evidence storage and retrieval with enhanced metadata."""
import time
from urllib.parse import urlparse
from typing import Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from config import (
    CHROMA_PERSIST_DIR, COLLECTION_NAME, EMBEDDING_MODEL,
    TOP_K_RETRIEVAL, SOURCE_CREDIBILITY
)


class VectorStore:
    """Manages ChromaDB collection for news evidence with access-count boosting."""

    def __init__(self):
        self._embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        self._client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def add_document(self, text: str, source: str, details: str = "",
                     timestamp: str = "", source_type: Optional[str] = None) -> str:
        """Index a document with enhanced metadata. Returns the generated doc id.

        Args:
            text: Evidence text
            source: Source URL or reference
            details: Additional details (title, description)
            timestamp: ISO timestamp (auto-generated if not provided)
            source_type: Type of source (news/academic/fact_checker/government)

        Returns:
            Document ID
        """
        ts = timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        doc_id = f"doc_{int(time.time()*1000)}_{hash(text) % 100000}"
        embedding = self._embedder.encode(text).tolist()

        # Extract domain and determine source type/credibility
        domain = self._extract_domain(source)
        credibility = SOURCE_CREDIBILITY.get(domain, 0.5)

        if not source_type:
            source_type = self._infer_source_type(domain)

        metadata = {
            "source": source,
            "source_type": source_type,
            "source_credibility": credibility,
            "details": details,
            "timestamp": ts,
            "access_count": 0,
            "verification_count": 0,
            "avg_relevance": 0.0,
            "last_accessed": ts,
            "domain": domain,
            "text_length": len(text),
            "language": "en",  # Default to English, can be enhanced with language detection
        }

        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
        )
        return doc_id

    def add_documents_batch(self, docs: list[dict]) -> list[str]:
        """Batch-index documents with enhanced metadata.

        Each dict needs: text, source, and optionally: details, timestamp, source_type

        Args:
            docs: List of document dicts

        Returns:
            List of document IDs
        """
        if not docs:
            return []
        ids, embeddings, texts, metas = [], [], [], []
        for d in docs:
            ts = d.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            doc_id = f"doc_{int(time.time()*1000)}_{hash(d['text']) % 100000}"

            # Extract domain and determine metadata
            source = d.get("source", "")
            domain = self._extract_domain(source)
            credibility = SOURCE_CREDIBILITY.get(domain, 0.5)
            source_type = d.get("source_type") or self._infer_source_type(domain)

            ids.append(doc_id)
            texts.append(d["text"])
            embeddings.append(self._embedder.encode(d["text"]).tolist())
            metas.append({
                "source": source,
                "source_type": source_type,
                "source_credibility": credibility,
                "details": d.get("details", ""),
                "timestamp": ts,
                "access_count": 0,
                "verification_count": 0,
                "avg_relevance": 0.0,
                "last_accessed": ts,
                "domain": domain,
                "text_length": len(d["text"]),
                "language": "en",
            })
        self._collection.add(ids=ids, embeddings=embeddings,
                             documents=texts, metadatas=metas)
        return ids

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def query(self, claim: str, top_k: int = TOP_K_RETRIEVAL) -> list[dict]:
        """Semantic search. Returns list of {text, source, details, timestamp,
        access_count, score, id}."""
        embedding = self._embedder.encode(claim).tolist()
        count = self._collection.count()
        if count == 0:
            return []
        k = min(top_k, count)
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            cosine_dist = results["distances"][0][i]
            sim_score = 1 - cosine_dist  # cosine similarity
            # Boost by access_count (popular docs rank higher)
            boosted = sim_score + meta.get("access_count", 0) * 0.02
            hits.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "source": meta.get("source", ""),
                "details": meta.get("details", ""),
                "timestamp": meta.get("timestamp", ""),
                "access_count": meta.get("access_count", 0),
                "score": round(boosted, 4),
            })
        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits

    def increment_access(self, doc_id: str):
        """Bump access_count for a retrieved document."""
        try:
            result = self._collection.get(ids=[doc_id], include=["metadatas"])
            if result["metadatas"]:
                meta = result["metadatas"][0]
                meta["access_count"] = meta.get("access_count", 0) + 1
                self._collection.update(ids=[doc_id], metadatas=[meta])
        except Exception:
            pass

    def count(self) -> int:
        return self._collection.count()

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL.

        Args:
            url: Full URL or partial URL

        Returns:
            Domain string (e.g., 'reuters.com')
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _infer_source_type(self, domain: str) -> str:
        """Infer source type from domain.

        Args:
            domain: Domain string

        Returns:
            Source type: news/academic/fact_checker/government/unknown
        """
        # Fact-checkers
        fact_checkers = ["snopes.com", "factcheck.org", "politifact.com", "fullfact.org"]
        if domain in fact_checkers:
            return "fact_checker"

        # Government/Scientific
        if domain.endswith(".gov") or domain.endswith(".gov.uk"):
            return "government"

        gov_scientific = ["who.int", "cdc.gov", "nasa.gov", "nih.gov"]
        if domain in gov_scientific:
            return "government"

        # Academic
        academic = ["scholar.google.com", "arxiv.org", "nature.com", "science.org"]
        if domain in academic or ".edu" in domain:
            return "academic"

        # News (if in SOURCE_CREDIBILITY with decent score)
        if domain in SOURCE_CREDIBILITY and SOURCE_CREDIBILITY[domain] >= 0.7:
            return "news"

        return "unknown"
