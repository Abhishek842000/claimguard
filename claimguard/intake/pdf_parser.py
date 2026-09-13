"""Text-native PDF extract with an OCR fallback for scanned pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

from pypdf import PdfReader

from claimguard.intake.ocr import OcrBackend, default_ocr
from claimguard.schemas.graph import DocumentRef

MIN_TEXT_CHARS = 40


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    filename: str
    storage_uri: str
    text: str
    page_count: int | None
    method: Literal["pdf_text", "ocr", "plain", "empty"]
    preview: str


def resolve_storage_uri(uri: str) -> Path:
    if uri.startswith("file://"):
        parsed = urlparse(uri)
        return Path(unquote(parsed.path))
    return Path(uri)


def parse_document(
    ref: DocumentRef,
    *,
    ocr: OcrBackend | None = None,
    min_text_chars: int = MIN_TEXT_CHARS,
) -> ParsedDocument:
    path = resolve_storage_uri(ref.storage_uri)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(ref, path, ocr=ocr or default_ocr(), min_text_chars=min_text_chars)
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        return _result(ref, text=text, page_count=None, method="plain" if text.strip() else "empty")
    return _result(ref, text="", page_count=None, method="empty")


def _parse_pdf(
    ref: DocumentRef,
    path: Path,
    *,
    ocr: OcrBackend,
    min_text_chars: int,
) -> ParsedDocument:
    if not path.is_file():
        return _result(ref, text="", page_count=None, method="empty")
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if len(text) >= min_text_chars:
        return _result(ref, text=text, page_count=len(reader.pages), method="pdf_text")
    ocr_text = ocr.extract_text(path).strip()
    if ocr_text:
        return _result(ref, text=ocr_text, page_count=len(reader.pages), method="ocr")
    return _result(ref, text=text, page_count=len(reader.pages), method="empty")


def _result(
    ref: DocumentRef,
    *,
    text: str,
    page_count: int | None,
    method: Literal["pdf_text", "ocr", "plain", "empty"],
) -> ParsedDocument:
    preview = text[:2000]
    return ParsedDocument(
        document_id=ref.document_id,
        filename=ref.filename,
        storage_uri=ref.storage_uri,
        text=text,
        page_count=page_count,
        method=method,
        preview=preview,
    )
