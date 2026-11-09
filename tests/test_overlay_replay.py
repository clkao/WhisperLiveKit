"""Model-level regression tests driven by the canonical captured event
streams (qwen3-asr + simul-MT, production event tap).

These tests drive the caption display model through its ``EventSink`` entry
point (``emit``) with recorded streams — no view code, no real time. The model
owns the display rules; a view only renders ``DisplayState``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from whisperlivekit.caption_display import (
    PROVISIONAL,
    CaptionDisplay,
    _split_sentences,
    load_caption_events,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
CANONICAL = GOLDEN_DIR / "zh_long_canonical.jsonl"
FALLBACK = GOLDEN_DIR / "zh_ja_fallback.jsonl"


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, s: float) -> None:
        self.now += s


def _replay(path, hold=1.2, pace=0.3, drain_seconds=30.0):
    """Replay a captured stream through the model and return every distinct
    line that reached the current line, plus the scrolled-up lines."""
    clock = _Clock()
    model = CaptionDisplay(hold_sec=hold, clock=clock)
    shown, scrolled = [], []

    def snap():
        state = model.state()
        cur = "".join(s.text for s in state.current)
        prev = "".join(s.text for s in state.prev)
        if cur and cur != (shown[-1] if shown else None):
            shown.append(cur)
        if prev and prev != (scrolled[-1] if scrolled else None):
            scrolled.append(prev)

    for event in load_caption_events(path):
        clock.advance(pace)
        model.emit(event)
        model.tick()
        snap()
    # the reader's clock keeps running after the stream ends: queued sentences
    # must still surface
    for _ in range(int(drain_seconds / 0.1)):
        clock.advance(0.1)
        model.tick()
        snap()
    return shown, scrolled


def test_reword_retraction_held():
    """The mic run's flicker: the hypothesis re-decodes and RETRACTS the tail
    ('我们今天来讨论镭射。在医学上的应用，镭射。' -> '确的切除。'). Any shorter
    text is held — the reader never sees a retraction; the commit resolves
    it."""
    model = CaptionDisplay(hold_sec=3.5, clock=_Clock())
    model.set_partial("我们今天来讨论镭射。在医学上的应用，镭射。")
    assert model.tick().partial == "我们今天来讨论镭射。在医学上的应用，镭射。"
    model.set_partial("确的切除。")   # retraction — held
    assert model.tick() is None, "retraction must not re-render"
    # growth past the held text shows again
    model.set_partial("我们今天来讨论镭射。在医学上的应用，镭射。确的切除肿瘤组织。")
    assert model.tick().partial == "我们今天来讨论镭射。在医学上的应用，镭射。确的切除肿瘤组织。"


def test_canonical_stream_every_final_sentence_reaches_the_line():
    """Replaying the captured zh_long production stream, every sentence of
    every finalized translation displays — at its own pace, not merged into
    one line and not dropped by a later draft. Fails if a queued sentence is
    lost, if a final jumps the queue, or if a draft supersedes committed
    content."""
    assert CANONICAL.exists(), "golden stream missing"
    events = load_caption_events(CANONICAL)
    finals = [e.text for e in events if e.type == "translation_final"]
    assert finals, "fixture should carry finalized translations"

    shown, _ = _replay(CANONICAL)
    displayed = "\n".join(shown)
    for text in finals:
        sentences, fragment = _split_sentences(text)
        for sentence in sentences or ([fragment] if fragment else []):
            assert sentence in displayed, f"never displayed: {sentence!r}\n saw: {displayed!r}"


def test_canonical_stream_never_scrolls_a_draft_into_history():
    """Only committed text scrolls up. While a line sits in history its spans
    are bright (final styling) — a dim provisional there would read as if a
    retractable draft had been committed."""
    clock = _Clock()
    model = CaptionDisplay(hold_sec=1.2, clock=clock)
    checked = 0
    for event in load_caption_events(CANONICAL):
        clock.advance(0.3)
        model.emit(event)
        model.tick()
        state = model.state()
        if not state.prev:
            continue
        assert all(s.style != PROVISIONAL for s in state.prev), state.prev
        checked += 1
    assert checked, "fixture should hold a caption in history"


def test_zh_ja_fallback_no_raw_source_provisional():
    """The zh->ja run has no calibrated heads — simul degrades to the base
    path, whose buffer holds the UNTRANSLATED source queue. That buffer must
    NOT be forwarded as a translation provisional: raw source flashing in the
    MT row until the real final replaced it. The emission gate lives in
    audio_processor; here we assert the captured fallback stream's
    provisionals are exactly what the gate removes."""
    events = load_caption_events(FALLBACK)
    raw = [e for e in events if e.type == "translation_provisional"]
    finals_zh = {e.text for e in events if e.type == "transcription_final"}
    leaked = [e.text for e in raw if e.text in finals_zh and not _is_target_script(e.text)]
    assert leaked, "fixture should contain the fallback raw-source provisionals"


def _is_target_script(text: str) -> bool:
    """True when the text is predominantly Japanese (kana present)."""
    return any("\u3040" <= ch <= "\u30ff" for ch in text)


def _unshown_committed(golden, hold=3.5, pace=0.3, drain_seconds=30.0):
    """Replay `golden` and return the committed captions that left the hold
    queue without being released to the line.

    A committed item is one routed from a ``translation_final`` (final styling,
    not a draft-routed placeholder the next final legitimately replaces). Every
    such item must reach the line; if it disappears from the queue while some
    other item is released, the queue bound dropped a caption the reader never
    saw.
    """
    clock = _Clock()
    model = CaptionDisplay(hold_sec=hold, clock=clock)
    unshown = []
    queued = {}  # id(item) -> item, the committed items last seen waiting

    def observe(state) -> None:
        live = {id(it): it for it in model._queue
                if it.is_final and not it.provisional}
        cur = "".join(s.text for s in state.current) if state is not None else ""
        for key, item in queued.items():
            if key not in live and item.plain not in cur:
                unshown.append(item.plain)
        queued.clear()
        queued.update(live)

    for event in load_caption_events(golden):
        clock.advance(pace)
        model.emit(event)
        observe(model.tick())
    for _ in range(int(drain_seconds / 0.1)):
        clock.advance(0.1)
        observe(model.tick())
    return unshown


@pytest.mark.parametrize("hold", [3.5, 1.2], ids=["hold3.5", "hold1.2"])
@pytest.mark.parametrize("golden", sorted(GOLDEN_DIR.glob("*.jsonl")),
                         ids=lambda p: p.stem)
def test_no_committed_caption_leaves_the_queue_unshown(golden, hold):
    """No captured final's sentence is dropped: every committed item that enters
    the hold queue is released to the line, for all five goldens, at the shipped
    hold and at a short one (the drainer releases one item per
    ``max(1.0, hold / 2)``, so a shorter hold changes which enqueues coincide).
    Fails if a queue bound — at a sentence enqueue, or at the final's queue
    rebuild — evicts an unshown committed caption the reader was owed."""
    unshown = _unshown_committed(golden, hold=hold)
    assert unshown == [], f"committed captions dropped without displaying: {unshown}"
