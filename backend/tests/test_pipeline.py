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


def test_convert_layout_records_low_confidence_lines() -> None:
    # "C" alone is a chord (ratio 1.0), but "C x y" is 0.333 -- a line that is
    # partly chord-like and falls strictly below the 0.5 threshold.
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C x y", 0), make_line("lyric line", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    assert song.qa.low_confidence_lines == [0]


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


def test_convert_layout_keeps_unknown_directive_line_intact() -> None:
    # A directive that is not title/artist must survive as its own line and
    # never have a chord merged into it.
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[
            make_line("C     G", 0),
            make_line("{start_of_chorus}", 14),
            make_line("[C]Hello", 28),
        ],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    assert [line.text for line in song.lines] == [
        "[C] [G]",
        "{start_of_chorus}",
        "[C]Hello",
    ]


def test_convert_layout_lifts_directives_into_metadata() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("{title: My Song}", 0), make_line("[C]Hello", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    # The title is lifted into metadata and not repeated in the body.
    assert song.metadata == {"title": "My Song"}
    assert [line.text for line in song.lines] == ["[C]Hello"]


def test_convert_layout_does_not_parse_two_directives_on_one_line() -> None:
    # "{title: A} {artist: B}" is not a single directive; it must survive
    # verbatim rather than being mis-split and dropped.
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("{title: A} {artist: B}", 0), make_line("[C]Hi", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    assert song.metadata == {}
    assert song.lines[0].text == "{title: A} {artist: B}"


def test_convert_layout_keeps_empty_valued_directive() -> None:
    # {title:} has no value, so it must not be lifted nor dropped.
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("{title:}", 0), make_line("[C]Hi", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    assert song.metadata == {}
    assert song.lines[0].text == "{title:}"


def test_convert_layout_prefers_title_over_subtitle() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("{subtitle: Sub}", 0), make_line("{title: Main}", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    assert song.metadata == {"title": "Main"}


def test_qa_low_confidence_lines_are_output_line_numbers() -> None:
    # The low-confidence line ("C x y") is output line 0; with a metadata
    # header, its display line number is 0 + header size.
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[
            make_line("{title: T}", 0),
            make_line("C x y", 14),
            make_line("Hello", 28),
        ],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    # Header is "{title: T}" + blank line = 2 lines, so the body starts at 2.
    assert song.qa.low_confidence_lines == [2]


def test_qa_unpaired_chord_lines_point_at_output_lines() -> None:
    # A chord line with no lyric beneath it becomes a chord_only line and is
    # reported as unpaired, addressed by its output line number.
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[
            make_line("{title: T}", 0),
            make_line("C     G", 14),
            make_line("Am", 28),  # another chord, then end of page
        ],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    # Both chord lines run off the page with no lyric -> chord_only lines.
    body = [line.text for line in song.lines]
    assert body == ["[C] [G]", "[Am]"]
    # With a 2-line header, the body lines are display lines 2 and 3.
    assert song.qa.unpaired_chord_lines == [2, 3]


def test_qa_line_numbers_span_multiple_pages() -> None:
    # A low-confidence line on page 2 must map to the right output line,
    # accounting for page 1's lines and the metadata header.
    page1 = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0), make_line("Hello world", 14)],
    )
    page2 = Page(
        number=2,
        width=600,
        height=800,
        lines=[make_line("C x y", 0), make_line("second line", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page1, page2]))
    # No metadata header here (no title), so display lines equal body lines.
    # Body: 0 "[C]Hello [G]world", 1 "C x y", 2 "second line".
    assert song.qa.low_confidence_lines == [1]
