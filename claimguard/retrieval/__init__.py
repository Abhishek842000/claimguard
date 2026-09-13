"""Hybrid retrieval: BM25 + pgvector + RRF. Cross-encoder rerank is swappable."""

from claimguard.retrieval.hybrid_retriever import (
    HybridRetriever,
    InMemoryRetriever,
    RetrievedChunk,
    Retriever,
)

__all__ = [
    "HybridRetriever",
    "InMemoryRetriever",
    "RetrievedChunk",
    "Retriever",
]
