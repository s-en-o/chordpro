"""Serialize a Song to ChordPro text and guess metadata."""

import re
import statistics

from app.ir import NO_HEADING_KEY, LayoutDoc
from app.models import Song

# Songbook exports often append a site suffix and wrap the artist, e.g.
# "Kansas City Chords by Wilbert Harrisontabs @ Ultimate Guitar Archive".
_SITE_SUFFIX = re.compile(r"\s*tabs?\s*@\s*Ultimate Guitar Archive\s*$", re.IGNORECASE)
_VERSION_MARKER = re.compile(r"\s*\(ver\s*\d+\)", re.IGNORECASE)
# Split on the LAST " by " so a song title that itself contains "By"
# (e.g. "Stand By Me") is not mistaken for the artist boundary.
_BY_ARTIST = re.compile(
    r"\A(?P<title>.*)\s+by\s+(?P<artist>.+?)\Z",
    re.IGNORECASE | re.DOTALL,
)
# Songbook titles are often "<Song> Chords by <Artist>"; drop the "Chords".
_TRAILING_CHORDS = re.compile(r"\s+chords?\s*$", re.IGNORECASE)

# The largest text on a page counts as a heading only when it is at least this
# many times the page's median text size. Real songbook titles are 1.3-1.9x the
# body size; uniform text (e.g. pasted text) is 1.0x and has no heading.
_TITLE_SIZE_RATIO = 1.15


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

    artist_match = _BY_ARTIST.match(text)
    if not artist_match:
        # No artist to recover; still drop a trailing "Chords" marker.
        return (_TRAILING_CHORDS.sub("", text).strip(), "")

    artist = artist_match.group("artist").strip()
    title = _TRAILING_CHORDS.sub("", artist_match.group("title")).strip()
    if not title or title.lower() in ("chord", "chords"):
        # A bare "Chords by X" has no song name; keep the raw text as the title.
        return (text, "")
    return (title, artist)


def guess_metadata(layout: LayoutDoc) -> dict[str, str]:
    """Best-effort title/artist extraction.

    Prefer the document's own metadata; otherwise fall back to the largest
    text on the first page, which is usually the title. Songbook-style titles
    are cleaned so the site suffix is removed and the artist recovered. Sources
    that set ``NO_HEADING_KEY`` (e.g. pasted text) never get an inferred title.
    """
    metadata: dict[str, str] = {}

    raw_title = layout.metadata.get("title", "").strip()
    if not raw_title and NO_HEADING_KEY not in layout.metadata:
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
    """Return the first page's heading text, or "" when there is no heading.

    The largest text is treated as a title only when it is meaningfully larger
    than the page's median text size. With uniform text (e.g. pasted text, where
    every line is the same size) there is no heading, so we return "".
    """
    if not layout.pages:
        return ""
    sizes = [
        span.size
        for line in layout.pages[0].lines
        for span in line.spans
        if span.size
    ]
    if not sizes:
        return ""

    best_text = ""
    best_size = 0.0
    for line in layout.pages[0].lines:
        for span in line.spans:
            size = span.size or 0.0
            if size > best_size and span.text.strip():
                best_size = size
                best_text = line.text.strip()

    # A directive line is metadata, not a title.
    if best_text.startswith("{"):
        return ""

    # With a single span there is no body to compare against, so treat it as a
    # heading (a title-only first page). Otherwise require the largest text to
    # be meaningfully larger than the page's median text size; uniform text
    # (e.g. pasted text) has no heading.
    if len(sizes) > 1:
        median_size = statistics.median(sizes)
        if median_size > 0 and best_size < median_size * _TITLE_SIZE_RATIO:
            return ""

    return best_text
