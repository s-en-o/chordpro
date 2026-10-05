from app.chordpro import clean_title, guess_metadata, serialize
from app.ir import LayoutDoc, Page, TextLine, TextSpan
from app.models import Song, SongLine


def make_line(text: str, size: float = 12) -> TextLine:
    span = TextSpan(
        text=text, x0=0, y0=0, x1=len(text) * size * 0.6, y1=size, size=size, bold=False
    )
    return TextLine(spans=[span], y0=0, y1=size)


def test_serialize_includes_metadata_then_blank_line() -> None:
    song = Song(
        lines=[SongLine(kind="lyric", text="[C]Hello")],
        metadata={"title": "My Song", "artist": "Me"},
    )
    assert serialize(song) == "{title: My Song}\n{artist: Me}\n\n[C]Hello\n"


def test_serialize_without_metadata() -> None:
    song = Song(lines=[SongLine(kind="blank", text="")])
    assert serialize(song) == "\n"


def test_guess_metadata_prefers_document_metadata() -> None:
    layout = LayoutDoc(metadata={"title": "Given", "author": "Someone"})
    assert guess_metadata(layout) == {"title": "Given", "artist": "Someone"}


def test_guess_metadata_falls_back_to_largest_text() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("Big Title", 24), make_line("small lyric", 10)],
    )
    layout = LayoutDoc(pages=[page])
    assert guess_metadata(layout) == {"title": "Big Title"}


def test_clean_title_extracts_title_and_artist() -> None:
    raw = "Take Me Home Country Roads Chords by John Denvertabs @ Ultimate Guitar Archive"
    assert clean_title(raw) == ("Take Me Home Country Roads", "John Denver")


def test_clean_title_strips_version_marker() -> None:
    raw = "Sloop John B Chords (ver 3) by The Beach Boystabs @ Ultimate Guitar Archive"
    assert clean_title(raw) == ("Sloop John B", "The Beach Boys")


def test_clean_title_leaves_plain_title_alone() -> None:
    assert clean_title("Amazing Grace") == ("Amazing Grace", "")


def test_guess_metadata_cleans_ultimate_guitar_title() -> None:
    layout = LayoutDoc(
        metadata={
            "title": "Kansas City Chords by Wilbert Harrisontabs @ Ultimate Guitar Archive"
        }
    )
    assert guess_metadata(layout) == {"title": "Kansas City", "artist": "Wilbert Harrison"}


def test_guess_metadata_keeps_document_artist_when_present() -> None:
    layout = LayoutDoc(
        metadata={
            "title": "Comes A Time Chords by Neil Youngtabs @ Ultimate Guitar Archive",
            "author": "Neil Young",
        }
    )
    assert guess_metadata(layout) == {"title": "Comes A Time", "artist": "Neil Young"}
