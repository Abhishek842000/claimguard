from io import StringIO
from logging import getLogger

import structlog
from claimguard.logging import configure_logging
from claimguard.observability.pii_redaction import redact_mapping, redact_pii


def test_redact_pii_masks_common_patterns() -> None:
    raw = (
        "Call Jane at 415-555-0148 or jane.doe@example.test. "
        "SSN 123-45-6789 VIN 4T1B11HK5KU123456. DOB 04/12/1988 or 1988-04-12."
    )
    redacted = redact_pii(raw)
    assert "415-555-0148" not in redacted
    assert "jane.doe@example.test" not in redacted
    assert "123-45-6789" not in redacted
    assert "4T1B11HK5KU123456" not in redacted
    assert "04/12/1988" not in redacted
    assert "1988-04-12" not in redacted
    assert "[PHONE]" in redacted
    assert "[EMAIL]" in redacted
    assert "[SSN]" in redacted
    assert "[VIN]" in redacted
    assert "[DOB]" in redacted


def test_redact_mapping_strips_known_pii_keys() -> None:
    payload = {
        "policy_number": "PA-2024-009188",
        "claimant": {"full_name": "Jordan Hale", "email": "j@example.test"},
        "ssn": "123-45-6789",
        "date_of_birth": "1988-04-12",
        "notes": "email backup at adjuster@carrier.test",
    }
    redacted = redact_mapping(payload)
    assert redacted["policy_number"] == "PA-2024-009188"
    assert redacted["claimant"] == "[REDACTED]"
    assert redacted["ssn"] == "[REDACTED]"
    assert redacted["date_of_birth"] == "[REDACTED]"
    assert "[EMAIL]" in redacted["notes"]


def test_application_logs_never_emit_ssn_or_dob() -> None:
    """Acceptance: SSN / DOB-like values cannot appear in rendered log output."""
    stream = StringIO()
    configure_logging("info", "test", stream=stream)
    bound = structlog.get_logger("claimguard.pii-test")
    bound.info(
        "intake_debug",
        claimant="Jordan Hale",
        ssn="123-45-6789",
        date_of_birth="1988-04-12",
        notes="Born 04/12/1988 SSN 123-45-6789 contact jane.doe@example.test",
    )
    getLogger("claimguard.pii-test-stdlib").info(
        "raw claimant SSN 123-45-6789 DOB 1988-04-12"
    )
    output = stream.getvalue()
    assert "123-45-6789" not in output
    assert "1988-04-12" not in output
    assert "04/12/1988" not in output
    assert "Jordan Hale" not in output
    assert "jane.doe@example.test" not in output
    assert "[SSN]" in output or "[REDACTED]" in output
    assert "[DOB]" in output or "[REDACTED]" in output
