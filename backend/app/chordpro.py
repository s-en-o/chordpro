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

# A section label like "[Chorus]", "{Verse 2}", "[Bridge - Sax break]". We
# capture the whole contents, then normalize in code (so "Pre-Chorus" survives).
_SECTION_LABEL = re.compile(r"^[\[{]\s*(?P<inner>.+?)\s*[\]}]\s*$")

# Section names we recognize as sections (not chords or lyrics). Keys are the
# normalized name; values are the ChordPro environment name when one exists,
# or None when the section has no environment and should become a comment.
_SECTION_ENVIRONMENTS: dict[str, str | None] = {
    "verse": "verse",
    "chorus": "chorus",
    "bridge": "bridge",
    "intro": None,
    "outro": None,
    "solo": None,
    "instrumental": None,
    "interlude": None,
    "pre-chorus": None,
    "tag": None,
    "coda": None,
    "middle": None,
    "refrain": None,
}


def section_label(text: str) -> str | None:
    """Return the normalized section name for a label line, else None.

    Recognizes bracket/brace labels like ``[Chorus]``, ``{Verse 2}``,
    ``[Bridge - Sax break]`` and ``[Outro tag]``. Real chords (``[C]``,
    ``[Am]``), metadata directives (``{title: ...}``) and ordinary lyrics
    return None. Any trailing detail after the section name is ignored.
    """
    stripped = text.strip()
    if not stripped:
        return None
    # A directive with a colon and value is metadata, never a section label.
    if ":" in stripped and "{" in stripped:
        return None
    match = _SECTION_LABEL.match(stripped)
    if not match:
        return None
    inner = match.group("inner").strip()
    # A BARE brace form like "{chorus}"/"{verse}"/"{tag}" is a real ChordPro
    # directive (e.g. recall-chorus, or the tag metadata item), not a section
    # label. Only a brace form carrying a label/detail ("{Verse 1}", "{Chorus 2}")
    # is treated as a section. Bracket forms ("[Chorus]") are always labels,
    # since a real chord would be "[C]" and not a section word.
    is_brace = stripped.startswith("{")
    if is_brace and " " not in inner and not any(c.isdigit() for c in inner):
        return None
    normalized = " ".join(inner.split()).lower()
    # A colon always separates trailing detail; a dash only when spaced, so the
    # hyphen inside "pre-chorus" survives.
    normalized = re.split(r"\s*:\s*|\s+[-–]\s+", normalized)[0].strip()
    # Normalize "pre chorus"/"pre-chorus" and match the leading section word.
    normalized = re.sub(r"\bpre[\s-]+chorus\b", "pre-chorus", normalized)
    for name in _SECTION_NAMES_BY_LENGTH:
        if normalized == name or normalized.startswith(name + " ") or (
            normalized.startswith(name) and normalized[len(name)].isdigit()
        ):
            return name
    return None


# Section names sorted longest-first so "pre-chorus" matches before "chorus".
_SECTION_NAMES_BY_LENGTH = sorted(_SECTION_ENVIRONMENTS, key=len, reverse=True)


def section_directives(text: str) -> tuple[str, str | None]:
    """Return ``(open, close)`` ChordPro directives for a section label.

    verse/chorus/bridge become bare environments (``{start_of_verse}`` /
    ``{end_of_verse}``). Sections with no ChordPro environment become a single
    ``{comment: <label>}`` line, with no close directive.
    """
    name = section_label(text)
    if name is None:
        raise ValueError(f"not a section label: {text!r}")
    environment = _SECTION_ENVIRONMENTS[name]
    if environment is None:
        label_text = _label_display_text(text)
        return (f"{{comment: {label_text}}}", None)
    return (f"{{start_of_{environment}}}", f"{{end_of_{environment}}}")


def _label_display_text(text: str) -> str:
    """Return the inner text of a section label, e.g. "[Outro]" -> "Outro"."""
    return text.strip()[1:-1].strip()

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


def header_line_count(metadata: dict[str, str]) -> int:
    """Number of lines serialize() emits before the body.

    One line per non-empty metadata entry, plus a blank separator line when
    there is any metadata. This lets QA line numbers line up with the text the
    user sees.
    """
    entries = sum(1 for value in metadata.values() if value)
    return entries + 1 if entries else 0


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
    # A placeholder in either spot is discarded rather than emitted.
    author = layout.metadata.get("author", "").strip()
    artist = author if author and not _is_placeholder(author) else derived_artist
    if _is_placeholder(artist):
        artist = ""
    if artist:
        metadata["artist"] = artist

    return metadata


def _is_placeholder(value: str) -> bool:
    """Return True for known junk metadata values (e.g. "untitled").

    The match is exact on a small known set, so a song genuinely titled
    "Unknown" would be dropped — an accepted trade-off, since such a title is
    far more likely to be tool-generated filler.
    """
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
        if section_label(line.text) is not None:
            # A section heading is not the song title.
            continue
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
