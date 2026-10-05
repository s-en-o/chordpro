import pytest

from app.adapters.base import NoTextLayerError
from app.adapters.paste import PasteTextAdapter
from app.geometry import char_x_centers, nearest_char_index, token_positions
from app.pipeline import convert_layout


def to_lines(text: str) -> list[str]:
    """Helper: convert pasted text and return the IR line texts."""
    layout = PasteTextAdapter().to_layout(text.encode("utf-8"))
    assert len(layout.pages) == 1
    return [line.text for line in layout.pages[0].lines]


def test_paste_splits_lines() -> None:
    assert to_lines("line one\nline two\nline three") == [
        "line one",
        "line two",
        "line three",
    ]


def test_paste_normalizes_crlf() -> None:
    assert to_lines("line one\r\nline two") == ["line one", "line two"]


def test_paste_expands_tabs_to_four_column_stops() -> None:
    # A tab advances to the next multiple of 4: after "C" (column 1) the next
    # stop is column 4, so three spaces are inserted.
    assert to_lines("C\tG") == ["C   G"]


def test_paste_normalizes_non_breaking_space() -> None:
    assert to_lines("C\u00a0G") == ["C G"]


def test_paste_strips_leading_bom() -> None:
    assert to_lines("\ufeffC     G") == ["C     G"]


def test_paste_preserves_leading_whitespace_for_alignment() -> None:
    # Leading spaces are how a chord is positioned over a lyric; they must
    # survive so the geometry-based alignment can use them.
    lines = to_lines("  C       G\n  Hello world")
    assert lines == ["  C       G", "  Hello world"]


def test_paste_rejects_empty_input() -> None:
    with pytest.raises(NoTextLayerError):
        PasteTextAdapter().to_layout(b"   \n  \n")


def test_paste_span_positions_follow_character_columns() -> None:
    # The chord "C" at column 0 and "G" at column 6 must map to x-positions
    # that make "G" sit just before the lyric character at the same column.
    layout = PasteTextAdapter().to_layout(b"C     G\nHello world\n")
    page = layout.pages[0]
    lyric_line = page.lines[1]
    chord_tokens = token_positions(page.lines[0])
    assert [token for token, _ in chord_tokens] == ["C", "G"]
    g_center = dict(chord_tokens)["G"]
    index = nearest_char_index(char_x_centers(lyric_line), g_center)
    # "Hello world": index 6 is 'w'.
    assert lyric_line.text[index] == "w"


def test_paste_inline_chordpro_passes_through() -> None:
    # Already-inline paste should not be re-parsed as chord-over-lyric.
    song = convert_layout(PasteTextAdapter().to_layout(b"[C]Hello [G]world\n"))
    assert song.lines[0].text == "[C]Hello [G]world"


def test_paste_chords_above_lyrics_get_aligned() -> None:
    song = convert_layout(PasteTextAdapter().to_layout(b"C     G\nHello world\n"))
    assert song.lines[0].text == "[C]Hello [G]world"


def test_paste_metadata_is_empty() -> None:
    layout = PasteTextAdapter().to_layout(b"[C]Hello\n")
    assert layout.metadata == {}
