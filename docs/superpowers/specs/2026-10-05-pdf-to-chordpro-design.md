# PDF → ChordPro Converter — Design

Date: 2026-10-05
Status: Draft (awaiting user review)

## 1. Purpose

A local-first web app that converts **text-based (digital) PDF** song sheets into
**ChordPro** format, letting the user review and correct the result before
downloading. The architecture is designed so that new input sources
(pasted text, screenshots) can be added later without changing the conversion
engine.

### What ChordPro is

ChordPro is a plain-text notation where chords are embedded in square brackets
inline with the lyrics, e.g.:

```
{title: Amazing Grace}
[G]Amazing [C]grace how [G]sweet the sound[D]
```

The hard part of this project is reconstructing this inline form from a PDF,
where chords are drawn *above* the lyrics at specific horizontal positions.

## 2. Goals

- Accept a digital PDF and produce ChordPro text.
- Reconstruct chord/lyric alignment from PDF geometry.
- Provide a review-and-edit UI so imperfect conversions can be fixed before download.
- Keep the conversion engine independent of the input source.
- Be understandable to a JavaScript/TypeScript engineer learning Python.

## 3. Non-Goals (YAGNI)

- OCR / scanned / image-only PDFs.
- Paste-text and screenshot input (interfaces defined; not implemented).
- Batch processing, multiple files at once.
- Authentication, user accounts, database, saved songs.
- ML document-layout models (LayoutLM/Donut).
- Perfect metadata extraction (title/artist are best-effort heuristics).

## 4. Architecture

```
Input (PDF bytes)
      │
      ▼
SourceAdapter ──► LayoutDoc (IR) ──► classify ──► align ──► Song ──► chordpro
   (PdfAdapter now)                  (detect lines)  (pair chords) (serialize)
```

The engine (`classify`, `align`, `chordpro`) consumes **only** the IR. It never
imports a PDF library. This seam is what makes future input sources additive.

### Components

| Component | Responsibility |
|---|---|
| `ir.py` | Intermediate Representation: `LayoutDoc`, `Page`, `TextLine`, `TextSpan` |
| `adapters/base.py` | `SourceAdapter` protocol |
| `adapters/pdf.py` | `PdfAdapter` — PyMuPDF spans → `LayoutDoc` |
| `classify.py` | Group IR lines into blocks; label chord-lines vs lyric-lines |
| `align.py` | Pair chord tokens with lyric characters; emit `Song` |
| `models.py` | `Song`, `SongLine`, `QAReport` domain models |
| `chordpro.py` | Serialize `Song` → ChordPro text; metadata heuristics |
| `api.py` | FastAPI: `POST /api/convert` → ChordPro + QA report |

### Frontend

- React + Vite.
- Single drag-and-drop upload UI (designed to grow paste/screenshot tabs later).
- Side-by-side: pdf.js page preview | editable ChordPro textarea.
- Download button produces a `.cho` file.

### Deployment

- Single Docker image: FastAPI serves the built static frontend and the API.
- Portable to any container host.

## 5. Intermediate Representation (IR)

Defined now, so the engine is source-agnostic. Coordinates are in PDF points
with a **top-left origin** (adapters normalize to this). `size` and `bold` are
nullable because future OCR/paste sources cannot supply reliable font metadata.

```python
@dataclass
class TextSpan:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float | None = None   # font size, if known
    bold: bool | None = None    # font weight hint, if known

@dataclass
class TextLine:
    spans: list[TextSpan]
    y0: float
    y1: float

@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[TextLine]       # in reading order

@dataclass
class LayoutDoc:
    pages: list[Page]
```

Line grouping is the **adapter's** responsibility (it knows its own geometry);
the engine treats `Page.lines` order as reading order.

## 6. Source adapter interface

Defined now; only the PDF implementation is built. Paste/OCR adapters are
deliberately not implemented (YAGNI) but the interface guarantees they can be
added without touching the engine.

```python
class SourceAdapter(Protocol):
    def to_layout(self, data: bytes) -> LayoutDoc: ...
```

- `PdfAdapter` — implemented now (PyMuPDF).
- `PasteTextAdapter` — future. A future implementation maps a monospace grid:
  column index × estimated char width → `x`, each line → `TextLine`.
- `OcrAdapter` — future. Would use Tesseract word boxes → `TextSpan`s.

## 7. Source-agnostic classification rule

Signals in priority order. **Font metadata is a bonus hint only, never
required** — this is what keeps paste/OCR viable.

1. **Chord-token shape (primary).** A token matches chord grammar: root `A–G`,
   optional `#`/`b`, quality (`m`, `maj`, `min`, `sus`, `dim`, `aug`, `add`),
   extensions (`6`, `7`, `9`, `11`, `13`), optional slash bass, optional
   parentheses. The regex is module-level and configurable.
2. **Geometry (primary).** A chord line sits directly above a lyric line within
   a block; chord tokens cluster sparsely horizontally while lyrics are dense.
3. **Font metadata (tiebreaker only).** Smaller / bolder / monospace.

A line is labeled a **chord line** when its ratio of chord-shaped tokens
exceeds a threshold **and** geometry supports it (i.e. a lyric line lies
beneath it). Otherwise it is treated as a lyric line.

## 8. Alignment engine (`align.py`)

For each lyric line:

1. Find the chord line directly above it in the same block.
2. Walk the chord tokens left-to-right.
3. For each token, compute its x-center, then insert `[Chord]` into the lyric
   string at the character index whose x-center is nearest.
4. A chord line with no lyric beneath it becomes a `[Chord]`-only line.
5. Lines already containing inline `[Chords]` pass through unchanged.

Edge cases handled: multiple chord lines per lyric, trailing spaces in chord
lines, chord tokens beyond the end of the lyric (appended at end).

Every conversion emits a `QAReport`: unpaired chords, lines below the chord
ratio threshold, and other low-confidence signals surfaced to the UI.

## 9. Data models (`models.py`)

```python
@dataclass
class SongLine:
    kind: Literal["lyric", "chord_only", "directive", "blank"]
    text: str                  # ChordPro-ready text

@dataclass
class QAReport:
    unpaired_chords: list[str]
    low_confidence_lines: list[int]
    notes: list[str]

@dataclass
class Song:
    lines: list[SongLine]
    metadata: dict[str, str]   # e.g. title, artist
    qa: QAReport
```

## 10. API

```
POST /api/convert
  body: multipart/form-data, field "file" = PDF
  200:  { "chordpro": "<text>", "qa": { ... } }
  400:  { "error": "not a text-based PDF" }   # no extractable text layer
  413:  { "error": "file too large" }
```

Upload size limit is enforced (default 10 MB) to bound memory use.

## 11. Testing strategy

- **Unit tests** on the chord regex (valid/invalid tokens).
- **Unit tests** on `align` x-snapping with synthetic IR (no PDF needed).
- **Integration tests** on `classify`/`align` using small PDFs generated with
  `reportlab`, plus any real samples the user provides.
- **API test** with FastAPI `TestClient` on a generated PDF.
- Test framework: `pytest`.

`pytest` maps to Vitest/Jest: functions named `test_*` ↔ `it(...)`,
`assert` ↔ `expect(...).toBe(...)`.

## 12. Python style guide (learner-oriented)

This is a first-class requirement. The author is an experienced
JavaScript/TypeScript engineer new to Python.

- **Type hints everywhere**, including return types.
- **Docstrings** on every module and function: one-line summary, then
  args and return value.
- **`dataclasses`** for all data shapes (see IR/models) — closest analogue to
  TS interfaces/types, with constructors and equality for free.
- **Pure functions** in `classify`/`align`: data in → data out, no hidden state,
  individually unit-testable.
- **No clever one-liners or dense comprehensions.** Prefer small named steps.
- **Imports** at top of file, ordered standard-library → third-party → local.
- **Small modules** so no single file must be held in one's head.
- **Comments are explicitly welcome here** (an exception to the default):
  every non-obvious heuristic in `classify`/`align` gets a plain-English
  comment explaining the musical/geometric reasoning.

### Concept bridges (JS/TS → Python)

| Python | JS/TS analogue |
|---|---|
| `dataclass` | interface/type + object literal |
| `Protocol` | structural `interface` |
| type hints | TypeScript annotations |
| `pytest` | Vitest/Jest |
| `uv`/`venv` | `package.json`/`node_modules` |
| FastAPI route decorator | Express route registration |
| `list`, `dict`, `set`, `tuple` | `Array`, `Object`/`Map`, `Set`, `readonly tuple` |

### Documentation

A short `README.md` titled "Python for a TS engineer" walks through the modules
in reading order and explains the runtime/tooling.

## 13. Project layout

```
chordpro/
├── backend/
│   ├── app/
│   │   ├── ir.py
│   │   ├── models.py
│   │   ├── classify.py
│   │   ├── align.py
│   │   ├── chordpro.py
│   │   ├── api.py
│   │   └── adapters/
│   │       ├── base.py
│   │       └── pdf.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   ├── index.html
│   └── package.json
├── docs/superpowers/specs/
├── Dockerfile
├── README.md
└── .gitignore
```

## 14. Open questions

- Chord regex may later be exposed as user-editable configuration.
- Metadata (title/artist) heuristics are accepted as best-effort.
