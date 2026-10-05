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


def test_read_lines_drops_whitespace_only_lines() -> None:
    # Interior spaces must be preserved, but a line that is only spaces carries
    # no content and must not become a blank line in the output.
    raw_lines = [make_raw_line(["real ", "content"]), make_raw_line(["", "   ", ""])]
    lines = PdfAdapter()._read_lines(raw_lines)
    assert [line.text for line in lines] == ["real content"]


def make_line(x0: float, y0: float, text: str) -> TextLine:
    """Build one TextLine at ``(x0, y0)`` with a single span."""
    return TextLine(
        spans=[
            TextSpan(
                text=text,
                x0=x0,
                y0=y0,
                x1=x0 + len(text) * 7.2,
                y1=y0 + 12,
                size=12.0,
                bold=False,
            )
        ],
        y0=y0,
        y1=y0 + 12,
    )


def make_block(x0: float, y0: float, x1: float, texts: list[str]) -> tuple:
    """Build one block's ``(bbox, lines)``, one line per text at increasing y."""
    lines = [
        make_line(x0, y0 + offset * 14, text) for offset, text in enumerate(texts)
    ]
    block_bottom = y0 + (len(texts) - 1) * 14 + 12
    return ((x0, y0, x1, block_bottom), lines)


def make_baseline_block(
    x0: float, y0: float, x1: float, words: list[str], reversed_order: bool = False
) -> tuple:
    """Build a block whose words all share one baseline (a chord row).

    PyMuPDF emits each word of a same-baseline row as its own line at the same
    ``y0`` but a different ``x0``; this reproduces that shape. Pass
    ``reversed_order=True`` to list the spans right-to-left, so a reader that
    fails to sort by ``x0`` would emit them in the wrong order.
    """
    spans = []
    x = x0
    for word in words:
        spans.append((x, make_line(x, y0, word)))
        x += len(word) * 7.2 + 12
    if reversed_order:
        spans.reverse()
    lines = [line for _, line in spans]
    return ((x0, y0, x1, y0 + 12), lines)


def test_order_blocks_stays_single_column_when_only_one_side_has_blocks() -> None:
    # All blocks start on the left; nothing on the right, so this is one
    # column and must be read top-to-bottom.
    blocks = [
        make_block(72, 0, 240, ["one"]),
        make_block(72, 20, 240, ["two"]),
        make_block(72, 40, 240, ["three"]),
    ]
    lines = PdfAdapter()._order_blocks_into_reading_order(
        blocks, page_width=612, page_height=800
    )
    assert [line.text for line in lines] == ["one", "two", "three"]


def test_order_blocks_reads_left_column_before_right() -> None:
    # Five blocks on each side of a 612pt page midpoint (306).
    blocks: list[tuple] = []
    for i in range(5):
        blocks.append(make_block(72, i * 20, 240, [f"L{i}"]))
        blocks.append(make_block(330, i * 20, 500, [f"R{i}"]))
    lines = PdfAdapter()._order_blocks_into_reading_order(
        blocks, page_width=612, page_height=800
    )
    texts = [line.text for line in lines]
    assert texts == ["L0", "L1", "L2", "L3", "L4", "R0", "R1", "R2", "R3", "R4"]


def test_order_blocks_keeps_same_baseline_chords_left_to_right() -> None:
    # A same-baseline chord row whose spans are listed right-to-left must come
    # out left-to-right, because lines are sorted by (y0, x0). If the x0 sort
    # were missing, this returns C, Em, D, G.
    blocks = [make_baseline_block(60, 40, 570, ["G", "D", "Em", "C"], reversed_order=True)]
    lines = PdfAdapter()._order_blocks_into_reading_order(
        blocks, page_width=612, page_height=800
    )
    assert [line.text for line in lines] == ["G", "D", "Em", "C"]


def test_order_blocks_reads_band_by_band_around_a_mid_page_divider() -> None:
    # Regression for the band logic: a full-width divider in the MIDDLE of the
    # page must split the columns into two bands, not be hoisted to the top.
    # Left/right blocks above the divider come first, then the divider, then
    # left/right blocks below it.
    blocks = [
        make_block(72, 100, 240, ["L-top"]),
        make_block(330, 100, 500, ["R-top"]),
        make_block(72, 140, 240, ["L-top2"]),
        make_block(330, 140, 500, ["R-top2"]),
        make_block(72, 160, 240, ["L-top3"]),
        make_block(330, 160, 500, ["R-top3"]),
        make_block(60, 300, 570, ["DIVIDER"]),  # full width, mid-page
        make_block(72, 400, 240, ["L-bot"]),
        make_block(330, 400, 500, ["R-bot"]),
        make_block(72, 430, 240, ["L-bot2"]),
        make_block(330, 430, 500, ["R-bot2"]),
        make_block(72, 460, 240, ["L-bot3"]),
        make_block(330, 460, 500, ["R-bot3"]),
    ]
    lines = PdfAdapter()._order_blocks_into_reading_order(
        blocks, page_width=612, page_height=800
    )
    texts = [line.text for line in lines]
    assert texts == [
        "L-top",
        "L-top2",
        "L-top3",
        "R-top",
        "R-top2",
        "R-top3",
        "DIVIDER",
        "L-bot",
        "L-bot2",
        "L-bot3",
        "R-bot",
        "R-bot2",
        "R-bot3",
    ]


def test_is_two_column_page_ignores_footer_page_number() -> None:
    # Regression for the footer exclusion. Three right-side blocks that all sit
    # in the bottom footer band must NOT count: without the exclusion the right
    # count reaches the threshold and this one-column page is misread as two.
    adapter = PdfAdapter()
    left = [
        make_block(72, 100, 400, ["a"]),
        make_block(72, 140, 400, ["b"]),
        make_block(72, 180, 400, ["c"]),
    ]
    three_footer_blocks = [
        make_block(520, 780, 567, ["Page 1/2"]),
        make_block(520, 800, 567, ["footer left"]),
        make_block(520, 820, 567, ["footer right"]),
    ]
    assert (
        adapter._is_two_column_page(left, three_footer_blocks, page_height=842) is False
    )

    # Three right-side body blocks (above the footer band) DO make it two-column.
    three_body_blocks = [
        make_block(430, 200, 567, ["x"]),
        make_block(430, 240, 567, ["y"]),
        make_block(430, 280, 567, ["z"]),
    ]
    assert (
        adapter._is_two_column_page(left, three_body_blocks, page_height=842) is True
    )


def test_order_blocks_does_not_split_wide_row_on_one_column_page() -> None:
    # Guard: a one-column page whose wide chord row straddles the midpoint must
    # stay in reading order. Here there are no right-side body blocks, so the
    # page is one column and everything is read top-to-bottom.
    blocks = [
        make_block(57, 200, 484, ["Country Roads, take me home"]),
        make_baseline_block(125, 240, 459, ["G", "D", "Em", "C"]),
        make_block(57, 300, 553, ["West Virginia, mountain mama"]),
    ]
    lines = PdfAdapter()._order_blocks_into_reading_order(
        blocks, page_width=612, page_height=800
    )
    assert [line.text for line in lines] == [
        "Country Roads, take me home",
        "G",
        "D",
        "Em",
        "C",
        "West Virginia, mountain mama",
    ]
