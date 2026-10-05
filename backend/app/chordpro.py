"""Serialize a Song to ChordPro text and guess metadata."""

from app.ir import LayoutDoc
from app.models import Song


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


def guess_metadata(layout: LayoutDoc) -> dict[str, str]:
    """Best-effort title/artist extraction.

    Prefer the document's own metadata; otherwise fall back to the largest
    text on the first page, which is usually the title.
    """
    metadata: dict[str, str] = {}

    title = layout.metadata.get("title", "").strip()
    if not title:
        title = _largest_text_first_page(layout)
    if title:
        metadata["title"] = title

    artist = layout.metadata.get("author", "").strip()
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
