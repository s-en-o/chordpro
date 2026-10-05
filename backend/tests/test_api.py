from io import BytesIO

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.api import app

client = TestClient(app)


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


def test_convert_rejects_pdf_without_text() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("blank.pdf", make_blank_pdf(), "application/pdf")},
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
