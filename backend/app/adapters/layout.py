"""Shared machinery for turning PyMuPDF page structures into the IR.

Both the text-layer PDF adapter and the OCR fallback adapter get their page
data from PyMuPDF in the same "dict" shape (``Page.get_text("dict")`` and
``TextPage.extractDICT()`` return identical structures). This module holds the
one copy of the line-grouping, column-detection, and reading-order logic so
both adapters behave the same way.
"""

from typing import Any

from app.ir import Page, TextLine, TextSpan

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

# Footer furniture (a right-aligned page number) sits within this fraction of
# the page height from the bottom edge. Such blocks are ignored when deciding
# whether a page has two columns; a page number must not make a one-column
# page look like two. Only the bottom band is used, because song content often
# starts near the very top of the page.
_BOTTOM_MARGIN_FRACTION = 0.08


class LayoutBuilder:
    """Builds a ``Page`` from a PyMuPDF page dict, in reading order."""

    def build_page(
        self,
        page_dict: dict[str, Any],
        number: int,
        width: float,
        height: float,
    ) -> Page:
        """Turn one PyMuPDF page dict into a Page with its lines in reading order."""
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
                blocks.append(((bbox[0], bbox[1], bbox[2], bbox[3]), lines))

        ordered = self._order_blocks_into_reading_order(blocks, width, height)
        return Page(number=number, width=width, height=height, lines=ordered)

    def _read_lines(self, raw_lines: list[dict[str, Any]]) -> list[TextLine]:
        """Convert raw PyMuPDF line dicts into TextLines.

        A line is dropped only when it has no visible text at all (a line that
        is entirely spaces carries no content).
        """
        lines: list[TextLine] = []
        for raw_line in raw_lines:
            line = self._read_line(raw_line)
            if line.spans and line.text.strip():
                lines.append(line)
        return lines

    def _order_blocks_into_reading_order(
        self,
        blocks: list[tuple[tuple[float, float, float, float], list[TextLine]]],
        page_width: float,
        page_height: float,
    ) -> list[TextLine]:
        """Flatten blocks into lines in reading order.

        Most pages are one column, read simply top-to-bottom. Two-column pages
        must be read a whole column at a time, or the two columns' lines
        interleave by y-position. Full-width blocks (a title, a section rule)
        divide the page into horizontal bands: each band's left column is read,
        then its right column, then the divider itself.
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

        if not self._is_two_column_page(left, right, page_height):
            return self._flatten_blocks(blocks)

        return self._read_two_column_bands(left, right, spanning)

    def _is_two_column_page(
        self,
        left: list[tuple[tuple[float, float, float, float], list[TextLine]]],
        right: list[tuple[tuple[float, float, float, float], list[TextLine]]],
        page_height: float,
    ) -> bool:
        """Return True when the page has enough body blocks on both sides.

        Footer furniture (a right-aligned page number) is ignored, so a
        one-column page with a page number does not look like two columns.
        """
        body_left = 0
        for block in left:
            if not self._in_margin(block[0], page_height):
                body_left += 1
        body_right = 0
        for block in right:
            if not self._in_margin(block[0], page_height):
                body_right += 1
        return (
            body_left >= MIN_BLOCKS_PER_COLUMN
            and body_right >= MIN_BLOCKS_PER_COLUMN
        )

    def _read_two_column_bands(
        self,
        left: list[tuple[tuple[float, float, float, float], list[TextLine]]],
        right: list[tuple[tuple[float, float, float, float], list[TextLine]]],
        spanning: list[tuple[tuple[float, float, float, float], list[TextLine]]],
    ) -> list[TextLine]:
        """Read two columns band by band, using full-width blocks as dividers."""
        remaining_left = sorted(left, key=lambda block: block[0][1])
        remaining_right = sorted(right, key=lambda block: block[0][1])
        dividers = sorted(spanning, key=lambda block: block[0][1])

        lines: list[TextLine] = []
        for divider_bbox, divider_lines in dividers:
            divider_top = divider_bbox[1]
            # Everything above this divider belongs to the current band.
            above_left = self._take_blocks_above(remaining_left, divider_top)
            above_right = self._take_blocks_above(remaining_right, divider_top)
            lines.extend(self._flatten_blocks(above_left))
            lines.extend(self._flatten_blocks(above_right))
            lines.extend(self._flatten_blocks([(divider_bbox, divider_lines)]))

        # Whatever is left sits below the last divider.
        lines.extend(self._flatten_blocks(remaining_left))
        lines.extend(self._flatten_blocks(remaining_right))
        return lines

    def _take_blocks_above(
        self,
        blocks: list[tuple[tuple[float, float, float, float], list[TextLine]]],
        y_limit: float,
    ) -> list[tuple[tuple[float, float, float, float], list[TextLine]]]:
        """Remove and return the front blocks that start above ``y_limit``.

        ``blocks`` must be sorted by top edge; it is mutated in place.
        """
        taken: list[tuple[tuple[float, float, float, float], list[TextLine]]] = []
        while blocks and blocks[0][0][1] < y_limit:
            taken.append(blocks.pop(0))
        return taken

    def _in_margin(
        self,
        bbox: tuple[float, float, float, float],
        page_height: float,
    ) -> bool:
        """Return True when a block sits in the bottom footer band."""
        _, y0, _, _ = bbox
        return y0 >= page_height * (1.0 - _BOTTOM_MARGIN_FRACTION)

    def _flatten_blocks(
        self,
        blocks: list[tuple[tuple[float, float, float, float], list[TextLine]]],
    ) -> list[TextLine]:
        """Return every line across the blocks in true reading order.

        Lines are sorted by (y0, x0) across all blocks, not block-by-block. A
        block's top edge can sit above a line that actually belongs to another
        block on nearly the same baseline (a decoration block above a chord
        row), so sorting whole blocks first would mis-order those lines.
        Sorting all lines by (y0, x0) keeps chords that share one baseline in
        left-to-right order and puts each chord next to its lyric. Block
        contiguity is intentionally not preserved: when two blocks overlap in
        y within the same column, their lines interleave by baseline.
        """
        all_lines: list[TextLine] = []
        for _, block_lines in blocks:
            all_lines.extend(block_lines)
        return sorted(
            all_lines,
            key=lambda line: (line.y0, self._line_left_edge(line)),
        )

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
