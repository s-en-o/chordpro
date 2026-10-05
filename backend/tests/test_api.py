import shutil
from io import BytesIO

import pymupdf
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.api import app

client = TestClient(app)

# get_tessdata() raises when Tesseract is absent, so check the binary instead.
tesseract_available = shutil.which("tesseract") is not None


def make_text_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Courier", 12)
    pdf.drawString(72, 700, "Hello world")
    pdf.setFont("Courier-Bold", 12)
    pdf.drawString(72, 716, "C     G")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_blank_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def test_convert_returns_chordpro_and_qa() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("song.pdf", make_text_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "[C]Hello [G]world" in body["chordpro"]
    assert body["qa"]["unpaired_chords"] == []


@pytest.mark.skipif(not tesseract_available, reason="Tesseract not installed")
def test_convert_rejects_pdf_without_text() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("blank.pdf", make_blank_pdf(), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "not a text-based PDF"


def test_convert_rejects_non_pdf_bytes() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("not.pdf", b"this is not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "not a text-based PDF"


def test_convert_rejects_oversized_file() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("big.pdf", b"0" * (10 * 1024 * 1024 + 1), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["error"] == "file too large"


def make_image_only_pdf() -> bytes:
    """A PDF whose only content is an image of text (no text layer)."""
    source = pymupdf.open()
    page = source.new_page(width=320, height=120)
    page.insert_text((20, 70), "Hello chord", fontsize=24)
    pixmap = page.get_pixmap(dpi=150)
    image_bytes = pixmap.tobytes("png")
    source.close()

    out = pymupdf.open()
    out_page = out.new_page(width=320, height=120)
    out_page.insert_image(out_page.rect, stream=image_bytes)
    data = out.tobytes()
    out.close()
    return data


def test_convert_reports_ocr_unavailable_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    # If OCR is needed but the engine is missing, the API returns a clear 400
    # (not a 500). We fake the adapter raising, so no Tesseract is required.
    from app.adapters import ocr as ocr_module
    from app.adapters.base import OcrUnavailableError

    def raise_unavailable(self: object, data: bytes) -> object:
        raise OcrUnavailableError("OCR unavailable (is Tesseract installed?)")

    monkeypatch.setattr(ocr_module.OcrAdapter, "to_layout", raise_unavailable)
    response = client.post(
        "/api/convert",
        files={"file": ("blank.pdf", make_blank_pdf(), "application/pdf")},
    )
    assert response.status_code == 400
    assert "OCR is unavailable" in response.json()["error"]


@pytest.mark.skipif(not tesseract_available, reason="Tesseract not installed")
def test_convert_falls_back_to_ocr_for_image_pdf() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("scan.pdf", make_image_only_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "Hello" in body["chordpro"]
    # The QA report tells the user OCR was used.
    assert any("OCR" in note for note in body["qa"]["notes"])


def test_convert_text_aligns_chords_above_lyrics() -> None:
    response = client.post(
        "/api/convert-text", json={"text": "C     G\nHello world\n"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "[C]Hello [G]world" in body["chordpro"]
    assert body["qa"]["notes"] == []


def test_convert_text_passes_inline_chordpro_through() -> None:
    response = client.post(
        "/api/convert-text", json={"text": "[C]Hello [G]world\n"}
    )
    assert response.status_code == 200
    assert "[C]Hello [G]world" in response.json()["chordpro"]


def test_convert_text_rejects_empty() -> None:
    response = client.post("/api/convert-text", json={"text": "   \n  \n"})
    assert response.status_code == 400
    assert response.json()["error"] == "no text to convert"


def test_convert_text_rejects_too_large() -> None:
    response = client.post("/api/convert-text", json={"text": "x" * (1024 * 1024 + 1)})
    assert response.status_code == 413
    assert response.json()["error"] == "text too large"


def test_convert_text_survives_lone_surrogate() -> None:
    # Crafted JSON can carry a lone surrogate; it must not become a 500.
    response = client.post(
        "/api/convert-text",
        content=b'{"text":"A\\ud800B"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
