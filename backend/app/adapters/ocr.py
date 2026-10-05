"""OCR fallback adapter for PDFs with no extractable text layer.

Some PDFs (scanned images, or pages whose text was converted to vector
outlines) contain no text for the normal adapter to read. This adapter
rasterizes each page and runs OCR on it, producing the same LayoutDoc IR.

It relies on Tesseract being installed on the system (PyMuPDF calls it
through its OCR support). If no text page is produced, ``NoTextLayerError``
is raised so the API can report a clear failure.
"""

from typing import Any

import pymupdf as fitz  # PyMuPDF; OCR runs Tesseract under the hood

from app.adapters.base import NoTextLayerError, OcrUnavailableError
from app.adapters.layout import LayoutBuilder
from app.ir import LayoutDoc, Page

# Render resolution for OCR. 300 dpi is the usual sweet spot for songbook
# text; higher values cost time without much accuracy gain.
OCR_DPI = 300
OCR_LANGUAGE = "eng"


class OcrAdapter(LayoutBuilder):
    """SourceAdapter implementation that OCRs each PDF page."""

    def to_layout(self, data: bytes) -> LayoutDoc:
        """Convert text-less PDF ``data`` into a LayoutDoc by OCRing each page."""
        try:
            document = fitz.open(stream=data, filetype="pdf")
        except Exception as error:  # unparseable bytes
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
            raise NoTextLayerError("OCR found no text")
        return LayoutDoc(pages=pages, metadata=metadata)

    def _read_metadata(self, document: Any) -> dict[str, str]:
        """Return the document's non-empty metadata entries.

        ``document`` is a PyMuPDF ``Document``; there is no clean public type
        to import for it, so it is typed ``Any``.
        """
        raw = document.metadata or {}
        return {key: value for key, value in raw.items() if value}

    def _read_page(self, page: Any, number: int) -> Page:
        """OCR one page and build a Page with its lines in reading order.

        ``page`` is a PyMuPDF ``Page``; there is no clean public type to
        import for it, so it is typed ``Any``.
        """
        # get_textpage_ocr renders the page to a bitmap and recognizes text.
        # Tesseract being missing or unusable surfaces as a low-level PyMuPDF
        # error; turn that into a domain error the API can report cleanly.
        try:
            text_page = page.get_textpage_ocr(
                dpi=OCR_DPI, full=True, language=OCR_LANGUAGE
            )
        except Exception as error:
            raise OcrUnavailableError(
                "OCR unavailable (is Tesseract installed?)"
            ) from error
        words = text_page.extractWORDS()
        page_dict = self._words_to_page_dict(words)
        return self.build_page(
            page_dict,
            number=number,
            width=page.rect.width,
            height=page.rect.height,
        )

    def _words_to_page_dict(self, words: list[tuple]) -> dict[str, Any]:
        """Group OCR words into visual rows and build a PyMuPDF-shaped page dict.

        PyMuPDF's OCR output fragments each visual row into many one-word
        "lines". We re-group words that share a baseline into a single row, then
        present each row as one block/line so the shared reading-order logic can
        handle them. Every word becomes its own span, keeping its own box, so
        chord/lyric alignment stays accurate.

        Each ``word`` tuple is ``(x0, y0, x1, y1, text, block, line, word_no)``.
        """
        rows: list[list[tuple]] = []
        for word in words:
            if word[4].strip():
                self._add_word_to_row(rows, word)
        blocks: list[dict[str, Any]] = []
        for row in rows:
            row.sort(key=lambda w: w[0])
            spans = []
            last_index = len(row) - 1
            for position, word in enumerate(row):
                x0, y0, x1, y1, text = word[0], word[1], word[2], word[3], word[4]
                # A trailing space keeps words from gluing together, but only
                # between words -- a trailing space on the last word would add
                # a phantom character that skews chord/lyric alignment.
                word_text = text if position == last_index else text + " "
                spans.append(
                    {
                        "text": word_text,
                        "bbox": (x0, y0, x1, y1),
                        "size": y1 - y0,
                        "flags": 0,
                    }
                )
            row_top = min(word[1] for word in row)
            row_bottom = max(word[3] for word in row)
            row_left = min(word[0] for word in row)
            row_right = max(word[2] for word in row)
            bbox = (row_left, row_top, row_right, row_bottom)
            blocks.append(
                {
                    "type": 0,
                    "bbox": bbox,
                    "lines": [{"spans": spans, "bbox": bbox}],
                }
            )
        return {"blocks": blocks}

    def _add_word_to_row(self, rows: list[list[tuple]], word: tuple) -> None:
        """Append a word to a row sharing its baseline, creating one if needed.

        Words group when their vertical centres are within half the *smaller*
        word's height. Using the smaller height (not the taller) keeps a chord
        row and the lyric row directly beneath it separate even when OCR gives
        them different box heights.
        """
        y_center = (word[1] + word[3]) / 2
        height = word[3] - word[1]
        for row in rows:
            row_center = sum((w[1] + w[3]) / 2 for w in row) / len(row)
            row_height = min(w[3] - w[1] for w in row)
            if abs(row_center - y_center) <= 0.5 * min(height, row_height):
                row.append(word)
                return
        rows.append([word])
