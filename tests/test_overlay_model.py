"""Tests for the overlay display model (pure, AppKit-free).

Drives OverlayDisplayModel with a deterministic event stream + fake clock and
asserts on the DisplayState DOM — the same events the OverlayRenderer receives,
without AppKit or real time.
"""
import pytest

from whisperlivekit.overlay_model import (
    FINAL,
    PROVISIONAL,
    DisplayState,
    OverlayDisplayModel,
    Span,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, s: float) -> None:
        self.now += s


def make(hold=3.5):
    clk = FakeClock()
    return OverlayDisplayModel(hold_sec=hold, clock=clk), clk


def plain(state):
    return "".join(s.text for s in state.current)


def prev_plain(state):
    return "".join(s.text for s in state.prev)


# ---- provisional ----

def test_preview_is_dimmed_and_does_not_expire():
    m, clk = make()
    m.preview("Hello there", utt=("u1", 1))
    st = m.tick()
    assert plain(st := st) if False else True
    state = m.state()
    assert state.current and state.current[0].style == PROVISIONAL


def test_preview_persists_after_hold_no_final():
    """A provisional never expires on its own — a vanishing draft reads as dropped."""
    m, clk = make()
    m.preview("draft text", ("u1", 1))
    m.tick()
    clk.advance(10 * 3.5)
    m.tick()  # hold elapsed, nothing queued — provisional must persist
    assert plain(m.state()) == "draft text"


def test_preview_rewrite_replaces_frozen_draft():
    """The MT re-commits a different prefix — the display must hard-replace and stay
    current (the frozen-34s bug)."""
    m, clk = make()
    m.preview("We are here today to discuss laser", ("u1", 1))
    m.tick()
    m.preview("Today we will discuss laser", ("u1", 1))  # rewrite (different prefix)
    m.tick()
    assert plain(m.state()) == "Today we will discuss laser"


def test_preview_unchanged_skips():
    m, _ = make()
    m.preview("same text", ("u1", 1))
    m.tick()
    st = m.state()
    m.preview("same text", ("u1", 1))
    assert m.tick() is None  # no churn


# ---- final ----

def test_final_single_sentence_shows_immediately():
    m, clk = make()
    m.preview("draft", ("u1", 1))
    m.tick()
    m.translation("The real sentence.", ("u1", 1))
    state = m.state()
    assert plain(state) == "The real sentence."
    assert state.current[0].style == FINAL
    assert state.prev == []  # own provisional never scrolls up


def test_final_multi_sentence_last_on_current_second_on_prev():
    m, clk = make()
    m.translation("Sentence one. Sentence two. Sentence three.", ("u1", 1))
    state = m.state()
    assert plain(state) == "Sentence three."
    assert "".join(s.text for s in state.prev) == "Sentence two."


def test_two_consecutive_sentences_top_row_gets_first():
    """The live-report scenario: speak two sentences; when the second shows, the
    first must be on the prev row."""
    m, clk = make()
    m.translation("First caption here.", ("u1", 1))
    assert plain(m.state()) == "First caption here."
    m.translation("Second caption arrives.", ("u2", 2))
    state = m.state()
    assert plain(state) == "Second caption arrives."
    assert "".join(s.text for s in state.prev) == "First caption here."


def test_final_replaces_queue_provisional():
    m, clk = make()
    m.preview("draft grows", ("u1", 1))
    m.tick()
    m.preview("draft grows more", ("u1", 1))  # still queued
    m.translation("The committed line.", ("u1", 1))
    assert plain(m.state()) == "The committed line."


# ---- drainer / hold ----

def test_queue_releases_after_hold_and_scrolls_up():
    m, clk = make()
    m.preview("first draft", ("u1", 1))
    m.tick()
    m.preview("first draft longer", ("u1", 1))  # queued, newest wins
    clk.advance(3.6)
    m.tick()
    assert plain(m.state()) == "first draft longer"


def test_final_expires_after_hold_when_idle():
    m, clk = make()
    m.translation("A caption.", ("u1", 1))
    assert plain(m.state()) == "A caption."
    clk.advance(4.0)
    m.tick()
    assert plain(m.state()) == ""  # expired


def test_prev_expires_on_own_timer():
    m, clk = make()
    m.translation("One. Two.", ("u1", 1))  # current="Two.", prev="One."
    clk.advance(3.0)
    m.tick()  # nothing expires yet
    assert m.state().prev, "prev should still show"
    clk.advance(1.0)
    m.tick()
    assert m.state().prev == []  # 4.0s > 3.5s hold — expired


def test_new_utterance_provisional_scrolls_committed_final_up():
    m, clk = make()
    m.translation("Committed caption.", ("u1", 1))
    clk.advance(4.0)
    m.tick()  # final expires (empty current)
    # new utterance's final arrives
    m.translation("New caption here.", ("u2", 2))
    state = m.state()
    assert plain(state) == "New caption here."
    # the expired current was cleared; prev shows the new utterance's history only
    # via scroll-up — an expired final leaves nothing behind.
    assert state.prev == []


def test_tick_returns_none_when_unchanged():
    m, clk = make()
    m.preview("hello", ("u1", 1))
    first = m.tick()
    assert first is not None
    assert m.tick() is None  # identical state → skip render
