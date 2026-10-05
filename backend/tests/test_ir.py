from app.ir import LayoutDoc, Page, TextLine, TextSpan


def make_span(text: str, x0: float, y0: float, width: float) -> TextSpan:
    return TextSpan(text=text, x0=x0, y0=y0, x1=x0 + width, y1=y0 + 12)


def test_text_line_joins_span_text() -> None:
    line = TextLine(
        spans=[make_span("Hello ", 0, 0, 30), make_span("world", 30, 0, 30)],
        y0=0,
        y1=12,
    )
    assert line.text == "Hello world"


def test_text_line_height() -> None:
    line = TextLine(spans=[make_span("x", 0, 10, 5)], y0=10, y1=24)
    assert line.height == 14


def test_layout_doc_defaults_are_independent() -> None:
    first = LayoutDoc()
    second = LayoutDoc()
    first.pages.append(Page(number=1, width=1, height=1))
    assert second.pages == []
    assert second.metadata == {}
