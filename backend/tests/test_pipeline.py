from app.ir import LayoutDoc, Page, TextLine, TextSpan
from app.pipeline import convert_layout


def make_line(text: str, y0: float, char_width: float = 7.2) -> TextLine:
    span = TextSpan(
        text=text, x0=0, y0=y0, x1=len(text) * char_width, y1=y0 + 12, size=12, bold=False
    )
    return TextLine(spans=[span], y0=y0, y1=y0 + 12)


def test_convert_layout_end_to_end() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0), make_line("Hello world", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    assert song.lines[0].text == "[C]Hello [G]world"


def test_convert_layout_spans_multiple_pages() -> None:
    page1 = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C", 0), make_line("one", 14)],
    )
    page2 = Page(
        number=2,
        width=600,
        height=800,
        lines=[make_line("G", 0), make_line("two", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page1, page2]))
    assert [line.text for line in song.lines] == ["[C]one", "[G]two"]
