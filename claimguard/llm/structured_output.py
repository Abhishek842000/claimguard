"""Instructor-style structured generation with retry / repair on validation failure."""

from __future__ import annotations

from pydantic import BaseModel


def generate_structured[T: BaseModel](
    prompt: str, schema: type[T], *, max_retries: int = 2
) -> T:
    """Call the model, validate against `schema`, repair on ValidationError.

    Guardrail: after `max_retries` failures, raise rather than passing free text
    downstream. Implemented in Phase 1.
    """
    raise NotImplementedError("Structured output is implemented in Phase 1")
