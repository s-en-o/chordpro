"""The intermediate representation (IR): a source-agnostic layout document.

Every input source (PDF now; pasted text or screenshots later) is normalized
into these dataclasses before the conversion engine runs. Coordinates use a
top-left origin, in points.
"""

from dataclasses import dataclass, field

# Metadata key a source sets to say "do not infer a title from my first line".
# Used by sources with no heading (e.g. pasted text), consumed by the metadata
# guesser.
NO_HEADING_KEY = "no_heading_inference"


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
