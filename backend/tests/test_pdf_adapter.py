from io import BytesIO

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.adapters.pdf import NoTextLayerError, PdfAdapter
from app.ir import TextLine, TextSpan


def make_raw_line(words: list[str]) -> dict:
    """Build one PyMuPDF-style ``get_text('dict')`` line from a list of span texts.

    Real PDFs emit each word as its own span, with a separate ``" "`` span for
    the whitespace between them. This helper reproduces that shape so we can
    test the adapter's line parsing without depending on a specific PDF tool.
    """
    spans = []
    x = 72.0
    for word in words:
        width = len(word) * 7.2
        spans.append(
            {
                "text": word,
                "bbox": (x, 100.0, x + width, 112.0),
                "size": 12.0,
                "flags": 0,
            }
        )
        x += width
    return {"spans": spans}


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


def test_read_line_preserves_space_spans() -> None:
    # Real PDFs split "Almost Heaven" into word spans plus " " spans; the
    # spaces must survive so words are not glued together into "AlmostHeaven".
    raw = make_raw_line(["Almost", " ", "Heaven", " ", "West"])
    line = PdfAdapter()._read_line(raw)
    assert line.text == "Almost Heaven West"


def test_read_line_keeps_spaces_inside_a_span() -> None:
    raw = make_raw_line(["C     G"])
    line = PdfAdapter()._read_line(raw)
    assert line.text == "C     G"


def test_read_line_drops_only_empty_spans() -> None:
    raw = make_raw_line(["Hello", "", "world"])
    line = PdfAdapter()._read_line(raw)
    assert line.text == "Helloworld"


def make_block(x0: float, y0: float, x1: float, texts: list[str]) -> tuple:
    """Build one block's ``(bbox, lines)`` for the reading-order tests."""
    lines = []
    for offset, text in enumerate(texts):
        line_y = y0 + offset * 14
        lines.append(
            TextLine(
                spans=[
                    TextSpan(
                        text=text,
                        x0=x0,
                        y0=line_y,
                        x1=x0 + len(text) * 7.2,
                        y1=line_y + 12,
                        size=12.0,
                        bold=False,
                    )
                ],
                y0=line_y,
                y1=line_y + 12,
            )
        )
    block_bottom = y0 + (len(texts) - 1) * 14 + 12
    return ((x0, y0, x1, block_bottom), lines)


def test_order_blocks_stays_single_column_when_only_one_side_has_blocks() -> None:
    # All blocks start on the left; nothing on the right, so this is one
    # column and must be read top-to-bottom.
    blocks = [
        make_block(72, 0, 240, ["one"]),
        make_block(72, 20, 240, ["two"]),
        make_block(72, 40, 240, ["three"]),
    ]
    lines = PdfAdapter()._order_blocks_into_reading_order(blocks, page_width=612)
    assert [line.text for line in lines] == ["one", "two", "three"]


def test_order_blocks_reads_left_column_before_right() -> None:
    # Five blocks on each side of a 612pt page midpoint (306).
    blocks: list[tuple] = []
    for i in range(5):
        blocks.append(make_block(72, i * 20, 240, [f"L{i}"]))
        blocks.append(make_block(330, i * 20, 500, [f"R{i}"]))
    lines = PdfAdapter()._order_blocks_into_reading_order(blocks, page_width=612)
    texts = [line.text for line in lines]
    assert texts == ["L0", "L1", "L2", "L3", "L4", "R0", "R1", "R2", "R3", "R4"]


def test_order_blocks_does_not_split_one_column_chords_across_midpoint() -> None:
    # Regression for a real PDF ("Country Roads"): a one-column page whose
    # chorus chord row straddles the midpoint must stay in reading order, not
    # be torn into two columns. The chords share one baseline and belong with
    # the lyric line beneath them.
    blocks = [
        make_block(57, 0, 484, ["Country Roads, take me home"]),
        make_block(125, 20, 459, ["G", "D", "Em", "C"]),
        make_block(57, 40, 553, ["West Virginia, mountain mama"]),
        make_block(57, 60, 450, ["[Verse 2]"]),
        make_block(57, 80, 300, ["almost heaven"]),
    ]
    lines = PdfAdapter()._order_blocks_into_reading_order(blocks, page_width=612)
    texts = [line.text for line in lines]
    # All four chords are present and stay together, in left-to-right order.
    assert texts == [
        "Country Roads, take me home",
        "G",
        "D",
        "Em",
        "C",
        "West Virginia, mountain mama",
        "[Verse 2]",
        "almost heaven",
    ]
