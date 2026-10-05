"""Orchestrate the full conversion from IR to Song."""

from app.align import align_page
from app.chordpro import guess_metadata
from app.classify import classify_page, low_confidence_line_indices
from app.ir import LayoutDoc
from app.models import QAReport, Song, SongLine


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

    return Song(
        lines=song_lines,
        metadata=guess_metadata(layout),
        qa=qa,
    )
