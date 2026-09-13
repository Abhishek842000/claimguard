"""Model router: cheap vs frontier. Agents never import a vendor SDK."""

from __future__ import annotations

from typing import Literal

import httpx

from claimguard.config import Settings, get_settings

ModelTier = Literal["cheap", "frontier"]


class LLMClient:
    """Thin OpenAI-compatible chat wrapper. Injected as a Completer."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def complete(self, prompt: str, *, tier: ModelTier = "cheap") -> str:
        return self._chat(
            [{"role": "user", "content": prompt}],
            tier=tier,
        )

    def as_completer(self, *, tier: ModelTier = "cheap"):
        client = self

        class _Completer:
            def complete(self, messages: list[dict[str, str]], *, schema_name: str) -> str:
                return client._chat(messages, tier=tier)

        return _Completer()

    def _chat(self, messages: list[dict[str, str]], *, tier: ModelTier) -> str:
        key = self.settings.openai_api_key
        if key is None or not key.get_secret_value():
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Inject a Completer in tests, or set the key."
            )
        model = self.settings.cheap_model if tier == "cheap" else self.settings.frontier_model
        model = model.removeprefix("openai/")
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
