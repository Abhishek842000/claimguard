"""Model router: cheap vs frontier. Implemented in Phase 1."""

from __future__ import annotations

from typing import Literal

ModelTier = Literal["cheap", "frontier"]


class LLMClient:
    """Thin wrapper so agents never import a vendor SDK directly."""

    def complete(self, prompt: str, *, tier: ModelTier = "cheap") -> str:
        raise NotImplementedError("LLM client is implemented in Phase 1")
