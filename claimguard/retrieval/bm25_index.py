"""In-memory BM25 persisted next to the corpora.

Tradeoff vs Postgres full-text search
------------------------------------
rank_bm25 (this module)
  + Classic BM25 scores, easy to fuse with dense ranks in Python
  + Zero extra schema; fine for a few hundred chunks
  - Must rebuild on ingest; not queryable from SQL or another language

Postgres `tsvector` / `ts_rank_cd`
  + Persistent, concurrent, no pickle
  - Ranking is not BM25; harder to match the paper-style hybrid RAG story

At this corpus size we keep BM25 in-process and can add a stored tsvector
later if the chunk count grows past a few thousand.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path

from rank_bm25 import BM25Okapi

INDEX_DIR = Path(__file__).resolve().parents[2] / "data" / "indexes"


@dataclass
class BM25Index:
    doc_ids: list[str]
    texts: list[str]
    tokenized: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.tokenized:
            self.tokenized = [_tokenize(t) for t in self.texts]
        self._bm25 = BM25Okapi(self.tokenized)

    def query(self, text: str, k: int = 5) -> list[tuple[str, float, str]]:
        scores = self._bm25.get_scores(_tokenize(text))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.doc_ids[i], float(scores[i]), self.texts[i]) for i in order]


def _tokenize(text: str) -> list[str]:
    return [part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if part]


def save_index(index: BM25Index, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps({"doc_ids": index.doc_ids, "texts": index.texts}))


def load_index(path: Path) -> BM25Index:
    payload = pickle.loads(path.read_bytes())
    return BM25Index(doc_ids=payload["doc_ids"], texts=payload["texts"])
