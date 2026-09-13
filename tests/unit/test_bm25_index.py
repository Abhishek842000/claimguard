from pathlib import Path

from claimguard.retrieval.bm25_index import BM25Index, load_index, save_index


def test_bm25_ranks_lexical_overlap(tmp_path: Path) -> None:
    index = BM25Index(
        doc_ids=["hail", "flood", "collision"],
        texts=[
            "Other than collision covers hail and windstorm to the covered auto.",
            "Flood and surface water are excluded under Section I.",
            "Collision pays for impact with another vehicle minus the deductible.",
        ],
    )
    top_id, _score, _text = index.query("Is hail a comprehensive loss?", k=1)[0]
    assert top_id == "hail"
    path = tmp_path / "bm25.pkl"
    save_index(index, path)
    reloaded = load_index(path)
    ranked = reloaded.query("excluded surface water Section I", k=2)
    assert ranked[0][0] == "flood"
    assert ranked[0][1] > ranked[1][1]
