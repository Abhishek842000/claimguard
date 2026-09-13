from claimguard.observability.pii_redaction import redact_mapping, redact_pii


def test_redact_pii_masks_common_patterns() -> None:
    raw = (
        "Call Jane at 415-555-0148 or jane.doe@example.test. "
        "SSN 123-45-6789 VIN 4T1B11HK5KU123456."
    )
    redacted = redact_pii(raw)
    assert "415-555-0148" not in redacted
    assert "jane.doe@example.test" not in redacted
    assert "123-45-6789" not in redacted
    assert "4T1B11HK5KU123456" not in redacted
    assert "[PHONE]" in redacted
    assert "[EMAIL]" in redacted
    assert "[SSN]" in redacted
    assert "[VIN]" in redacted


def test_redact_mapping_strips_known_pii_keys() -> None:
    payload = {
        "policy_number": "PA-2024-009188",
        "claimant": {"full_name": "Jordan Hale", "email": "j@example.test"},
        "notes": "email backup at adjuster@carrier.test",
    }
    redacted = redact_mapping(payload)
    assert redacted["policy_number"] == "PA-2024-009188"
    assert redacted["claimant"] == "[REDACTED]"
    assert "[EMAIL]" in redacted["notes"]
