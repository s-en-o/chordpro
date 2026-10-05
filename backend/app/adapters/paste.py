"""Source adapter for pasted chord sheets (plain text).

Pasted text has no fonts and no coordinates, so we reconstruct a simple
monospace grid: each character sits in a fixed-width column, and each line
sits on a fixed-height row. That is enough for the conversion engine, whose
chord/lyric alignment is driven by character positions relative to each other.
"""

from app.adapters.base import NoTextLayerError
from app.ir import LayoutDoc, Page, TextLine, TextSpan

# Size of one character cell in the synthetic grid. The absolute values do not
# matter, only their consistency: alignment compares relative positions.
CHAR_WIDTH = 7.2
LINE_HEIGHT = 14.0

# A tab advances to the next multiple of this many columns.
TAB_WIDTH = 4


class PasteTextAdapter:
    """SourceAdapter implementation that reads pasted plain text."""

    def to_layout(self, data: bytes) -> LayoutDoc:
        """Convert pasted ``data`` into a LayoutDoc on a monospace grid."""
        text = data.decode("utf-8", errors="replace")
        normalized = self._normalize(text)
        raw_lines = normalized.split("\n")
        lines: list[TextLine] = []
        for index, raw_line in enumerate(raw_lines):
            if raw_line.strip() == "":
                continue
            lines.append(self._build_line(raw_line, index))

        if not lines:
            raise NoTextLayerError("no text to convert")
        return LayoutDoc(
            pages=[
                Page(
                    number=1,
                    width=self._page_width(lines),
                    height=len(raw_lines) * LINE_HEIGHT,
                    lines=lines,
                )
            ],
            metadata={},
        )

    def _normalize(self, text: str) -> str:
        """Normalize line endings, tabs, leading BOM, and non-breaking spaces."""
        text = text.replace("\ufeff", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u00a0", " ")
        return text.expandtabs(TAB_WIDTH)

    def _build_line(self, raw_line: str, index: int) -> TextLine:
        """Build one TextLine at the given row, its span spanning the line."""
        y0 = index * LINE_HEIGHT
        y1 = y0 + LINE_HEIGHT
        # The span spans the whole line, so a character's x-center is derived
        # from its column by the geometry helpers.
        x0 = 0.0
        x1 = len(raw_line) * CHAR_WIDTH
        span = TextSpan(
            text=raw_line,
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            size=LINE_HEIGHT,
            bold=False,
        )
        return TextLine(spans=[span], y0=y0, y1=y1)

    def _page_width(self, lines: list[TextLine]) -> float:
        """Return a page width just wide enough for the longest line."""
        widest = 0.0
        for line in lines:
            for span in line.spans:
                if span.x1 > widest:
                    widest = span.x1
        return widest
