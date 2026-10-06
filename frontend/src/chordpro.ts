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

export type LineKind = "chord" | "directive" | "section" | "blank";

export interface Segment {
  /** The chord to show above this text, or null when there is none. */
  chord: string | null;
  /** The lyric text this chord sits above. */
  text: string;
}

export interface PreviewLine {
  kind: LineKind;
  /** Text of a directive, section, or blank line. */
  text: string;
  /** Chord/lyric segments for a chord line. */
  segments: Segment[];
  /** For a section line: true if it opens an environment. */
  opens?: boolean;
  /** For a section line: true if it closes an environment. */
  closes?: boolean;
}

/** Matches a leading or inline "[Chord]" marker. */
const CHORD_MARKER = /\[([^\]]*)\]/g;

/** Environment open/close directives that mark a section boundary. */
const SECTION_OPEN = /^\{start_of_[a-z_]+\s*:?\s*(?<label>[^}]*)\}$/;
const SECTION_CLOSE = /^\{end_of_[a-z_]+\}$/;

// Short forms, e.g. {soc}/{eoc}. Map to their long names so headings are nice.
const SHORT_ENV: Record<string, string> = {
  soc: "chorus",
  eoc: "chorus",
  sov: "verse",
  eov: "verse",
  sob: "bridge",
  eob: "bridge",
  sot: "tab",
  eot: "tab",
  sog: "grid",
  eog: "grid",
};
const SHORT_OPEN = /^\{(?<key>so[a-z])\}$/;
const SHORT_CLOSE = /^\{(?<key>eo[a-z])\}$/;

/** A bracket section label, e.g. "[Chorus]" or "[Verse 2]". */
const SECTION_LABEL =
  /^\[\s*(intro|verse|chorus|bridge|pre[\s-]?chorus|outro|solo|instrumental|interlude|tag|coda|middle|refrain)([\s\d][\s\d\w-]*)?\]$/i;
/** A brace section label carrying detail, e.g. "{Verse 1}" (not bare "{chorus}"). */
const SECTION_LABEL_BRACE =
  /^\{\s*(intro|verse|chorus|bridge|pre[\s-]?chorus|outro|solo|instrumental|interlude|tag|coda|middle|refrain)[\s\d][\s\d\w-]*\}$/i;

/** True when a line opens a ChordPro section environment (long or short form). */
export function opensEnvironment(text: string): boolean {
  const trimmed = text.trim();
  if (/^\{start_of_[a-z_]+\s*:?\s*[^}]*\}$/.test(trimmed)) return true;
  const short = SHORT_OPEN.exec(trimmed);
  return Boolean(short && SHORT_ENV[short.groups?.key ?? ""]);
}

/** True when a line closes a ChordPro section environment (long or short form). */
export function closesEnvironment(text: string): boolean {
  const trimmed = text.trim();
  if (/^\{end_of_[a-z_]+\}$/.test(trimmed)) return true;
  const short = SHORT_CLOSE.exec(trimmed);
  return Boolean(short && SHORT_ENV[short.groups?.key ?? ""]);
}

/**
 * Turn a section directive into a human heading, or null if it is not one.
 *
 * ``{start_of_chorus}`` -> "Chorus"; ``{comment: Intro}`` -> "Intro";
 * ``{start_of_chorus: Chorus 2}`` -> "Chorus 2"; ``{end_of_chorus}`` -> "".
 */
export function sectionHeading(text: string): string | null {
  const trimmed = text.trim();
  const open = SECTION_OPEN.exec(trimmed);
  if (open) {
    const label = (open.groups?.label ?? "").trim();
    if (label) return label;
    const key = trimmed.slice("{start_of_".length, trimmed.indexOf("}"));
    return key.charAt(0).toUpperCase() + key.slice(1);
  }
  if (SECTION_CLOSE.test(trimmed)) {
    return "";
  }
  // Short forms, e.g. {soc} / {eoc}.
  const shortOpen = SHORT_OPEN.exec(trimmed);
  if (shortOpen && SHORT_ENV[shortOpen.groups?.key ?? ""]) {
    const name = SHORT_ENV[shortOpen.groups!.key];
    return name.charAt(0).toUpperCase() + name.slice(1);
  }
  if (SHORT_CLOSE.test(trimmed)) {
    return "";
  }
  // A comment directive requires a colon, so {comment_italic: ...} is not one.
  const comment = /^\{comment\s*:\s*(?<label>[^}]*)\}$/i.exec(trimmed);
  if (comment) {
    return (comment.groups?.label ?? "").trim();
  }
  // A pre-conversion bracket label such as "[Chorus]" must not render as a
  // chord named "Chorus". A bare brace directive like "{chorus}" is NOT a
  // label (it is the real recall-chorus directive), so it is excluded.
  if (SECTION_LABEL.test(trimmed) || SECTION_LABEL_BRACE.test(trimmed)) {
    return trimmed.slice(1, -1).trim();
  }
  return null;
}

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
  const heading = sectionHeading(line);
  if (heading !== null) {
    // A section open/close or comment directive, or a bare "[Chorus]" label.
    return {
      kind: "section",
      text: heading,
      segments: [],
      opens: opensEnvironment(line),
      closes: closesEnvironment(line),
    };
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

/**
 * Return the `[start, end)` character range of a 0-based line within a text,
 * clamped to the text's actual lines. Used to select a line in the editor.
 */
export function lineCharRange(text: string, line: number): [number, number] {
  const lines = text.split("\n");
  const target = Math.max(0, Math.min(line, lines.length - 1));
  let start = 0;
  for (let i = 0; i < target; i += 1) {
    start += lines[i].length + 1;
  }
  return [start, start + lines[target].length];
}
