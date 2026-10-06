"""Orchestrate the full conversion from IR to Song."""

from app.align import align_page
from app.chordpro import (
    extract_directives,
    guess_metadata,
    header_line_count,
    is_metadata_directive,
)
from app.classify import classify_page, low_confidence_line_indices
from app.ir import LayoutDoc
from app.models import QAReport, Song, SongLine


def _is_lifted_directive(line: SongLine) -> bool:
    """Return True when a directive line was lifted into metadata."""
    return line.kind == "directive" and is_metadata_directive(line.text)


def convert_layout(layout: LayoutDoc) -> Song:
    """Run classification and alignment over every page, then attach metadata."""
    qa = QAReport()
    song_lines: list[SongLine] = []
    # Global source line numbers flagged as low-confidence (across all pages).
    low_confidence_sources: list[int] = []
    source_offset = 0
    for page in layout.pages:
        for line_index in low_confidence_line_indices(page):
            low_confidence_sources.append(source_offset + line_index)
        labels = classify_page(page)
        song_lines.extend(align_page(labels, qa, source_offset=source_offset))
        source_offset += len(page.lines)

    # Drop title/artist directives from the body; they move into metadata.
    song_lines = [line for line in song_lines if not _is_lifted_directive(line)]

    metadata = guess_metadata(layout)
    # An explicit {title: ...} / {artist: ...} directive wins over inference.
    metadata.update(extract_directives(layout))

    # Translate source line numbers into display line numbers (body index plus
    # the metadata header that serialize() emits).
    header = header_line_count(metadata)
    source_to_body = {
        line.source_line: body_index
        for body_index, line in enumerate(song_lines)
        if line.source_line is not None
    }
    qa.low_confidence_lines = [
        header + source_to_body[source]
        for source in low_confidence_sources
        if source in source_to_body
    ]
    qa.unpaired_chord_lines = [
        header + source_to_body[source]
        for source in qa.unpaired_chord_lines
        if source in source_to_body
    ]

    return Song(lines=song_lines, metadata=metadata, qa=qa)
