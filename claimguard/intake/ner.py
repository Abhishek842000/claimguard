"""Entity extractors. Regex is the default; an HF token classifier can swap in."""

from __future__ import annotations

import re
from typing import Protocol

from claimguard.schemas.intake import ExtractedEntity

_POLICY = re.compile(r"\b(?:PA|HO)-\d{4}-\d+\b", re.IGNORECASE)
_VIN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_MONEY = re.compile(r"\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_NAMED_INSURED = re.compile(r"Named insured:\s*(.+)", re.IGNORECASE)


class EntityExtractor(Protocol):
    name: str

    def extract(self, text: str) -> list[ExtractedEntity]: ...


class RegexEntityExtractor:
    """Deterministic catch-net for layout fields the LLM might skip."""

    name = "regex-ner-v1"

    def extract(self, text: str) -> list[ExtractedEntity]:
        found: list[ExtractedEntity] = []
        found.extend(_spans(text, _POLICY, "POLICY_NUMBER", 0.95))
        found.extend(_spans(text, _VIN, "VIN", 0.90))
        found.extend(_spans(text, _DATE, "DATE", 0.85))
        found.extend(_spans(text, _MONEY, "MONEY", 0.85))
        found.extend(_spans(text, _EMAIL, "EMAIL", 0.99))
        found.extend(_spans(text, _PHONE, "PHONE", 0.90))
        for match in _NAMED_INSURED.finditer(text):
            value = match.group(1).strip()
            if value:
                found.append(
                    ExtractedEntity(
                        entity_type="PERSON",
                        value=value,
                        start_char=match.start(1),
                        end_char=match.end(1),
                        confidence=0.80,
                    )
                )
        return found


class HuggingFaceNerExtractor:
    """Optional HF token-classification swap-in. Lazy-imports transformers."""

    name = "hf-ner"

    def __init__(self, model_id: str = "dslim/bert-base-NER") -> None:
        self.model_id = model_id
        self._pipe = None

    def extract(self, text: str) -> list[ExtractedEntity]:
        pipe = self._pipeline()
        raw = pipe(text[:8000])
        entities: list[ExtractedEntity] = []
        for item in raw:
            entities.append(
                ExtractedEntity(
                    entity_type=str(item.get("entity_group") or item.get("entity") or "MISC"),
                    value=str(item.get("word") or ""),
                    start_char=item.get("start"),
                    end_char=item.get("end"),
                    confidence=float(item.get("score") or 0.5),
                )
            )
        return entities

    def _pipeline(self):
        if self._pipe is None:
            from transformers import pipeline

            self._pipe = pipeline("ner", model=self.model_id, aggregation_strategy="simple")
        return self._pipe


def _spans(
    text: str, pattern: re.Pattern[str], entity_type: str, confidence: float
) -> list[ExtractedEntity]:
    out: list[ExtractedEntity] = []
    for match in pattern.finditer(text):
        value = match.group(0)
        out.append(
            ExtractedEntity(
                entity_type=entity_type,
                value=value,
                start_char=match.start(),
                end_char=match.end(),
                confidence=confidence,
            )
        )
    return out
