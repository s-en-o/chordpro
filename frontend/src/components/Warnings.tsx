import { useEffect, useState } from "react";

import type { QAReport } from "../api";

interface WarningsProps {
  qa: QAReport;
  /** Jump to (and highlight) a display line number in the output. */
  onJump: (line: number) => void;
}

/** A clickable "line N" chip that jumps to that output line. */
function LineChip({ line, onJump }: { line: number; onJump: (n: number) => void }) {
  return (
    <button
      type="button"
      onClick={() => onJump(line)}
      className="rounded border border-amber-400 bg-amber-100 px-1.5 py-0.5 font-mono text-xs text-amber-900 transition hover:bg-amber-200 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-100 dark:hover:bg-amber-800"
      title={`Jump to line ${line}`}
    >
      line {line}
    </button>
  );
}

/**
 * A dismissible panel summarising the conversion's quality flags: OCR notes,
 * unpaired chords, and low-confidence lines. Line references are clickable,
 * so the user can jump straight to each spot in the output.
 */
export default function Warnings({ qa, onJump }: WarningsProps) {
  const [dismissed, setDismissed] = useState(false);

  // A fresh conversion (new qa object) should surface its warnings again.
  useEffect(() => {
    setDismissed(false);
  }, [qa]);

  const hasContent =
    qa.notes.length > 0 ||
    qa.low_confidence_lines.length > 0 ||
    qa.unpaired_chord_lines.length > 0;
  if (!hasContent || dismissed) {
    return null;
  }

  return (
    <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="font-semibold">Review these</p>
          {qa.notes.map((note, index) => (
            <p key={`note-${index}`}>{note}</p>
          ))}
          {qa.low_confidence_lines.length > 0 && (
            <p className="flex flex-wrap items-center gap-1">
              <span>Low-confidence lines:</span>
              {qa.low_confidence_lines.map((line) => (
                <LineChip key={`lc-${line}`} line={line} onJump={onJump} />
              ))}
            </p>
          )}
          {qa.unpaired_chord_lines.length > 0 && (
            <p className="flex flex-wrap items-center gap-1">
              <span>
                Unpaired chord{qa.unpaired_chord_lines.length === 1 ? "" : "s"}:
              </span>
              {qa.unpaired_chord_lines.map((line) => (
                <LineChip key={`uc-${line}`} line={line} onJump={onJump} />
              ))}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="shrink-0 rounded p-1 text-amber-700 hover:bg-amber-100 dark:text-amber-200 dark:hover:bg-amber-900"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
