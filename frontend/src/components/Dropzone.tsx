import { useRef, useState, type DragEvent } from "react";

interface DropzoneProps {
  file: File | null;
  onFile: (file: File | null) => void;
}

/** Format a byte count as a short human-readable size. */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * A drag-and-drop target for choosing a PDF, with click-to-browse as a
 * fallback. Reports the chosen file (or null when cleared) to the parent.
 */
export default function Dropzone({ file, onFile }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  // Count enter/leave events so moving over child elements does not flicker.
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0] ?? null;
    if (dropped) {
      onFile(dropped);
    }
  }

  return (
    <div
      onDragEnter={(event) => {
        event.preventDefault();
        dragDepth.current += 1;
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => {
        dragDepth.current -= 1;
        if (dragDepth.current <= 0) {
          dragDepth.current = 0;
          setDragging(false);
        }
      }}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={[
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center transition",
        dragging
          ? "border-brand-500 bg-brand-50 dark:bg-slate-800"
          : "border-slate-300 hover:border-brand-500 dark:border-slate-700",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(event) => onFile(event.target.files?.[0] ?? null)}
      />
      {file ? (
        <>
          <p className="font-medium">{file.name}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {formatSize(file.size)}
          </p>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onFile(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="text-sm font-medium text-brand-600 underline dark:text-brand-500"
          >
            Choose a different file
          </button>
        </>
      ) : (
        <>
          <p className="font-medium">Drop a PDF here</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            or click to browse
          </p>
        </>
      )}
    </div>
  );
}
