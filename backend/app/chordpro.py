"""Serialize a Song to ChordPro text and guess metadata."""

import re

from app.ir import LayoutDoc
from app.models import Song

# Songbook exports often append a site suffix and wrap the artist, e.g.
# "Kansas City Chords by Wilbert Harrisontabs @ Ultimate Guitar Archive".
_SITE_SUFFIX = re.compile(r"\s*tabs?\s*@\s*Ultimate Guitar Archive\s*$", re.IGNORECASE)
_VERSION_MARKER = re.compile(r"\s*\(ver\s*\d+\)", re.IGNORECASE)
_BY_ARTIST = re.compile(r"\s+by\s+(?P<artist>.+)$", re.IGNORECASE)
# Songbook titles are often "<Song> Chords by <Artist>"; drop the "Chords".
_TRAILING_CHORDS = re.compile(r"\s+chords?\s*$", re.IGNORECASE)


def serialize(song: Song) -> str:
    """Render a Song as ChordPro text."""
    output: list[str] = []
    for key, value in song.metadata.items():
        if value:
            output.append(f"{{{key}: {value}}}")
    if output:
        output.append("")
    for line in song.lines:
        output.append(line.text)
    return "\n".join(output) + "\n"


def clean_title(raw: str) -> tuple[str, str]:
    """Split a raw songbook title into ``(title, artist)``.

    Raw titles often look like ``"Kansas City Chords by Wilbert Harrisontabs @
    Ultimate Guitar Archive"``. This strips the site suffix and version marker,
    then splits on the last ``" by "`` so the artist can be recovered. A title
    without that pattern is returned unchanged with an empty artist.
    """
    text = _SITE_SUFFIX.sub("", raw.strip())
    text = _VERSION_MARKER.sub("", text).strip()

    artist_match = _BY_ARTIST.search(text)
    if not artist_match:
        return (text, "")

    artist = artist_match.group("artist").strip()
    title = text[: artist_match.start()].strip()
    title = _TRAILING_CHORDS.sub("", title).strip()
    # A leading "Chords by ..." with no song name would leave an empty title.
    if not title:
        return (text, "")
    return (title, artist)


def guess_metadata(layout: LayoutDoc) -> dict[str, str]:
    """Best-effort title/artist extraction.

    Prefer the document's own metadata; otherwise fall back to the largest
    text on the first page, which is usually the title. Songbook-style titles
    are cleaned so the site suffix is removed and the artist recovered.
    """
    metadata: dict[str, str] = {}

    raw_title = layout.metadata.get("title", "").strip()
    if not raw_title:
        raw_title = _largest_text_first_page(layout)

    title, derived_artist = clean_title(raw_title) if raw_title else ("", "")
    if title:
        metadata["title"] = title

    # An explicit document author wins over the artist parsed from the title.
    artist = layout.metadata.get("author", "").strip() or derived_artist
    if artist:
        metadata["artist"] = artist

    return metadata


def _largest_text_first_page(layout: LayoutDoc) -> str:
    """Return the text of the largest span on the first page, if any."""
    if not layout.pages:
        return ""
    best_text = ""
    best_size = 0.0
    for line in layout.pages[0].lines:
        for span in line.spans:
            size = span.size or 0.0
            if size > best_size and span.text.strip():
                best_size = size
                best_text = line.text.strip()
    return best_text
