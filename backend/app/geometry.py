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
            # Round to a sub-micropoint precision so repeated floating-point
            # arithmetic gives stable, comparable character centers.
            centers.append(round(span.x0 + fraction * width, 6))
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
