"""Tests for the overlay display model (pure, AppKit-free).

Drives OverlayDisplayModel with a deterministic event stream + fake clock and
asserts on the DisplayState DOM — the same events the OverlayRenderer receives,
without AppKit or real time. Uses the segment-based API (list of (speaker, text)
tuples) matching the live callback contract.
"""
from datetime import datetime
import pytest

from whisperlivekit.overlay_model import (
    FINAL_SAME,
    FINAL_ADD,
    PROVISIONAL,
    DisplayState,
    OverlayDisplayModel,
    Span,
)

U1 = datetime(2026, 1, 1, 0, 0, 1)
U2 = datetime(2026, 1, 1, 0, 0, 2)


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


def segs(text, diff=None):
    """Build a single-speaker segment list (None speaker = no marker)."""
    return [(None, text, diff)] if diff else [(None, text)]


def plain(state):
    return "".join(s.text for s in state.current)


def prev_plain(state):
    return "".join(s.text for s in state.prev)


# ---- provisional ----

def test_preview_is_dimmed_and_does_not_expire():
    m, clk = make()
    m.preview(segs("Hello there"), started_at=U1)
    m.tick()
    state = m.state()
    assert state.current and state.current[0].style == PROVISIONAL


def test_preview_persists_after_hold_no_final():
    """A provisional never expires on its own — a vanishing draft reads as dropped."""
    m, clk = make()
    m.preview(segs("draft text"), started_at=U1)
    m.tick()
    clk.advance(10 * 3.5)
    m.tick()
    assert plain(m.state()) == "draft text"


def test_preview_rewrite_replaces_frozen_draft():
    """The MT re-commits a different prefix — the display must hard-replace."""
    m, clk = make()
    m.preview(segs("We are here today to discuss laser"), started_at=U1)
    m.tick()
    m.preview(segs("Today we will discuss laser"), started_at=U1)
    m.tick()
    assert plain(m.state()) == "Today we will discuss laser"


def test_preview_unchanged_skips():
    m, _ = make()
    m.preview(segs("same text"), started_at=U1)
    m.tick()
    m.preview(segs("same text"), started_at=U1)
    assert m.tick() is None  # no churn


# ---- final ----

def test_final_single_sentence_shows_immediately():
    m, clk = make()
    m.preview(segs("draft"), started_at=U1)
    m.tick()
    m.translation(segs("The real sentence."), started_at=U1)
    m.tick()  # drain the queued delta
    state = m.state()
    assert plain(state) == "The real sentence."
    assert state.current[0].style == FINAL_SAME
    assert state.prev == []  # own provisional never scrolls up


def test_two_consecutive_finals_scroll_up():
    """Speak two sentences; when the second shows, the first must be on prev."""
    m, clk = make()
    m.translation(segs("First caption here."), started_at=U1)
    m.tick()
    m.translation(segs("Second caption arrives."), started_at=U1)
    m.tick()  # drain the queued delta
    state = m.state()
    assert plain(state) == "Second caption arrives."
    assert prev_plain(state) == "First caption here."


def test_final_replaces_provisional_in_place():
    """A same-utterance final correcting a provisional: the common-prefix amend keeps
    the shown prefix (flips to final style) and only enqueues the delta. The committed
    prefix scrolls up when the delta shows (multi-sentence pacing). No cross-utterance
    scroll — the prev row holds the committed prefix, not an old caption."""
    m, clk = make()
    m.preview(segs("draft grows"), started_at=U1)
    m.tick()
    m.preview(segs("draft grows more"), started_at=U1)
    m.tick()
    m.translation(segs("draft grows more now final"), started_at=U1)
    m.tick()  # drain
    state = m.state()
    # delta "now final" on current; committed prefix scrolled to prev
    assert "now final" in plain(state)
    assert prev_plain(state) == "draft grows more"  # committed prefix, not old caption


def test_final_expires_after_hold():
    m, clk = make()
    m.translation(segs("Temporary caption."), started_at=U1)
    m.tick()
    clk.advance(3.6)
    m.tick()  # hold elapsed
    assert plain(m.state()) == ""


def test_prev_expires_on_own_timer():
    m, clk = make()
    m.translation(segs("First."), started_at=U1)
    m.tick()
    m.translation(segs("Second."), started_at=U1)
    m.tick()
    assert prev_plain(m.state()) == "First."
    clk.advance(3.6)
    m.tick()  # prev hold elapsed
    assert prev_plain(m.state()) == ""


# ---- diff rendering ----

def test_final_with_diff_shows_add_green():
    """A final with diff spans renders 'add' as FINAL_ADD, 'same' as FINAL_SAME,
    'del' omitted."""
    m, clk = make()
    diff = [("same", "Hello "), ("del", "world"), ("add", "there")]
    m.translation([(None, "Hello there", diff)], started_at=U1)
    m.tick()
    state = m.state()
    styles = [s.style for s in state.current]
    texts = [s.text for s in state.current]
    assert FINAL_ADD in styles
    assert "there" in texts
    assert "world" not in texts  # del omitted


def test_provisional_with_diff_renders_all_dimmed():
    m, clk = make()
    diff = [("same", "Hello "), ("add", "world")]
    m.preview([(None, "Hello world", diff)], started_at=U1)
    m.tick()
    state = m.state()
    assert all(s.style == PROVISIONAL for s in state.current)


# ---- partial ----

def test_partial_in_state():
    m, clk = make()
    m.set_partial("源语言 partial")
    m.tick()
    state = m.state()
    assert state.partial == "源语言 partial"
