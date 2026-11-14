"""The overlay is a renderer of the caption display model's state.

``overlay.layout(state, history)`` is the whole projection from ``DisplayState``
to the rows the window draws — the committed source lines, the live source row,
the previous target line, the active target line, each as plain text plus a
resolved style name (``DRAFT``/``COMMITTED``). ``reveal_steps`` is the one piece
of view policy left: how much of a line appears at once. Neither may decide
anything the model decided (which text is provisional, where a sentence ends,
when a line scrolls up, how long it holds).

These tests drive the recorded golden streams through the model on a stepped
clock and read the layout — no window, no AppKit, no threads. What they are for:
every view that re-derives a display rule from string prefixes is one more place
the rule can drift, so the assertions below pin the model's answers as the only
source of truth.

The overlay keeps two target rows and no scrollback, so "the target transcript"
here is the record a reader keeps from those two rows: a committed line is
written down when it leaves the window (the prev row retires it, or the active
line is replaced without scrolling up and without being reworded in place), and
an exact repeat of a line already written is not written twice (the model may
re-show a sentence). That rule is how the layout is READ, not a display
decision — and it is the terminal view's own rule (``TuiRenderer._reconcile``),
reused here so the two views can be compared line for line.
"""

from __future__ import annotations

import io
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
from whisperlivekit.overlay import (
    COMMITTED,
    DRAFT,
    Layout,
    OverlayRenderer,
    Run,
    layout,
    reveal_steps,
    runs_text,
)
from whisperlivekit.tui import _is_reword, replay

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDENS = sorted(GOLDEN_DIR.glob("*.jsonl"))
CANONICAL = GOLDEN_DIR / "zh_long_canonical.jsonl"

# The pacing tests/test_tui_display.py uses: same hold, same virtual time per
# event, same drain, so both views are looking at the same model frames.
HOLD = 3.5
PACE = 0.3
DRAIN = 30.0


class _Clock:
    """Deterministic seconds counter: the walk advances it, nothing else does."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _feed(renderer: OverlayRenderer, event: CaptionEvent) -> None:
    """Deliver one caption event the way the pipeline's sink does.

    The production adapter is ``scripts/lc_terminal.py:OverlaySink``, which also
    converts the display text (``--opencc``); the routing is the same four kinds.
    """
    if event.type == "transcription_provisional":
        renderer.partial("", event.text)
    elif event.type == "transcription_final":
        renderer.final("", [(None, event.text)])
    elif event.type == "translation_provisional":
        renderer.preview("", [(None, event.text)])
    elif event.type == "translation_final":
        renderer.translation("", [(None, event.text)])


def _walk(path, hold: float = HOLD, pace: float = PACE, drain: float = DRAIN):
    """Every layout the window would draw for a golden stream, in order.

    The renderer owns the model and the source history; the frame clock runs on
    its own thread only inside ``__enter__``, so here the stepped clock is the
    only thing that moves and ``pump`` draws one frame per step.
    """
    clock = _Clock()
    renderer = OverlayRenderer(overlay_mode="both", hold_sec=hold, clock=clock)
    frames = []

    def step() -> None:
        if renderer.pump() is not None:
            frames.append(renderer.layout())

    for event in load_caption_events(path):
        clock.advance(pace)
        _feed(renderer, event)
        step()
    for _ in range(int(drain / 0.1)):
        clock.advance(0.1)
        step()
    return frames


def expected_sentences(path):
    """The sentences the recorded finals commit, in stream order."""
    sentences = []
    for event in load_caption_events(path):
        if event.type != "translation_final":
            continue
        complete, fragment = _split_sentences(event.text)
        sentences.extend(complete or ([fragment] if fragment else []))
    return sentences


def _is_draft(runs) -> bool:
    """True when a row holds nothing but a dim draft."""
    return bool(runs) and all(run.style == DRAFT for run in runs)


def transcript(frames, flush: bool = True) -> list:
    """The target lines a reader keeps from the window, in order.

    The overlay shows two target lines and keeps no scrollback, so the record is
    kept the way the terminal view keeps its scrollback (``TuiRenderer._reconcile``):
    a committed line is written down when it leaves the window — the prev row
    retires it, or the active line is replaced without scrolling up and without
    being reworded in place — and the line the window closes on is written down
    too. An exact repeat of a line already written is not written twice: the
    model may re-show a sentence.

    ``flush=False`` reads a stream still in progress: the flagged line stays
    held, exactly as the window holds it (the terminal view only writes its
    resting line when it closes).
    """
    record = _Record()
    for frame in frames:
        record.observe(frame)
    if flush:
        record.flush()
    return record.lines()


class _Record:
    """``transcript``'s fold: observe one frame at a time, append-only."""

    def __init__(self) -> None:
        self._written: list = []
        self._held = None
        self._last = ""
        self._last_committed = False

    def observe(self, frame: Layout) -> None:
        current, previous = runs_text(frame.current), runs_text(frame.prev)
        committed = bool(frame.current) and all(
            run.style == COMMITTED for run in frame.current)
        if not previous:
            self._retire()
        elif previous != self._held:
            if previous == self._last or not _is_reword(self._held, previous):
                self._retire()
            self._held = previous
        if self._last and self._last != current:
            if (self._last_committed and previous != self._last
                    and not _is_reword(self._last, current)):
                self._retire()
                self._write(self._last)
        self._last, self._last_committed = current, committed

    def flush(self) -> None:
        """The window closed: its held line and its resting committed line are
        what the reader keeps."""
        self._retire()
        if self._last_committed:
            self._write(self._last)

    def lines(self) -> list:
        return list(self._written)

    def _write(self, text: str) -> None:
        if text and text not in self._written:
            self._written.append(text)

    def _retire(self) -> None:
        retiring, self._held = self._held, None
        if retiring:
            self._write(retiring)


# ---- the model's answers reach the target rows ---------------------------


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_every_final_sentence_reaches_a_committed_target_row(golden):
    """Every sentence of every finalized translation is drawn on a target row, in
    committed style. Fails if the layout drops ``prev``, filters or merges runs,
    or styles a committed line as a draft — the reader never gets to read it."""
    frames = _walk(golden)
    shown = set()
    for frame in frames:
        for runs in (frame.prev, frame.current):
            if runs and all(run.style == COMMITTED for run in runs):
                shown.add(runs_text(runs))
    expected = expected_sentences(golden)
    assert expected, "golden should carry finalized translations"
    lost = [sentence for sentence in expected if sentence not in shown]
    assert not lost, f"never reached a committed target row: {lost}"


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_every_final_sentence_reaches_the_transcript_exactly_once(golden):
    """Read as a transcript, the window's two target lines carry each committed
    sentence exactly once: nothing lost, nothing written twice, nothing written
    that no final committed. Fails if a line is dropped when the model replaces
    or expires it, or if the same sentence is typed into the record twice (a
    draft's wording printed and then the final's)."""
    frames = _walk(golden)
    record = transcript(frames)
    expected = expected_sentences(golden)
    assert record, "golden should scroll at least one committed line"
    repeated = [line for line in set(record) if record.count(line) > 1]
    invented = [line for line in record if line not in expected]
    lost = [sentence for sentence in expected if sentence not in record]
    assert not repeated, f"reached the transcript more than once: {repeated}"
    assert not invented, f"reached the transcript without a final: {invented}"
    assert not lost, f"never reached the transcript: {lost}"


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_target_transcript_is_append_only(golden):
    """The record only ever grows: no line is rewritten, removed or reordered as
    later frames arrive. Fails if the record is rebuilt from the current row
    instead of appended to, which is what shuffles a transcript."""
    frames = _walk(golden)
    previous: list = []
    for index, frame in enumerate(frames):
        record = transcript(frames[: index + 1], flush=False)
        assert record[: len(previous)] == previous, (
            f"frame {index}: the transcript rewrote or reordered its lines: "
            f"{previous!r} -> {record!r}"
        )
        previous = record
    assert transcript(frames), "golden should scroll at least one committed line"
    assert previous, "golden should hold a committed line at some point"


def test_canonical_transcript_is_the_final_sentence_order():
    """On the canonical stream the transcript is exactly the finalized sentences
    in the order the model committed them — no merge, no reorder.

    Not asserted for every golden: ``zh_long_time_frontier`` shows a sentence
    from the running draft before the final that commits it, so its display order
    legitimately differs from its final-sentence order (each sentence still
    appears exactly once — see the test above)."""
    assert transcript(_walk(CANONICAL)) == expected_sentences(CANONICAL)


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_a_draft_that_commits_reaches_the_transcript_once_in_committed_style(golden):
    """A sentence that reaches the line as a draft and is then committed appears
    in the transcript once, in the final's wording, and never in the draft's.

    Fails if the view treats the draft as a caption of its own, or if the layout
    keeps the draft's style on the committed row (then the record's ``COMMITTED``
    filter sees nothing)."""
    frames = _walk(golden)
    promotions = [
        index for index in range(1, len(frames))
        if _is_draft(frames[index - 1].current) and frames[index].current
        and all(run.style == COMMITTED for run in frames[index].current)
    ]
    assert promotions, "golden should commit a draft on the line"
    record = transcript(frames)
    for index in promotions:
        draft = runs_text(frames[index - 1].current)
        final = runs_text(frames[index].current)
        assert record.count(final) == 1, (
            f"the promoted sentence is not one transcript line: {final!r}"
        )
        if draft != final:
            assert draft not in record, "a dim draft entered the transcript"


# ---- the source row ------------------------------------------------------


def test_a_commit_retires_the_source_row_into_the_history():
    """The source row is the model's ``partial``; a commit clears it, and the text
    the reader was reading becomes the newest source-history line.

    The committed segment text is NOT what lands in the history: a commit carries
    one ASR segment (``我们今天``) while the row holds the accumulated sentence
    the reader watched. Fails if the view re-assembles committed segments into a
    source line of its own."""
    clock = _Clock()
    renderer = OverlayRenderer(overlay_mode="both", hold_sec=HOLD, clock=clock)
    renderer.partial("", "我们今天来讨论镭射。")
    assert renderer.layout().source == "我们今天来讨论镭射。"
    assert renderer.layout().history == ()

    renderer.final("", [(None, "我们今天")])
    assert renderer.layout().source == "", "the model cleared the live row"
    assert renderer.layout().history == ("我们今天来讨论镭射。",)


def test_a_stale_row_expires_without_entering_the_history():
    """The model drops a source row after a silence (``tick``); that is not a
    commit, so it leaves no history line — only committed source does."""
    clock = _Clock()
    renderer = OverlayRenderer(overlay_mode="both", hold_sec=HOLD, clock=clock)
    renderer.partial("", "镭射技术")
    for _ in range(int(HOLD / 0.1) + 2):
        clock.advance(0.1)
        renderer.pump()
    assert renderer.layout().source == ""
    assert renderer.layout().history == ()


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_source_history_only_holds_rows_the_window_showed(golden):
    """The live source row carries the model's partial while speech is in flight,
    and the source history is append-only, holding only rows that row actually
    displayed — a commit retires what was on screen and nothing else. Fails if
    the history is re-derived from committed segments, or if a commit rewrites
    or reorders an earlier line."""
    frames = _walk(golden)
    rows = {frame.source for frame in frames}
    assert any(frame.source for frame in frames), "golden should roll a live source row"
    previous: tuple = ()
    for frame in frames:
        assert frame.history[: len(previous)] == previous, (
            f"the source history rewrote its lines: {previous!r} -> {frame.history!r}"
        )
        previous = frame.history
    assert previous, "golden should commit source"
    invented = [line for line in previous if line not in rows]
    assert not invented, f"history holds a row the window never showed: {invented}"


# ---- the layout itself ---------------------------------------------------


def test_layout_resolves_the_models_styles_and_drops_nothing():
    """A model span is one run, in order, with its tag resolved to the window's
    two-name vocabulary: the draft is ``DRAFT``, the committed text and the
    correction are both ``COMMITTED`` (the window has no green). Fails if the
    layout re-styles a correction, drops a run, or reorders them."""
    state = DisplayState(
        current=[Span("Dentists ", FINAL_SAME), Span("also use lasers", PROVISIONAL),
                 Span(", reducing bleeding.", FINAL_ADD)],
        prev=[Span("Laser technology can precisely remove tumor tissue.", FINAL_SAME)],
        partial="牙医也使用镭射。",
    )
    frame = layout(state, ["我们今天来讨论镭射。"])
    assert frame == Layout(
        history=("我们今天来讨论镭射。",),
        source="牙医也使用镭射。",
        prev=(Run("Laser technology can precisely remove tumor tissue.", COMMITTED),),
        current=(Run("Dentists ", COMMITTED), Run("also use lasers", DRAFT),
                 Run(", reducing bleeding.", COMMITTED)),
    )
    assert runs_text(frame.current) == "Dentists also use lasers, reducing bleeding."


def test_layout_is_a_pure_function_of_the_model_state():
    """``layout`` needs nothing but a ``DisplayState`` and the source history: no
    window, no renderer, no clock. Fails if the projection starts reading view
    state of its own (the removed ``SrcReadingBuffer`` was exactly that: a second
    copy of the source row rule living beside the model)."""
    clock = _Clock()
    model = CaptionDisplay(hold_sec=HOLD, clock=clock)
    model.preview("Dentists also use lasers.")
    clock.advance(PACE)
    state = model.tick()
    assert state is not None
    assert layout(state) == layout(state), "the projection is not deterministic"
    assert layout(state, ["镭射。"]) == Layout(
        history=("镭射。",),
        source="",
        prev=(),
        current=(Run("Dentists also use lasers.", DRAFT),),
    )


def test_canonical_layout_snapshot():
    """One deterministic snapshot of all four layout parts on the canonical
    stream: the source history, the live source row, the previous target line,
    the active target line. Pins the projection, so a regression — a history line
    that stopped being handed over, the source row moving above the caption, a
    blank caption row — shows up in the diff.

    The source history repeats ``镭射技术可以精确的。`` because the ASR commits source
    in segments: that rolling row was on screen, then retired, then came back and
    retired again. The history is the log of retired rows; the window shows the
    newest one."""
    frames = _walk(CANONICAL)
    populated = [frame for frame in frames
                 if frame.history and frame.source and frame.prev and frame.current]
    assert populated, "canonical stream should show all four parts at once"
    assert populated[1] == Layout(
        history=(
            "我们今天来讨论镭射。",
            "来讨论镭射。",
            "镭射技术可以精确的。",
            "镭射技术可以精确的。",
            "减少对周围健康组织。",
        ),
        source="围健康组织。",
        prev=(Run("Today, we will discuss the applications of laser in medicine.",
                  COMMITTED),),
        current=(Run("Laser technology can precisely remove tumor tissue.", COMMITTED),),
    )


# ---- the view's one piece of state (the frame buffer) --------------------


def test_the_active_row_takes_the_models_style_when_the_text_does_not_change():
    """A draft committed word-for-word brightens in place: the model re-styles the
    line without changing its text, and the view must follow.

    Fails if the view decides whether to redraw from "did the text change?" — the
    ``_shown_en_final`` flag this seam removed — or from a style of its own: the
    frame buffer is the model's runs."""
    clock = _Clock()
    renderer = OverlayRenderer(overlay_mode="target", hold_sec=HOLD, clock=clock)
    renderer.preview("", [(None, "Dentists also use lasers.")])
    clock.advance(PACE)
    assert renderer.pump() is not None
    draft = renderer.layout().current
    assert [run.style for run in draft] == [DRAFT]
    assert renderer._shown == draft

    renderer.translation("", [(None, "Dentists also use lasers.")])
    clock.advance(PACE)
    assert renderer.pump() is not None
    final = renderer.layout().current
    assert runs_text(final) == runs_text(draft), "the final kept the draft's wording"
    assert [run.style for run in final] == [COMMITTED]
    assert renderer._shown == final, "the row still shows the draft's style"


def test_the_view_keeps_no_provisional_or_committed_flag():
    """The frame buffer is the view's only state. Fails if a flag that re-derives
    which row is committed comes back (``_shown_en_final``, or a cached
    provisional/committed copy of the model's style)."""
    renderer = OverlayRenderer(overlay_mode="target", hold_sec=HOLD, clock=_Clock())
    flags = [name for name in vars(renderer)
             if "final" in name or "prov" in name or "commit" in name]
    assert flags == []
    assert isinstance(renderer._shown, tuple)


# ---- the animation policy (the only view policy left) --------------------


def test_a_grown_line_types_its_delta_on():
    """A line that only grew is revealed in steps, each a prefix of the model's
    line, ending at the model's line: the reader watches the sentence continue."""
    shown = (Run("Today, we", DRAFT),)
    target = (Run("Today, we will discuss lasers.", DRAFT),)
    steps = reveal_steps(shown, target)
    assert len(steps) > 1
    assert steps[-1] == target
    texts = [runs_text(step) for step in steps]
    assert texts[0].startswith("Today, we ")
    assert all(target_text.startswith(text) for text, target_text in zip(texts, texts[1:]))
    assert all(run.style == DRAFT for step in steps for run in step)


def test_a_line_that_is_not_a_growth_appears_at_once():
    """A rewrite, a new caption and a draft replaced by its final all appear
    whole: typing a fresh chunk character by character is unreadable.

    Fails if a common-prefix heuristic comes back to keep a prefix on screen and
    type the divergent suffix (the ``_common_prefix_len >= 0.35`` branch the
    model replaced with its own hold-draft rule). The second case is
    ``zh_long_time_frontier``'s real mid-draft correction, which shares 49
    characters with what is on screen — the longest common prefix the goldens
    have, and still a reword rather than a growth."""
    target = (Run("Reduce damage to surrounding healthy tissues.", COMMITTED),)
    for shown in ((Run("Reduces damage to", DRAFT),), (), (Run("Anyway.", COMMITTED),)):
        assert reveal_steps(shown, target) == (target,)
    corrected = (Run(
        "Today, we will discuss the applications of laser technology in medicine.",
        COMMITTED),)
    assert reveal_steps(
        (Run("Today, we will discuss the applications of laser in medicine.", COMMITTED),),
        corrected,
    ) == (corrected,)


def test_reveal_steps_carry_each_runs_own_style():
    """Every step is a prefix of the model's runs, so a step that crosses from
    committed text into a draft carries both styles. Fails if the reveal renders
    the line in one flat colour (the deleted ``_spans_to_attributed_simple``,
    which took a single provisional/final flag)."""
    target = (Run("In ophthalmic surgery, ", COMMITTED), Run("lasers are used", DRAFT))
    steps = reveal_steps((Run("In ophthalmic", COMMITTED),), target)
    assert steps[-1] == target
    crossed = [step for step in steps if {run.style for run in step} == {COMMITTED, DRAFT}]
    assert crossed, "no step exposed both of the model's styles"


# ---- view parity ---------------------------------------------------------


def _terminal_scrollback(path) -> list:
    """The terminal view's scrollback for the same golden, same pacing."""
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    return replay(load_caption_events(path), console, hold=HOLD, pace=PACE,
                  drain_seconds=DRAIN).history_lines()


@pytest.mark.parametrize("golden", GOLDENS, ids=lambda path: path.stem)
def test_target_transcript_matches_the_terminal_scrollback(golden):
    """View parity: the overlay's two target rows, read as a transcript, are the
    terminal view's scrollback — the same model, the same lines, the same order.

    Fails if the overlay's layout loses, duplicates or reorders a line relative to
    the model (the terminal view is a thin consumer too, so a disagreement is a
    layout defect, not a difference of taste)."""
    assert transcript(_walk(golden)) == _terminal_scrollback(golden)
