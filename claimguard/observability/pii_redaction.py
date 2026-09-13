"""Redact PII before any log, trace, or Langfuse export.

This is intentionally conservative: a false positive (over-redaction) is
acceptable; leaking a Social Security number in a portfolio demo is not.
Only synthetic data is used in this repo, but the same path will run in eval.

Every application log event and every Langfuse payload must pass through
`redact_mapping` / `redact_pii` — never log the raw request or claimant object.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# SSN: 123-45-6789 (and the unpunctuated 9-digit form after a SSN/SS# label).
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_SSN_LABELED = re.compile(r"\b(?:SSN|SS#|Social Security(?: Number)?)\s*[:#]?\s*\d{9}\b", re.I)
# DOB-like dates. ISO dates immediately followed by `T` (timestamps) are left alone.
_DOB_ISO = re.compile(
    r"(?<![T\d])((?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))(?![T\d])"
)
_DOB_US = re.compile(r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_VIN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_CC = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_PII_KEYS = {
    "full_name",
    "email",
    "phone",
    "date_of_birth",
    "dob",
    "ssn",
    "social_security",
    "social_security_number",
    "street_address",
    "postal_code",
    "vin",
    "license_plate",
    "claimant",
}


def redact_pii(text: str) -> str:
    """Replace well-known PII patterns in a free-text string."""
    redacted = _SSN.sub("[SSN]", text)
    redacted = _SSN_LABELED.sub("[SSN]", redacted)
    redacted = _DOB_US.sub("[DOB]", redacted)
    redacted = _DOB_ISO.sub("[DOB]", redacted)
    redacted = _EMAIL.sub("[EMAIL]", redacted)
    redacted = _PHONE.sub("[PHONE]", redacted)
    redacted = _VIN.sub("[VIN]", redacted)
    redacted = _CC.sub("[CARD]", redacted)
    return redacted


def redact_mapping(payload: Any) -> Any:
    """Recursively redact dict/list structures used as trace inputs, logs, or exports."""
    if isinstance(payload, str):
        return redact_pii(payload)
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if str(key).lower() in _PII_KEYS:
                out[key] = "[REDACTED]"
            else:
                out[key] = redact_mapping(value)
        return out
    if isinstance(payload, list):
        return [redact_mapping(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_mapping(item) for item in payload)
    return payload


def redact_log_event(
    _logger: object, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: wipe PII from the event dict before it is rendered."""
    return redact_mapping(event_dict)


class PiiRedactingFilter(logging.Filter):
    """stdlib logging filter so `logging.info(...)` cannot leak SSN/DOB either."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_pii(str(record.msg))
        if isinstance(record.args, dict):
            record.args = redact_mapping(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_mapping(arg) for arg in record.args)
        return True
