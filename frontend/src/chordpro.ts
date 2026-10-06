/**
 * Parsing for the ChordPro preview.
 *
 * The converter produces lines where chords are inline in square brackets,
 * e.g. "[C]Hello [G]world". To render chords above their lyrics we split each
 * line into segments, pairing each chord with the text that follows it.
 *
 * This module is deliberately pure (no React, no DOM) so it can be unit
 * tested on its own.
 */

export type LineKind = "chord" | "directive" | "blank";

export interface Segment {
  /** The chord to show above this text, or null when there is none. */
  chord: string | null;
  /** The lyric text this chord sits above. */
  text: string;
}

export interface PreviewLine {
  kind: LineKind;
  /** Text of a directive or blank line (used for directives). */
  text: string;
  /** Chord/lyric segments for a chord line. */
  segments: Segment[];
}

/** Matches a leading or inline "[Chord]" marker. */
const CHORD_MARKER = /\[([^\]]*)\]/g;

/**
 * Parse one ChordPro line into a structure the preview can render.
 *
 * A directive line (starting with "{") and a blank line are their own kinds;
 * everything else is treated as a chord line and split into segments.
 */
export function parseLine(rawLine: string): PreviewLine {
  const line = rawLine.replace(/\r$/, "");

  if (line.trim() === "") {
    return { kind: "blank", text: "", segments: [] };
  }
  if (line.trimStart().startsWith("{")) {
    return { kind: "directive", text: line, segments: [] };
  }

  const segments: Segment[] = [];
  let lastIndex = 0;
  let pendingChord: string | null = null;
  let match: RegExpExecArray | null;

  CHORD_MARKER.lastIndex = 0;
  while ((match = CHORD_MARKER.exec(line)) !== null) {
    const textBefore = line.slice(lastIndex, match.index);
    if (pendingChord !== null) {
      // A chord always renders above the text that follows it.
      segments.push({ chord: pendingChord, text: textBefore });
      pendingChord = null;
    } else if (textBefore !== "") {
      // Leading text with no chord (spaces at the start of a line).
      segments.push({ chord: null, text: textBefore });
    }
    pendingChord = match[1];
    lastIndex = match.index + match[0].length;
  }

  const textAfter = line.slice(lastIndex);
  if (pendingChord !== null) {
    // A trailing chord with no lyric after it (e.g. "[C]" alone on a line).
    segments.push({ chord: pendingChord, text: textAfter });
  } else if (textAfter !== "") {
    segments.push({ chord: null, text: textAfter });
  }

  if (segments.length === 0) {
    // A line that was only empty brackets, or otherwise produced nothing.
    segments.push({ chord: null, text: line });
  }

  return { kind: "chord", text: line, segments };
}

/** Parse a whole ChordPro document into preview lines. */
export function parseChordPro(chordpro: string): PreviewLine[] {
  return chordpro.replace(/\n$/, "").split("\n").map(parseLine);
}

/** Render preview lines back to a plain string (used to test round-tripping). */
export function segmentsToText(segments: Segment[]): string {
  return segments
    .map((segment) => (segment.chord === null ? "" : `[${segment.chord}]`) + segment.text)
    .join("");
}
