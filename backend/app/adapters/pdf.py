"""PDF source adapter, backed by PyMuPDF (imported as ``fitz``)."""

from typing import Any

import pymupdf as fitz  # PyMuPDF; `pymupdf` is the current module name, aliased to keep brief code unchanged

from app.ir import LayoutDoc, Page, TextLine, TextSpan

# PyMuPDF's span "flags" use bit 4 (value 16) to mark bold text.
_BOLD_FLAG = 1 << 4

# A page is treated as two columns only when *both* sides of the page
# midpoint contain at least this many text blocks. A block that straddles the
# midpoint (a full-width title, or a chord row that crosses the middle) is not
# counted on either side, so a one-column page is never split in two.
MIN_BLOCKS_PER_COLUMN = 3

# Blocks may cross the midpoint by a few points without spanning it. This
# tolerance keeps near-misses on their own side.
_COLUMN_MIDPOINT_TOLERANCE = 4.0


class NoTextLayerError(Exception):
    """Raised when a PDF contains no extractable text."""


class PdfAdapter:
    """SourceAdapter implementation that reads a PDF's text layer."""

    def to_layout(self, data: bytes) -> LayoutDoc:
        """Convert PDF ``data`` into a LayoutDoc."""
        try:
            document = fitz.open(stream=data, filetype="pdf")
        except Exception as error:  # PyMuPDF raises FileDataError for unparseable bytes
            raise NoTextLayerError("could not read PDF") from error
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

    def _read_metadata(self, document: Any) -> dict[str, str]:
        """Return the document's non-empty metadata entries.

        ``document`` is a PyMuPDF ``Document``; there is no clean public type
        to import for it, so it is typed ``Any``.
        """
        raw = document.metadata or {}
        return {key: value for key, value in raw.items() if value}

    def _read_page(self, page: Any, number: int) -> Page:
        """Build a Page from one PyMuPDF page, with its lines in reading order.

        ``page`` is a PyMuPDF ``Page``; there is no clean public type to
        import for it, so it is typed ``Any``.
        """
        # get_text("dict") already reports span y-coordinates with a top-left
        # origin, so no coordinate flip is needed here.
        page_dict = page.get_text("dict")

        # Keep each block's bounding box together with its lines. Column
        # detection works on whole blocks, because a single line can cross the
        # page midpoint (a wide chord row) without the page being two-column.
        blocks: list[tuple[tuple[float, float, float, float], list[TextLine]]] = []
        for block in page_dict["blocks"]:
            if block.get("type") != 0:  # 0 = text block
                continue
            lines = self._read_lines(block["lines"])
            if lines:
                bbox = block["bbox"]
                blocks.append(
                    ((bbox[0], bbox[1], bbox[2], bbox[3]), lines)
                )

        ordered = self._order_blocks_into_reading_order(blocks, page.rect.width)

        return Page(
            number=number,
            width=page.rect.width,
            height=page.rect.height,
            lines=ordered,
        )

    def _read_lines(self, raw_lines: list[dict[str, Any]]) -> list[TextLine]:
        """Convert raw PyMuPDF line dicts into TextLines (dropping empty ones)."""
        lines: list[TextLine] = []
        for raw_line in raw_lines:
            line = self._read_line(raw_line)
            if line.spans:
                lines.append(line)
        return lines

    def _order_blocks_into_reading_order(
        self,
        blocks: list[tuple[tuple[float, float, float, float], list[TextLine]]],
        page_width: float,
    ) -> list[TextLine]:
        """Flatten blocks into lines in reading order.

        Most pages are one column, read simply top-to-bottom. Two-column pages
        must be read a whole column at a time, or the two columns' lines
        interleave by y-position. Blocks that span the page width (a title, a
        divider) are read first, ahead of both columns.
        """
        midpoint = page_width / 2
        left: list[tuple[tuple[float, float, float, float], list[TextLine]]] = []
        right: list[tuple[tuple[float, float, float, float], list[TextLine]]] = []
        spanning: list[tuple[tuple[float, float, float, float], list[TextLine]]] = []

        for bbox, lines in blocks:
            x0, _, x1, _ = bbox
            if x1 <= midpoint + _COLUMN_MIDPOINT_TOLERANCE:
                left.append((bbox, lines))
            elif x0 >= midpoint - _COLUMN_MIDPOINT_TOLERANCE:
                right.append((bbox, lines))
            else:
                spanning.append((bbox, lines))

        is_two_column = (
            len(left) >= MIN_BLOCKS_PER_COLUMN
            and len(right) >= MIN_BLOCKS_PER_COLUMN
        )
        if not is_two_column:
            return self._flatten_blocks(blocks)

        return (
            self._flatten_blocks(spanning)
            + self._flatten_blocks(left)
            + self._flatten_blocks(right)
        )

    def _flatten_blocks(
        self,
        blocks: list[tuple[tuple[float, float, float, float], list[TextLine]]],
    ) -> list[TextLine]:
        """Sort blocks top-to-bottom, then their lines top-to-bottom, left-to-right."""
        lines: list[TextLine] = []
        for _, block_lines in sorted(blocks, key=lambda item: (item[0][1], item[0][0])):
            # Sorting lines by (y0, x0) keeps chords that share one baseline in
            # left-to-right order instead of an arbitrary order.
            for line in sorted(
                block_lines,
                key=lambda line: (line.y0, self._line_left_edge(line)),
            ):
                lines.append(line)
        return lines

    def _line_left_edge(self, line: TextLine) -> float:
        """Return the leftmost x-coordinate touched by a line's spans."""
        return min(span.x0 for span in line.spans)

    def _read_line(self, raw_line: dict[str, Any]) -> TextLine:
        """Turn one PyMuPDF line dict into a TextLine of spans.

        Whitespace-only spans are kept: real PDFs store the spaces between
        words as their own spans, and dropping them glues words together
        (``"Almost Heaven"`` would become ``"AlmostHeaven"``). Only truly
        empty spans are skipped.

        ``raw_line`` is PyMuPDF's ``get_text("dict")`` line structure; there is
        no clean public type to import for it, so it is typed as a str-keyed
        dict of ``Any``.
        """
        spans: list[TextSpan] = []
        for raw_span in raw_line["spans"]:
            text = raw_span["text"]
            if text == "":
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
