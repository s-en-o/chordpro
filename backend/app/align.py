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
    lyric_text = lyric_label.line.text
    lyric_centers = char_x_centers(lyric_label.line)

    insertions: list[tuple[int, str]] = []
    for token, x_center in token_positions(chord_label.line):
        if not is_chord(token):
            continue
        index = nearest_char_index(lyric_centers, x_center)
        insertions.append((index, f"[{token}]"))

    # Insert from right to left so earlier indices stay valid.
    insertions.sort(key=lambda item: item[0], reverse=True)
    result = lyric_text
    for index, chord_text in insertions:
        result = result[:index] + chord_text + result[index:]
    return SongLine(kind="lyric", text=result)


def chord_only_text(line: TextLine) -> str:
    """Render a chord line that has no lyric beneath it."""
    chords = [token for token, _ in token_positions(line) if is_chord(token)]
    return " ".join(f"[{chord}]" for chord in chords)


def align_page(labels: list[LineLabel], qa: QAReport) -> list[SongLine]:
    """Turn classified lines into ChordPro-ready lines for one page."""
    song_lines: list[SongLine] = []
    index = 0
    while index < len(labels):
        label = labels[index]
        if label.kind == "chord":
            # classify_page guarantees the next line is a lyric.
            next_label = labels[index + 1]
            song_lines.append(merge_chord_lyric(label, next_label, qa))
            index += 2
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
