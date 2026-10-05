"""Pair chord tokens with the lyric characters beneath them.

The rule is geometric and simple: for each chord token, find the lyric
character whose horizontal center is closest to the chord's center, and
insert ``[Chord]`` immediately before that character.
"""

from app.classify import LineLabel, is_chord
from app.geometry import char_x_centers, nearest_char_index, token_positions
from app.ir import TextLine
from app.models import QAReport, SongLine


def merge_chord_lyric(
    chord_label: LineLabel,
    lyric_label: LineLabel,
    qa: QAReport,
) -> SongLine:
    """Insert ``[chord]`` markers into a lyric line at the nearest characters."""
    return merge_chord_lines([chord_label], lyric_label, qa)


def merge_chord_lines(
    chord_labels: list[LineLabel],
    lyric_label: LineLabel,
    qa: QAReport,
) -> SongLine:
    """Merge one or more stacked chord lines into a single lyric line."""
    lyric_text = lyric_label.line.text
    lyric_centers = char_x_centers(lyric_label.line)

    # Bucket chord markers by the character index they are inserted before.
    # Index len(lyric_text) means "append after the whole lyric", used for
    # chords that sit beyond the end of the lyric.
    buckets: dict[int, list[str]] = {}
    # Walk the stack top-to-bottom so, when two chords land on the same
    # character, the one from the higher line appears first (leftmost).
    for chord_label in chord_labels:
        for token, x_center in token_positions(chord_label.line):
            if not is_chord(token):
                continue
            if lyric_centers and x_center > lyric_centers[-1]:
                index = len(lyric_text)
            else:
                index = nearest_char_index(lyric_centers, x_center)
            buckets.setdefault(index, []).append(f"[{token}]")

    # Rebuild the line left-to-right, emitting each character's chords first.
    # Python note for JS/TS readers: strings are immutable, so `result += x`
    # inside a loop copies the whole string every time. Collect the pieces in
    # a list and join once at the end instead.
    parts: list[str] = []
    for position in range(len(lyric_text) + 1):
        parts.extend(buckets.get(position, []))
        if position < len(lyric_text):
            parts.append(lyric_text[position])
    return SongLine(kind="lyric", text="".join(parts))


def chord_only_text(line: TextLine) -> str:
    """Render a chord line that has no lyric beneath it."""
    chords = [token for token, _ in token_positions(line) if is_chord(token)]
    return " ".join(f"[{chord}]" for chord in chords)


def _collect_chord_stack(
    labels: list[LineLabel],
    start: int,
) -> tuple[list[LineLabel], list[LineLabel], int]:
    """Collect a run of chord lines (possibly separated by blanks) and its trailing blanks.

    Blank lines *between* two chord lines are interior to the stack and dropped;
    blank lines *after* the last chord (before the lyric) are trailing and
    returned so the caller can preserve them. Returns the chord labels, the
    trailing blank labels, and the index of the lyric line the stack pairs with.
    """
    chord_labels: list[LineLabel] = []
    trailing_blanks: list[LineLabel] = []
    index = start
    while index < len(labels) and labels[index].kind in ("chord", "blank"):
        if labels[index].kind == "chord":
            # A new chord after blanks means those blanks were interior.
            chord_labels.append(labels[index])
            trailing_blanks = []
        else:
            trailing_blanks.append(labels[index])
        index += 1
    return chord_labels, trailing_blanks, index


def align_page(labels: list[LineLabel], qa: QAReport) -> list[SongLine]:
    """Turn classified lines into ChordPro-ready lines for one page."""
    song_lines: list[SongLine] = []
    index = 0
    while index < len(labels):
        label = labels[index]
        if label.kind == "chord":
            # Collect the whole stack of chord lines above one lyric.
            # classify_page guarantees the stack ends at a lyric line, but
            # check anyway so this public function cannot IndexError on
            # hand-built labels.
            chord_labels, trailing_blanks, index = _collect_chord_stack(labels, index)
            if index >= len(labels):
                # Defensive: a stack with no lyric beneath it. Emit each chord
                # line on its own and record the chords as unpaired.
                for chord_label in chord_labels:
                    song_lines.append(
                        SongLine(kind="chord_only", text=chord_only_text(chord_label.line))
                    )
                    for token, _ in token_positions(chord_label.line):
                        if is_chord(token):
                            qa.unpaired_chords.append(token)
                continue
            song_lines.append(merge_chord_lines(chord_labels, labels[index], qa))
            index += 1
            for _ in trailing_blanks:
                song_lines.append(SongLine(kind="blank", text=""))
        elif label.kind == "chord_only":
            song_lines.append(
                SongLine(kind="chord_only", text=chord_only_text(label.line))
            )
            for token, _ in token_positions(label.line):
                if is_chord(token):
                    qa.unpaired_chords.append(token)
            index += 1
        elif label.kind == "blank":
            song_lines.append(SongLine(kind="blank", text=""))
            index += 1
        else:
            song_lines.append(SongLine(kind="lyric", text=label.line.text))
            index += 1
    return song_lines
