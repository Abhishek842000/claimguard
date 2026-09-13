"""Embedding backend. Production: BAAI/bge-base-en-v1.5 via FastEmbed (ONNX).

FastEmbed ships the same HF weights without a multi-GB PyTorch install, which
matters for a one-off ingest on a laptop. Tests use HashEmbedder.
"""

from __future__ import annotations

import hashlib
import os
from typing import Protocol

import numpy as np

from claimguard.config import get_settings

DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    dim: int
    model_id: str

    def encode_documents(self, texts: list[str]) -> np.ndarray: ...

    def encode_queries(self, texts: list[str]) -> np.ndarray: ...


class HashEmbedder:
    """Deterministic unit vectors. For tests only — not for retrieval quality."""

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim
        self.model_id = "hash/sha256"

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts])

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self.encode_documents(texts)

    def _vec(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = np.frombuffer((digest * ((self.dim // 32) + 1))[: self.dim], dtype=np.uint8)
        vec = raw.astype(np.float32) - 127.5
        norm = np.linalg.norm(vec) or 1.0
        return vec / norm


class FastEmbedEmbedder:
    def __init__(self, model_id: str = DEFAULT_MODEL) -> None:
        from fastembed import TextEmbedding

        self.model_id = model_id
        self._model = TextEmbedding(model_name=model_id)
        self.dim = get_settings().embedding_dim

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        vectors = list(self._model.embed(texts))
        return np.vstack([np.asarray(v, dtype=np.float32) for v in vectors])

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        prefixed = [QUERY_PREFIX + t for t in texts]
        return self.encode_documents(prefixed)


def get_embedder(kind: str | None = None) -> Embedder:
    resolved = kind or os.environ.get("CLAIMGUARD_EMBEDDER") or "fastembed"
    if resolved == "hash":
        return HashEmbedder(dim=get_settings().embedding_dim)
    return FastEmbedEmbedder(model_id=get_settings().embedding_model)
