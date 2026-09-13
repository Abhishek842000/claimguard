"""OCR fallback for scanned / image-only claim forms.

The default backend is Tesseract via pytesseract when installed. Tests inject
a fake backend. A HF document-QA model can implement the same protocol later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class OcrBackend(Protocol):
    name: str

    def extract_text(self, path: Path) -> str: ...


class UnavailableOcr:
    """Used when no OCR engine is installed. Intake records the miss and continues."""

    name = "unavailable"

    def extract_text(self, path: Path) -> str:
        return ""


class TesseractOcr:
    """Lazy pytesseract wrapper. Import is optional so unit tests stay light."""

    name = "pytesseract"

    def extract_text(self, path: Path) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return ""
        return pytesseract.image_to_string(Image.open(path))


def default_ocr() -> OcrBackend:
    try:
        import pytesseract  # noqa: F401

        return TesseractOcr()
    except ImportError:
        return UnavailableOcr()
