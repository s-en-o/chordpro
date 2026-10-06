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

# Placeholder values some tools write into PDF metadata (e.g. reportlab writes
# title="untitled", author="anonymous"). They carry no information and must not
# become song metadata.
_PLACEHOLDER_VALUES = frozenset(
    {"untitled", "anonymous", "unknown", "none", "n/a", "unspecified", "unknown artist"}
)

# A ChordPro directive line: one whole line of the form "{key: value}". The
# value stops at the first "}" and the whole line must be a single directive,
# so a line containing two directives is not mis-parsed.
_DIRECTIVE = re.compile(r"^\{(?P<key>[a-zA-Z_]+)\s*:\s*(?P<value>[^}]*)\}\s*$")

# Keys that map to a song's title. An explicit title/t wins over a subtitle.
_TITLE_KEYS = ("title", "t")
# Keys that map to a song's artist.
_ARTIST_KEYS = ("artist", "composer", "author")
# Keys that are lifted into metadata at all (their lines leave the body).
METADATA_DIRECTIVE_KEYS = frozenset(
    _TITLE_KEYS + _ARTIST_KEYS + ("subtitle",)
)


def _directive_key_value(text: str) -> tuple[str, str] | None:
    """Return ``(lowercased key, value)`` for a directive line, else None."""
    match = _DIRECTIVE.match(text.strip())
    if not match:
        return None
    return (match.group("key").lower(), match.group("value").strip())


def extract_directives(layout: LayoutDoc) -> dict[str, str]:
    """Collect ``{key: value}`` directives that populate song metadata.

    A ``{title: ...}`` (or ``{t: ...}``) sets the title and ``{artist: ...}``
    (or composer/author) sets the artist. Only non-empty values count. Title
    keys are preferred over a subtitle regardless of order.
    """
    found: dict[str, str] = {}
    subtitle = ""
    for page in layout.pages:
        for line in page.lines:
            parsed = _directive_key_value(line.text)
            if not parsed:
                continue
            key, value = parsed
            if not value:
                continue
            if key in _TITLE_KEYS and "title" not in found:
                found["title"] = value
            elif key == "subtitle" and not subtitle:
                subtitle = value
            elif key in _ARTIST_KEYS and "artist" not in found:
                found["artist"] = value
    # A real title wins over a subtitle; a subtitle stands in only if there is
    # no title at all.
    if "title" not in found and subtitle:
        found["title"] = subtitle
    return found


def is_metadata_directive(text: str) -> bool:
    """Return True when a line is a non-empty directive that moves into metadata."""
    parsed = _directive_key_value(text)
    if parsed is None:
        return False
    key, value = parsed
    return bool(value) and key in METADATA_DIRECTIVE_KEYS


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
    if _is_placeholder(raw_title):
        raw_title = ""
    if not raw_title and NO_HEADING_KEY not in layout.metadata:
        raw_title = _largest_text_first_page(layout)

    title, derived_artist = clean_title(raw_title) if raw_title else ("", "")
    if title:
        metadata["title"] = title

    # An explicit document author wins over the artist parsed from the title.
    artist = layout.metadata.get("author", "").strip() or derived_artist
    if _is_placeholder(artist):
        artist = derived_artist
    if artist:
        metadata["artist"] = artist

    return metadata


def _is_placeholder(value: str) -> bool:
    """Return True for known junk metadata values (e.g. "untitled")."""
    return value.strip().lower() in _PLACEHOLDER_VALUES


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
