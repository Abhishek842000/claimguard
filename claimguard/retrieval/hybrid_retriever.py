"""BM25 + dense retrieval fused with reciprocal rank fusion.

Tradeoff: we fuse ranks in Python (classic RRF, k=60) instead of a
cross-encoder reranker. RRF needs no GPU and is deterministic in tests.
A BGE reranker can implement `Reranker` later without changing agents.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass

from claimguard.retrieval.query import Hit, bm25_search, dense_search
from claimguard.retrieval.reranker import Reranker, identity_rerank
from claimguard.schemas.common import RetrievalSource


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    title: str
    text: str
    score: float
    source: RetrievalSource


class Retriever:
    def search(self, query: str, *, k: int = 5) -> list[RetrievedChunk]:
        raise NotImplementedError


class HybridRetriever(Retriever):
    def __init__(
        self,
        corpus: str,
        *,
        reranker: Reranker | None = None,
        use_dense: bool = True,
    ) -> None:
        if corpus not in {"policy", "fraud"}:
            raise ValueError(f"unknown corpus {corpus}")
        self.corpus = corpus
        self.reranker = reranker
        self.use_dense = use_dense

    def search(self, query: str, *, k: int = 5) -> list[RetrievedChunk]:
        lists: list[list[Hit]] = []
        try:
            lists.append(bm25_search(self.corpus, query, k=max(k, 8)))
        except Exception:
            lists.append([])
        if self.use_dense:
            with suppress(Exception):
                lists.append(dense_search(self.corpus, query, k=max(k, 8)))
        fused = _rrf(lists)
        ranked = identity_rerank(query, fused, top_n=k) if self.reranker is None else self.reranker(
            query, fused, top_n=k
        )
        return [
            RetrievedChunk(
                chunk_id=hit.id,
                title=hit.title,
                text=hit.preview,
                score=hit.score,
                source=RetrievalSource.RRF if len(lists) > 1 else RetrievalSource(hit.source),
            )
            for hit in ranked[:k]
        ]


class InMemoryRetriever(Retriever):
    """Test double: keyword overlap over a fixed chunk list."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks

    def search(self, query: str, *, k: int = 5) -> list[RetrievedChunk]:
        tokens = {part.lower() for part in query.split() if len(part) > 2}
        scored: list[tuple[float, RetrievedChunk]] = []
        for chunk in self.chunks:
            hay = f"{chunk.title} {chunk.text}".lower()
            score = sum(1.0 for token in tokens if token in hay)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:k] if score > 0] or self.chunks[:k]


def _rrf(rank_lists: list[list[Hit]], k: int = 60) -> list[Hit]:
    scores: dict[str, float] = defaultdict(float)
    payload: dict[str, Hit] = {}
    for hits in rank_lists:
        for rank, hit in enumerate(hits, start=1):
            scores[hit.id] += 1.0 / (k + rank)
            payload[hit.id] = hit
    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [
        Hit(
            id=doc_id,
            score=scores[doc_id],
            title=payload[doc_id].title,
            preview=payload[doc_id].preview,
            source="rrf",
        )
        for doc_id in ordered
    ]
