import { useEffect, useState } from "react";

import { convertPdf, type QAReport } from "./api";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [chordpro, setChordpro] = useState<string>("");
  const [qa, setQa] = useState<QAReport | null>(null);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);

  // Keep an object URL for the preview, and clean it up when it changes.
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
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const result = await convertPdf(file);
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
    link.download = (file?.name.replace(/\.pdf$/i, "") ?? "song") + ".cho";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="app">
      <h1>PDF to ChordPro</h1>

      <input
        type="file"
        accept="application/pdf"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
      />
      <button onClick={handleConvert} disabled={!file || busy}>
        {busy ? "Converting…" : "Convert"}
      </button>

      {error && <p className="error">{error}</p>}

      <div className="panes">
        <div className="pane">
          <h2>Original</h2>
          {previewUrl ? (
            <iframe title="PDF preview" src={previewUrl} className="preview" />
          ) : (
            <p className="hint">Choose a PDF to preview it here.</p>
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

      {qa && qa.unpaired_chords.length > 0 && (
        <p className="warning">
          Unpaired chords: {qa.unpaired_chords.join(", ")}
        </p>
      )}
    </main>
  );
}
