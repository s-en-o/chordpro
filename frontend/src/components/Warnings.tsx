import { useEffect, useState } from "react";

import type { QAReport } from "../api";

interface WarningsProps {
  qa: QAReport;
}

/**
 * A dismissible panel summarising the conversion's quality flags: OCR notes,
 * unpaired chords, and low-confidence lines.
 */
export default function Warnings({ qa }: WarningsProps) {
  const [dismissed, setDismissed] = useState(false);

  // A fresh conversion (new qa object) should surface its warnings again.
  useEffect(() => {
    setDismissed(false);
  }, [qa]);

  const hasContent =
    qa.notes.length > 0 ||
    qa.unpaired_chords.length > 0 ||
    qa.low_confidence_lines.length > 0;
  if (!hasContent || dismissed) {
    return null;
  }

  return (
    <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="font-semibold">Review these</p>
          {qa.notes.map((note, index) => (
            <p key={`note-${index}`}>{note}</p>
          ))}
          {qa.unpaired_chords.length > 0 && (
            <p>
              {qa.unpaired_chords.length} unpaired chord
              {qa.unpaired_chords.length === 1 ? "" : "s"}:{" "}
              {qa.unpaired_chords.join(", ")}
            </p>
          )}
          {qa.low_confidence_lines.length > 0 && (
            <p>
              {qa.low_confidence_lines.length} low-confidence line
              {qa.low_confidence_lines.length === 1 ? "" : "s"} to check.
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
