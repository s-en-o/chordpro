"""PDF source adapter, backed by PyMuPDF (imported as ``fitz``)."""

import pymupdf as fitz  # PyMuPDF; `pymupdf` is the current module name, aliased to keep brief code unchanged

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
