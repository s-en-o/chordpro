"""The domain output of the conversion: a Song and its quality report."""

from dataclasses import dataclass, field
from typing import Literal

# The kinds of line a converted song can contain.
LineKind = Literal["lyric", "chord_only", "directive", "blank"]


@dataclass
class SongLine:
    """One line of ChordPro-ready text."""

    kind: LineKind
    text: str


@dataclass
class QAReport:
    """Signals surfaced to the UI so the user can spot bad conversions."""

    unpaired_chords: list[str] = field(default_factory=list)
    low_confidence_lines: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Song:
    """A converted song: its lines, metadata, and quality report."""

    lines: list[SongLine] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    qa: QAReport = field(default_factory=QAReport)
