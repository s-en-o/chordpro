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
