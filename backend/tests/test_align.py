from app.align import (
    align_page,
    chord_only_text,
    merge_chord_lines,
    merge_chord_lyric,
)
from app.classify import LineLabel
from app.ir import TextLine, TextSpan
from app.models import QAReport


def make_line(text: str, y0: float, char_width: float = 7.2) -> TextLine:
    span = TextSpan(
        text=text,
        x0=0,
        y0=y0,
        x1=len(text) * char_width,
        y1=y0 + 12,
        size=12,
        bold=False,
    )
    return TextLine(spans=[span], y0=y0, y1=y0 + 12)


def test_merge_inserts_chords_at_nearest_characters() -> None:
    chord = LineLabel(make_line("C     G", 0), "chord")
    lyric = LineLabel(make_line("Hello world", 14), "lyric")
    result = merge_chord_lyric(chord, lyric, QAReport())
    assert result.kind == "lyric"
    # Chord "G" is centered on x=46.8, which is exactly the center of lyric
    # character index 6 ('w' of "world"); the marker is inserted there.
    assert result.text == "[C]Hello [G]world"


def test_merge_ignores_non_chord_tokens() -> None:
    chord = LineLabel(make_line("C  x  G", 0), "chord")
    lyric = LineLabel(make_line("abcdefgh", 14), "lyric")
    result = merge_chord_lyric(chord, lyric, QAReport())
    assert result.text == "[C]abcdef[G]gh"


def test_chord_only_text() -> None:
    assert chord_only_text(make_line("C   G   Am", 0)) == "[C] [G] [Am]"


def test_align_page_pairs_chord_and_lyric() -> None:
    labels = [
        LineLabel(make_line("C     G", 0), "chord"),
        LineLabel(make_line("Hello world", 14), "lyric"),
        LineLabel(make_line("Am", 28), "chord_only"),
    ]
    qa = QAReport()
    lines = align_page(labels, qa)
    assert [line.text for line in lines] == ["[C]Hello [G]world", "[Am]"]
    assert qa.unpaired_chords == ["Am"]


def test_align_page_passes_plain_lyric_through() -> None:
    labels = [LineLabel(make_line("just a lyric", 0), "lyric")]
    lines = align_page(labels, QAReport())
    assert lines[0].text == "just a lyric"
    assert lines[0].kind == "lyric"


def test_align_page_pairs_across_blank_line() -> None:
    labels = [
        LineLabel(make_line("C", 0), "chord"),
        LineLabel(make_line("", 14), "blank"),
        LineLabel(make_line("ab", 28), "lyric"),
    ]
    lines = align_page(labels, QAReport())
    assert [line.text for line in lines] == ["[C]ab", ""]


def test_align_page_folds_blanks_between_stacked_chords() -> None:
    # A blank line BETWEEN two stacked chord lines must not split the stack:
    # both chords belong to the lyric below, and the interior blank is dropped.
    labels = [
        LineLabel(make_line("C", 0), "chord"),
        LineLabel(make_line("", 14), "blank"),
        LineLabel(make_line("G", 28), "chord"),
        LineLabel(make_line("hello world", 42), "lyric"),
    ]
    lines = align_page(labels, QAReport())
    assert [line.text for line in lines] == ["[C][G]hello world"]


def test_align_page_keeps_blank_after_chord_lyric_pair() -> None:
    # A blank line AFTER a chord/lyric pair is a real separator and stays.
    labels = [
        LineLabel(make_line("C", 0), "chord"),
        LineLabel(make_line("ab", 14), "lyric"),
        LineLabel(make_line("", 28), "blank"),
        LineLabel(make_line("cd", 42), "lyric"),
    ]
    lines = align_page(labels, QAReport())
    assert [line.text for line in lines] == ["[C]ab", "", "cd"]


def test_merge_appends_chords_beyond_end_of_lyric() -> None:
    chord = LineLabel(make_line("C          G", 0), "chord")
    lyric = LineLabel(make_line("ab", 14), "lyric")
    result = merge_chord_lines([chord], lyric, QAReport())
    assert result.text == "[C]ab[G]"


def test_merge_stacks_multiple_chord_lines() -> None:
    top = LineLabel(make_line("C", 0), "chord")
    bottom = LineLabel(make_line("G", 14), "chord")
    lyric = LineLabel(make_line("ab", 28), "lyric")
    result = merge_chord_lines([top, bottom], lyric, QAReport())
    assert result.text == "[C][G]ab"


def test_align_page_merges_stacked_chords() -> None:
    labels = [
        LineLabel(make_line("C", 0), "chord"),
        LineLabel(make_line("G", 14), "chord"),
        LineLabel(make_line("ab", 28), "lyric"),
    ]
    lines = align_page(labels, QAReport())
    assert len(lines) == 1
    assert lines[0].text == "[C][G]ab"
