"""PDF source adapter, backed by PyMuPDF (imported as ``fitz``)."""

from typing import Any

import pymupdf as fitz  # PyMuPDF; `pymupdf` is the current module name, aliased to keep brief code unchanged

from app.adapters.base import NoTextLayerError
from app.adapters.layout import LayoutBuilder
from app.ir import LayoutDoc, Page

# Re-exported so existing imports (``from app.adapters.pdf import NoTextLayerError``)
# keep working; the class itself is defined in base.py.
__all__ = ["NoTextLayerError", "PdfAdapter"]


class PdfAdapter(LayoutBuilder):
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
        return self.build_page(
            page_dict,
            number=number,
            width=page.rect.width,
            height=page.rect.height,
        )
