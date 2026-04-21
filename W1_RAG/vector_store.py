"""ChromaDB vector store for evidence storage and retrieval with enhanced metadata."""
import hashlib
import time
from urllib.parse import urlparse
from typing import Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import (
    CHROMA_PERSIST_DIR, COLLECTION_NAME, EMBEDDING_MODEL,
    TOP_K_RETRIEVAL, SOURCE_CREDIBILITY,
    CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_MIN_LENGTH,
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
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
        )

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks; short texts pass through untouched."""
        if not text:
            return []
        if len(text) <= CHUNK_SIZE:
            return [text.strip()]
        chunks = self._splitter.split_text(text)
        return [c.strip() for c in chunks if len(c.strip()) >= CHUNK_MIN_LENGTH]

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def add_document(self, text: str, source: str, details: str = "",
                     timestamp: str = "", source_type: Optional[str] = None) -> list[str]:
        """Chunk text with RecursiveCharacterTextSplitter then index each chunk.

        Args:
            text: Evidence text (may be long; will be chunked if needed)
            source: Source URL or reference
            details: Additional details (title, description)
            timestamp: ISO timestamp (auto-generated if not provided)
            source_type: Type of source (news/academic/fact_checker/government)

        Returns:
            List of document IDs (one per chunk)
        """
        return self.add_documents_batch([{
            "text": text,
            "source": source,
            "details": details,
            "timestamp": timestamp,
            "source_type": source_type,
        }])

    def add_documents_batch(self, docs: list[dict]) -> list[str]:
        """Chunk each doc then batch-index all chunks with enhanced metadata.

        Each dict needs: text, source, and optionally: details, timestamp, source_type

        Returns:
            List of document IDs (one per chunk).
        """
        if not docs:
            return []

        ids: list[str] = []
        texts: list[str] = []
        metas: list[dict] = []

        for d in docs:
            raw_text = (d.get("text") or "").strip()
            if not raw_text:
                continue

            chunks = self._chunk_text(raw_text)
            if not chunks:
                continue

            ts = d.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            source = d.get("source", "")
            domain = self._extract_domain(source)
            credibility = SOURCE_CREDIBILITY.get(domain, 0.5)
            source_type = d.get("source_type") or self._infer_source_type(domain)
            # Deterministic ID so re-indexing the same (source, text) is a no-op
            fingerprint = hashlib.md5(
                f"{source}||{raw_text}".encode("utf-8", errors="ignore")
            ).hexdigest()[:16]
            parent_id = f"doc_{fingerprint}"
            total = len(chunks)

            for idx, chunk in enumerate(chunks):
                chunk_id = f"{parent_id}_c{idx}" if total > 1 else parent_id
                ids.append(chunk_id)
                texts.append(chunk)
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
                    "text_length": len(chunk),
                    "language": "en",
                    "parent_id": parent_id,
                    "chunk_index": idx,
                    "total_chunks": total,
                })

        if not ids:
            return []

        # Skip chunks already in the collection — preserves access_count
        # and keeps the KB from bloating on repeated queries.
        try:
            existing = set(self._collection.get(ids=ids).get("ids", []) or [])
        except Exception:
            existing = set()

        new_items = [(i, t, m) for i, t, m in zip(ids, texts, metas)
                     if i not in existing]
        if not new_items:
            return ids

        new_ids, new_texts, new_metas = map(list, zip(*new_items))
        embeddings = self._embedder.encode(new_texts, batch_size=32).tolist()
        self._collection.add(
            ids=new_ids,
            embeddings=embeddings,
            documents=new_texts,
            metadatas=new_metas,
        )
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

    def update_relevance_stats(self, doc_id: str, relevance_score: float):
        """Bump verification_count and update running average of relevance."""
        try:
            result = self._collection.get(ids=[doc_id], include=["metadatas"])
            if not result["metadatas"]:
                return
            meta = result["metadatas"][0]
            n = meta.get("verification_count", 0)
            avg = meta.get("avg_relevance", 0.0)
            meta["verification_count"] = n + 1
            meta["avg_relevance"] = round((avg * n + float(relevance_score)) / (n + 1), 4)
            meta["last_accessed"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
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
