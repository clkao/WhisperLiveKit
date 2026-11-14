"""Terminal TUI view: the caption display model's ``DisplayState`` rendered as a
three-region ``rich.Live`` layout.

The view is thin by design. ``CaptionDisplay`` (``caption_display.py``) owns the
display rules — hold-drain, draft-to-final promotion, sentence partitioning,
scroll-up, monotonic source — and this module maps its ``DisplayState`` to three
regions:

  1. history: committed caption lines, appended to the terminal scrollback when
     a line leaves the live region (append-only, monotonic);
  2. caption: the active line, rendered span by span — ``PROVISIONAL`` is dim
     (a draft), ``FINAL_SAME`` bright (committed), ``FINAL_ADD`` green (the
     correction or the new words);
  3. source: the ASR partial (``DisplayState.partial``), plain and dim.

Install (``rich`` is an optional extra; the web UI and the pipeline do not
need it) and run the replay::

    pip install -e ".[tui]"
    python -m whisperlivekit.tui --replay tests/golden/zh_long_canonical.jsonl

``--replay`` needs no network, no model weights and no audio: it loads a
recorded caption event stream (what ``--event-log`` writes), feeds it to a
``CaptionDisplay``, and renders it on a stepped clock, so one log always
produces the same frames. ``--help`` lists the pacing knobs.

What reaches the transcript: a caption line is printed once, when it leaves the
live region, because the model may still reword it while it is shown and a
terminal scrollback cannot rewrite a printed line (``_is_reword`` documents the
heuristic that stands in for the line identity ``DisplayState`` does not
carry).

A live session attaches the renderer as the pipeline's caption-event sink::

    with TuiRenderer(CaptionDisplay(hold_sec=3.5)) as tui:
        processor = AudioProcessor(..., caption_display=tui)

``TuiRenderer.emit`` is the ``EventSink`` entry point; it forwards to the model
under the same lock the frame clock uses, because the model is single-threaded
and the frame clock runs on its own thread (``threaded``).
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Sequence

try:  # optional dependency: the `tui` extra
    from rich.console import Console, Group
    from rich.live import Live
    from rich.text import Text
except ImportError as exc:  # pragma: no cover - only without the extra installed
    raise ImportError(
        "whisperlivekit.tui needs rich; install the extra: pip install 'whisperlivekit[tui]'"
    ) from exc

from whisperlivekit.caption_display import (
    FINAL_ADD,
    FINAL_SAME,
    PROVISIONAL,
    CaptionDisplay,
    DisplayState,
    load_caption_events,
)
from whisperlivekit.caption_events import CaptionEvent

# The frame clock: the view advances the model's hold-drain at this rate.
FRAME_HZ = 12

# Span tag -> rich style, per resolved theme. The model's three span kinds are
# the whole vocabulary; nothing else may appear on a caption line.
_SPAN_STYLES = {
    PROVISIONAL: {
        "default": "grey50",
        "dark": "grey50",
        "light": "grey39",
    },
    FINAL_SAME: {
        "default": "bold",
        "dark": "bold bright_cyan",
        "light": "deep_sky_blue4",
    },
    FINAL_ADD: {
        "default": "bold green",
        "dark": "bold bright_green",
        "light": "green4",
    },
}
_SOURCE_STYLES = {
    "default": "grey50",
    "dark": "grey50",
    "light": "grey39",
}
_HISTORY_STYLE = FINAL_SAME

DEFAULT_EVENTS = Path(__file__).resolve().parent.parent / "tests" / "golden" / "zh_long_canonical.jsonl"


def _resolve_theme(theme: str) -> str:
    """Map ``auto`` to light/dark from the terminal's background, else pass through."""
    if theme in ("light", "dark", "default"):
        return theme
    bg = os.environ.get("COLORFGBG", "").split(";")[-1].strip()
    if bg in ("7", "15"):
        return "light"
    if bg.isdigit():
        return "dark"
    return "default"


def _plain(spans: Sequence) -> str:
    """The unstyled text of a span list (what the reader sees, no colours)."""
    return "".join(span.text for span in spans)


def _is_committed(state: DisplayState) -> bool:
    """True when the active line holds committed text (no dim draft span)."""
    return bool(state.current) and all(span.style != PROVISIONAL for span in state.current)


class TuiRenderer:
    """Renders ``CaptionDisplay``'s ``DisplayState`` in a three-region layout.

    The renderer holds no display policy: every rule (when a caption releases,
    when a draft becomes final, which sentence scrolls up) belongs to the model.
    Its own state is the scrollback (lines already printed, append-only) and the
    one history line still held back for possible in-place amendment.

    Threading: ``emit`` is called from the pipeline's event-loop thread; the
    frame clock (``threaded=True``, the default) calls ``pump`` from a daemon
    thread at ``FRAME_HZ``. Both take ``self._lock``, which is what keeps the
    single-threaded model single-threaded. ``threaded=False`` leaves `pump` to
    the caller — the replay consumer steps the clock and pumps by hand.
    """

    def __init__(
        self,
        display: CaptionDisplay,
        console: Optional[Console] = None,
        theme: str = "auto",
        frame_hz: float = FRAME_HZ,
        threaded: bool = True,
    ) -> None:
        self.display = display
        self.console = console or Console()
        resolved = _resolve_theme(theme)
        self._span_styles = {tag: table[resolved] for tag, table in _SPAN_STYLES.items()}
        self._source_style = _SOURCE_STYLES[resolved]
        self._frame_interval = 1.0 / frame_hz
        self._threaded = threaded
        self._lock = threading.RLock()
        self._history: List[str] = []
        self._printed: set = set()
        self._held_history: Optional[str] = None
        self._last_current = ""
        self._last_current_committed = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._live: Optional[Live] = None

    # ---- lifecycle ----

    def __enter__(self) -> "TuiRenderer":
        self._live = Live(self._live_region(self.display.state()), console=self.console, transient=False)
        self._live.start()
        if self._threaded:
            self._thread = threading.Thread(target=self._frame_loop, name="tui-frames", daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._lock:
            self.pump()  # one last frame: state mutated since the clock stopped
            self.flush()
            live, self._live = self._live, None
        if live is not None:
            live.stop()

    def _frame_loop(self) -> None:
        while not self._stop.wait(self._frame_interval):
            self.pump()

    # ---- the sink (what the pipeline drives) ----

    def emit(self, event: CaptionEvent) -> None:
        """``EventSink`` entry point: forward one caption event to the model."""
        with self._lock:
            self.display.emit(event)

    def state(self) -> DisplayState:
        """The model's current state without advancing its clock."""
        with self._lock:
            return self.display.state()

    # ---- the frame clock ----

    def pump(self) -> Optional[DisplayState]:
        """Advance the model one frame and render it; None if nothing changed."""
        with self._lock:
            state = self.display.tick()
            if state is None:
                return None
            self._reconcile(state)
            if self._live is not None:
                self._live.update(self._live_region(state))
            return state

    def flush(self) -> None:
        """Print the held history line and the resting caption line.

        On exit the live region is torn down: the line held back for amendment
        has not retired yet and the active caption has not scrolled anywhere,
        so both are written to the scrollback — the reader keeps what was on
        screen.
        """
        with self._lock:
            self._commit_held_history()
            current_state = self.display.state()
            # the resting line only joins the scrollback when it is committed:
            # a dim draft is not history (the model's rule is that only finals
            # scroll), and the live region is about to be torn down
            if _is_committed(current_state):
                self._print_caption(_plain(current_state.current))

    # ---- reconciliation: DisplayState -> scrollback + live region ----

    def _reconcile(self, state: DisplayState) -> None:
        """Fold one frame into the scrollback, then remember the frame.

        A caption line reaches the scrollback when it *leaves the live region*,
        not when it first appears, because the model may still amend it in
        place while it is shown (a draft-promoted sentence reworded by its
        final: ``CaptionDisplay.preview`` promotes a completed sentence to
        ``prev`` and ``CaptionDisplay.translation`` rewords it there). A
        terminal scrollback cannot rewrite a printed line, so printing on first
        sight would type the same sentence twice.

        Both live slots are tracked:

          - ``prev`` is held and printed when it retires — when it clears, or
            when a different line replaces it. A change that only extends or
            trims the held text is the model's in-place reword: it replaces the
            held text and prints nothing;
          - ``current`` is printed when it leaves the region *without* scrolling
            up (``prev`` is then some older line): the model can replace or
            expire the active line without a scroll, and committed text the
            reader saw must not be dropped. Provisional (dim) text is not
            history — the model's rule is that only finals scroll — so a draft
            that leaves is dropped.

        Exact repeats are not typed twice: the model can re-show the same
        sentence from the draft stream and then from its final (see
        ``tests/golden/demo_en_30s_ideal.jsonl``), and a transcript that repeats
        a line reads as a rendering glitch.
        """
        current = _plain(state.current)
        previous = _plain(state.prev)
        # prev: the held history line retires when a different line lands or it clears
        if not previous:
            self._commit_held_history()
        elif previous != self._held_history:
            if previous == self._last_current or not _is_reword(self._held_history, previous):
                self._commit_held_history()
            self._held_history = previous
        # current: committed text that left the live region without scrolling up
        # and without being reworded in place (an amendment, not a new caption)
        if self._last_current and self._last_current != current:
            if (self._last_current_committed and previous != self._last_current
                    and not _is_reword(self._last_current, current)):
                self._commit_held_history()
                self._print_caption(self._last_current)
        self._last_current = current
        self._last_current_committed = _is_committed(state)

    def _commit_held_history(self) -> None:
        held, self._held_history = self._held_history, None
        if held:
            self._print_caption(held)

    def _print_caption(self, text: str) -> None:
        if not text or text in self._printed:
            return
        self._printed.add(text)
        self._history.append(text)
        self.console.print(Text(text, style=self._span_styles[_HISTORY_STYLE]))

    # ---- the three regions ----

    def caption_line(self, state: DisplayState) -> Text:
        """Region 2: the active caption line, one styled run per model span."""
        line = Text()
        for span in state.current:
            line.append(span.text, style=self._span_styles.get(span.style, ""))
        return line

    def source_line(self, state: DisplayState) -> Text:
        """Region 3: the ASR partial — the source the caption is made from."""
        line = Text()
        if state.partial:
            line.append("[src] ", style=self._source_style)
            line.append(state.partial, style=self._source_style)
        return line

    def _live_region(self, state: DisplayState) -> Group:
        return Group(self.caption_line(state), self.source_line(state))

    def history_lines(self) -> List[str]:
        """The scrollback as plain text, oldest first (append-only)."""
        with self._lock:
            return list(self._history)


def _is_reword(held: Optional[str], text: str) -> bool:
    """True when ``text`` rewords ``held`` in place rather than replacing it.

    A reword keeps the bulk of the line — a draft promoted mid-sentence then
    completed, or a final fixing one word: ``... healthy tissue.`` ->
    ``... healthy tissues.`` is one caption reworded, not two captions. A
    different caption shares little with the held one, so the two land on
    opposite sides of a character-overlap ratio of 0.8. This is a heuristic
    because ``DisplayState.prev`` carries no line identity (see the module
    notes on the model's in-place amendment); the cost of a wrong answer is one
    extra or one missing line in the scrollback.
    """
    if not held or not text:
        return False
    if text.startswith(held) or held.startswith(text):
        return True
    import difflib
    return difflib.SequenceMatcher(a=held, b=text, autojunk=False).ratio() >= 0.8


class _StepClock:
    """Deterministic seconds counter: the replay advances it, nothing else does."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def replay(
    events: Sequence[CaptionEvent],
    console: Optional[Console] = None,
    hold: float = 3.5,
    pace: float = 0.3,
    drain_seconds: float = 10.0,
    delay: float = 0.0,
    theme: str = "auto",
) -> TuiRenderer:
    """Render a recorded caption event stream through a fresh ``CaptionDisplay``.

    ``pace`` virtual seconds are advanced per event, then the clock keeps
    running for ``drain_seconds`` in 0.1 s steps so the hold queue empties —
    the reader's clock does not stop when the recording does. The clock is
    stepped, never read from the wall, so the same stream always renders the
    same frames. ``delay`` is real seconds slept after each changed frame, for
    a human-watchable run (0 renders as fast as the terminal accepts).
    """
    clock = _StepClock()
    renderer = TuiRenderer(CaptionDisplay(hold_sec=hold, clock=clock), console=console,
                           theme=theme, threaded=False)
    with renderer:
        for event in events:
            clock.advance(pace)
            renderer.emit(event)
            _frame(renderer, delay)
        for _ in range(int(drain_seconds / 0.1)):
            clock.advance(0.1)
            _frame(renderer, delay)
    return renderer


def _frame(renderer: TuiRenderer, delay: float) -> None:
    if renderer.pump() is not None and delay:
        time.sleep(delay)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m whisperlivekit.tui",
        description="Render a recorded caption event stream in the terminal TUI "
                    "(the caption display model's terminal consumer). "
                    "No network, no model weights, no audio.",
        epilog="example: python -m whisperlivekit.tui --replay "
               "tests/golden/zh_long_canonical.jsonl --delay 0.05",
    )
    parser.add_argument("--replay", metavar="LOG.jsonl", default=str(DEFAULT_EVENTS),
                        help="caption event stream to render, one JSON event per line "
                             "(what --event-log writes); default: the checked-in "
                             "tests/golden/zh_long_canonical.jsonl")
    parser.add_argument("--hold", type=float, default=3.5,
                        help="seconds a caption holds on the line before the next one "
                             "releases (default: 3.5)")
    parser.add_argument("--pace", type=float, default=0.3,
                        help="virtual seconds advanced per event (default: 0.3)")
    parser.add_argument("--drain", type=float, default=10.0,
                        help="virtual seconds rendered after the last event, so queued "
                             "captions still release (default: 10)")
    parser.add_argument("--delay", type=float, default=0.02,
                        help="real seconds per changed frame; 0 renders as fast as "
                             "possible (default: 0.02)")
    parser.add_argument("--theme", default="auto", choices=("auto", "dark", "light", "default"),
                        help="colour theme; auto reads COLORFGBG (default: auto)")
    parser.add_argument("--width", type=int, default=None,
                        help="console width in columns (default: the terminal's)")
    args = parser.parse_args(argv)

    path = Path(args.replay)
    if not path.is_file():
        parser.error(f"no such caption log: {path}")
    events = load_caption_events(path)
    console = Console(width=args.width) if args.width else Console()
    console.print(f"[dim]{len(events)} caption events from {path}[/dim]")
    renderer = replay(events, console, hold=args.hold, pace=args.pace,
                      drain_seconds=args.drain, delay=args.delay, theme=args.theme)
    console.print(f"[dim]{len(renderer.history_lines())} caption lines[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
