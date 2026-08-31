"""Tests for the overlay display model (pure, AppKit-free).

Drives OverlayDisplayModel with a deterministic event stream + fake clock and
asserts on the DisplayState DOM — the same events the OverlayRenderer receives,
without AppKit or real time. Uses the segment-based API (list of (speaker, text)
tuples) matching the live callback contract.
"""
"""Tests for the overlay display model (pure, AppKit-free).

Drives OverlayDisplayModel with a deterministic event stream + fake clock and
asserts on the DisplayState DOM — the same events the OverlayRenderer receives,
without AppKit or real time. Uses the segment-based API (list of (speaker, text)
tuples) matching the live callback contract.
"""
from datetime import datetime, timedelta
import io
import os

from rich.console import Console
import pytest

from whisperlivekit.caption_events import EventLog

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "zh_long_ideal.jsonl")

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
    # the delta appends to the line — one coherent caption, prefix + delta
    assert plain(state) == "draft grows more now final"
    assert prev_plain(state) == ""  # nothing split off to history


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


# ---- append effect (provisional growth) ----

def test_preview_growth_appends_in_place_no_scroll():
    """The append effect: when a provisional extends the shown draft, the line
    grows in place — no scroll-up, no queue, no retype. The reader sees one
    growing line, not a new caption per update."""
    m, clk = make()
    m.preview(segs("Today we will discuss"), started_at=U1)
    m.tick()
    assert plain(m.state()) == "Today we will discuss"
    clk.advance(0.2)
    m.preview(segs("Today we will discuss laser"), started_at=U1)
    st = m.tick()
    assert st is not None
    assert plain(st) == "Today we will discuss laser"
    assert st.current[0].style == PROVISIONAL
    # the old draft must NOT have scrolled into history
    assert prev_plain(st) == ""


def test_preview_growth_does_not_churn_history():
    """Rapid provisional growth (the 42-drafts case) leaves history untouched."""
    m, clk = make()
    texts = ["Today we will discuss",
             "Today we will discuss laser",
             "Today we will discuss laser applications",
             "Today we will discuss laser applications in medicine"]
    for t in texts:
        m.preview(segs(t), started_at=U1)
        m.tick()
        clk.advance(0.1)
    st = m.state()
    assert plain(st) == texts[-1]
    assert prev_plain(st) == ""  # no draft ever scrolled up


def test_preview_rewrite_discards_draft_not_history():
    """A rewrite (different prefix) replaces the draft in place; history stays clean."""
    m, clk = make()
    m.preview(segs("We are here today to discuss laser"), started_at=U1)
    m.tick()
    m.preview(segs("Today we will discuss laser"), started_at=U1)
    m.tick()
    assert plain(m.state()) == "Today we will discuss laser"
    assert prev_plain(m.state()) == ""


def test_finals_scroll_but_drafts_never():
    """final→final scrolls the old final to history; draft→final does not."""
    m, clk = make()
    # draft shown
    m.preview(segs("Today we will discuss laser applications"), started_at=U1)
    m.tick()
    # final arrives (amend path: prefix to prev, delta becomes current)
    m.translation(segs("Today we will discuss laser applications in medicine."), started_at=U1)
    m.tick()
    st = m.state()
    # amend appends the delta to the line: one coherent final sentence
    assert plain(st) == "Today we will discuss laser applications in medicine."
    assert prev_plain(st) == ""  # the discarded draft never scrolled
    # next utterance's final scrolls the previous final up
    clk.advance(4.0)
    m.translation(segs("Dentists also use lasers for oral surgery."), started_at=U2)
    m.tick()
    st = m.state()
    assert "Dentists" in plain(st)
    assert "Today we will discuss laser applications in medicine." in prev_plain(st)  # the full final scrolled up


# ---- TUI append effect ----

def test_tui_preview_append_marks_delta():
    """TuiRenderer: a growing provisional renders the stable prefix dim and the
    newly-appended tail brighter (the append effect)."""
    from whisperlivekit.tui import TuiRenderer
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    r = TuiRenderer(console=console)
    r.partial("u1", "hello", U1)  # production order: ASR partial precedes preview
    r.preview("u1", [(None, "Today we will discuss")], U1)
    first = r._partials["u1"][3]
    assert first is not None and first.plain == "Today we will discuss"
    assert "grey50" in str(first.spans[0].style)
    r.preview("u1", [(None, "Today we will discuss laser")], U1)
    grown = r._partials["u1"][3]
    assert grown.plain == "Today we will discuss laser"
    assert "grey50" in str(grown.spans[0].style)      # stable prefix: draft style
    assert "grey70" in str(grown.spans[-1].style)     # appended tail: brighter


def test_tui_preview_rewrites_use_draft_style():
    """A rewrite (different prefix) renders the whole line in the draft style."""
    from whisperlivekit.tui import TuiRenderer
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    r = TuiRenderer(console=console)
    r.partial("u1", "hello", U1)
    r.preview("u1", [(None, "We are here today")], U1)
    r.preview("u1", [(None, "Today we discuss")], U1)
    line = r._partials["u1"][3]
    assert line.plain == "Today we discuss"
    assert all("grey70" not in str(sp.style) for sp in line.spans)


def test_tui_preview_updates_without_started_at_match():
    """Callers pass datetime.now() per update; the preview must still update
    (regression: timestamp equality froze the preview on its first version)."""
    from whisperlivekit.tui import TuiRenderer
    console = Console(file=io.StringIO(), force_terminal=False, width=200)
    r = TuiRenderer(console=console)
    r._partials["u1"] = (U1, "some text", None, None)
    r.preview("u1", [(None, "draft v1")], datetime.now())
    assert "draft v1" in r._partials["u1"][3].plain
    r.preview("u1", [(None, "draft v2 grows")], datetime.now())
    assert "draft v2 grows" in r._partials["u1"][3].plain  # NOT frozen on v1


# ---- golden-stream display sanity (the "what shows in overlay makes sense" bar) ----

def _feed_golden_to_overlay(hold=3.5):
    """Drive the real overlay model with the golden CaptionEvents (the OverlaySink mapping)."""
    events = EventLog.load(GOLDEN_PATH).events
    EPOCH = datetime(2026, 1, 1)

    class C:
        now = 0.0
        def __call__(self): return self.now
        def advance(self, s): self.now += s
    c = C()
    m = OverlayDisplayModel(hold_sec=1.2, clock=c)  # short hold so pacing progresses
    trace = []
    for e in events:
        t = e.type
        if t == "transcription_provisional":
            m.set_partial(e.text)
        elif t == "transcription_final":
            m.clear_partial()
        elif t == "translation_provisional":
            m.preview([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        elif t == "translation_final":
            m.translation([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        c.advance(0.3)
        m.tick()
        snap = m.state()
        trace.append((e, m._en_plain, [sp.style for sp in snap.current],
                      "".join(s.text for s in snap.prev)))
    return events, trace


def test_golden_final_survives_its_hold():
    """After a translation_final lands, the row holds the polished sentence for
    the hold duration — the next sentence's in-flight draft must not wipe it."""
    events = EventLog.load(GOLDEN_PATH).events
    EPOCH = datetime(2026, 1, 1)

    class C:
        now = 0.0

        def __call__(self):
            return self.now

        def advance(self, s):
            self.now += s

    c = C()
    m = OverlayDisplayModel(hold_sec=1.0, clock=c)
    finals_seen = 0
    for e in events:
        t = e.type
        if t == "transcription_provisional":
            m.set_partial(e.text)
        elif t == "transcription_final":
            m.clear_partial()
        elif t == "translation_provisional":
            m.preview([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        elif t == "translation_final":
            m.translation([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        c.advance(0.2)
        m.tick()
        cur = m._en_plain
        if e.type == "translation_final":
            finals_seen += 1
            assert cur == e.text, f"final not displayed when it lands: {cur!r}"
            assert m._en_is_final, "final must be final-styled"
            c.advance(0.1)
            m.tick()
            assert m._en_plain == e.text, "final wiped before its hold elapsed"
    assert finals_seen == 6


def test_preempting_final_clears_stale_queued_draft():
    """A final that takes over the line while its own draft is still queued
    must clear the queue: on a >hold pause, the stale dim draft must not pop
    and regress the bright final (bright->dim on same content)."""
    m, clk = make()
    # draft queued behind nothing (first show)
    m.preview(segs("Sentence two"), started_at=U1)
    m.tick()
    clk.advance(0.1)
    # the final lands while the draft is still queued (preempt)
    m.translation(segs("Sentence two."), started_at=U1)
    m.tick()
    assert m._en_plain == "Sentence two."
    assert m._en_is_final
    assert m._queue == [], "stale draft left queued after the final took over"
    # speaker pauses past the hold: the final must persist (or expire cleanly),
    # never regress to the stale dim draft
    clk.advance(4.0)
    m.tick()
    assert m._en_plain != "Sentence two", "stale draft popped over the bright final"
