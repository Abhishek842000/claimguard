from claimguard.retrieval.hybrid_retriever import InMemoryRetriever, RetrievedChunk
from claimguard.schemas.common import RetrievalSource


def test_in_memory_retriever_ranks_keyword_overlap() -> None:
    retriever = InMemoryRetriever(
        [
            RetrievedChunk(
                chunk_id="fraud-04-duplicate-vin:0",
                title="duplicate VIN",
                text="same VIN appearing on two unrelated claims",
                score=0.2,
                source=RetrievalSource.BM25,
            ),
            RetrievedChunk(
                chunk_id="fraud-05-weather-mismatch:0",
                title="weather mismatch",
                text="hail claim with no storm event at the loss location",
                score=0.2,
                source=RetrievalSource.BM25,
            ),
        ]
    )
    hits = retriever.search("hail claim with no NOAA storm event", k=2)
    assert hits[0].chunk_id.startswith("fraud-05")
