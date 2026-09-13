#!/usr/bin/env python3
"""Chunk, embed, and load policy + fraud corpora into pgvector + BM25."""

from __future__ import annotations

import argparse
import json

from claimguard.retrieval.embeddings import get_embedder
from claimguard.retrieval.ingestion import ingest_corpora


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--embedder",
        default=None,
        help="fastembed (default) or hash (tests / offline)",
    )
    args = parser.parse_args(argv)
    counts = ingest_corpora(embedder=get_embedder(args.embedder))
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
