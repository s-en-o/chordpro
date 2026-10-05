"""Orchestrate the full conversion from IR to Song."""

from app.align import align_page
from app.chordpro import extract_directives, guess_metadata, is_metadata_directive
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
    source_offset = 0
    for page in layout.pages:
        for line_index in low_confidence_line_indices(page):
            qa.low_confidence_lines.append(source_offset + line_index)
        source_offset += len(page.lines)
        labels = classify_page(page)
        song_lines.extend(align_page(labels, qa))

    # Drop title/artist directives from the body; they move into metadata.
    song_lines = [line for line in song_lines if not _is_lifted_directive(line)]

    metadata = guess_metadata(layout)
    # An explicit {title: ...} / {artist: ...} directive wins over inference.
    metadata.update(extract_directives(layout))

    return Song(lines=song_lines, metadata=metadata, qa=qa)
