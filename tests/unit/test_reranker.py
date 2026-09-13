from claimguard.retrieval.query import Hit
from claimguard.retrieval.reranker import identity_rerank


def test_identity_reranker_keeps_rrf_order_and_truncates() -> None:
    candidates = [
        Hit(id="a", score=0.9, title="first", preview="one", source="rrf"),
        Hit(id="b", score=0.5, title="second", preview="two", source="rrf"),
        Hit(id="c", score=0.1, title="third", preview="three", source="rrf"),
    ]
    ranked = identity_rerank("hail coverage", candidates, top_n=2)
    assert [hit.id for hit in ranked] == ["a", "b"]
