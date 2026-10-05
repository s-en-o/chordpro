from io import BytesIO
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.adapters.pdf import NoTextLayerError, PdfAdapter


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


def test_pdf_adapter_extracts_lines() -> None:
    layout = PdfAdapter().to_layout(make_text_pdf())
    assert len(layout.pages) == 1
    page = layout.pages[0]
    texts = [line.text for line in page.lines]
    assert "Hello world" in texts
    assert "C     G" in texts


def test_pdf_adapter_orders_chord_above_lyric() -> None:
    page = PdfAdapter().to_layout(make_text_pdf()).pages[0]
    # In a top-left origin, the chord line must come first (smaller y).
    assert page.lines[0].text == "C     G"


def test_pdf_adapter_raises_without_text_layer() -> None:
    with pytest.raises(NoTextLayerError):
        PdfAdapter().to_layout(make_blank_pdf())
