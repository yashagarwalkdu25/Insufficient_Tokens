"""Configuration constants for the Claim Verification system."""
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.1

# Embedding
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Reranker (cross-encoder)
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# ChromaDB
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "news_evidence"

# Retrieval
TOP_K_RETRIEVAL = 20
TOP_K_RERANK = 5
MIN_RELEVANCE_SCORE = 0.3

# Web search
MAX_SEARCH_RESULTS = 8
TRUSTED_DOMAINS = [
    "reuters.com", "bbc.com", "apnews.com", "nytimes.com",
    "theguardian.com", "washingtonpost.com", "snopes.com",
    "factcheck.org", "politifact.com", "aljazeera.com",
    "npr.org", "pbs.org", "who.int", "cdc.gov", "nasa.gov",
]

# Verdicts
VERDICTS = ["True", "False", "Partially True", "Misleading", "Not Enough Evidence"]
