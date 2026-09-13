# Retrieval

Hybrid RAG is wired in a later phase. Phase 1 only **loads** the two corpora.

## Dense

`BAAI/bge-base-en-v1.5` (768-d) via FastEmbed / ONNX. Queries are prefixed
with the official BGE instruction. Documents are embedded raw.

## Sparse (BM25)

`rank_bm25.BM25Okapi` pickled under `data/indexes/`.

**Why not Postgres FTS?** At a few hundred chunks, in-process BM25 gives
textbook scores we can fuse with dense ranks (RRF) without inventing a
`ts_rank` mapping. Postgres `tsvector` would be the right persistence model
once the corpus is large enough that loading pickle on every worker is
wasteful.

## Ingest

```bash
uv run alembic upgrade head
uv run python scripts/ingest_corpora.py
uv run python scripts/query_corpora.py --corpus policy --query "Is hail covered under other than collision?"
```
