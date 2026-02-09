"""ChromaDB vector store for evidence storage and retrieval."""
import time
import chromadb
from sentence_transformers import SentenceTransformer
from config import (
    CHROMA_PERSIST_DIR, COLLECTION_NAME, EMBEDDING_MODEL,
    TOP_K_RETRIEVAL, EMBEDDING_DIM
)


class VectorStore:
    """Manages ChromaDB collection for news evidence with access-count boosting."""

    def __init__(self):
        self._embedder = SentenceTransformer(EMBEDDING_MODEL)
        self._client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def add_document(self, text: str, source: str, details: str = "",
                     timestamp: str = "") -> str:
        """Index a document with metadata. Returns the generated doc id."""
        ts = timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        doc_id = f"doc_{int(time.time()*1000)}_{hash(text) % 100000}"
        embedding = self._embedder.encode(text).tolist()
        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "source": source,
                "details": details,
                "timestamp": ts,
                "access_count": 0,
            }],
        )
        return doc_id

    def add_documents_batch(self, docs: list[dict]) -> list[str]:
        """Batch-index documents. Each dict needs: text, source, details."""
        if not docs:
            return []
        ids, embeddings, texts, metas = [], [], [], []
        for d in docs:
            ts = d.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            doc_id = f"doc_{int(time.time()*1000)}_{hash(d['text']) % 100000}"
            ids.append(doc_id)
            texts.append(d["text"])
            embeddings.append(self._embedder.encode(d["text"]).tolist())
            metas.append({
                "source": d.get("source", ""),
                "details": d.get("details", ""),
                "timestamp": ts,
                "access_count": 0,
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
