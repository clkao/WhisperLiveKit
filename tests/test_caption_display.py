"""Tests for the caption display model (pure, no view).

Drives ``CaptionDisplay`` with a deterministic clock and either the feed
methods or recorded caption event streams (``tests/golden/*.jsonl``), and
asserts on the ``DisplayState`` the model publishes — the state a view
renders. No view, AppKit, or real time is involved.
"""
from pathlib import Path

import pytest

from whisperlivekit.caption_display import (
    FINAL_ADD,
    FINAL_SAME,
    PROVISIONAL,
    CaptionDisplay,
    DisplayState,
    load_caption_events,
)
from whisperlivekit.caption_events import CaptionEvent

GOLDEN_DIR = Path(__file__).parent / "golden"
ZH_LONG_IDEAL = GOLDEN_DIR / "zh_long_ideal.jsonl"
ZH_LONG_TIME_FRONTIER = GOLDEN_DIR / "zh_long_time_frontier.jsonl"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, s: float) -> None:
        self.now += s


def make(hold=3.5):
    clk = FakeClock()
    return CaptionDisplay(hold_sec=hold, clock=clk), clk


def plain(state):
    return "".join(s.text for s in state.current)


def prev_plain(state):
    return "".join(s.text for s in state.prev)


def is_bright(state):
    """The line holds committed text (no dim draft span on it)."""
    return bool(state.current) and all(s.style != PROVISIONAL for s in state.current)


def event(kind, text, audio_t=1.0, **kw):
    return CaptionEvent(t=0.0, audio_t=audio_t, type=kind, text=text, **kw)


# ---- provisional ----

def test_preview_is_dimmed_and_does_not_expire():
    m, clk = make()
    m.preview("Hello there")
    m.tick()
    state = m.state()
    assert state.current and state.current[0].style == PROVISIONAL


def test_preview_persists_after_hold_no_final():
    """A provisional never expires on its own — a vanishing draft reads as dropped."""
    m, clk = make()
    m.preview("draft text")
    m.tick()
    clk.advance(10 * 3.5)
    m.tick()
    assert plain(m.state()) == "draft text"


def test_preview_rewrite_replaces_frozen_draft():
    """The MT re-commits a different prefix — the display must hard-replace."""
    m, clk = make()
    m.preview("We are here today to discuss laser")
    m.tick()
    m.preview("Today we will discuss laser")
    m.tick()
    assert plain(m.state()) == "Today we will discuss laser"


def test_preview_unchanged_skips():
    m, _ = make()
    m.preview("same text")
    m.tick()
    m.preview("same text")
    assert m.tick() is None  # no churn


# ---- final ----

def test_final_single_sentence_shows_immediately():
    m, clk = make()
    m.preview("draft")
    m.tick()
    m.translation("The real sentence.")
    m.tick()  # drain the queued delta
    state = m.state()
    assert plain(state) == "The real sentence."
    assert state.current[0].style == FINAL_SAME
    assert state.prev == []  # own provisional never scrolls up


def test_two_consecutive_finals_scroll_up():
    """Speak two sentences; when the second shows, the first must be on prev.
    A final landing while the first is inside its hold queues behind it and
    pops after MIN_SHOW (half the hold) — no flash, no loss."""
    m, clk = make()
    m.translation("First caption here.")
    m.tick()
    m.translation("Second caption arrives.")
    # queued behind the shown final's minimum show (hold/2)
    clk.advance(2.0)
    m.tick()
    state = m.state()
    assert plain(state) == "Second caption arrives."
    assert prev_plain(state) == "First caption here."


def test_final_replaces_provisional_in_place():
    """A same-utterance final correcting a provisional: the common-prefix amend keeps
    the shown prefix (flips to final style) and only enqueues the delta. The committed
    prefix scrolls up when the delta shows (multi-sentence pacing). No cross-utterance
    scroll — the prev row holds the committed prefix, not an old caption."""
    m, clk = make()
    m.preview("draft grows")
    m.tick()
    m.preview("draft grows more")
    m.tick()
    m.translation("draft grows more now final")
    m.tick()  # drain
    state = m.state()
    # the delta appends to the line — one coherent caption, prefix + delta
    assert plain(state) == "draft grows more now final"
    assert prev_plain(state) == ""  # nothing split off to history


def test_final_expires_after_hold():
    m, clk = make()
    m.translation("Temporary caption.")
    m.tick()
    clk.advance(3.6)
    m.tick()  # hold elapsed
    assert plain(m.state()) == ""


def test_prev_expires_on_own_timer():
    m, clk = make()
    m.translation("First.")
    m.tick()
    m.translation("Second.")
    clk.advance(2.0)  # queued final pops after MIN_SHOW
    m.tick()
    assert prev_plain(m.state()) == "First."
    clk.advance(3.6)
    m.tick()  # prev hold elapsed
    assert prev_plain(m.state()) == ""
    clk.advance(3.6)
    m.tick()  # prev hold elapsed
    assert prev_plain(m.state()) == ""


# ---- styling: the model's own word diff on a reword ----

def test_reworded_line_marks_the_correction_green():
    """A reworded final amends the sentence on the line with the model's word
    diff: unchanged words stay bright, the changed/new words are green, and
    deleted words are omitted — the correction is visible instead of the whole
    line silently swapping."""
    m, clk = make()
    S1 = "Dentists also use laser technology for oral surgery."
    m.preview("Dentists also use laser technology for ")
    m.tick()
    m.preview(S1 + " This reduces")
    m.tick()
    assert prev_plain(m.state()) == S1  # the completed sentence promoted bright
    m.translation(S1 + " It reduces bleeding, sweating, and pain.")
    state = m.state()
    assert FINAL_ADD in [s.style for s in state.current], state.current
    assert "bleeding" in plain(state), plain(state)


def test_provisional_line_is_all_dim():
    m, clk = make()
    m.preview("Hello world, this is a draft")
    m.tick()
    assert all(s.style == PROVISIONAL for s in m.state().current)


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
    m.preview("Today we will discuss")
    m.tick()
    assert plain(m.state()) == "Today we will discuss"
    clk.advance(0.2)
    m.preview("Today we will discuss laser")
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
        m.preview(t)
        m.tick()
        clk.advance(0.1)
    st = m.state()
    assert plain(st) == texts[-1]
    assert prev_plain(st) == ""  # no draft ever scrolled up


def test_preview_rewrite_discards_draft_not_history():
    """A rewrite (different prefix) replaces the draft in place; history stays clean."""
    m, clk = make()
    m.preview("We are here today to discuss laser")
    m.tick()
    m.preview("Today we will discuss laser")
    m.tick()
    assert plain(m.state()) == "Today we will discuss laser"
    assert prev_plain(m.state()) == ""


def test_finals_scroll_but_drafts_never():
    """final→final scrolls the old final to history; draft→final does not."""
    m, clk = make()
    # draft shown
    m.preview("Today we will discuss laser applications")
    m.tick()
    # final arrives (amend path: prefix to prev, delta becomes current)
    m.translation("Today we will discuss laser applications in medicine.")
    m.tick()
    st = m.state()
    # amend appends the delta to the line: one coherent final sentence
    assert plain(st) == "Today we will discuss laser applications in medicine."
    assert prev_plain(st) == ""  # the discarded draft never scrolled
    # next utterance's final scrolls the previous final up
    clk.advance(4.0)
    m.translation("Dentists also use lasers for oral surgery.")
    m.tick()
    st = m.state()
    assert "Dentists" in plain(st)
    assert "Today we will discuss laser applications in medicine." in prev_plain(st)  # the full final scrolled up


# ---- golden-stream display sanity (the "what shows in overlay makes sense" bar) ----

def test_golden_final_survives_its_hold():
    """After a translation_final lands, the row holds the polished sentence for
    the hold duration — the next sentence's in-flight draft must not wipe it."""
    events = load_caption_events(ZH_LONG_IDEAL)
    clk = FakeClock()
    m = CaptionDisplay(hold_sec=1.0, clock=clk)
    finals_seen = 0
    for e in events:
        m.emit(e)
        clk.advance(0.2)
        m.tick()
        state = m.state()
        if e.type == "translation_final":
            finals_seen += 1
            cur = plain(state)
            assert cur == e.text, f"final not displayed when it lands: {cur!r}"
            assert is_bright(state), "final must be bright"
            clk.advance(0.1)
            m.tick()
            assert plain(m.state()) == e.text, "final wiped before its hold elapsed"
    assert finals_seen == 6


def test_preempting_final_clears_stale_queued_draft():
    """A final that takes over the line while its own draft is still queued
    must clear the queue: on a >hold pause, the stale dim draft must not pop
    and regress the bright final. The event stream's draft shows first, then
    its final lands inside the same tick window."""
    m, clk = make()
    # draft queued behind nothing (first show)
    m.preview("Sentence two")
    m.tick()
    clk.advance(0.1)
    # the final lands while the draft is still queued (preempt)
    m.translation("Sentence two.")
    m.tick()
    state = m.state()
    assert plain(state) == "Sentence two."
    assert is_bright(state)
    assert m._queue == [], "stale draft left queued after the final took over"
    # speaker pauses past the hold: the final must persist (or expire cleanly),
    # never regress to the stale dim draft
    clk.advance(4.0)
    m.tick()
    assert plain(m.state()) != "Sentence two", "stale draft popped over the bright final"


# ---- monotonic src display (no vanish/reappear on hypothesis revision) ----

def test_set_partial_holds_on_pure_shrink():
    """A streaming revision that shrinks the tail is held — the display never
    vanishes/reappears on hypothesis churn."""
    m = CaptionDisplay(hold_sec=3.5)
    m.set_partial("我們今天來討論鐳射在醫學上的應用")
    m.set_partial("我們今天來討論鐳射在")  # revision shrank
    assert m.state().partial == "我們今天來討論鐳射在醫學上的應用", "shrink must be held"
    m.set_partial("我們今天來討論鐳射在醫學上的應用，未來")  # growth shows
    assert m.state().partial == "我們今天來討論鐳射在醫學上的應用，未來"


def test_transcription_final_releases_the_held_tail():
    """A commit arrives as its own transcription_final event: it clears the
    displayed tail, so the next (shorter) rolling hypothesis is a fresh line,
    not a shrink against committed text."""
    m = CaptionDisplay(hold_sec=3.5)
    m.emit(event("transcription_provisional", "我們今天來討論鐳射在醫學上的應用"))
    assert m.state().partial == "我們今天來討論鐳射在醫學上的應用"
    m.emit(event("transcription_final", "我們今天來討論鐳射", audio_t=2.0))
    assert m.state().partial == ""
    m.emit(event("transcription_provisional", "在醫學上的應用", audio_t=2.5))
    assert m.state().partial == "在醫學上的應用"


def test_partial_expires_after_hold_with_no_activity():
    """A stale reading buffer that never clears reads as a stuck caption."""
    m, clk = make()
    m.set_partial("我們今天來討論鐳射")
    m.tick()
    clk.advance(3.6)
    m.tick()
    assert m.state().partial == ""


# ---- sentence-partitioned commit display (the captain's sentence queue) ----

def drain(m, clk, steps=1):
    for _ in range(steps):
        clk.advance(0.1)
        st = m.tick()
        if st is not None:
            pass
    return m.state()


def test_multi_sentence_final_queues_each_sentence():
    """A multi-sentence final queues each sentence as its own bright item —
    each earns its own hold instead of one long line being replaced whole."""
    m, clk = make()
    m.translation("Dentists also use lasers. This reduces bleeding.")
    st = m.tick()
    st = m.state()
    assert plain(st) == "Dentists also use lasers.", plain(st)
    # the second sentence is queued and paces after the first's hold
    clk.advance(1.0)
    st = drain(m, clk)
    assert plain(st) == "Dentists also use lasers.", "second sentence preempted the first's hold"
    clk.advance(2.0)
    st = m.tick()
    st = m.state()
    assert plain(st) == "This reduces bleeding.", plain(st)
    assert prev_plain(st) == "Dentists also use lasers.", prev_plain(st)


def test_commit_crossing_terminator_freezes_completed_sentence():
    """When the growing commit/draft crosses '.', the completed sentence
    freezes (bright) and the line carries only the next sentence's fragment —
    the completed sentence is never extended by the next sentence's words."""
    m, clk = make()
    m.preview("Dentists also use lasers for oral surgery.")
    m.tick()
    clk.advance(0.2)
    # the draft crosses the terminator and starts the next sentence
    m.preview("Dentists also use lasers for oral surgery. This reduces")
    m.tick()
    st = m.state()
    assert "Dentists also use lasers for oral surgery." in plain(st) or \
           "Dentists also use lasers for oral surgery." in prev_plain(st), \
        f"completed sentence not frozen: {plain(st)!r} / {prev_plain(st)!r}"
    # the completed sentence's text is stable while the next sentence grows
    text_now = prev_plain(st) or plain(st)
    assert text_now.endswith("surgery.")
    m.preview("Dentists also use lasers for oral surgery. This reduces bleeding")
    m.tick()
    st = m.state()
    shown = plain(st) + " " + prev_plain(st)
    assert "Dentists also use lasers for oral surgery." in shown, \
        f"completed sentence lost on fragment growth: {shown!r}"


def test_reworded_final_amends_only_current_sentence():
    """A reworded final amends the sentence on the line; a completed bright
    sentence already scrolled to history is never retracted."""
    m, clk = make()
    # commit stream: sentence 1 completes and freezes (bright on the line)
    m.preview("Dentists also use lasers for oral surgery. This reduces")
    m.tick()
    st = m.state()
    assert "Dentists also use lasers for oral surgery." in plain(st) + prev_plain(st)
    clk.advance(1.0)
    m.tick()
    assert "Dentists also use lasers for oral surgery." in plain(m.state()), \
        "the bright sentence did not survive its hold"
    # the final re-words the sentence: amend in place (green adds), never a
    # blank flash between the old wording and the new
    m.translation("Dentists also use laser technology for oral surgery, reducing bleeding.")
    m.tick()
    st = m.state()
    cur, prev = plain(st), prev_plain(st)
    shown = cur + " " + prev
    assert "surgery" in shown and "reducing bleeding" in shown, f"current sentence lost: {cur!r} / {prev!r}"
    assert cur != "", "the line blanked on the final (retraction)"


def test_dermatology_tail_displays_before_next_caption():
    """The captain's scenario: the commit stream showed only
    'Dermatologists use lasers to remove' when the segment's final arrived —
    the tail ('spots and tattoos') must display as part of the completed
    sentence before the next sentence's caption takes the line."""
    m, clk = make()
    m.preview("This reduces bleeding, sweating, pain. Dermatologists use lasers to remove")
    m.tick()
    # the final lands while the reader is mid-'remove'
    m.translation("Dentists also use laser technology for oral surgery, reducing bleeding, sweating, and pain. "
                  "Dermatologists use lasers to remove spots and tattoos.")
    m.tick()
    st = m.state()
    clk.advance(2.0)
    m.tick()
    st = m.state()
    shown = plain(st) + " | " + prev_plain(st)
    assert "spots and tattoos" in shown, f"the tail never displayed: {shown!r}"
    # and both sentences pace: the second sentence holds before the next final
    clk.advance(1.0)
    m.tick()
    st = m.state()
    assert plain(st) == "Dentists also use laser technology for oral surgery, reducing bleeding, sweating, and pain." or \
           "spots and tattoos" in plain(st) + prev_plain(st), plain(st)


# ---- end-of-stream drained replay (round-2: queued sentences must display) ----

def _drained_replay(path, hold=3.5, drain_seconds=30.0, pace=0.8):
    """Replay a captured event stream through the REAL display model with the
    drainer pumped past the last event — what a viewer sees when the stream
    ends and real time keeps running. Returns the ordered list of distinct
    lines that reached the current line."""
    m, clk = make(hold=hold)
    seen = []

    for e in load_caption_events(path):
        clk.advance(pace)  # ~real-time pacing per event
        m.emit(e)
        st = m.tick()
        if st is not None:
            cur = plain(st)
            if cur and cur != (seen[-1] if seen else None):
                seen.append(cur)
    # pump the drainer past the end of the stream (the reader's clock keeps
    # running): every completed sentence must reach the line
    for _ in range(int(drain_seconds / 0.1)):
        clk.advance(0.1)
        st = m.tick()
        if st is not None:
            cur = plain(st)
            if cur and cur != (seen[-1] if seen else None):
                seen.append(cur)
    return seen


def test_drained_replay_displays_every_completed_sentence():
    """End-of-stream guarantee: replaying the captured zh_long time-frontier
    stream through the display model and draining past the last event, EVERY
    completed sentence of every final displays — including the dermatology
    tail ('spots and tattoos') that motivated the sentence queue. Fails if a
    queued sentence is dropped by a later draft or a queue-jumping final."""
    assert ZH_LONG_TIME_FRONTIER.exists(), "golden stream missing"
    seen = _drained_replay(ZH_LONG_TIME_FRONTIER)
    for sentence in (
        "Dermatologists use lasers to remove spots and tattoos.",
        "It reduces bleeding, sweating, and pain.",
        "In summary, laser plays an increasingly important role in modern medicine.",
    ):
        assert any(sentence in s for s in seen), \
            f"never displayed: {sentence!r}; saw: {seen!r}"


def test_pending_sentences_survive_next_utterance_draft():
    """A new utterance's DRAFT must not drop queued committed sentences
    (round-2: the 'In short.' draft wiped the dentist final's backlog)."""
    m, clk = make()
    m.translation("Dentists also use lasers for oral surgery. It reduces bleeding, "
                  "sweating, and pain. Dermatologists use lasers to remove spots and tattoos.")
    m.tick()
    st = m.state()
    assert plain(st) == "Dentists also use lasers for oral surgery.", plain(st)
    # the next utterance's fragment draft arrives while two sentences are queued
    m.preview("In short.")
    m.tick()
    seen = [plain(m.state())]
    for _ in range(60):
        clk.advance(0.25)
        m.tick()
        seen.append(plain(m.state()))
    joined = "\n".join(seen)
    assert "It reduces bleeding, sweating, and pain." in joined, f"draft dropped a queued sentence: {joined!r}"
    assert "spots and tattoos" in joined, f"draft dropped the tail sentence: {joined!r}"


def test_new_final_enqueues_behind_pending_sentences_fifo():
    """A new final enqueues BEHIND pending completed sentences and pops in
    order — it never jumps the queue (round-2: 'In summary' went straight to
    bright over the dentist final's pending sentences)."""
    m, clk = make()
    m.translation("First sentence here. Second sentence here.")
    m.tick()
    assert plain(m.state()) == "First sentence here."
    # second final arrives while the second sentence is still queued
    m.translation("Third sentence entirely different.")
    m.tick()
    # FIFO: the pending second sentence displays next, NOT the new final
    clk.advance(2.0)
    m.tick()
    st = m.state()
    shown = plain(st) + "|" + prev_plain(st)
    assert "Second sentence here" in shown, f"queue jumped: {shown!r}"
    clk.advance(3.0)
    m.tick()
    st = m.state()
    shown = plain(st) + "|" + prev_plain(st)
    assert "Third sentence" in shown, f"the new final never displayed: {shown!r}"


def test_committed_sentences_faster_than_the_release_interval_all_display():
    """Committed captions are never evicted in favour of a newer one.

    At the shipped hold the drainer releases one queued caption every
    ``max(1.0, hold / 2)`` = 1.75s, so finals that land faster than that build
    a backlog. The queue must DRAIN that backlog, not trim it: trimming drops
    a sentence the reader was never shown, which is a lost caption, not
    back-pressure. Fails if any queue bound discards an unshown committed
    item."""
    m, clk = make(hold=3.5)  # the shipped hold, hence the 1.75s release
    committed = [f"{w} is here." for w in (
        "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
        "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima")]
    shown = []

    def snap() -> None:
        cur = plain(m.state())
        if cur and cur != (shown[-1] if shown else None):
            shown.append(cur)

    for sentence in committed:
        m.translation(sentence)
        snap()
        m.tick()
        snap()
        for _ in range(9):  # the next final lands 0.9s later (a 10fps view)
            clk.advance(0.1)
            m.tick()
            snap()
    for _ in range(600):  # the reader's clock keeps running: the backlog drains
        clk.advance(0.1)
        m.tick()
        snap()

    displayed = [s for s in shown if s in committed]
    assert displayed == committed, (
        f"committed sentences never displayed: {[s for s in committed if s not in displayed]}"
    )


def test_new_multi_sentence_final_never_evicts_the_pending_backlog():
    """A final rebuilds the hold queue (pending committed sentences + its own
    new sentences); that rebuild must not trim the backlog. Older sentences
    still waiting are committed content the reader has not seen — the rebuild
    keeps them and the new ones queue behind, in order. Fails if the rebuild
    keeps only the newest few items (which evicts an unshown caption)."""
    m, clk = make(hold=3.5)
    m.translation("Alpha is here. Bravo is here. Charlie is here.")
    m.tick()  # Alpha on the line; Bravo and Charlie wait in the backlog
    assert plain(m.state()) == "Alpha is here."
    m.translation("Delta is here. Echo is here.")
    m.tick()
    committed = ["Alpha is here.", "Bravo is here.", "Charlie is here.",
                 "Delta is here.", "Echo is here."]
    shown = []

    def snap() -> None:
        cur = plain(m.state())
        if cur and cur != (shown[-1] if shown else None):
            shown.append(cur)

    snap()
    for _ in range(600):  # the reader's clock keeps running
        clk.advance(0.1)
        m.tick()
        snap()
    assert [s for s in shown if s in committed] == committed, (
        f"never displayed: {[s for s in committed if s not in shown]}"
    )


# ---- promote-in-place (round 3: no identical-content retype) ----

def test_promote_in_place_flips_bright_without_retype():
    """The sentence the reader is watching type promotes at its terminator as
    a single style flip (bright, scrolled to the prev line) — never a
    clear+re-render of identical text (round 3: the dentist retype, where the
    line reset and the queue re-rendered the words the reader had just read)."""
    m, clk = make()
    S1 = "Dentists also use laser technology for oral surgery."
    m.preview("Dentists also use laser technology for ")
    m.tick()
    # the draft crosses the terminator: the completed sentence promotes
    m.preview(S1 + " This reduces")
    m.tick()
    st = m.state()
    # the completed sentence is bright exactly once — on the prev line
    assert prev_plain(st) == S1, prev_plain(st)
    assert prev_plain(st) not in plain(st), "promoted sentence re-rendered on the current line"
    # the line keeps only the in-progress fragment (a layout split, not a clear)
    assert plain(st) == "This reduces", plain(st)
    # no queue round-trip: the completed sentence was never enqueued
    assert all(it.plain != S1 for it in m._queue), \
        [it.plain for it in m._queue]
    # the current line never went clear between the dim and bright frames of
    # the same content (the clear+retype signature)
    assert plain(st) != "", "line cleared at the boundary"


def test_promote_in_place_final_amends_without_retype():
    """The final amends the promoted sentence in its scrolled position and the
    never-typed tail sentence enqueues — no whole-line re-render."""
    m, clk = make()
    S1 = "Dentists also use laser technology for oral surgery."
    m.preview("Dentists also use laser technology for ")
    m.tick()
    m.preview(S1 + " This reduces")
    m.tick()
    st = m.state()
    assert prev_plain(st) == S1
    # the final's authoritative wording amends the promoted sentence in place
    m.translation(S1 + " It reduces bleeding, sweating, and pain. "
                       "Dermatologists use lasers to remove spots and tattoos.")
    st = m.state()
    assert prev_plain(st) == S1, "promoted sentence was re-rendered instead of amended"
    # the reworded sentence is on the line (bright) or queued — never a full
    # re-render of S1
    cur = plain(st)
    assert cur != S1, "S1 re-typed on the current line"
    # the tail sentence the reader never saw is queued (or on the line), not lost
    all_pending = cur + "".join(it.plain for it in m._queue)
    assert "Dermatologists use lasers to remove spots and tattoos." in all_pending or \
           "Dermatologists use lasers to remove spots and tattoos." in prev_plain(st), \
           (cur, [it.plain for it in m._queue])


# ---- the EventSink contract (how the pipeline drives the model) ----

def test_emit_drives_one_utterance_through_the_display():
    """The model is a caption-stream consumer: feeding the typed event
    sequence of one utterance produces the provisional draft, then the bright
    final, with the source tail cleared by the commit."""
    m, clk = make()
    m.emit(event("transcription_provisional", "今天我們討論皮膚科", audio_t=0.8))
    m.tick()
    assert m.state().partial == "今天我們討論皮膚科"
    assert plain(m.state()) == ""

    m.emit(event("translation_provisional", "Today we", audio_t=1.5,
                 committed="今天我們", source="今天我們討論皮膚科。", fresh=True))
    m.tick()
    assert plain(m.state()) == "Today we"
    assert not is_bright(m.state())

    m.emit(event("transcription_final", "今天我們討論皮膚科。", audio_t=1.4))
    m.tick()
    assert m.state().partial == ""

    m.emit(event("translation_final", "Today we discuss dermatology.", audio_t=1.9))
    m.tick()
    state = m.state()
    assert plain(state) == "Today we discuss dermatology."
    assert is_bright(state)


def test_emit_ignores_an_unknown_event_kind():
    """The stream may grow; an unknown kind is not a display event."""
    m, clk = make()
    m.emit(event("speaker_change", "S2", audio_t=1.0))
    assert m.tick() is None


def test_placeholder_artifact_never_reaches_the_display():
    """The MT template marker is model plumbing, not caption content."""
    m, clk = make()
    m.preview("<|im_start|>Hello there")
    m.tick()
    assert plain(m.state()) == "Hello there"
    m.translation("<|im_start|>Hello there, world.")
    m.tick()
    assert "im_start" not in plain(m.state())


# ---- pipeline wiring: the model is built only when a consumer asks ----

def _bare_processor(processor_kwargs=None, **config_kwargs):
    """An AudioProcessor with no ASR/translation models (pipeline wiring only)."""
    from argparse import Namespace
    from dataclasses import asdict

    from whisperlivekit.audio_processor import AudioProcessor
    from whisperlivekit.config import WhisperLiveKitConfig
    from whisperlivekit.core import TranscriptionEngine

    engine = object.__new__(TranscriptionEngine)
    engine.args = Namespace(**asdict(WhisperLiveKitConfig(
        transcription=False, vac=False, pcm_input=True, **config_kwargs,
    )))
    engine.asr = None
    engine.diarization_model = None
    engine.translation_model = None
    return AudioProcessor(transcription_engine=engine, **(processor_kwargs or {}))


def _cleanup(processor):
    import asyncio

    asyncio.run(processor.cleanup())


def test_no_display_state_without_a_consumer():
    """AC-3: nothing consumes the stream, so no display state exists."""
    processor = _bare_processor()
    assert processor.caption_display is None
    # EventTap holds no sink at all (its private sink is the contract's seam)
    assert processor.event_tap._sink is None
    processor.event_tap.translation_final(1.0, "nobody reads this")
    _cleanup(processor)


def test_display_consumer_receives_the_stream():
    clk = FakeClock()
    display = CaptionDisplay(hold_sec=1.0, clock=clk)
    processor = _bare_processor(processor_kwargs={"caption_display": display})
    assert processor.caption_display is display
    processor.event_tap.translation_final(1.0, "Hello there.")
    clk.advance(0.1)
    display.tick()
    assert plain(display.state()) == "Hello there."
    _cleanup(processor)


def test_event_log_and_display_both_receive_the_stream(tmp_path):
    """The fan-out exists for exactly this pairing: the display model renders
    the stream while --event-log records the same events for replay."""
    import json

    log_path = tmp_path / "events.jsonl"
    clk = FakeClock()
    display = CaptionDisplay(hold_sec=1.0, clock=clk)
    processor = _bare_processor(
        event_log=str(log_path),
        processor_kwargs={"caption_display": display},
    )
    processor.event_tap.translation_final(1.0, "Hello there.")
    clk.advance(0.1)
    display.tick()
    assert plain(display.state()) == "Hello there."
    _cleanup(processor)

    rows = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert [r["text"] for r in rows] == ["Hello there."]


@pytest.mark.asyncio
async def test_harness_exposes_the_display_state_to_its_consumer():
    """A display consumer reads the model's state through the harness again:
    the ``TestState.display`` field carries the display snapshot for every
    result the harness collects."""
    from whisperlivekit.test_harness import TestHarness

    display = CaptionDisplay(hold_sec=1.0, clock=FakeClock())
    async with TestHarness(transcription=False, vac=False, pcm_input=True,
                           caption_display=display) as harness:
        import asyncio

        harness._processor.event_tap.translation_provisional(1.0, "Today we")
        display.tick()  # the model renders the draft on its own frame clock
        await asyncio.sleep(0.2)
        state = harness.state.display
        assert isinstance(state, DisplayState)
        assert "".join(s.text for s in state.current) == "Today we"
