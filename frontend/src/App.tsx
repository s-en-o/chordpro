import { useEffect, useState } from "react";

import { convertPdf, convertText, type QAReport } from "./api";

type Mode = "pdf" | "text";

export default function App() {
  const [mode, setMode] = useState<Mode>("pdf");
  const [file, setFile] = useState<File | null>(null);
  const [pastText, setPastText] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [chordpro, setChordpro] = useState<string>("");
  const [qa, setQa] = useState<QAReport | null>(null);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);

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

  async function handleConvert() {
    setBusy(true);
    setError("");
    try {
      const result =
        mode === "pdf" && file
          ? await convertPdf(file)
          : await convertText(pastText);
      setChordpro(result.chordpro);
      setQa(result.qa);
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
      mode === "pdf"
        ? (file?.name.replace(/\.pdf$/i, "") ?? "song")
        : "song";
    link.download = baseName + ".cho";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  const canConvert = mode === "pdf" ? Boolean(file) : pastText.trim().length > 0;

  return (
    <main className="app">
      <h1>ChordPro Converter</h1>

      <div className="tabs">
        <button
          className={mode === "pdf" ? "tab active" : "tab"}
          onClick={() => setMode("pdf")}
        >
          PDF
        </button>
        <button
          className={mode === "text" ? "tab active" : "tab"}
          onClick={() => setMode("text")}
        >
          Paste text
        </button>
      </div>

      <button onClick={handleConvert} disabled={!canConvert || busy}>
        {busy ? "Converting…" : "Convert"}
      </button>

      {error && <p className="error">{error}</p>}

      <div className="panes">
        <div className="pane">
          <h2>Original</h2>
          {mode === "pdf" ? (
            <>
              <input
                type="file"
                accept="application/pdf"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setChordpro("");
                  setQa(null);
                  setError("");
                }}
              />
              {previewUrl ? (
                <iframe title="PDF preview" src={previewUrl} className="preview" />
              ) : (
                <p className="hint">Choose a PDF to preview it here.</p>
              )}
            </>
          ) : (
            <textarea
              className="editor"
              value={pastText}
              onChange={(event) => setPastText(event.target.value)}
              placeholder={"Paste a chord sheet here.\n\nC     G\nHello world"}
            />
          )}
        </div>

        <div className="pane">
          <h2>ChordPro</h2>
          <textarea
            className="editor"
            value={chordpro}
            onChange={(event) => setChordpro(event.target.value)}
            placeholder="Converted ChordPro will appear here."
          />
          <button onClick={handleDownload} disabled={!chordpro}>
            Download .cho
          </button>
        </div>
      </div>

      {qa && qa.notes.length > 0 && (
        <p className="warning">{qa.notes.join(" ")}</p>
      )}

      {qa && qa.unpaired_chords.length > 0 && (
        <p className="warning">
          Unpaired chords: {qa.unpaired_chords.join(", ")}
        </p>
      )}

      {qa && qa.low_confidence_lines.length > 0 && (
        <p className="warning">
          Low-confidence lines: {qa.low_confidence_lines.join(", ")}
        </p>
      )}
    </main>
  );
}
