"""Load policy + fraud corpora into pgvector and rebuild BM25 indexes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete

from claimguard.db.models import FraudCaseChunk, PolicyChunk
from claimguard.db.session import session_scope
from claimguard.retrieval.bm25_index import INDEX_DIR, BM25Index, save_index
from claimguard.retrieval.chunking import Chunk, chunk_file
from claimguard.retrieval.embeddings import Embedder, get_embedder

ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "data" / "policy_docs"
FRAUD_DIR = ROOT / "data" / "fraud_corpus"


def ingest_corpora(
    *,
    embedder: Embedder | None = None,
    policy_dir: Path = POLICY_DIR,
    fraud_dir: Path = FRAUD_DIR,
) -> dict[str, int]:
    backend = embedder or get_embedder()
    policy_chunks = _load_markdown_chunks(policy_dir)
    fraud_chunks = _load_markdown_chunks(fraud_dir)
    _replace_table(PolicyChunk, policy_chunks, backend, kind="policy")
    _replace_table(FraudCaseChunk, fraud_chunks, backend, kind="fraud")
    save_index(
        BM25Index(
            doc_ids=[c.document_id + f":{c.chunk_index}" for c in policy_chunks],
            texts=[c.content for c in policy_chunks],
        ),
        INDEX_DIR / "policy_bm25.pkl",
    )
    save_index(
        BM25Index(
            doc_ids=[c.document_id + f":{c.chunk_index}" for c in fraud_chunks],
            texts=[c.content for c in fraud_chunks],
        ),
        INDEX_DIR / "fraud_bm25.pkl",
    )
    return {"policy_chunks": len(policy_chunks), "fraud_chunks": len(fraud_chunks)}


def _load_markdown_chunks(directory: Path) -> list[Chunk]:
    files = sorted(
        p
        for p in directory.glob("*.md")
        if p.name.lower() != "readme.md"
    )
    chunks: list[Chunk] = []
    for path in files:
        chunks.extend(chunk_file(path))
    return chunks


def _replace_table(
    model: type[PolicyChunk] | type[FraudCaseChunk],
    chunks: list[Chunk],
    embedder: Embedder,
    *,
    kind: str,
) -> None:
    vectors = embedder.encode_documents([c.content for c in chunks])
    with session_scope() as session:
        session.execute(delete(model))
        for chunk, vector in zip(chunks, vectors, strict=True):
            session.add(_to_row(model, chunk, vector.tolist(), kind=kind))


def _to_row(
    model: type[Any],
    chunk: Chunk,
    embedding: list[float],
    *,
    kind: str,
) -> Any:
    if kind == "policy":
        return PolicyChunk(
            id=uuid4(),
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_hash=chunk.content_hash,
            section=chunk.section,
            page=None,
            extra=chunk.extra,
            embedding=embedding,
        )
    return FraudCaseChunk(
        id=uuid4(),
        case_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        content_hash=chunk.content_hash,
        citation=chunk.extra.get("citation"),
        extra=chunk.extra,
        embedding=embedding,
    )
