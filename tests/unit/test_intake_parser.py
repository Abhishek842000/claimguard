"""PDF text extract, OCR fallback, and regex NER without an LLM."""

from __future__ import annotations

from pathlib import Path

from claimguard.intake.ner import RegexEntityExtractor
from claimguard.intake.pdf_parser import parse_document
from claimguard.schemas.common import DocumentType
from claimguard.schemas.graph import DocumentRef
from pypdf import PdfWriter

SAMPLE_DIR = Path("data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6")


class _FakeOcr:
    name = "fake-ocr"

    def extract_text(self, path: Path) -> str:
        return f"OCR FALLBACK from {path.name}: Policy number: PA-1999-000001"


def test_sample_fnol_pdf_is_text_native() -> None:
    pdf = SAMPLE_DIR / "documents" / "fnol-claim-form.pdf"
    parsed = parse_document(
        DocumentRef(
            document_id="doc-1",
            filename=pdf.name,
            storage_uri=pdf.resolve().as_uri(),
            document_type=DocumentType.CLAIM_FORM,
        )
    )
    assert parsed.method == "pdf_text"
    assert "PA-2026-000039" in parsed.text
    assert "Casey Patel" in parsed.text
    assert "Phoenix" in parsed.text


def test_ocr_fallback_when_pdf_has_no_text(tmp_path: Path) -> None:
    blank = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with blank.open("wb") as handle:
        writer.write(handle)
    parsed = parse_document(
        DocumentRef(
            document_id="doc-2",
            filename=blank.name,
            storage_uri=blank.resolve().as_uri(),
        ),
        ocr=_FakeOcr(),
        min_text_chars=40,
    )
    assert parsed.method == "ocr"
    assert "PA-1999-000001" in parsed.text


def test_regex_ner_catches_policy_vin_and_money() -> None:
    text = (
        "Policy number: PA-2026-000039\n"
        "Named insured: Casey Patel\n"
        "VIN 3G83UC0P55S0G0ZD2 claimed $6,225.00 on 2026-06-12"
    )
    entities = RegexEntityExtractor().extract(text)
    types = {item.entity_type: item.value for item in entities}
    assert types["POLICY_NUMBER"] == "PA-2026-000039"
    assert types["VIN"] == "3G83UC0P55S0G0ZD2"
    assert types["PERSON"] == "Casey Patel"
    assert any(item.entity_type == "MONEY" and item.value == "$6,225.00" for item in entities)
    assert any(item.entity_type == "DATE" for item in entities)
