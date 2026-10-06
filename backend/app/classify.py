"""Decide which lines are chords and which are lyrics.

The primary signal is the shape of the tokens themselves (does each token
look like a chord symbol?), not the font. That keeps this module usable for
future pasted-text or OCR sources that have no reliable font metadata.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.chordpro import section_label
from app.ir import Page, TextLine

# A permissive chord grammar: root note, optional accidental, optional
# quality/extension, optional altered tensions, optional slash bass. Kept as a
# module constant so it can be tuned or exposed as configuration later.
CHORD_REGEX = re.compile(
    r"""
    \A
    [A-G]                                     # root note A..G
    (?:\#|b)?                                 # optional sharp or flat
    (?:maj|min|m|M|sus|dim|aug|add|°|ø|\+|-)?  # optional quality word
    (?:sus\d|add\d+|\d+|no\d+|b\d+|\#\d+)*    # extensions, tensions, alterations
    (?:/[A-G](?:\#|b)?)?                      # optional slash bass note
    \Z
    """,
    re.VERBOSE,
)

# Punctuation that can trail a chord token in running text, e.g. "B7,".
_TRAILING_PUNCTUATION = ",.;:"

DEFAULT_CHORD_THRESHOLD = 0.5
DEFAULT_GAP_FACTOR = 2.5

LineKind = Literal["chord", "chord_only", "lyric", "blank", "directive", "section"]


@dataclass
class LineLabel:
    """A line plus the role we assigned it."""

    line: TextLine
    kind: LineKind
    # Position of this line within the page, used to trace output lines back to
    # their source. Defaults to -1 for hand-built labels in tests.
    page_index: int = -1


def is_chord(token: str) -> bool:
    """Return True when a token looks like a chord symbol."""
    candidate = token.strip("()").strip(_TRAILING_PUNCTUATION)
    return bool(CHORD_REGEX.match(candidate))


def chord_ratio(line: TextLine) -> float:
    """Return the fraction of tokens on a line that look like chords."""
    tokens = line.text.split()
    if not tokens:
        return 0.0
    chord_count = 0
    for token in tokens:
        if is_chord(token):
            chord_count += 1
    return chord_count / len(tokens)


def low_confidence_line_indices(
    page: Page,
    chord_threshold: float = DEFAULT_CHORD_THRESHOLD,
) -> list[int]:
    """Return indices of ambiguous lines: some chord tokens, but below threshold.

    A line with a chord ratio strictly between 0 and the threshold might be a
    chord line we mislabeled as a lyric (or a lyric containing a word that looks
    like a chord). We surface these so the user can review them.
    """
    result: list[int] = []
    for index, line in enumerate(page.lines):
        ratio = chord_ratio(line)
        if 0.0 < ratio < chord_threshold:
            result.append(index)
    return result


def _median_line_height(page: Page) -> float:
    """Return the median height of non-empty lines, used to scale the gap test."""
    heights = sorted(line.height for line in page.lines if line.height > 0)
    if not heights:
        return 0.0
    return heights[len(heights) // 2]


def classify_page(
    page: Page,
    chord_threshold: float = DEFAULT_CHORD_THRESHOLD,
    gap_factor: float = DEFAULT_GAP_FACTOR,
) -> list[LineLabel]:
    """Label every line on a page as chord, chord_only, lyric, or blank.

    A line whose tokens are mostly chords is a chord *candidate*. It becomes
    a real chord line only when a lyric line sits directly beneath it and the
    vertical gap is small; otherwise it becomes a chord-only line (chords with
    no lyrics under them).
    """
    labels: list[LineLabel] = []
    for page_index, line in enumerate(page.lines):
        if not line.text.strip():
            labels.append(LineLabel(line=line, kind="blank", page_index=page_index))
        elif line.text.lstrip().startswith("{"):
            # A ChordPro directive like {title: ...} is metadata, not content;
            # it must not be paired with a chord or treated as a lyric.
            labels.append(LineLabel(line=line, kind="directive", page_index=page_index))
        elif section_label(line.text) is not None:
            # A section label like [Chorus] or [Verse 2] is a heading, not a
            # chord or a lyric line.
            labels.append(LineLabel(line=line, kind="section", page_index=page_index))
        elif chord_ratio(line) >= chord_threshold:
            labels.append(LineLabel(line=line, kind="chord", page_index=page_index))
        else:
            labels.append(LineLabel(line=line, kind="lyric", page_index=page_index))

    median_height = _median_line_height(page)
    max_gap = gap_factor * median_height

    # Walk bottom-up so a chord line can tell whether the line below it is a
    # lyric OR another valid chord (a chord stack). A candidate stays a real
    # "chord" only if that line below is a lyric or a valid chord within the
    # gap; otherwise it becomes a chord-only line.
    for index in range(len(labels) - 1, -1, -1):
        label = labels[index]
        if label.kind != "chord":
            continue
        below_index = index + 1
        while below_index < len(labels) and labels[below_index].kind == "blank":
            below_index += 1
        if below_index >= len(labels):
            label.kind = "chord_only"
            continue
        below = labels[below_index]
        vertical_gap = below.line.y0 - label.line.y1
        if vertical_gap > max_gap or below.kind not in ("lyric", "chord"):
            label.kind = "chord_only"

    return labels
