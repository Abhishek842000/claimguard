"""Structured logging. JSON in non-local environments, console locally.

PII redaction is a required processor, not an opt-in: every event is scrubbed
before ConsoleRenderer / JSONRenderer (and before stdlib handlers emit).
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

import structlog

from claimguard.observability.pii_redaction import PiiRedactingFilter, redact_log_event


def configure_logging(
    log_level: str = "info",
    app_env: str = "local",
    stream: TextIO | None = None,
) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    target = stream or sys.stdout
    logging.basicConfig(format="%(message)s", stream=target, level=level, force=True)
    root = logging.getLogger()
    if not any(isinstance(item, PiiRedactingFilter) for item in root.filters):
        root.addFilter(PiiRedactingFilter())
    for handler in root.handlers:
        if not any(isinstance(item, PiiRedactingFilter) for item in handler.filters):
            handler.addFilter(PiiRedactingFilter())

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_log_event,
    ]
    if app_env == "local":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=False,
        logger_factory=structlog.PrintLoggerFactory(file=target)
        if stream is not None
        else structlog.PrintLoggerFactory(),
    )
