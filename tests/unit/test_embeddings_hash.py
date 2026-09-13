from claimguard.retrieval.embeddings import HashEmbedder


def test_hash_embedder_unit_vectors() -> None:
    embedder = HashEmbedder(dim=768)
    docs = embedder.encode_documents(["collision deductible", "collision deductible"])
    assert docs.shape == (2, 768)
    assert abs(float((docs[0] ** 2).sum() ** 0.5) - 1.0) < 1e-5
    assert (docs[0] == docs[1]).all()
    other = embedder.encode_documents(["flood exclusion"])[0]
    assert not (other == docs[0]).all()
