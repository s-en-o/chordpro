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
    """Run classification and alignment over every page, then attach metadata.

    The QA line references are recorded as *source* line numbers here; call
    :func:`map_qa_to_display_lines` once the metadata (and any user overrides)
    are final to turn them into display line numbers.
    """
    qa = QAReport()
    song_lines: list[SongLine] = []
    source_offset = 0
    for page in layout.pages:
        # Low-confidence lines are recorded as source line numbers and mapped
        # to display numbers later, once the metadata header is final.
        for line_index in low_confidence_line_indices(page):
            qa.low_confidence_lines.append(source_offset + line_index)
        labels = classify_page(page)
        song_lines.extend(align_page(labels, qa, source_offset=source_offset))
        source_offset += len(page.lines)

    # Drop title/artist directives from the body; they move into metadata.
    song_lines = [line for line in song_lines if not _is_lifted_directive(line)]

    metadata = guess_metadata(layout)
    # An explicit {title: ...} / {artist: ...} directive wins over inference.
    metadata.update(extract_directives(layout))

    return Song(lines=song_lines, metadata=metadata, qa=qa)


def map_qa_to_display_lines(song: Song) -> None:
    """Convert QA *source* line numbers into display line numbers, in place.

    Must run after metadata is final (including user overrides), because the
    metadata header shifts every body line down. ``qa.unpaired_chord_lines``
    and ``qa.low_confidence_lines`` hold source line numbers on entry and
    display line numbers on return. Safe to call more than once: a private
    flag on the song makes repeat calls no-ops.
    """
    if song.qa_mapped:
        return
    song.qa_mapped = True

    header = header_line_count(song.metadata)
    source_to_body = {
        line.source_line: body_index
        for body_index, line in enumerate(song.lines)
        if line.source_line is not None
    }
    song.qa.low_confidence_lines = [
        header + source_to_body[source]
        for source in song.qa.low_confidence_lines
        if source in source_to_body
    ]
    song.qa.unpaired_chord_lines = [
        header + source_to_body[source]
        for source in song.qa.unpaired_chord_lines
        if source in source_to_body
    ]
