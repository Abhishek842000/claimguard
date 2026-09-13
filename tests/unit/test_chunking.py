from claimguard.retrieval.chunking import chunk_markdown, parse_front_matter


def test_parse_front_matter() -> None:
    meta, body = parse_front_matter("---\ndocument_id: x\ntitle: Hello\n---\n# Body\n")
    assert meta["document_id"] == "x"
    assert body.startswith("# Body")


def test_chunk_respects_headings_and_overlap() -> None:
    paragraphs = "\n\n".join(f"Token{i} " * 40 for i in range(20))
    text = f"---\ndocument_id: doc\ntitle: T\n---\n\n## Section A\n\n{paragraphs}\n"
    chunks = chunk_markdown(text, document_id="doc", document_title="T")
    assert len(chunks) >= 2
    assert all(c.document_id == "doc" for c in chunks)
    assert chunks[0].section == "Section A"
    assert 200 <= chunks[0].token_count <= 600
