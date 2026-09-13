"""Rerank fused candidates.

Default is identity (keep RRF order). A cross-encoder can implement `Reranker`
without touching fraud/policy agents. Deferred because a local cross-encoder
adds a large HF download to the worker image.
"""

from __future__ import annotations

from collections.abc import Callable

from claimguard.retrieval.query import Hit

Reranker = Callable[[str, list[Hit], int], list[Hit]]


def identity_rerank(query: str, candidates: list[Hit], top_n: int = 5) -> list[Hit]:
    _ = query
    return candidates[:top_n]


def rerank(query: str, candidates: list[object], top_n: int = 5) -> list[object]:
    hits = [item for item in candidates if isinstance(item, Hit)]
    return identity_rerank(query, hits, top_n)
