"""Orchestrate the full conversion from IR to Song."""

from app.align import align_page
from app.chordpro import guess_metadata
from app.classify import classify_page
from app.ir import LayoutDoc
from app.models import QAReport, Song


def convert_layout(layout: LayoutDoc) -> Song:
    """Run classification and alignment over every page, then attach metadata."""
    qa = QAReport()
    song_lines = []
    for page in layout.pages:
        labels = classify_page(page)
        song_lines.extend(align_page(labels, qa))

    return Song(
        lines=song_lines,
        metadata=guess_metadata(layout),
        qa=qa,
    )
