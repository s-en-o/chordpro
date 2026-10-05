import shutil
from io import BytesIO
from typing import Any

import pymupdf
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.adapters.ocr import OcrAdapter
from app.adapters.pdf import NoTextLayerError, PdfAdapter

# get_tessdata() raises when Tesseract is absent, so check the binary instead.
tesseract_available = shutil.which("tesseract") is not None


def make_vector_only_pdf() -> bytes:
    """A PDF with no text layer and no image: the shape of the failing file.

    A blank page stands in for the vector-outline case. OCR will find nothing,
    which is exactly what we want to test for the "OCR also found nothing"
    path.
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.mark.skipif(not tesseract_available, reason="Tesseract not installed")
def test_ocr_adapter_raises_when_ocr_finds_nothing() -> None:
    # A truly blank page yields no OCR text -> NoTextLayerError, so the API can
    # report a clear failure instead of returning an empty song.
    with pytest.raises(NoTextLayerError):
        OcrAdapter().to_layout(make_vector_only_pdf())


def test_ocr_adapter_rejects_non_pdf_bytes() -> None:
    with pytest.raises(NoTextLayerError):
        OcrAdapter().to_layout(b"this is not a pdf")


def test_ocr_adapter_groups_words_on_one_baseline_into_a_row() -> None:
    # Two words on the same baseline belong to one line; a chord row above a
    # lyric row must stay separate.
    adapter = OcrAdapter()
    result = adapter._words_to_page_dict(
        [
            (100.0, 10.0, 130.0, 24.0, "Hello", 0, 0, 0),
            (140.0, 10.0, 170.0, 24.0, "world", 0, 0, 1),
            (100.0, 28.0, 120.0, 42.0, "G", 0, 0, 2),
            (100.0, 46.0, 200.0, 60.0, "lyric", 0, 0, 3),
        ]
    )
    texts = [
        "".join(span["text"] for span in block["lines"][0]["spans"]).strip()
        for block in result["blocks"]
    ]
    assert texts == ["Hello world", "G", "lyric"]


def test_ocr_adapter_keeps_rows_separate_with_mismatched_heights() -> None:
    # A tall chord box directly above a shorter lyric box must stay two rows.
    # With a "taller word wins" threshold these would merge.
    adapter = OcrAdapter()
    result = adapter._words_to_page_dict(
        [
            (100.0, 38.0, 120.0, 60.0, "G", 0, 0, 0),  # height 22
            (100.0, 52.0, 170.0, 66.0, "hello", 0, 0, 1),  # height 14
        ]
    )
    texts = [
        "".join(span["text"] for span in block["lines"][0]["spans"]).strip()
        for block in result["blocks"]
    ]
    assert texts == ["G", "hello"]


def test_ocr_adapter_has_no_trailing_space_on_last_word() -> None:
    adapter = OcrAdapter()
    result = adapter._words_to_page_dict(
        [
            (100.0, 10.0, 130.0, 24.0, "Hello", 0, 0, 0),
            (140.0, 10.0, 170.0, 24.0, "world", 0, 0, 1),
        ]
    )
    spans = result["blocks"][0]["lines"][0]["spans"]
    assert [span["text"] for span in spans] == ["Hello ", "world"]


def test_ocr_adapter_builds_page_with_ocr_words() -> None:
    # Drive the parsing path with a fake textpage that returns OCR words.
    class FakeTextPage:
        def extractWORDS(self) -> list[tuple]:
            return [(72.0, 100.0, 200.0, 112.0, "Hello", 0, 0, 0)]

    class FakePage:
        rect = pymupdf.Rect(0, 0, 600, 800)

        def get_textpage_ocr(self, **kwargs: Any) -> FakeTextPage:
            return FakeTextPage()

    adapter = OcrAdapter()
    page = adapter._read_page(FakePage(), 1)
    assert [line.text.strip() for line in page.lines] == ["Hello"]


@pytest.mark.skipif(not tesseract_available, reason="Tesseract not installed")
def test_ocr_adapter_reads_text_from_rendered_image() -> None:
    # Build a PDF whose only content is an image of text, then confirm OCR
    # recovers it. This exercises the real Tesseract path.
    image_doc = pymupdf.open()
    image_page = image_doc.new_page(width=300, height=100)
    image_page.insert_text((20, 60), "Hello chord", fontsize=24)
    pixmap = image_page.get_pixmap(dpi=150)
    image_bytes = pixmap.tobytes("png")
    image_doc.close()

    # Wrap the image into a new PDF page as a picture (no text layer).
    out_doc = pymupdf.open()
    out_page = out_doc.new_page(width=300, height=100)
    out_page.insert_image(out_page.rect, stream=image_bytes)
    pdf_bytes = out_doc.tobytes()
    out_doc.close()

    # The image-only PDF has no text layer...
    with pytest.raises(NoTextLayerError):
        PdfAdapter().to_layout(pdf_bytes)
    # ...but the OCR adapter recovers the text.
    layout = OcrAdapter().to_layout(pdf_bytes)
    text = " ".join(line.text for line in layout.pages[0].lines)
    assert "Hello" in text
