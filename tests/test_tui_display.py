"""The terminal view is a thin consumer of the caption display model.

Every display rule — when a caption releases, when a draft becomes final, which
sentence scrolls up — lives in ``CaptionDisplay``. ``TuiRenderer`` only maps the
``DisplayState`` it publishes to the three regions (scrollback history, the
active caption line, the ASR source row) and advances the model's hold-drain on
its own frame clock. These tests drive that model-to-view path over the captured
golden streams on a stepped clock: no terminal, no threads, no real time —
``test_frame_clock_pumps_on_its_own_thread`` is the one exception, because the
daemon frame clock is what it covers.
"""

from __future__ import annotations

import io
import time
from pathlib import Path

import pytest
from rich.console import Console

from whisperlivekit.caption_display import (
    FINAL_ADD,
    FINAL_SAME,
    PROVISIONAL,
    CaptionDisplay,
    DisplayState,
    Span,
    _split_sentences,
    load_caption_events,
)
from whisperlivekit.caption_events import CaptionEvent
from whisperlivekit.tui import TuiRenderer, replay

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDENS = sorted(GOLDEN_DIR.glob("*.jsonl"))
CANONICAL = GOLDEN_DIR / "zh_long_canonical.jsonl"

# The pacing every test shares: the model's shipped hold, a third of a second of
# virtual time per event (the shape scripts/replay_canonical_overlay.py uses),
# and a drain long enough for the hold queue to empty after the stream ends.
HOLD = 3.5
PACE = 0.3
DRAIN = 30.0


class _Clock:
    """Deterministic seconds counter: the replay advances it, nothing else does."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _console(width: int = 120) -> Console:
    return Console(file=io.StringIO(), force_terminal=False, width=width)


def _committed(state: DisplayState) -> bool:
    return bool(state.current) and all(span.style != PROVISIONAL for span in state.current)


def _plain(spans) -> str:
    return "".join(span.text for span in spans)


def _frame_text(history, renderer: TuiRenderer, state: DisplayState, width: int = 100) -> str:
    """The three regions as plain text: history, the active line, the source row."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=width)
    for line in history:
        console.print(line)
    console.print(renderer.caption_line(state))
    console.print(renderer.source_line(state))
    return buffer.getvalue()


def _walk(path, hold: float = HOLD, pace: float = PACE, drain: float = DRAIN):
    """Replay a golden through the model and the view, one frame per step.

    Returns the renderer (its final scrollback) and every frame the view
    rendered, each ``(history snapshot, state)``.
    """
    clock = _Clock()
    renderer = TuiRenderer(CaptionDisplay(hold_sec=hold, clock=clock), console=_console(), threaded=False)
    frames = []
    with renderer:
        def step() -> None:
            state = renderer.pump()
            if state is not None:
                frames.append((renderer.history_lines(), state))

        for event in load_caption_events(path):
            clock.advance(pace)
            renderer.emit(event)
            step()
        for _ in range(int(drain / 0.1)):
            clock.advance(0.1)
            step()
    return renderer, frames


def expected_sentences(path):
    """The sentences the recorded finals commit, in stream order."""
    sentences = []
    for event in load_caption_events(path):
        if event.type != "translation_final":
            continue
        complete, fragment = _split_sentences(event.text)
        sentences.extend(complete or ([fragment] if fragment else []))
    return sentences


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_every_final_sentence_reaches_the_scrollback_exactly_once(golden):
    """Every sentence of every finalized translation lands in the scrollback
    once — nothing lost, nothing typed twice, nothing the model never committed.
    Fails if the view prints a line on first sight and then prints the model's
    reworded version of it, if it drops a committed line the model replaced or
    expired without scrolling up, or if it lets a provisional draft into the
    transcript."""
    renderer = replay(load_caption_events(golden), _console(), hold=HOLD, pace=PACE, drain_seconds=DRAIN)
    history = renderer.history_lines()
    expected = expected_sentences(golden)
    assert expected, "golden should carry finalized translations"

    lost = [sentence for sentence in expected if sentence not in history]
    retyped = [line for line in set(history) if history.count(line) > 1]
    invented = [line for line in history if line not in expected]
    assert not lost, f"never reached the scrollback: {lost}"
    assert not retyped, f"reached the scrollback more than once: {retyped}"
    assert not invented, f"reached the scrollback without a final: {invented}"


def test_canonical_scrollback_is_the_final_sentence_order():
    """On the canonical stream the scrollback is exactly the finalized sentences
    in the order the model committed them — the whole transcript, no merge, no
    reorder.

    Not asserted for every golden: ``zh_long_time_frontier`` displays one
    sentence from the running draft before the final that commits it, so its
    display order legitimately differs from its final-sentence order (that
    sentence still appears exactly once — see the test above).
    """
    renderer = replay(load_caption_events(CANONICAL), _console(), hold=HOLD, pace=PACE, drain_seconds=DRAIN)
    assert renderer.history_lines() == expected_sentences(CANONICAL)


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_scrollback_is_append_only(golden):
    """Across every rendered frame the scrollback only ever grows: an earlier
    line is never rewritten, removed or reordered. Fails if the view rebuilds
    history from the model's current line, or if the hold-queue drain makes a
    printed line move."""
    renderer, frames = _walk(golden)
    assert frames, "golden should render at least one frame"

    previous: list = []
    for index, (history, _state) in enumerate(frames):
        assert history[:len(previous)] == previous, (
            f"frame {index}: scrollback rewrote or reordered its lines: {previous!r} -> {history!r}"
        )
        previous = history
    assert previous == renderer.history_lines(), (
        "the last frame's scrollback must be the one the renderer reports"
    )
    assert previous, "golden should scroll at least one caption into the transcript"


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_source_row_renders_the_partial_while_speech_is_in_flight(golden):
    """The ASR partial reaches the source row while speech is in flight, and the
    row is empty on every frame where the model holds no partial. Fails if the
    view never reads ``DisplayState.partial`` or keeps rendering a stale one
    after the ASR commits it."""
    renderer, frames = _walk(golden)
    in_flight = [state for _history, state in frames if state.partial]
    assert in_flight, "golden should roll an ASR partial at some point"
    for state in in_flight:
        assert renderer.source_line(state).plain == f"[src] {state.partial}"

    idle = [state for _history, state in frames if not state.partial]
    assert idle, "golden should have frames with nothing rolling"
    assert all(renderer.source_line(state).plain == "" for state in idle)


def test_source_row_shows_the_partial_then_clears_at_a_commit():
    """The source row carries the rolling ASR tail and empties when the ASR
    commits: ``transcription_provisional`` fills it, ``transcription_final``
    clears it."""
    clock = _Clock()
    renderer = TuiRenderer(CaptionDisplay(hold_sec=HOLD, clock=clock), console=_console(), threaded=False)
    with renderer:
        clock.advance(PACE)
        renderer.emit(CaptionEvent(0.0, 1.0, "transcription_provisional", "镭射技术可以精确的"))
        state = renderer.pump()
        assert state is not None
        assert renderer.source_line(state).plain == "[src] 镭射技术可以精确的"

        clock.advance(PACE)
        renderer.emit(CaptionEvent(0.0, 1.6, "transcription_final", "镭射技术可以精确地切除肿瘤组织。"))
        state = renderer.pump()
        assert state is not None
        assert state.partial == ""
        assert renderer.source_line(state).plain == ""


def test_caption_line_renders_each_span_kind_with_its_own_style():
    """A model span is one styled run: a draft is dim, committed text is bright,
    a correction is green. Fails if the view collapses the spans into one style
    (the draft and the final then look identical) or reorders them."""
    renderer = TuiRenderer(CaptionDisplay(hold_sec=HOLD, clock=_Clock()), console=_console(), threaded=False)
    state = DisplayState(
        current=[Span("Dentists ", FINAL_SAME), Span("also use lasers", PROVISIONAL),
                 Span(", reducing bleeding.", FINAL_ADD)],
        prev=[Span("Laser technology can precisely remove tumor tissue.", FINAL_SAME)],
        partial="牙医也使用镭射。",
    )
    line = renderer.caption_line(state)
    assert line.plain == "Dentists also use lasers, reducing bleeding."
    assert {line.plain[span.start:span.end]: span.style for span in line.spans} == {
        "Dentists ": renderer._span_styles[FINAL_SAME],
        "also use lasers": renderer._span_styles[PROVISIONAL],
        ", reducing bleeding.": renderer._span_styles[FINAL_ADD],
    }
    assert len({renderer._span_styles[FINAL_SAME], renderer._span_styles[PROVISIONAL],
                renderer._span_styles[FINAL_ADD]}) == 3


def test_three_regions_snapshot():
    """One deterministic snapshot of the three regions on the canonical stream:
    the scrollback above, the active caption line, the source row below it. Pins
    the layout, so a region regression — a history line that stopped printing,
    the source row moving above the caption, a blank caption row — shows up in
    the diff."""
    renderer, frames = _walk(CANONICAL)
    populated = [(history, state) for history, state in frames
                 if history and state.partial and _committed(state)]
    assert populated, "canonical stream should show all three regions at once"
    history, state = populated[1]
    assert _frame_text(history, renderer, state) == (
        "Today, we will discuss the applications of laser in medicine.\n"
        "Laser technology can precisely remove tumor tissue.\n"
        "In ophthalmic surgery.\n"
        "[src] 牙医也使用镭射来进行。\n"
    )


def test_draft_becomes_final_on_the_same_caption_line():
    """The promotion a reader waits for: the dim draft types on the caption
    line, then the model's final brightens that same line in place. The view
    restyles the line instead of scrolling a new one in, and the draft it
    replaced never reaches the transcript. Fails if the view rebuilds the line
    from scratch (a retype), renders the final dim, or prints the draft."""
    renderer, frames = _walk(CANONICAL)
    promotions = [
        index for index, (_history, state) in enumerate(frames)
        if index and _committed(state) and frames[index - 1][1].current
        and not _committed(frames[index - 1][1])
    ]
    assert promotions, "canonical stream should promote a draft to final"

    draft = frames[promotions[0] - 1][1]
    final = frames[promotions[0]][1]
    assert [span.style for span in draft.current] == [PROVISIONAL]
    assert _committed(final)
    promoted = _plain(final.current)
    assert promoted != _plain(draft.current), "the final reworded the draft it replaced"

    transcript = renderer.history_lines()
    assert transcript.count(promoted) == 1, "the promoted sentence is one line, typed once"
    assert _plain(draft.current) not in transcript, "a dim draft never enters the transcript"


def test_frame_clock_pumps_on_its_own_thread():
    """The renderer advances the model on its own daemon frame clock, so a
    caller never has to pump. Fails if the clock thread is not started on enter,
    is not daemonic, or outlives the renderer."""
    display = CaptionDisplay(hold_sec=0.05, clock=time.monotonic)
    renderer = TuiRenderer(display, console=_console())
    with renderer:
        assert renderer._thread is not None and renderer._thread.is_alive()
        assert renderer._thread.daemon
        renderer.emit(CaptionEvent(0.0, 0.5, "translation_final", "A caption."))
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not renderer.history_lines():
            time.sleep(0.01)  # the frame clock is the only thing pumping
        pumped = renderer.history_lines()
    assert pumped == ["A caption."]
    assert renderer._thread is None, "the frame clock must stop with the renderer"
