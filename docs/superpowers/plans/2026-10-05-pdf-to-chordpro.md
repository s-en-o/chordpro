# PDF → ChordPro Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first web app that converts text-based PDF song sheets into ChordPro, with a review-and-edit UI.

**Architecture:** A source-agnostic pipeline: `SourceAdapter → LayoutDoc (IR) → classify → align → Song → ChordPro`. Only the PDF adapter is implemented now; the IR and adapter protocol make paste/screenshot inputs additive later. The engine never imports a PDF library.

**Tech Stack:** Python 3.11+ (FastAPI, PyMuPDF, pytest, reportlab), React + Vite + TypeScript, Docker.

**Spec:** `docs/superpowers/specs/2026-10-05-pdf-to-chordpro-design.md`

## Global Constraints

- Python `requires-python = ">=3.11"` (IR uses `X | None` and `list[...]` syntax). Use `uv` to manage the environment; system Python 3.9 is too old.
- All Python code is **learner-oriented**: type hints everywhere (incl. returns), docstrings on every module/function, `dataclasses` for data shapes, pure functions in `classify`/`align`, no clever one-liners, imports ordered stdlib → third-party → local, plain-English comments on non-obvious heuristics.
- Engine modules (`classify`, `align`, `chordpro`, `pipeline`, `geometry`, `models`, `ir`) MUST NOT import `fitz`/PyMuPDF or any adapter.
- Coordinates in the IR use a **top-left origin**; adapters normalize.
- `TextSpan.size` and `TextSpan.bold` are nullable (`None` allowed).
- Upload limit: 10 MiB → HTTP 413.
- No OCR, no paste/screenshot adapters, no batch, no auth, no DB (YAGNI).
- Chord regex and thresholds are module-level constants, configurable via parameters.

**Plan refinement over spec:** `LayoutDoc` gains a `metadata: dict[str, str]` field so document title/author (source-agnostic) can flow to the ChordPro metadata heuristics.

---

## Task 1: Backend scaffolding

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/adapters/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable `app` package; `uv run pytest` from `backend/`.

- [ ] **Step 1: Create the git repo and ignore file**

`.gitignore`:
```gitignore
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.egg-info/

# Node
node_modules/
frontend/dist/

# OS
.DS_Store
```

Run:
```bash
git init
```

- [ ] **Step 2: Create the backend project file**

`backend/pyproject.toml`:
```toml
[project]
name = "chordpro"
version = "0.1.0"
description = "Convert text-based PDF song sheets to ChordPro"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pymupdf>=1.24",
    "python-multipart>=0.0.12",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "reportlab>=4.2",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: Create the package markers**

`backend/app/__init__.py` and `backend/app/adapters/__init__.py` and `backend/tests/__init__.py` are all empty files.

- [ ] **Step 4: Install dependencies and verify the toolchain**

Run (from `backend/`):
```bash
uv sync
uv run python -c "import fastapi, fitz; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore backend/pyproject.toml backend/app/__init__.py backend/app/adapters/__init__.py backend/tests/__init__.py
git commit -m "chore: scaffold backend project and tooling"
```

---

## Task 2: IR dataclasses and geometry helpers

**Files:**
- Create: `backend/app/ir.py`
- Create: `backend/app/geometry.py`
- Test: `backend/tests/test_ir.py`
- Test: `backend/tests/test_geometry.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `TextSpan(text, x0, y0, x1, y1, size=None, bold=None)`
  - `TextLine(spans, y0, y1)` with properties `.text: str`, `.height: float`
  - `Page(number, width, height, lines=[])`
  - `LayoutDoc(pages=[], metadata={})`
  - `char_x_centers(line: TextLine) -> list[float]`
  - `token_positions(line: TextLine) -> list[tuple[str, float]]`
  - `nearest_char_index(centers: list[float], x: float) -> int`

- [ ] **Step 1: Write the failing IR test**

`backend/tests/test_ir.py`:
```python
from app.ir import LayoutDoc, Page, TextLine, TextSpan


def make_span(text: str, x0: float, y0: float, width: float) -> TextSpan:
    return TextSpan(text=text, x0=x0, y0=y0, x1=x0 + width, y1=y0 + 12)


def test_text_line_joins_span_text() -> None:
    line = TextLine(
        spans=[make_span("Hello ", 0, 0, 30), make_span("world", 30, 0, 30)],
        y0=0,
        y1=12,
    )
    assert line.text == "Hello world"


def test_text_line_height() -> None:
    line = TextLine(spans=[make_span("x", 0, 10, 5)], y0=10, y1=24)
    assert line.height == 14


def test_layout_doc_defaults_are_independent() -> None:
    first = LayoutDoc()
    second = LayoutDoc()
    first.pages.append(Page(number=1, width=1, height=1))
    assert second.pages == []
    assert second.metadata == {}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ir.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ir'`.

- [ ] **Step 3: Implement the IR**

`backend/app/ir.py`:
```python
"""The intermediate representation (IR): a source-agnostic layout document.

Every input source (PDF now; pasted text or screenshots later) is normalized
into these dataclasses before the conversion engine runs. Coordinates use a
top-left origin, in points.
"""

from dataclasses import dataclass, field


@dataclass
class TextSpan:
    """A run of text sharing one font and one horizontal position."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float | None = None
    bold: bool | None = None


@dataclass
class TextLine:
    """One visual line of text, made of one or more spans."""

    spans: list[TextSpan]
    y0: float
    y1: float

    @property
    def text(self) -> str:
        """The concatenated text of every span on the line."""
        return "".join(span.text for span in self.spans)

    @property
    def height(self) -> float:
        """The vertical height of the line in points."""
        return self.y1 - self.y0


@dataclass
class Page:
    """A single page, with its lines in reading order."""

    number: int
    width: float
    height: float
    lines: list[TextLine] = field(default_factory=list)


@dataclass
class LayoutDoc:
    """A whole document: pages plus optional source metadata."""

    pages: list[Page] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_ir.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Write the failing geometry test**

`backend/tests/test_geometry.py`:
```python
from app.geometry import char_x_centers, nearest_char_index, token_positions
from app.ir import TextLine, TextSpan


def make_line(text: str, x0: float, y0: float, char_width: float = 7.2) -> TextLine:
    span = TextSpan(
        text=text,
        x0=x0,
        y0=y0,
        x1=x0 + len(text) * char_width,
        y1=y0 + 12,
        size=12,
        bold=False,
    )
    return TextLine(spans=[span], y0=y0, y1=y0 + 12)


def test_char_centers_are_evenly_spaced() -> None:
    line = make_line("abc", 0, 0)
    assert char_x_centers(line) == [3.6, 10.8, 18.0]


def test_token_positions_reports_centers() -> None:
    line = make_line("C     G", 0, 0)
    positions = token_positions(line)
    assert positions == [("C", 3.6), ("G", 46.8)]


def test_nearest_char_index_picks_closest() -> None:
    assert nearest_char_index([0.0, 10.0, 20.0], 12.0) == 1


def test_nearest_char_index_on_empty_list() -> None:
    assert nearest_char_index([], 5.0) == 0
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `uv run pytest tests/test_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.geometry'`.

- [ ] **Step 7: Implement the geometry helpers**

`backend/app/geometry.py`:
```python
"""Geometry helpers that map text positions onto character positions.

These are deliberately approximate: characters are assumed to be evenly
spread across each span's width. That is exact for monospace fonts and a good
approximation for proportional fonts.
"""

import re

from app.ir import TextLine

_TOKEN = re.compile(r"\S+")


def char_x_centers(line: TextLine) -> list[float]:
    """Return the horizontal center of every character on the line."""
    centers: list[float] = []
    for span in line.spans:
        count = len(span.text)
        if count == 0:
            continue
        width = span.x1 - span.x0
        for index in range(count):
            fraction = (index + 0.5) / count
            centers.append(span.x0 + fraction * width)
    return centers


def token_positions(line: TextLine) -> list[tuple[str, float]]:
    """Return ``(token, x_center)`` for every whitespace-separated token."""
    text = line.text
    centers = char_x_centers(line)
    positions: list[tuple[str, float]] = []
    for match in _TOKEN.finditer(text):
        start, end = match.span()
        if end > len(centers):
            continue
        token_centers = centers[start:end]
        x_center = sum(token_centers) / len(token_centers)
        positions.append((match.group(), x_center))
    return positions


def nearest_char_index(centers: list[float], x: float) -> int:
    """Return the index of the character whose center is closest to ``x``."""
    if not centers:
        return 0
    best_index = 0
    best_distance = abs(centers[0] - x)
    for index, center in enumerate(centers):
        distance = abs(center - x)
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `uv run pytest tests/test_geometry.py -v`
Expected: PASS (4 passed).

- [ ] **Step 9: Commit**

```bash
git add backend/app/ir.py backend/app/geometry.py backend/tests/test_ir.py backend/tests/test_geometry.py
git commit -m "feat: add IR dataclasses and geometry helpers"
```

---

## Task 3: Domain models

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `LineKind = Literal["lyric", "chord_only", "directive", "blank"]`
  - `SongLine(kind: LineKind, text: str)`
  - `QAReport(unpaired_chords=[], low_confidence_lines=[], notes=[])`
  - `Song(lines=[], metadata={}, qa=QAReport())`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_models.py`:
```python
from app.models import QAReport, Song, SongLine


def test_song_defaults_are_independent() -> None:
    first = Song()
    second = Song()
    first.lines.append(SongLine(kind="blank", text=""))
    assert second.lines == []
    assert isinstance(second.qa, QAReport)


def test_qa_report_defaults() -> None:
    report = QAReport()
    assert report.unpaired_chords == []
    assert report.low_confidence_lines == []
    assert report.notes == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implement the models**

`backend/app/models.py`:
```python
"""The domain output of the conversion: a Song and its quality report."""

from dataclasses import dataclass, field
from typing import Literal

# The kinds of line a converted song can contain.
LineKind = Literal["lyric", "chord_only", "directive", "blank"]


@dataclass
class SongLine:
    """One line of ChordPro-ready text."""

    kind: LineKind
    text: str


@dataclass
class QAReport:
    """Signals surfaced to the UI so the user can spot bad conversions."""

    unpaired_chords: list[str] = field(default_factory=list)
    low_confidence_lines: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Song:
    """A converted song: its lines, metadata, and quality report."""

    lines: list[SongLine] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    qa: QAReport = field(default_factory=QAReport)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: add Song and QAReport domain models"
```

---

## Task 4: SourceAdapter protocol

**Files:**
- Create: `backend/app/adapters/base.py`
- Test: `backend/tests/test_adapter_protocol.py`

**Interfaces:**
- Consumes: `LayoutDoc` from Task 2.
- Produces: `SourceAdapter` protocol with `to_layout(self, data: bytes) -> LayoutDoc`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_adapter_protocol.py`:
```python
from app.adapters.base import SourceAdapter
from app.ir import LayoutDoc


class FakeAdapter:
    def to_layout(self, data: bytes) -> LayoutDoc:
        return LayoutDoc(metadata={"source": "fake"})


def test_protocol_is_satisfied_structurally() -> None:
    adapter: SourceAdapter = FakeAdapter()
    layout = adapter.to_layout(b"anything")
    assert layout.metadata == {"source": "fake"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_adapter_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.adapters.base'`.

- [ ] **Step 3: Implement the protocol**

`backend/app/adapters/base.py`:
```python
"""The interface every input source must satisfy.

A future PasteTextAdapter or OcrAdapter only needs a ``to_layout`` method to
plug into the pipeline; the engine is never modified.
"""

from typing import Protocol

from app.ir import LayoutDoc


class SourceAdapter(Protocol):
    """Turns raw input bytes into the shared LayoutDoc IR."""

    def to_layout(self, data: bytes) -> LayoutDoc:
        """Convert ``data`` into a LayoutDoc."""
        ...
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_adapter_protocol.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/base.py backend/tests/test_adapter_protocol.py
git commit -m "feat: add SourceAdapter protocol"
```

---

## Task 5: PDF adapter

**Files:**
- Create: `backend/app/adapters/pdf.py`
- Test: `backend/tests/test_pdf_adapter.py`

**Interfaces:**
- Consumes: `LayoutDoc`, `Page`, `TextLine`, `TextSpan` (Task 2).
- Produces: `PdfAdapter().to_layout(data: bytes) -> LayoutDoc`; `NoTextLayerError`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pdf_adapter.py`:
```python
from io import BytesIO
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.adapters.pdf import NoTextLayerError, PdfAdapter


def make_text_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Courier", 12)
    pdf.drawString(72, 700, "Hello world")
    pdf.setFont("Courier-Bold", 12)
    pdf.drawString(72, 716, "C     G")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_blank_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def test_pdf_adapter_extracts_lines() -> None:
    layout = PdfAdapter().to_layout(make_text_pdf())
    assert len(layout.pages) == 1
    page = layout.pages[0]
    texts = [line.text for line in page.lines]
    assert "Hello world" in texts
    assert "C     G" in texts


def test_pdf_adapter_orders_chord_above_lyric() -> None:
    page = PdfAdapter().to_layout(make_text_pdf()).pages[0]
    # In a top-left origin, the chord line must come first (smaller y).
    assert page.lines[0].text == "C     G"


def test_pdf_adapter_raises_without_text_layer() -> None:
    with pytest.raises(NoTextLayerError):
        PdfAdapter().to_layout(make_blank_pdf())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_pdf_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.adapters.pdf'`.

- [ ] **Step 3: Implement the adapter**

`backend/app/adapters/pdf.py`:
```python
"""PDF source adapter, backed by PyMuPDF (imported as ``fitz``)."""

import fitz  # PyMuPDF

from app.ir import LayoutDoc, Page, TextLine, TextSpan

# PyMuPDF's span "flags" use bit 4 (value 16) to mark bold text.
_BOLD_FLAG = 1 << 4


class NoTextLayerError(Exception):
    """Raised when a PDF contains no extractable text."""


class PdfAdapter:
    """SourceAdapter implementation that reads a PDF's text layer."""

    def to_layout(self, data: bytes) -> LayoutDoc:
        """Convert PDF ``data`` into a LayoutDoc."""
        document = fitz.open(stream=data, filetype="pdf")
        try:
            pages = [
                self._read_page(page, index + 1)
                for index, page in enumerate(document)
            ]
            metadata = self._read_metadata(document)
        finally:
            document.close()

        if not any(page.lines for page in pages):
            raise NoTextLayerError("PDF contains no extractable text")
        return LayoutDoc(pages=pages, metadata=metadata)

    def _read_metadata(self, document) -> dict[str, str]:
        raw = document.metadata or {}
        return {key: value for key, value in raw.items() if value}

    def _read_page(self, page, number: int) -> Page:
        page_dict = page.get_text("dict")
        lines: list[TextLine] = []
        for block in page_dict["blocks"]:
            if block.get("type") != 0:  # 0 = text block
                continue
            for raw_line in block["lines"]:
                line = self._read_line(raw_line)
                if line.spans:
                    lines.append(line)
        # PyMuPDF does not guarantee reading order, so sort top-to-bottom.
        lines.sort(key=lambda line: line.y0)
        return Page(
            number=number,
            width=page.rect.width,
            height=page.rect.height,
            lines=lines,
        )

    def _read_line(self, raw_line: dict) -> TextLine:
        spans: list[TextSpan] = []
        for raw_span in raw_line["spans"]:
            text = raw_span["text"]
            if not text.strip():
                continue
            x0, y0, x1, y1 = raw_span["bbox"]
            spans.append(
                TextSpan(
                    text=text,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    size=raw_span.get("size"),
                    bold=bool(raw_span.get("flags", 0) & _BOLD_FLAG),
                )
            )
        if spans:
            top = min(span.y0 for span in spans)
            bottom = max(span.y1 for span in spans)
        else:
            top = bottom = 0.0
        return TextLine(spans=spans, y0=top, y1=bottom)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_pdf_adapter.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/pdf.py backend/tests/test_pdf_adapter.py
git commit -m "feat: add PyMuPDF-backed PDF source adapter"
```

---

## Task 6: Chord detection and line classification

**Files:**
- Create: `backend/app/classify.py`
- Test: `backend/tests/test_classify.py`

**Interfaces:**
- Consumes: `Page`, `TextLine` (Task 2).
- Produces:
  - `CHORD_REGEX: re.Pattern`
  - `DEFAULT_CHORD_THRESHOLD: float`, `DEFAULT_GAP_FACTOR: float`
  - `is_chord(token: str) -> bool`
  - `chord_ratio(line: TextLine) -> float`
  - `LineLabel(line: TextLine, kind: LineKind)` where `LineKind = Literal["chord", "chord_only", "lyric", "blank"]`
  - `classify_page(page, chord_threshold=DEFAULT_CHORD_THRESHOLD, gap_factor=DEFAULT_GAP_FACTOR) -> list[LineLabel]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_classify.py`:
```python
from app.classify import LineLabel, chord_ratio, classify_page, is_chord
from app.ir import Page, TextLine, TextSpan


def make_line(text: str, y0: float, char_width: float = 7.2) -> TextLine:
    span = TextSpan(
        text=text,
        x0=0,
        y0=y0,
        x1=len(text) * char_width,
        y1=y0 + 12,
        size=12,
        bold=False,
    )
    return TextLine(spans=[span], y0=y0, y1=y0 + 12)


def test_is_chord_accepts_common_chords() -> None:
    for token in ["C", "Gm", "F#m7", "Bb", "Amaj7", "Dsus4", "C/G", "E7", "Aadd9"]:
        assert is_chord(token), token


def test_is_chord_rejects_words() -> None:
    for token in ["Hello", "world", "the", "grace"]:
        assert not is_chord(token), token


def test_chord_ratio() -> None:
    assert chord_ratio(make_line("C     G", 0)) == 1.0
    assert chord_ratio(make_line("Hello world", 0)) == 0.0


def test_classify_marks_chord_above_lyric() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0), make_line("Hello world", 14)],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["chord", "lyric"]


def test_classify_marks_lonely_chord_as_chord_only() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0)],
    )
    labels = classify_page(page)
    assert [label.kind for label in labels] == ["chord_only"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_classify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.classify'`.

- [ ] **Step 3: Implement classification**

`backend/app/classify.py`:
```python
"""Decide which lines are chords and which are lyrics.

The primary signal is the shape of the tokens themselves (does each token
look like a chord symbol?), not the font. That keeps this module usable for
future pasted-text or OCR sources that have no reliable font metadata.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.ir import Page, TextLine

# A permissive chord grammar: root note, optional accidental, optional
# quality/extension, optional slash bass. Kept as a module constant so it can
# be tuned or exposed as configuration later.
CHORD_REGEX = re.compile(
    r"""
    \A
    [A-G]                                     # root note A..G
    (?:\#|b)?                                 # optional sharp or flat
    (?:maj|min|m|M|sus|dim|aug|add|°|ø|\+|-)?  # optional quality word
    (?:sus\d|add\d+|\d+)*                     # any run of modifiers / extensions
    (?:/[A-G](?:\#|b)?)?                      # optional slash bass note
    \Z
    """,
    re.VERBOSE,
)

DEFAULT_CHORD_THRESHOLD = 0.5
DEFAULT_GAP_FACTOR = 2.5

LineKind = Literal["chord", "chord_only", "lyric", "blank"]


@dataclass
class LineLabel:
    """A line plus the role we assigned it."""

    line: TextLine
    kind: LineKind


def is_chord(token: str) -> bool:
    """Return True when a token looks like a chord symbol."""
    return bool(CHORD_REGEX.match(token.strip("()")))


def chord_ratio(line: TextLine) -> float:
    """Return the fraction of tokens on a line that look like chords."""
    tokens = line.text.split()
    if not tokens:
        return 0.0
    chord_count = 0
    for token in tokens:
        if is_chord(token):
            chord_count += 1
    return chord_count / len(tokens)


def _median_line_height(page: Page) -> float:
    heights = sorted(line.height for line in page.lines if line.height > 0)
    if not heights:
        return 0.0
    return heights[len(heights) // 2]


def classify_page(
    page: Page,
    chord_threshold: float = DEFAULT_CHORD_THRESHOLD,
    gap_factor: float = DEFAULT_GAP_FACTOR,
) -> list[LineLabel]:
    """Label every line on a page as chord, chord_only, lyric, or blank.

    A line whose tokens are mostly chords is a chord *candidate*. It becomes
    a real chord line only when a lyric line sits directly beneath it and the
    vertical gap is small; otherwise it becomes a chord-only line (chords with
    no lyrics under them).
    """
    labels: list[LineLabel] = []
    for line in page.lines:
        if not line.text.strip():
            labels.append(LineLabel(line=line, kind="blank"))
        elif chord_ratio(line) >= chord_threshold:
            labels.append(LineLabel(line=line, kind="chord"))
        else:
            labels.append(LineLabel(line=line, kind="lyric"))

    median_height = _median_line_height(page)
    max_gap = gap_factor * median_height

    for index, label in enumerate(labels):
        if label.kind != "chord":
            continue
        if index + 1 >= len(labels):
            label.kind = "chord_only"
            continue
        below = labels[index + 1]
        vertical_gap = below.line.y0 - label.line.y1
        if below.kind != "lyric" or vertical_gap > max_gap:
            label.kind = "chord_only"

    return labels
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_classify.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/classify.py backend/tests/test_classify.py
git commit -m "feat: add chord detection and line classification"
```

---

## Task 7: Alignment engine

**Files:**
- Create: `backend/app/align.py`
- Test: `backend/tests/test_align.py`

**Interfaces:**
- Consumes: `LineLabel`, `is_chord` (Task 6); `SongLine`, `QAReport` (Task 3); geometry helpers (Task 2).
- Produces:
  - `merge_chord_lyric(chord_label: LineLabel, lyric_label: LineLabel, qa: QAReport) -> SongLine`
  - `chord_only_text(line: TextLine) -> str`
  - `align_page(labels: list[LineLabel], qa: QAReport) -> list[SongLine]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_align.py`:
```python
from app.align import align_page, chord_only_text, merge_chord_lyric
from app.classify import LineLabel
from app.ir import TextLine, TextSpan
from app.models import QAReport


def make_line(text: str, y0: float, char_width: float = 7.2) -> TextLine:
    span = TextSpan(
        text=text,
        x0=0,
        y0=y0,
        x1=len(text) * char_width,
        y1=y0 + 12,
        size=12,
        bold=False,
    )
    return TextLine(spans=[span], y0=y0, y1=y0 + 12)


def test_merge_inserts_chords_at_nearest_characters() -> None:
    chord = LineLabel(make_line("C     G", 0), "chord")
    lyric = LineLabel(make_line("Hello world", 14), "lyric")
    result = merge_chord_lyric(chord, lyric, QAReport())
    assert result.kind == "lyric"
    assert result.text == "[C]Hello[G] world"


def test_merge_ignores_non_chord_tokens() -> None:
    chord = LineLabel(make_line("C  x  G", 0), "chord")
    lyric = LineLabel(make_line("abcdefgh", 14), "lyric")
    result = merge_chord_lyric(chord, lyric, QAReport())
    assert result.text == "[C]abcdef[G]gh"


def test_chord_only_text() -> None:
    assert chord_only_text(make_line("C   G   Am", 0)) == "[C] [G] [Am]"


def test_align_page_pairs_chord_and_lyric() -> None:
    labels = [
        LineLabel(make_line("C     G", 0), "chord"),
        LineLabel(make_line("Hello world", 14), "lyric"),
        LineLabel(make_line("Am", 28), "chord_only"),
    ]
    qa = QAReport()
    lines = align_page(labels, qa)
    assert [line.text for line in lines] == ["[C]Hello[G] world", "[Am]"]
    assert qa.unpaired_chords == ["Am"]


def test_align_page_passes_plain_lyric_through() -> None:
    labels = [LineLabel(make_line("just a lyric", 0), "lyric")]
    lines = align_page(labels, QAReport())
    assert lines[0].text == "just a lyric"
    assert lines[0].kind == "lyric"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_align.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.align'`.

- [ ] **Step 3: Implement the alignment engine**

`backend/app/align.py`:
```python
"""Pair chord tokens with the lyric characters beneath them.

The rule is geometric and simple: for each chord token, find the lyric
character whose horizontal center is closest to the chord's center, and
insert ``[Chord]`` immediately before that character.
"""

from app.classify import LineLabel, is_chord
from app.geometry import char_x_centers, nearest_char_index, token_positions
from app.ir import TextLine
from app.models import QAReport, SongLine


def merge_chord_lyric(
    chord_label: LineLabel,
    lyric_label: LineLabel,
    qa: QAReport,
) -> SongLine:
    """Insert ``[chord]`` markers into a lyric line at the nearest characters."""
    lyric_text = lyric_label.line.text
    lyric_centers = char_x_centers(lyric_label.line)

    insertions: list[tuple[int, str]] = []
    for token, x_center in token_positions(chord_label.line):
        if not is_chord(token):
            continue
        index = nearest_char_index(lyric_centers, x_center)
        insertions.append((index, f"[{token}]"))

    # Insert from right to left so earlier indices stay valid.
    insertions.sort(key=lambda item: item[0], reverse=True)
    result = lyric_text
    for index, chord_text in insertions:
        result = result[:index] + chord_text + result[index:]
    return SongLine(kind="lyric", text=result)


def chord_only_text(line: TextLine) -> str:
    """Render a chord line that has no lyric beneath it."""
    chords = [token for token, _ in token_positions(line) if is_chord(token)]
    return " ".join(f"[{chord}]" for chord in chords)


def align_page(labels: list[LineLabel], qa: QAReport) -> list[SongLine]:
    """Turn classified lines into ChordPro-ready lines for one page."""
    song_lines: list[SongLine] = []
    index = 0
    while index < len(labels):
        label = labels[index]
        if label.kind == "chord":
            # classify_page guarantees the next line is a lyric.
            next_label = labels[index + 1]
            song_lines.append(merge_chord_lyric(label, next_label, qa))
            index += 2
        elif label.kind == "chord_only":
            song_lines.append(
                SongLine(kind="chord_only", text=chord_only_text(label.line))
            )
            for token, _ in token_positions(label.line):
                if is_chord(token):
                    qa.unpaired_chords.append(token)
            index += 1
        elif label.kind == "blank":
            song_lines.append(SongLine(kind="blank", text=""))
            index += 1
        else:
            song_lines.append(SongLine(kind="lyric", text=label.line.text))
            index += 1
    return song_lines
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_align.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/align.py backend/tests/test_align.py
git commit -m "feat: add chord-to-lyric alignment engine"
```

---

## Task 8: ChordPro serialization and metadata

**Files:**
- Create: `backend/app/chordpro.py`
- Test: `backend/tests/test_chordpro.py`

**Interfaces:**
- Consumes: `Song`, `SongLine` (Task 3); `LayoutDoc`, `TextLine` (Task 2).
- Produces:
  - `serialize(song: Song) -> str`
  - `guess_metadata(layout: LayoutDoc) -> dict[str, str]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_chordpro.py`:
```python
from app.chordpro import guess_metadata, serialize
from app.ir import LayoutDoc, Page, TextLine, TextSpan
from app.models import Song, SongLine


def make_line(text: str, size: float = 12) -> TextLine:
    span = TextSpan(
        text=text, x0=0, y0=0, x1=len(text) * size * 0.6, y1=size, size=size, bold=False
    )
    return TextLine(spans=[span], y0=0, y1=size)


def test_serialize_includes_metadata_then_blank_line() -> None:
    song = Song(
        lines=[SongLine(kind="lyric", text="[C]Hello")],
        metadata={"title": "My Song", "artist": "Me"},
    )
    assert serialize(song) == "{title: My Song}\n{artist: Me}\n\n[C]Hello\n"


def test_serialize_without_metadata() -> None:
    song = Song(lines=[SongLine(kind="blank", text="")])
    assert serialize(song) == "\n"


def test_guess_metadata_prefers_document_metadata() -> None:
    layout = LayoutDoc(metadata={"title": "Given", "author": "Someone"})
    assert guess_metadata(layout) == {"title": "Given", "artist": "Someone"}


def test_guess_metadata_falls_back_to_largest_text() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("Big Title", 24), make_line("small lyric", 10)],
    )
    layout = LayoutDoc(pages=[page])
    assert guess_metadata(layout) == {"title": "Big Title"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_chordpro.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.chordpro'`.

- [ ] **Step 3: Implement serialization**

`backend/app/chordpro.py`:
```python
"""Serialize a Song to ChordPro text and guess metadata."""

from app.ir import LayoutDoc
from app.models import Song


def serialize(song: Song) -> str:
    """Render a Song as ChordPro text."""
    output: list[str] = []
    for key, value in song.metadata.items():
        if value:
            output.append(f"{{{key}: {value}}}")
    if output:
        output.append("")
    for line in song.lines:
        output.append(line.text)
    return "\n".join(output) + "\n"


def guess_metadata(layout: LayoutDoc) -> dict[str, str]:
    """Best-effort title/artist extraction.

    Prefer the document's own metadata; otherwise fall back to the largest
    text on the first page, which is usually the title.
    """
    metadata: dict[str, str] = {}

    title = layout.metadata.get("title", "").strip()
    if not title:
        title = _largest_text_first_page(layout)
    if title:
        metadata["title"] = title

    artist = layout.metadata.get("author", "").strip()
    if artist:
        metadata["artist"] = artist

    return metadata


def _largest_text_first_page(layout: LayoutDoc) -> str:
    if not layout.pages:
        return ""
    best_text = ""
    best_size = 0.0
    for line in layout.pages[0].lines:
        for span in line.spans:
            size = span.size or 0.0
            if size > best_size and span.text.strip():
                best_size = size
                best_text = line.text.strip()
    return best_text
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_chordpro.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/chordpro.py backend/tests/test_chordpro.py
git commit -m "feat: add ChordPro serialization and metadata heuristics"
```

---

## Task 9: Pipeline orchestration

**Files:**
- Create: `backend/app/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `LayoutDoc` (Task 2); `classify_page` (Task 6); `align_page` (Task 7); `guess_metadata` (Task 8); `Song`, `QAReport` (Task 3).
- Produces: `convert_layout(layout: LayoutDoc) -> Song`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pipeline.py`:
```python
from app.ir import LayoutDoc, Page, TextLine, TextSpan
from app.pipeline import convert_layout


def make_line(text: str, y0: float, char_width: float = 7.2) -> TextLine:
    span = TextSpan(
        text=text, x0=0, y0=y0, x1=len(text) * char_width, y1=y0 + 12, size=12, bold=False
    )
    return TextLine(spans=[span], y0=y0, y1=y0 + 12)


def test_convert_layout_end_to_end() -> None:
    page = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C     G", 0), make_line("Hello world", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page]))
    assert song.lines[0].text == "[C]Hello[G] world"


def test_convert_layout_spans_multiple_pages() -> None:
    page1 = Page(
        number=1,
        width=600,
        height=800,
        lines=[make_line("C", 0), make_line("one", 14)],
    )
    page2 = Page(
        number=2,
        width=600,
        height=800,
        lines=[make_line("G", 0), make_line("two", 14)],
    )
    song = convert_layout(LayoutDoc(pages=[page1, page2]))
    assert [line.text for line in song.lines] == ["[C]one", "[G]two"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline'`.

- [ ] **Step 3: Implement the pipeline**

`backend/app/pipeline.py`:
```python
"""Orchestrate the full conversion from IR to Song."""

from app.align import align_page
from app.chordpro import guess_metadata
from app.classify import classify_page
from app.ir import LayoutDoc
from app.models import QAReport, Song


def convert_layout(layout: LayoutDoc) -> Song:
    """Run classification and alignment over every page, then attach metadata."""
    qa = QAReport()
    song_lines = []
    for page in layout.pages:
        labels = classify_page(page)
        song_lines.extend(align_page(labels, qa))

    return Song(
        lines=song_lines,
        metadata=guess_metadata(layout),
        qa=qa,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: add IR-to-Song conversion pipeline"
```

---

## Task 10: FastAPI endpoint

**Files:**
- Create: `backend/app/api.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `PdfAdapter`, `NoTextLayerError` (Task 5); `convert_layout` (Task 9); `serialize` (Task 8).
- Produces: `app` (FastAPI instance); `MAX_UPLOAD_BYTES`; `POST /api/convert`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api.py`:
```python
from io import BytesIO

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.api import app

client = TestClient(app)


def make_text_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Courier", 12)
    pdf.drawString(72, 700, "Hello world")
    pdf.setFont("Courier-Bold", 12)
    pdf.drawString(72, 716, "C     G")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_blank_pdf() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def test_convert_returns_chordpro_and_qa() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("song.pdf", make_text_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "[C]Hello[G] world" in body["chordpro"]
    assert body["qa"]["unpaired_chords"] == []


def test_convert_rejects_pdf_without_text() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("blank.pdf", make_blank_pdf(), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "not a text-based PDF"


def test_convert_rejects_oversized_file() -> None:
    response = client.post(
        "/api/convert",
        files={"file": ("big.pdf", b"0" * (10 * 1024 * 1024 + 1), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["error"] == "file too large"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api'`.

- [ ] **Step 3: Implement the API**

`backend/app/api.py`:
```python
"""FastAPI application exposing the PDF-to-ChordPro conversion endpoint."""

from dataclasses import asdict

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from app.adapters.pdf import NoTextLayerError, PdfAdapter
from app.chordpro import serialize
from app.pipeline import convert_layout

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="ChordPro Converter")


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)) -> JSONResponse:
    """Convert an uploaded PDF into ChordPro text plus a QA report."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return JSONResponse(status_code=413, content={"error": "file too large"})

    try:
        layout = PdfAdapter().to_layout(data)
    except NoTextLayerError:
        return JSONResponse(
            status_code=400, content={"error": "not a text-based PDF"}
        )

    song = convert_layout(layout)
    return JSONResponse(
        status_code=200,
        content={"chordpro": serialize(song), "qa": asdict(song.qa)},
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the whole backend suite**

Run: `uv run pytest -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api.py backend/tests/test_api.py
git commit -m "feat: add FastAPI convert endpoint"
```

---

## Task 11: Frontend (React + Vite + TypeScript)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`

**Interfaces:**
- Consumes: `POST /api/convert` from Task 10 via the Vite dev proxy.
- Produces: a browser UI at `http://localhost:5173` during development.

- [ ] **Step 1: Create the frontend manifest and config**

`frontend/package.json`:
```json
{
  "name": "chordpro-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^6.0.3"
  }
}
```

`frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true
  },
  "include": ["src"]
}
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PDF to ChordPro</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Create the API client**

`frontend/src/api.ts`:
```ts
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
```

- [ ] **Step 3: Create the app UI**

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`frontend/src/App.tsx`:
```tsx
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
```

`frontend/src/index.css`:
```css
:root {
  font-family: system-ui, sans-serif;
  line-height: 1.5;
}

.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem;
}

.panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 1rem;
}

.pane {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.preview,
.editor {
  width: 100%;
  height: 480px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.editor {
  font-family: ui-monospace, monospace;
  padding: 0.5rem;
  resize: vertical;
}

.error {
  color: #b00020;
}

.warning {
  color: #8a6d00;
}
```

- [ ] **Step 4: Install dependencies and verify the production build**

Run (from `frontend/`):
```bash
npm install
npm run build
```
Expected: `dist/` is created with no TypeScript errors.

- [ ] **Step 5: Verify the dev proxy against the backend**

In one terminal (from `backend/`): `uv run uvicorn app.api:app --port 8000`
In another (from `frontend/`): `npm run dev`
Open `http://localhost:5173`, upload a chord PDF, click Convert. Expected: the ChordPro pane fills with `[C]Hello...`-style text.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: add React upload/review/download UI"
```

---

## Task 12: Docker image, static serving, and README

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `backend/app/api.py` (serve the built frontend)
- Create: `README.md`

**Interfaces:**
- Consumes: built `frontend/dist/` (Task 11) and `app` (Task 10).
- Produces: a container serving UI + API on port 8000.

- [ ] **Step 1: Add static file serving to the API**

Append to `backend/app/api.py` (after the endpoint definition):
```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles

# In the Docker image the built frontend is copied to /app/frontend_dist.
# Locally, this path simply won't exist, so we only mount it when present.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend_dist"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
```

- [ ] **Step 2: Verify tests still pass**

Run (from `backend/`): `uv run pytest -v`
Expected: PASS (all tests; the static dir does not exist locally).

- [ ] **Step 3: Create the multi-stage Dockerfile**

`Dockerfile`:
```dockerfile
# --- Stage 1: build the frontend ---
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: run the backend ---
FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" "pymupdf>=1.24" "python-multipart>=0.0.12"
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./frontend_dist
EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore`:
```
node_modules
frontend/node_modules
frontend/dist
.venv
__pycache__
*.pyc
.pytest_cache
.git
```

- [ ] **Step 4: Build and smoke-test the image**

Run:
```bash
docker build -t chordpro .
docker run --rm -p 8000:8000 chordpro
```
Then open `http://localhost:8000` and convert a PDF. Expected: the UI loads and returns ChordPro.

- [ ] **Step 5: Write the README**

`README.md`:
```markdown
# PDF → ChordPro

Convert text-based PDF song sheets (chords above lyrics) into
[ChordPro](https://www.chordpro.org/) text, with a review-and-edit UI.

## How it works

```
PDF ─► PdfAdapter ─► LayoutDoc (IR) ─► classify ─► align ─► Song ─► ChordPro
```

The conversion engine only knows the `LayoutDoc` IR, so future input sources
(pasted text, screenshots) can be added by writing a new adapter.

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

- Only text-based (digital) PDFs. Scanned images without a text layer are
  rejected with HTTP 400.
- Metadata (title/artist) is best-effort.
- Pasted-text and screenshot inputs are planned but not yet implemented.
```

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .dockerignore README.md backend/app/api.py
git commit -m "feat: add Docker image, static serving, and README"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Task(s) |
|---|---|
| §4 architecture / components | Tasks 2–10 (all modules) |
| §5 IR | Task 2 |
| §6 SourceAdapter + PdfAdapter | Tasks 4, 5 |
| §7 source-agnostic classification | Task 6 |
| §8 alignment engine | Task 7 |
| §9 data models | Task 3 |
| §10 API (200/400/413) | Task 10 |
| §11 testing strategy | Every task (pytest) |
| §12 Python style guide | Global Constraints + all code |
| §13 project layout | Tasks 1, 11, 12 |
| §14 open questions | Chord regex is a module constant (Task 6); metadata best-effort (Task 8) |

**2. Placeholder scan:** No "TBD"/"TODO"/"handle errors"-style steps; every code step contains complete code.

**3. Type consistency:** `LineLabel(kind=...)` uses `Literal["chord","chord_only","lyric","blank"]` in Task 6 and is matched exactly in Task 7. `merge_chord_lyric`, `chord_only_text`, `align_page`, `convert_layout`, `serialize`, `guess_metadata` signatures are defined in their producing task and used verbatim in later tasks. `SongLine.kind` values in Task 3 (`lyric`,`chord_only`,`directive`,`blank`) match what Task 7 emits.
