from app.classify import LineLabel, chord_ratio, classify_page, is_chord
from app.ir import Page, TextLine, TextSpan


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


def test_is_chord_accepts_common_chords() -> None:
    for token in ["C", "Gm", "F#m7", "Bb", "Amaj7", "Dsus4", "C/G", "E7", "Aadd9"]:
        assert is_chord(token), token


def test_is_chord_accepts_altered_and_extended_chords() -> None:
    # Half-diminished and altered-tension chords seen in real songbooks.
    for token in ["Bm7b5", "C#m7b5", "E7b9", "G7#11", "D7#9", "F7b13", "C7no5"]:
        assert is_chord(token), token


def test_is_chord_tolerates_trailing_punctuation() -> None:
    # Chords in running text can carry a trailing comma or period.
    for token in ["B7,", "C.", "Am7;", "G7:"]:
        assert is_chord(token), token


def test_is_chord_rejects_words() -> None:
    for token in [
        "Hello",
        "world",
        "the",
        "grace",
        "And",
        "Chords",
        "But",
        "City",
        "Cry",
        "Dad",
    ]:
        assert not is_chord(token), token


def test_chord_ratio() -> None:
    assert chord_ratio(make_line("C     G", 0)) == 1.0
    assert chord_ratio(make_line("Hello world", 0)) == 0.0


def test_classify_marks_chord_above_lyric() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0), make_line("Hello world", 14)],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["chord", "lyric"]


def test_classify_marks_lonely_chord_as_chord_only() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0)],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["chord_only"]


def test_classify_treats_blank_between_chord_and_lyric_as_transparent() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0), make_line("", 14), make_line("Hello world", 28)],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["chord", "blank", "lyric"]


def test_classify_marks_directive_lines() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("{title: My Song}", 0), make_line("[C]Hello", 14)],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["directive", "lyric"]


def test_classify_does_not_merge_chord_into_directive() -> None:
    # A chord row directly above a directive is a boundary, not a lyric pair.
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[
            make_line("C     G", 0),
            make_line("{title: My Song}", 14),
            make_line("[C]Hello", 28),
        ],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["chord_only", "directive", "lyric"]


def test_classify_keeps_stacked_chord_lines() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C", 0), make_line("G", 14), make_line("ab", 28)],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["chord", "chord", "lyric"]
