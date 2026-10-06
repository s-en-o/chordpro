import { useEffect, useRef } from "react";

import { parseChordPro, type PreviewLine } from "../chordpro";

interface ChordPreviewProps {
  chordpro: string;
  /** Display line number to highlight and scroll to, or null. */
  highlightLine: number | null;
}

/** Render one parsed line: directives as headings, chords above lyrics. */
function PreviewLineView({ line }: { line: PreviewLine }) {
  if (line.kind === "blank") {
    return <div className="h-4" />;
  }
  if (line.kind === "directive") {
    return (
      <div className="mt-4 font-semibold text-slate-700 dark:text-slate-200">
        {line.text}
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-end">
      {line.segments.map((segment, index) => (
        <span key={index} className="inline-flex flex-col">
          {segment.chord !== null && (
            <span className="font-semibold leading-tight text-brand-600 dark:text-brand-500">
              {segment.chord}
            </span>
          )}
          {/* Preserve spaces so the words stay in their original positions. */}
          <span className="whitespace-pre">{segment.text}</span>
        </span>
      ))}
    </div>
  );
}

/** Show converted ChordPro with chords rendered above their lyrics. */
export default function ChordPreview({ chordpro, highlightLine }: ChordPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll the highlighted line into view when the target changes.
  useEffect(() => {
    if (highlightLine === null || !containerRef.current) {
      return;
    }
    const target = containerRef.current.querySelector(
      `[data-line="${highlightLine}"]`,
    );
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [highlightLine]);

  if (!chordpro.trim()) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Converted ChordPro will appear here.
      </p>
    );
  }

  const lines = parseChordPro(chordpro);
  return (
    <div
      ref={containerRef}
      className="h-[480px] overflow-auto rounded-lg border border-slate-200 bg-white p-4 font-mono text-sm dark:border-slate-800 dark:bg-slate-900"
    >
      {lines.map((line, index) => (
        <div
          key={index}
          data-line={index}
          className={
            index === highlightLine
              ? "-mx-2 rounded bg-amber-100 px-2 dark:bg-amber-900/50"
              : ""
          }
        >
          <PreviewLineView line={line} />
        </div>
      ))}
    </div>
  );
}
