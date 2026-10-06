from app.chordpro import section_directives, section_label


def test_section_label_recognizes_bracket_and_brace_forms() -> None:
    assert section_label("[Chorus]") == "chorus"
    assert section_label("{Verse 1}") == "verse"
    assert section_label("[Bridge]") == "bridge"
    assert section_label("[Intro]") == "intro"
    assert section_label("[Outro]") == "outro"


def test_section_label_is_case_insensitive() -> None:
    assert section_label("[CHORUS]") == "chorus"
    assert section_label("[verse 2]") == "verse"


def test_section_label_ignores_trailing_detail() -> None:
    assert section_label("[Verse 3 - Sax break]") == "verse"
    assert section_label("[Chorus 2]") == "chorus"


def test_section_label_normalizes_pre_chorus() -> None:
    assert section_label("[Pre-Chorus]") == "pre-chorus"
    assert section_label("[Pre Chorus]") == "pre-chorus"


def test_section_label_rejects_real_chords() -> None:
    for token in ["[C]", "[Am]", "[G7]", "{chord}"]:
        assert section_label(token) is None, token


def test_section_label_rejects_metadata_and_plain_lyrics() -> None:
    assert section_label("{title: My Song}") is None
    assert section_label("just a lyric") is None
    assert section_label("[C]Hello world") is None
    assert section_label("") is None


def test_section_directives_for_environments_are_bare() -> None:
    # verse/chorus/bridge get real, unlabelled environments.
    assert section_directives("[Verse 1]") == ("{start_of_verse}", "{end_of_verse}")
    assert section_directives("[Chorus]") == ("{start_of_chorus}", "{end_of_chorus}")
    assert section_directives("[Bridge]") == ("{start_of_bridge}", "{end_of_bridge}")


def test_section_directives_for_others_are_comments() -> None:
    # No ChordPro environment exists for these, so they become comments that
    # keep the original label text.
    assert section_directives("[Intro]") == ("{comment: Intro}", None)
    assert section_directives("[Outro]") == ("{comment: Outro}", None)
    assert section_directives("[Solo]") == ("{comment: Solo}", None)
    assert section_directives("[Instrumental]") == ("{comment: Instrumental}", None)
    assert section_directives("[Pre-Chorus]") == ("{comment: Pre-Chorus}", None)


def test_section_directives_bare_environment_drops_trailing_detail() -> None:
    # Bare environments carry no label, so "[Verse 3 - Sax break]" becomes a
    # plain verse environment (the extra detail is not preserved).
    assert section_directives("[Verse 3 - Sax break]") == (
        "{start_of_verse}",
        "{end_of_verse}",
    )
