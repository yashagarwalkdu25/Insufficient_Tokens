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

# Source Credibility Scores (0.0 to 1.0)
SOURCE_CREDIBILITY = {
    # Fact-checkers (highest credibility)
    "snopes.com": 0.95,
    "factcheck.org": 0.95,
    "politifact.com": 0.95,
    "fullfact.org": 0.90,

    # News agencies (high credibility)
    "reuters.com": 0.90,
    "apnews.com": 0.90,
    "bbc.com": 0.85,
    "npr.org": 0.85,
    "pbs.org": 0.85,

    # Major newspapers (high credibility)
    "nytimes.com": 0.80,
    "washingtonpost.com": 0.80,
    "theguardian.com": 0.80,
    "wsj.com": 0.80,

    # Government/Scientific (very high credibility)
    "who.int": 0.95,
    "cdc.gov": 0.95,
    "nasa.gov": 0.95,
    "nih.gov": 0.95,
    "gov.uk": 0.90,

    # Academic (high credibility)
    "scholar.google.com": 0.85,
    "arxiv.org": 0.80,
    "nature.com": 0.90,
    "science.org": 0.90,

    # International news (good credibility)
    "aljazeera.com": 0.75,
    "dw.com": 0.75,
    "france24.com": 0.75,
}

# Credibility boost factors for reranking
CREDIBILITY_BOOST_FACTOR = 0.3  # Max boost for highest credibility sources

# Claim type classification
CLAIM_TYPES = {
    "FACTUAL": "Contains verifiable factual statements",
    "OPINION": "Subjective opinion or personal preference",
    "MIXED": "Contains both factual and subjective elements",
    "AMBIGUOUS": "Unclear or needs clarification",
}

# Temporal relevance decay (days)
TEMPORAL_DECAY_DAYS = 365  # Evidence older than 1 year gets reduced weight
