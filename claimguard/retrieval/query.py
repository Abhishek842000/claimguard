"""Raw similarity search used by scripts/query_corpora.py."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from claimguard.db.session import session_scope
from claimguard.retrieval.bm25_index import INDEX_DIR, load_index
from claimguard.retrieval.embeddings import Embedder, get_embedder


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    title: str
    preview: str
    source: str


def dense_search(corpus: str, query: str, k: int = 5, embedder: Embedder | None = None) -> list[Hit]:
    backend = embedder or get_embedder()
    vector = backend.encode_queries([query])[0].tolist()
    table = "policy_chunks" if corpus == "policy" else "fraud_case_chunks"
    title_col = "document_title" if corpus == "policy" else "citation"
    id_col = "document_id" if corpus == "policy" else "case_id"
    sql = text(
        f"""
        SELECT {id_col} AS doc_id,
               COALESCE({title_col}, {id_col}) AS title,
               left(content, 280) AS preview,
               1 - (embedding <=> CAST(:vec AS vector)) AS score
        FROM {table}
        ORDER BY embedding <=> CAST(:vec AS vector)
        LIMIT :k
        """
    )
    vec_literal = "[" + ",".join(f"{x:.8f}" for x in vector) + "]"
    with session_scope() as session:
        rows = session.execute(sql, {"vec": vec_literal, "k": k}).mappings().all()
    return [
        Hit(
            id=str(row["doc_id"]),
            score=float(row["score"]),
            title=str(row["title"] or row["doc_id"]),
            preview=str(row["preview"]),
            source="dense",
        )
        for row in rows
    ]


def bm25_search(corpus: str, query: str, k: int = 5) -> list[Hit]:
    path = INDEX_DIR / ("policy_bm25.pkl" if corpus == "policy" else "fraud_bm25.pkl")
    index = load_index(path)
    return [
        Hit(id=doc_id, score=score, title=doc_id, preview=text[:280], source="bm25")
        for doc_id, score, text in index.query(query, k=k)
    ]
