export interface QAReport {
  unpaired_chords: string[];
  low_confidence_lines: number[];
  notes: string[];
}

export interface ConvertResponse {
  chordpro: string;
  qa: QAReport;
}

export async function convertPdf(file: File): Promise<ConvertResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/convert", { method: "POST", body: formData });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: "Request failed" }));
    throw new Error(body.error ?? "Request failed");
  }
  return (await response.json()) as ConvertResponse;
}
