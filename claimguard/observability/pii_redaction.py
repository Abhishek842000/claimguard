"""Redact PII before any log, trace, or Langfuse export.

This is intentionally conservative: a false positive (over-redaction) is
acceptable; leaking a Social Security number in a portfolio demo is not.
Only synthetic data is used in this repo, but the same path will run in eval.
"""

from __future__ import annotations

import re
from typing import Any

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(
    r"\b(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)
_VIN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_CC = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_PII_KEYS = {
    "full_name",
    "email",
    "phone",
    "date_of_birth",
    "street_address",
    "postal_code",
    "vin",
    "license_plate",
    "claimant",
}


def redact_pii(text: str) -> str:
    """Replace well-known PII patterns in a free-text string."""
    redacted = _SSN.sub("[SSN]", text)
    redacted = _EMAIL.sub("[EMAIL]", redacted)
    redacted = _PHONE.sub("[PHONE]", redacted)
    redacted = _VIN.sub("[VIN]", redacted)
    redacted = _CC.sub("[CARD]", redacted)
    return redacted


def redact_mapping(payload: Any) -> Any:
    """Recursively redact dict/list structures used as trace inputs."""
    if isinstance(payload, str):
        return redact_pii(payload)
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if key in _PII_KEYS:
                out[key] = "[REDACTED]"
            else:
                out[key] = redact_mapping(value)
        return out
    if isinstance(payload, list):
        return [redact_mapping(item) for item in payload]
    return payload
