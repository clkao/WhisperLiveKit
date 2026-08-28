"""Tests for the CJK-aware inline diff (terminal correction rendering)."""
from whisperlivekit.inline_diff import inline_diff


def test_word_correction_produces_del_add():
    spans = inline_diff("lets discuss the laser", ["let's discuss the laser"])[0]
    assert spans is not None
    kinds = [k for k, _ in spans]
    assert "del" in kinds and "add" in kinds
    # the final text must reconstruct via same+add spans (del omitted)
    joined = "".join(w for k, w in spans if k in ("same", "add"))
    assert joined == "let's discuss the laser"


def test_punctuation_only_change_yields_no_spans():
    spans = inline_diff("America", ["America,"])[0]
    assert spans is None  # casing/punctuation compares equal


def test_cjk_chars_are_individually_tokenized():
    old = "我們在討論雷射"
    new = "我們正在討論雷射"
    spans = inline_diff(old, [new])[0]
    assert spans is not None
    assert any(k == "add" for k, _ in spans)
    # verbatim reconstruction: same+add spans reproduce the new text
    assert "".join(t for k, t in spans if k != "del") == new


def test_no_change_returns_none():
    assert inline_diff("same text", ["same text"])[0] is None


def test_segments_sliced_per_segment():
    spans = inline_diff("one two", ["one", "TWO three"])
    assert len(spans) == 2
    # second segment carries the change
    assert spans[0] is None
    assert spans[1] is not None
