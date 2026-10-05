from app.align import align_page, chord_only_text, merge_chord_lyric
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
