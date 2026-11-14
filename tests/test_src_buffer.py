"""The one helper left in ``src_buffer.py`` (the source-row sentence test).

``ends_sentence`` is what the terminal driver asks about a grown cumulative
source line: has it landed a whole sentence, so the suffix may print on its own
(``scripts/lc_terminal.py:TerminalSink``). The overlay's reading buffer — the
second copy of the source row rule, with its own promote/freeze bookkeeping — is
gone; the caption display model owns that rule now (``DisplayState.partial``,
``tests/test_caption_display.py``, and the overlay layout tests).
"""


def test_ends_sentence_latin_and_cjk_terminators():
    """A finished sentence in either script ends the line; an in-flight clause
    does not (the terminal prints the suffix only when this is true)."""
    from whisperlivekit.src_buffer import ends_sentence
    assert ends_sentence("and I will give a short overview of the paper.")
    assert ends_sentence("镭射在现代医学中扮演着越来越重要的角色。")
    assert ends_sentence("真的吗？")
    assert ends_sentence("太棒了！")
    assert ends_sentence('He called it "the laser age."')
    assert not ends_sentence("and I will give")
    assert not ends_sentence("镭射在医学上的应用")


def test_ends_sentence_ignores_trailing_whitespace():
    """The ASR fragment carries trailing spaces; they are not the last character
    the test looks at."""
    from whisperlivekit.src_buffer import ends_sentence
    assert ends_sentence("of the paper.  ")
    assert not ends_sentence("")
