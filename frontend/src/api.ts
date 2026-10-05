export interface QAReport {
  unpaired_chords: string[];
  low_confidence_lines: number[];
  notes: string[];
}

export interface Metadata {
  title?: string;
  artist?: string;
}

export interface ConvertResponse {
  chordpro: string;
  qa: QAReport;
  metadata: Metadata;
}

export interface ConvertOptions {
  title?: string;
  artist?: string;
}

export async function convertPdf(
  file: File,
  options: ConvertOptions = {},
): Promise<ConvertResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (options.title) formData.append("title", options.title);
  if (options.artist) formData.append("artist", options.artist);

  const response = await fetch("/api/convert", { method: "POST", body: formData });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: "Request failed" }));
    throw new Error(body.error ?? "Request failed");
  }
  return (await response.json()) as ConvertResponse;
}

export async function convertText(
  text: string,
  options: ConvertOptions = {},
): Promise<ConvertResponse> {
  const response = await fetch("/api/convert-text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, ...options }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: "Request failed" }));
    throw new Error(body.error ?? "Request failed");
  }
  return (await response.json()) as ConvertResponse;
}
