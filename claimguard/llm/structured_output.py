"""Instructor-style structured generation: validate → repair → exhaust.

This is the production boundary every agent uses. A vendor SDK is *not*
imported here. Tests inject a `Completer`. Live runs pass `LLMClient.as_completer()`.

If the model returns JSON that fails Pydantic validation, the validation error
is fed back and the call is retried. After `max_retries` failed repairs the
caller must flag human review — we never pass free text downstream.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, ValidationError

DEFAULT_MAX_RETRIES = 2
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class Completer(Protocol):
    """Anything that turns a chat into a string. Mocked in unit tests."""

    def complete(self, messages: list[dict[str, str]], *, schema_name: str) -> str: ...


@dataclass
class StructuredResult[T: BaseModel]:
    """Outcome of `generate_structured`. Agents branch on `ok` / `exhausted`."""

    value: T | None
    ok: bool
    exhausted: bool
    attempts: int
    errors: list[str] = field(default_factory=list)
    raw_texts: list[str] = field(default_factory=list)

    @property
    def requires_human_review(self) -> bool:
        return self.exhausted or not self.ok


class StructuredOutputExhausted(Exception):
    """Raised only if a caller asks `generate_structured` to raise on failure."""

    def __init__(self, result: StructuredResult[BaseModel]) -> None:
        self.result = result
        super().__init__(
            f"{result.attempts} attempt(s) failed Pydantic validation: {result.errors[-1]}"
        )


def generate_structured[T: BaseModel](
    prompt: str,
    schema: type[T],
    *,
    completer: Completer,
    system: str | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    raise_on_exhaust: bool = False,
) -> StructuredResult[T]:
    """Call the model, validate against `schema`, repair on ValidationError.

    `max_retries` is the number of *repair* attempts after the first call
    (default 2 → 3 total tries).
    """

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    errors: list[str] = []
    raw_texts: list[str] = []
    attempts = 0
    max_attempts = max_retries + 1

    while attempts < max_attempts:
        attempts += 1
        raw = completer.complete(messages, schema_name=schema.__name__)
        raw_texts.append(raw)
        try:
            payload = _loads_json(raw)
            value = schema.model_validate(payload)
            return StructuredResult(
                value=value,
                ok=True,
                exhausted=False,
                attempts=attempts,
                errors=errors,
                raw_texts=raw_texts,
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            detail = _format_error(exc)
            errors.append(detail)
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous reply did not validate as "
                        f"{schema.__name__}. Fix the JSON and reply with the "
                        "object only.\n\nValidation error:\n"
                        f"{detail}\n\nJSON schema:\n"
                        f"{json.dumps(schema.model_json_schema(), indent=2)}"
                    ),
                }
            )

    result: StructuredResult[T] = StructuredResult(
        value=None,
        ok=False,
        exhausted=True,
        attempts=attempts,
        errors=errors,
        raw_texts=raw_texts,
    )
    if raise_on_exhaust:
        raise StructuredOutputExhausted(result)
    return result


def _loads_json(text: str) -> object:
    cleaned = _FENCE.sub("", text.strip()).strip()
    return json.loads(cleaned)


def _format_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return exc.json()
    return f"{type(exc).__name__}: {exc}"


def scripted_completer(responses: Sequence[str]) -> Completer:
    """Test helper: return canned replies in order."""

    queue = list(responses)

    class _Scripted:
        def complete(self, messages: list[dict[str, str]], *, schema_name: str) -> str:
            if not queue:
                raise AssertionError(
                    f"completer exhausted; last messages were {messages[-1:]!r} "
                    f"for schema {schema_name}"
                )
            return queue.pop(0)

    return _Scripted()
