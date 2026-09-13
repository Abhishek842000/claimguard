"""BM25 + dense retrieval fused with reciprocal rank fusion."""


def retrieve(query: str, corpus: str, k: int = 20) -> list[object]:
    raise NotImplementedError("Hybrid retrieval is implemented in Phase 2")
