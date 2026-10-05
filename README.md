# PDF → ChordPro

Convert text-based PDF song sheets (chords above lyrics) into
[ChordPro](https://www.chordpro.org/) text, with a review-and-edit UI.

## How it works

```
PDF ─► PdfAdapter ─► LayoutDoc (IR) ─► classify ─► align ─► Song ─► ChordPro
          │ no text layer
          ▼
      OcrAdapter ──────► LayoutDoc (IR)
```

The conversion engine only knows the `LayoutDoc` IR, so future input sources
(pasted text, screenshots) can be added by writing a new adapter.

### OCR fallback

PDFs with no text layer — scans, or pages whose text was saved as vector
outlines — are detected automatically and re-read with OCR. This requires the
**Tesseract** engine on the system:

- macOS: `brew install tesseract`
- Debian/Ubuntu: `apt-get install tesseract-ocr tesseract-ocr-eng`

The Docker image installs it already. OCR output is less reliable than a text
layer (chords especially), so the QA report adds a note whenever OCR was used,
and the review-and-edit UI is where you correct mistakes.

## Python for a TS engineer

You are an experienced TypeScript engineer, so here are the direct analogues:

| Python | TypeScript |
|---|---|
| `@dataclass` | an `interface` plus an object literal |
| `Protocol` | a structural `interface` |
| type hints (`x: float \| None`) | type annotations |
| `pytest` (`test_x`, `assert`) | Vitest/Jest (`it`, `expect`) |
| `uv sync` | `npm install` |
| `.venv/` | `node_modules/` |
| FastAPI route decorator | Express route registration |

### Reading order

1. `backend/app/ir.py` — the shared data shapes (start here).
2. `backend/app/geometry.py` — mapping x-positions to characters.
3. `backend/app/classify.py` — is this line chords or lyrics?
4. `backend/app/align.py` — inserting `[chords]` into lyrics.
5. `backend/app/chordpro.py` — rendering the final text.
6. `backend/app/pipeline.py` — wiring it together.
7. `backend/app/adapters/pdf.py` — the one concrete input source.

## Development

Backend:
```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.api:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api` to the backend.

## Production / deployment

```bash
docker build -t chordpro .
docker run --rm -p 8000:8000 chordpro
```

Then open `http://localhost:8000`.

## Limitations (by design)

- PDF only (no direct image upload). PDFs without a text layer are OCR'd when
  Tesseract is installed; if OCR also finds nothing, the request is rejected
  with HTTP 400.
- OCR accuracy on small chord text is limited; use the edit UI.
- Metadata (title/artist) is best-effort.
- Pasted-text and direct screenshot inputs are planned but not yet implemented.
