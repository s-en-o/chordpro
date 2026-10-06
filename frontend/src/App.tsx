import { useEffect, useRef, useState } from "react";

import { convertPdf, convertText, type Metadata, type QAReport } from "./api";
import { lineCharRange } from "./chordpro";
import ChordPreview from "./components/ChordPreview";
import Dropzone from "./components/Dropzone";
import ThemeToggle from "./components/ThemeToggle";
import Warnings from "./components/Warnings";

type Mode = "pdf" | "text";
type OutputView = "edit" | "preview";

export default function App() {
  const [mode, setMode] = useState<Mode>("pdf");
  const [file, setFile] = useState<File | null>(null);
  const [pastText, setPastText] = useState<string>("");
  const [title, setTitle] = useState<string>("");
  const [artist, setArtist] = useState<string>("");
  const [suggested, setSuggested] = useState<Metadata>({});
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [chordpro, setChordpro] = useState<string>("");
  const [qa, setQa] = useState<QAReport | null>(null);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const [view, setView] = useState<OutputView>("edit");
  const [copied, setCopied] = useState<boolean>(false);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [edited, setEdited] = useState<boolean>(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editRef = useRef<HTMLTextAreaElement>(null);

  // Keep an object URL for the PDF preview, and clean it up when it changes.
  useEffect(() => {
    if (!file) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Clear any pending timers when the component unmounts.
  useEffect(() => {
    return () => {
      if (copyTimer.current !== null) clearTimeout(copyTimer.current);
      if (highlightTimer.current !== null) clearTimeout(highlightTimer.current);
    };
  }, []);

  async function handleConvert() {
    setBusy(true);
    setError("");
    try {
      const result =
        mode === "pdf" && file
          ? await convertPdf(file, { title, artist })
          : await convertText(pastText, { title, artist });
      setChordpro(result.chordpro);
      setQa(result.qa);
      setEdited(false);
      // Remember what was detected so the download name survives clearing the
      // input fields below.
      setSuggested(result.metadata);
      // The fields were sent as overrides; clear them so the next conversion
      // starts fresh (the converted output keeps the title/artist header).
      setTitle("");
      setArtist("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Conversion failed");
    } finally {
      setBusy(false);
    }
  }

  function handleDownload() {
    const blob = new Blob([chordpro], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const baseName =
      (title.trim() ||
        suggested.title ||
        (mode === "pdf" ? file?.name.replace(/\.pdf$/i, "") : "")) ||
      "song";
    const safeName = baseName.replace(/[\\/:*?"<>|]+/g, "-");
    link.download = safeName + ".cho";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(chordpro);
      setCopied(true);
      if (copyTimer.current !== null) {
        clearTimeout(copyTimer.current);
      }
      copyTimer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("Could not copy to the clipboard.");
    }
  }

  function resetResult() {
    setChordpro("");
    setQa(null);
    setError("");
    setCopied(false);
    setSuggested({});
    setHighlightLine(null);
    setEdited(false);
  }

  /**
   * Jump to a display line number in the output. In Preview the line is
   * highlighted and scrolled into view; in Edit the textarea selects and
   * scrolls to it. The highlight clears itself after a moment.
   */
  function jumpToLine(line: number) {
    setHighlightLine(line);
    if (editRef.current) {
      const field = editRef.current;
      const target = Math.max(0, Math.min(line, chordpro.split("\n").length - 1));
      const [start, end] = lineCharRange(chordpro, line);
      field.focus();
      field.setSelectionRange(start, end);
      // Scroll so the target line sits near the middle of the textarea.
      const lineHeight = parseFloat(getComputedStyle(field).lineHeight) || 20;
      field.scrollTop = Math.max(0, target * lineHeight - field.clientHeight / 2);
    }
    if (highlightTimer.current !== null) {
      clearTimeout(highlightTimer.current);
    }
    highlightTimer.current = setTimeout(() => setHighlightLine(null), 2500);
  }

  function startOver() {
    setFile(null);
    setPastText("");
    setTitle("");
    setArtist("");
    resetResult();
  }

  const canConvert =
    mode === "pdf" ? Boolean(file) : pastText.trim().length > 0;

  const tabClass = (active: boolean) =>
    [
      "rounded-md px-4 py-2 text-sm font-medium transition",
      active
        ? "bg-brand-600 text-white"
        : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800",
    ].join(" ");

  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">ChordPro Converter</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Turn chord sheets into ChordPro — from a PDF or pasted text.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <div className="mb-4 inline-flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-900">
        <button
          aria-pressed={mode === "pdf"}
          className={tabClass(mode === "pdf")}
          onClick={() => { setMode("pdf"); resetResult(); }}
        >
          PDF
        </button>
        <button
          aria-pressed={mode === "text"}
          className={tabClass(mode === "text")}
          onClick={() => { setMode("text"); resetResult(); }}
        >
          Paste text
        </button>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm font-medium">
              Title
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="(optional)"
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-normal outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium">
              Artist
              <input
                type="text"
                value={artist}
                onChange={(event) => setArtist(event.target.value)}
                placeholder="(optional)"
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-normal outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
          </div>
          <button
            onClick={handleConvert}
            disabled={!canConvert || busy}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy && (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            )}
            {busy ? "Converting…" : "Convert"}
          </button>
        </div>
      </section>

      {error && (
        <p className="mt-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Original
          </h2>
          {mode === "pdf" ? (
            <>
              <Dropzone
                file={file}
                onFile={(chosen) => {
                  setFile(chosen);
                  resetResult();
                }}
              />
              {previewUrl ? (
                <iframe
                  title="PDF preview"
                  src={previewUrl}
                  className="h-[420px] w-full rounded-lg border border-slate-200 dark:border-slate-800"
                />
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  A preview will appear here once you choose a PDF.
                </p>
              )}
            </>
          ) : (
            <textarea
              value={pastText}
              onChange={(event) => {
                setPastText(event.target.value);
                resetResult();
              }}
              placeholder={"Paste a chord sheet here.\n\nC     G\nHello world"}
              className="h-[480px] w-full resize-y rounded-lg border border-slate-200 bg-white p-3 font-mono text-sm outline-none focus:border-brand-500 dark:border-slate-800 dark:bg-slate-900"
            />
          )}
        </section>

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              ChordPro
            </h2>
            <div className="inline-flex gap-1 rounded-md bg-slate-100 p-0.5 text-xs dark:bg-slate-900">
              <button
                aria-pressed={view === "edit"}
                className={`rounded px-2 py-1 ${view === "edit" ? "bg-white shadow dark:bg-slate-700" : ""}`}
                onClick={() => setView("edit")}
              >
                Edit
              </button>
              <button
                aria-pressed={view === "preview"}
                className={`rounded px-2 py-1 ${view === "preview" ? "bg-white shadow dark:bg-slate-700" : ""}`}
                onClick={() => setView("preview")}
              >
                Preview
              </button>
            </div>
          </div>

          {view === "edit" ? (
            <textarea
              ref={editRef}
              value={chordpro}
              onChange={(event) => {
                setChordpro(event.target.value);
                // Line numbers in the QA report no longer match an edited
                // document, so the jump chips are disabled.
                setEdited(true);
              }}
              placeholder="Converted ChordPro will appear here."
              className="h-[480px] w-full resize-y rounded-lg border border-slate-200 bg-white p-3 font-mono text-sm outline-none focus:border-brand-500 dark:border-slate-800 dark:bg-slate-900"
            />
          ) : (
            <ChordPreview chordpro={chordpro} highlightLine={highlightLine} />
          )}

          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleDownload}
              disabled={!chordpro}
              className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Download .cho
            </button>
            <button
              onClick={handleCopy}
              disabled={!chordpro}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
            <button
              onClick={startOver}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium transition hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              Start over
            </button>
          </div>
        </section>
      </div>

      {qa && <Warnings qa={qa} onJump={jumpToLine} jumpsDisabled={edited} />}
    </div>
  );
}
