#!/usr/bin/env python3
"""Eyeball a raw similarity search against the ingested corpora."""

from __future__ import annotations

import argparse
import json

from claimguard.retrieval.query import bm25_search, dense_search


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", choices=("policy", "fraud"), required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--mode", choices=("dense", "bm25", "both"), default="both")
    parser.add_argument("--embedder", default=None)
    args = parser.parse_args(argv)

    from claimguard.retrieval.embeddings import get_embedder

    embedder = get_embedder(args.embedder) if args.mode in {"dense", "both"} else None
    payload: dict[str, object] = {"corpus": args.corpus, "query": args.query}
    if args.mode in {"dense", "both"}:
        payload["dense"] = [hit.__dict__ for hit in dense_search(args.corpus, args.query, args.k, embedder)]
    if args.mode in {"bm25", "both"}:
        payload["bm25"] = [hit.__dict__ for hit in bm25_search(args.corpus, args.query, args.k)]
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
