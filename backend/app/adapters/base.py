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
