from app.models import QAReport, Song, SongLine


def test_song_defaults_are_independent() -> None:
    first = Song()
    second = Song()
    first.lines.append(SongLine(kind="blank", text=""))
    assert second.lines == []
    assert isinstance(second.qa, QAReport)


def test_qa_report_defaults() -> None:
    report = QAReport()
    assert report.unpaired_chords == []
    assert report.low_confidence_lines == []
    assert report.notes == []
