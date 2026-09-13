"""Cross-encoder reranking over the fused candidate set."""


def rerank(query: str, candidates: list[object], top_n: int = 5) -> list[object]:
    raise NotImplementedError("Reranking is implemented in Phase 2")
