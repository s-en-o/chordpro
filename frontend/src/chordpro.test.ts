import { describe, expect, it } from "vitest";

import {
  lineCharRange,
  parseChordPro,
  parseLine,
  segmentsToText,
} from "./chordpro";

describe("parseLine", () => {
  it("splits inline chords from the lyric that follows", () => {
    const line = parseLine("[C]Hello [G]world");
    expect(line.kind).toBe("chord");
    expect(line.segments).toEqual([
      { chord: "C", text: "Hello " },
      { chord: "G", text: "world" },
    ]);
  });

  it("keeps a chord with no lyric after it", () => {
    const line = parseLine("[C]");
    expect(line.segments).toEqual([{ chord: "C", text: "" }]);
  });

  it("keeps leading text that has no chord", () => {
    const line = parseLine("Hello [C]world");
    expect(line.segments).toEqual([
      { chord: null, text: "Hello " },
      { chord: "C", text: "world" },
    ]);
  });

  it("handles a chord-only line with several chords", () => {
    const line = parseLine("[C] [G]");
    expect(line.segments).toEqual([
      { chord: "C", text: " " },
      { chord: "G", text: "" },
    ]);
  });

  it("treats a directive line as its own kind", () => {
    const line = parseLine("{title: My Song}");
    expect(line.kind).toBe("directive");
    expect(line.text).toBe("{title: My Song}");
  });

  it("treats a blank line as its own kind", () => {
    expect(parseLine("").kind).toBe("blank");
    expect(parseLine("   ").kind).toBe("blank");
  });

  it("leaves a plain lyric line as a single segment", () => {
    const line = parseLine("just a lyric");
    expect(line.segments).toEqual([{ chord: null, text: "just a lyric" }]);
  });

  it("keeps text between two chords", () => {
    const line = parseLine("[C]one[G]two");
    expect(line.segments).toEqual([
      { chord: "C", text: "one" },
      { chord: "G", text: "two" },
    ]);
    expect(segmentsToText(line.segments)).toBe("[C]one[G]two");
  });

  it("tolerates an empty chord marker", () => {
    // "[]" is unusual but must not crash; it becomes an empty chord segment.
    const line = parseLine("[]word");
    expect(segmentsToText(line.segments)).toBe("[]word");
  });

  it("strips a trailing carriage return", () => {
    const line = parseLine("[C]Hello\r");
    expect(line.segments).toEqual([{ chord: "C", text: "Hello" }]);
  });
});

describe("parseChordPro", () => {
  it("parses every line and drops a trailing newline", () => {
    const lines = parseChordPro("[C]Hello\n[G]world\n");
    expect(lines).toHaveLength(2);
    expect(lines[0].segments[0]).toEqual({ chord: "C", text: "Hello" });
    expect(lines[1].segments[0]).toEqual({ chord: "G", text: "world" });
  });

  it("keeps blank lines between stanzas", () => {
    const lines = parseChordPro("[C]one\n\n[G]two");
    expect(lines.map((line) => line.kind)).toEqual(["chord", "blank", "chord"]);
  });
});

describe("segmentsToText", () => {
  it("round-trips inline chords", () => {
    const original = "[C]Hello [G]world";
    expect(segmentsToText(parseLine(original).segments)).toBe(original);
  });

  it("round-trips a leading-chord-free line", () => {
    const original = "Hello [C]world";
    expect(segmentsToText(parseLine(original).segments)).toBe(original);
  });

  it("round-trips a lone trailing chord", () => {
    expect(segmentsToText(parseLine("[Am]").segments)).toBe("[Am]");
  });
});

describe("lineCharRange", () => {
  it("returns the range of the first line", () => {
    expect(lineCharRange("abc\ndef", 0)).toEqual([0, 3]);
  });

  it("returns the range of a later line", () => {
    // "abc\n" is 4 chars, so "def" starts at index 4.
    expect(lineCharRange("abc\ndef", 1)).toEqual([4, 7]);
  });

  it("clamps an out-of-range line to the last line", () => {
    expect(lineCharRange("abc\ndef", 99)).toEqual([4, 7]);
  });

  it("clamps a negative line to the first line", () => {
    expect(lineCharRange("abc\ndef", -3)).toEqual([0, 3]);
  });
});
