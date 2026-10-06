"""The domain output of the conversion: a Song and its quality report."""

from dataclasses import dataclass, field
from typing import Literal

# The kinds of line a converted song can contain.
LineKind = Literal["lyric", "chord_only", "directive", "blank", "section"]


@dataclass
class SongLine:
    """One line of ChordPro-ready text."""

    kind: LineKind
    text: str
    # Which source IR line this came from (global index across pages), or None
    # for lines we synthesize (e.g. a blank line kept for layout). Used to map
    # source-based QA signals onto output line numbers.
    source_line: int | None = None


@dataclass
class QAReport:
    """Signals surfaced to the UI so the user can spot bad conversions.

    ``low_confidence_lines`` and ``unpaired_chord_lines`` hold *source* line
    numbers when a Song leaves ``convert_layout``; the API calls
    ``map_qa_to_display_lines`` (after overrides) to rewrite them as display
    line numbers in the rendered ChordPro text.
    """

    unpaired_chords: list[str] = field(default_factory=list)
    low_confidence_lines: list[int] = field(default_factory=list)
    unpaired_chord_lines: list[int] = field(default_factory=list)
    # Sections that likely need review (e.g. an empty section with no content).
    section_lines: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Song:
    """A converted song: its lines, metadata, and quality report."""

    lines: list[SongLine] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    qa: QAReport = field(default_factory=QAReport)
    # Internal: set once QA line numbers have been mapped to display numbers.
    qa_mapped: bool = False
