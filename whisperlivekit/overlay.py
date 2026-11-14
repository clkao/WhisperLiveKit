"""Borderless always-on-top caption overlay (PyObjC / AppKit).

``OverlayRenderer`` is the native window view over the shared caption display
model. It owns a ``CaptionDisplay`` (``caption_display.py``) — the same model
the terminal view and the replay consumer render — and feeds it plain text: the
rolling source row, provisional translations, committed translations. All
display policy (hold-drain, draft-to-final promotion, sentence partitioning,
monotonic source, scroll-up, expiry) stays in the model.

The projection from model to screen is a pure function, ``layout(state,
history) -> Layout``: the committed source lines, the live source row, the
previous target line and the active target line, each as plain text plus a
resolved style name (``DRAFT`` dim / ``COMMITTED`` bright). ``OverlayRenderer``
draws what ``layout`` returns and decides nothing else; ``reveal_steps`` is the
one piece of view policy left (how much of a grown line appears at once). Both
are AppKit-free and unit-tested in ``tests/test_overlay_layout.py`` — a view that
re-derived "is this provisional?", "did the line extend or was it rewritten?"
from string prefixes is what this seam removed.

Design:
- One NSWindow, borderless, transparent, draggable, level 27 (above
  ``NSStatusWindowLevel`` 25 and Keynote Play's 26), collectionBehavior includes
  ``.canJoinAllSpaces`` + ``.stationary`` + ``.fullScreenAuxiliary`` so it can
  appear over a fullscreen Space.
- ``overlay_mode`` selects the layout: ``both`` = source row + source history +
  large target row; ``target`` = two target rows (the committed caption
  scrolls up to the dimmer history row); ``source`` = the ASR rows only.
- AppKit is imported lazily (see ``_create_window``) so this module imports on a
  headless host or without pyobjc installed. NSApplication + the window are
  created on the main thread (a PyObjC requirement) in ``__enter__``, and
  ``run_until`` pumps the AppKit run loop on the main thread with a
  Python-controlled loop so a SIGINT handler still gets control between
  iterations (a native ``app.run()`` swallows Ctrl-C).
- ``--mem`` prints MLX active/cache/peak + asr/cap latency to stderr on a 1s
  timer: the window has no status line of its own.

Fullscreen caveat: if the overlay does NOT appear over true-fullscreen Keynote,
bump ``OVERLAY_LEVEL`` (try a high raw NSInteger above
``NSMainMenuWindowLevel``, e.g. 2147483623).
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from whisperlivekit.caption_display import (
    FINAL_ADD,
    FINAL_SAME,
    PROVISIONAL,
    CaptionDisplay,
    DisplayState,
)
from whisperlivekit.inline_diff import _DIFF_TOKEN_RE

# AppKit is imported lazily at instantiation (see _create_window) so this module
# imports cleanly even on a headless host or without pyobjc installed. The level /
# collection-behavior constants are resolved against AppKit the first time an
# OverlayRenderer is constructed.
AppKit = None
Foundation = None

# Default window level: NSStatusBarLevel (25) sits above the main menu (24). If the
# overlay doesn't show over a true-fullscreen app, raise OVERLAY_LEVEL (try a high
# raw NSInteger above NSMainMenuWindowLevel, e.g. 2147483623; see module docstring).
OVERLAY_LEVEL = 27  # above NSStatusWindowLevel(25) and Keynote Play's level(26)
OVERLAY_ALPHA = 1.0       # window alpha; the pill bg below is the visible opacity
# Minimum time a finalized EN caption stays visible before the next may replace it.
# Stops the flash where a fast speaker's 1s utterances replace the EN line before the
# audience reads it. Long multi-sentence translations are split into sentences and each
# is held this long (FIFO, so they read in order). A new utterance clears pending unshown
# sentences (newest-utterance wins); the currently-shown stays for its hold. Previews
# never set the field directly — they queue too, so a draft can't flicker over a held
# final. ``hold_sec`` (--overlay-hold) overrides it per renderer.
MIN_HOLD_SEC = 3.5

# CJK range for tokenization (mirrors inline_diff._CJK subset).
_CJK = "　-〿㐀-翿一-鿿豈-﫿＀-￯"  # same ranges as inline_diff._CJK
_CJK_RE = re.compile(rf"[{_CJK}]")


def _is_cjk(ch: str) -> bool:
    return bool(_CJK_RE.match(ch))


def _merge_cjk_pairs(tokens: list) -> list:
    """Merge consecutive single-CJK-char tokens into pairs so the streaming
    reveals 2 chars at a time (1 char at 0.05s is too slow to read; a 4-char
    word at 0.05s is fast but CJK has no spaces to group by)."""
    out = []
    cjk_buf = ""
    for tok in tokens:
        if len(tok) == 1 and _is_cjk(tok):
            cjk_buf += tok
            if len(cjk_buf) >= 2:
                out.append(cjk_buf)
                cjk_buf = ""
        else:
            if cjk_buf:
                out.append(cjk_buf)
                cjk_buf = ""
            out.append(tok)
    if cjk_buf:
        out.append(cjk_buf)
    return out


# Flattening helper (mirrors render._segments_text): drop the diff spans, keep
# inline [S1]/[S2] speaker markers so multi-speaker utterances still read right.
def _segments_text(segments: list) -> str:
    parts = []
    for seg in segments:
        speaker, text = seg[0], seg[1]
        parts.append(f"[S{speaker + 1}] {text}" if speaker is not None else text)
    return "  ".join(parts)


# ---- the layout: DisplayState -> the rows the window draws (no AppKit) ----

# The window's visual vocabulary. The model publishes three span tags
# (PROVISIONAL / FINAL_SAME / FINAL_ADD); the window's grammar is two — dim is a
# draft, bright is committed — because the draft already grew by append and a
# third colour read as noise.
DRAFT = "draft"
COMMITTED = "committed"
_STYLE_NAMES = {PROVISIONAL: DRAFT, FINAL_SAME: COMMITTED, FINAL_ADD: COMMITTED}

# The row fonts (pt) and the brightness each resolved style renders at: the
# history row sits back so the active line owns the eye.
TARGET_FONT_PT = 42.0
PREV_FONT_PT = 28.0
_TARGET_WHITE = {DRAFT: 0.55, COMMITTED: 1.0}
_PREV_WHITE = {DRAFT: 0.5, COMMITTED: 0.8}


@dataclass(frozen=True)
class Run:
    """One styled text run: a model span with its tag resolved to a style name."""
    text: str
    style: str


@dataclass(frozen=True)
class Layout:
    """Everything the window draws, and nothing it decides.

    history: the committed source lines, oldest first (append-only)
    source:  the live source row — the model's ``DisplayState.partial``
    prev:    the previous target line (the row above the active one)
    current: the active target line
    """
    history: Tuple[str, ...] = ()
    source: str = ""
    prev: Tuple[Run, ...] = ()
    current: Tuple[Run, ...] = ()


def runs_text(runs: Sequence[Run]) -> str:
    """The plain text of a run list."""
    return "".join(run.text for run in runs)


def _runs(spans) -> Tuple[Run, ...]:
    """The model's spans as runs, in order (empty spans dropped)."""
    return tuple(Run(span.text, _STYLE_NAMES[span.style]) for span in spans if span.text)


def _truncate(runs: Sequence[Run], n: int) -> Tuple[Run, ...]:
    """The first n characters of a run list (the boundary run is split)."""
    out: List[Run] = []
    used = 0
    for run in runs:
        if used >= n:
            break
        text = run.text[:n - used]
        out.append(Run(text, run.style))
        used += len(text)
    return tuple(out)


def reveal_steps(shown: Sequence[Run],
                 target: Sequence[Run]) -> Tuple[Tuple[Run, ...], ...]:
    """The frames the active row is revealed in, from what is on screen to the
    model's line.

    A line that only GREW types its delta on unit by unit, so the reader watches
    the sentence continue. Anything else — a new caption, a rewrite, a draft
    replaced by its final — appears at once: typing a fresh chunk character by
    character is unreadable. Every step's styles are the model's own (each step
    is a prefix of ``target``), so the reveal can never disagree with the model
    about which part of the line is committed.
    """
    shown_text, target_text = runs_text(shown), runs_text(target)
    if not target or not shown_text or not target_text.startswith(shown_text):
        return (tuple(target),) if target else ()
    cur = shown_text
    steps: List[Tuple[Run, ...]] = []
    for unit in _merge_cjk_pairs(_DIFF_TOKEN_RE.findall(target_text[len(shown_text):])):
        needs_space = (cur and unit and not unit.startswith(" ")
                       and not cur.endswith(" ") and not _is_cjk(unit[0]))
        cur = (cur + " " + unit) if needs_space else (cur + unit)
        steps.append(_truncate(target, len(cur)))
    return tuple(steps)


def layout(state: DisplayState, history: Sequence[str] = ()) -> Layout:
    """Project a ``DisplayState`` onto the window's rows.

    Pure: the same state and history always give the same layout, with no clock
    and no AppKit. Every display decision was made by the model — which text is
    provisional, where a sentence ends, when a committed line scrolls up, how
    long it holds; this only names the four parts the window has rows for.
    """
    return Layout(history=tuple(history), source=state.partial,
                  prev=_runs(state.prev), current=_runs(state.current))


class OverlayRenderer:
    """The caption overlay window: a view over ``CaptionDisplay``.

    Feed it text (``partial`` / ``final`` / ``preview`` / ``translation``); the
    model it owns decides every display rule, the drain thread lays the resulting
    ``DisplayState`` out (``layout``) and draws it. ``--mem`` and the latency
    status line belong to the driver's ``StatsTracker``, not to the window: the
    caption event stream carries no per-utterance start time, so the view reports
    no latency.
    """

    def __init__(
        self,
        overlay_mode: str = "both",
        hold_sec: float = MIN_HOLD_SEC,
        clock=time.monotonic,
    ) -> None:
        self._overlay_mode = overlay_mode  # "both" | "target" | "source"
        self._stop = threading.Event()
        # window + fields (created in __enter__ on the main thread)
        self._win: AppKit.NSWindow | None = None
        self._field_zh: AppKit.NSTextField | None = None        # newest committed source line
        self._field_en: AppKit.NSTextField | None = None
        self._field_en_prev: AppKit.NSTextField | None = None  # two-row target mode only
        self._field_partial: AppKit.NSTextField | None = None   # the live source row
        # Display model: the pure, AppKit-free state machine (hold-drain, provisional
        # -> final replacement, monotonic source, scroll-up-to-history, expiry) in
        # caption_display.py. The renderer feeds TEXT in; the drainer ticks the model,
        # ``layout`` projects the returned DisplayState onto the rows and this view draws
        # it. Tests drive the model directly with a fake clock
        # (tests/test_caption_display.py) and the projection without a window
        # (tests/test_overlay_layout.py).
        self._model = CaptionDisplay(hold_sec=hold_sec, clock=clock)
        # The source lines the reader has already been shown, oldest first: a commit
        # retires the model's live row into this list (see ``final``). A record, not a
        # decision — nothing here is re-derived from committed text.
        self._source_history: List[str] = []
        self._en_drain_stop = threading.Event()
        self._append_stop = threading.Event()  # cancels a stale reveal thread
        # The frame buffer: the runs already typed onto the active row. The view's only
        # state, and it decides only HOW MUCH of the model's line is on screen — never
        # which part of it is provisional (the runs carry the model's styles).
        self._shown: Tuple[Run, ...] = ()
        self._streaming_target: Tuple[Run, ...] = ()  # the line a reveal is typing toward
        self._streaming_active = False  # is a reveal thread running
        self._en_drain_thread: threading.Thread | None = None

    # ---- lifecycle (context manager, same shape as render.Renderer) ----
    def __enter__(self) -> "OverlayRenderer":
        self._create_window()
        # AppKit's run loop MUST run on the main thread for the window to display and
        # redraw. The driver's main thread later calls renderer.run_until(stop_event) (in
        # place of stop_event.wait()), which pumps the AppKit loop on the main thread via
        # a Python-controlled loop — so SIGINT's handler actually gets control and Ctrl-C
        # exits reliably (a native app.run() would swallow SIGINT).
        self._en_drain_thread = threading.Thread(
            target=self._drain_en, daemon=True, name="en-hold-drain"
        )
        self._en_drain_thread.start()
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self._stop.set()
        self._en_drain_stop.set()
        if self._en_drain_thread is not None:
            self._en_drain_thread.join(timeout=2)
        if self._win is not None:
            self._win.orderOut_(None)

    def _create_window(self) -> None:
        global AppKit, Foundation
        if AppKit is None:
            import AppKit as _AppKit
            import Foundation as _Foundation
            AppKit = _AppKit
            Foundation = _Foundation
        collection_behavior = (
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        app = AppKit.NSApplication.sharedApplication()
        # accessory: no dock icon, no focus stealing from Keynote
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        screen = AppKit.NSScreen.mainScreen()
        sf = screen.frame()
        # full-width bottom bar: edge to edge, sits at the very bottom of the screen.
        w = sf.size.width
        if self._overlay_mode == "both":
            h = 160
        elif self._overlay_mode == "target":
            # two rows: prev (history) 50px (28pt) + current 100px (42pt, ~3 wrap lines
            # for the provisional). The committed caption scrolls up to the prev row.
            h = 150
        else:
            h = 60  # single field, vertically centered
        x = 0
        y = 0
        rect = Foundation.NSMakeRect(x, y, w, h)

        win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        win.setLevel_(OVERLAY_LEVEL)
        win.setCollectionBehavior_(collection_behavior)
        win.setOpaque_(False)
        win.setBackgroundColor_(AppKit.NSColor.clearColor())
        win.setHasShadow_(True)
        # Draggable: accept mouse events and let the whole background move the window.
        # Tradeoff: clicking the overlay briefly takes focus — position it once before
        # presenting. Accessory activation policy keeps the dock/menu out of the way.
        win.setIgnoresMouseEvents_(False)
        win.setMovableByWindowBackground_(True)
        win.setAlphaValue_(OVERLAY_ALPHA)

        # opaque dark bar background so text reads over any slide. 0.85 = the slide is
        # faintly visible behind (the "opacity 85%" UX target). Window alpha is 1.0 so the
        # text itself stays full-bright; only the bar dims.
        view = AppKit.NSView.alloc().initWithFrame_(Foundation.NSMakeRect(0, 0, w, h))
        view.setWantsLayer_(True)
        layer = view.layer()
        layer.setBackgroundColor_(AppKit.NSColor.blackColor().colorWithAlphaComponent_(0.85).CGColor())
        layer.setCornerRadius_(0.0)
        layer.setOpaque_(False)

        # three stacked fields. Layout bottom-up (AppKit origin is bottom-left):
        #   partial (dim italic) at y=12, zh (small muted) above it, en (large, WRAPPING, top).
        def make_field(y, fh, font_size, color, italic=False, bold=False, wrap=False, vcenter=False):
            f = AppKit.NSTextField.alloc().initWithFrame_(
                Foundation.NSMakeRect(40, y, w - 80, fh)
            )
            f.setBezeled_(False)
            f.setDrawsBackground_(False)
            f.setEditable_(False)
            f.setSelectable_(False)
            f.setAlignment_(AppKit.NSCenterTextAlignment)
            if vcenter:
                f.cell()._setVerticallyCentered_(True)
            if wrap:
                # multi-line wrapping so long EN captions don't clip; 0 lines = no cap
                f.setUsesSingleLineMode_(False)
                f.cell().setWraps_(True)
                f.cell().setLineBreakMode_(AppKit.NSLineBreakByWordWrapping)
                f.setMaximumNumberOfLines_(0)
            font = AppKit.NSFont.systemFontOfSize_weight_(font_size, AppKit.NSFontWeightBold if bold else AppKit.NSFontWeightRegular)
            if italic:
                # italic via the manager; system font has an italic variant
                font = AppKit.NSFontManager.sharedFontManager().convertFont_toHaveTrait_(font, AppKit.NSFontItalicTrait)
            f.setFont_(font)
            f.setTextColor_(color)
            f.setStringValue_("")
            view.addSubview_(f)
            return f

        # taller window + a tall wrapping EN field so 2-3 lines fit without clipping.
        # EN is the focus: large (42pt), white, bold, wrapping. zh and partial smaller below.
        if self._overlay_mode == "both":
            self._field_partial = make_field(12, 22, 16, AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.6, 0.9), italic=True)
            self._field_zh = make_field(38, 26, 19, AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.78, 0.95))
            self._field_en = make_field(68, 84, 42, AppKit.NSColor.whiteColor(), bold=True, wrap=True)
        elif self._overlay_mode == "target":
            # two-row layout: current (large) + prev (dimmer, history)
            prev_h = 50
            self._field_partial = None
            self._field_zh = None
            self._field_en = make_field(0, h - prev_h, 42, AppKit.NSColor.whiteColor(), bold=True, wrap=True, vcenter=True)
            self._field_en_prev = make_field(h - prev_h, prev_h, 28, AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.5, 0.8), bold=True, wrap=True, vcenter=True)
        else:  # "source"
            self._field_partial = make_field(12, 22, 16, AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.6, 0.9), italic=True)
            self._field_zh = make_field(38, h - 40, 19, AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.78, 0.95))
            self._field_en = None

        win.setContentView_(view)
        win.orderFrontRegardless()
        self._win = win

    def run_until(self, stop_event: threading.Event) -> None:
        """Pump the AppKit run loop on the MAIN thread (the caller) until stop_event fires.
        cli.py calls this in place of stop_event.wait() when the overlay is active.

        Uses a Python-controlled pump loop (not app.run()) so SIGINT's handler actually
        gets control between iterations and Ctrl-C exits within ~50ms; a native app.run()
        swallows SIGINT and would hang on Ctrl-C.
        """
        global AppKit, Foundation
        if AppKit is None:
            import AppKit as _AppKit
            import Foundation as _Foundation
            AppKit = _AppKit
            Foundation = _Foundation
        app = AppKit.NSApplication.sharedApplication()
        while not stop_event.wait(0.05):
            event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                AppKit.NSAnyEventMask,
                Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.0),
                AppKit.NSDefaultRunLoopMode,
                True,
            )
            if event is not None:
                app.sendEvent_(event)

    def _drain_en(self) -> None:
        """Daemon thread: advance the model on a 100ms cadence (``pump``)."""
        while not self._en_drain_stop.wait(0.1):
            self.pump()

    def pump(self):
        """Advance the model one frame and draw it; None if nothing changed.

        The frame clock's single step: all hold/expiry/scroll-up policy lives in
        the model (caption_display.py, unit-tested); this lays the returned
        DisplayState out and draws it. The drain thread calls it on a timer; a
        test can call it directly (AppKit-free: the field writes no-op when no
        window was created)."""
        state = self._model.tick()
        if state is not None:
            self._reconcile(layout(state, self._source_history))
        return state

    def layout(self) -> Layout:
        """What the window would draw now: the model's state laid out, without
        advancing its clock."""
        return layout(self._model.state(), self._source_history)

    def _reconcile(self, frame: Layout) -> None:
        """Draw one ``Layout``: four parts onto four fields, nothing decided.

        The frame buffer (``_shown``) is the view's only state, and it only
        decides HOW MUCH of the model's line appears at once (``reveal_steps``,
        which reveals a grown line and shows anything else whole). Provisional vs
        committed is never re-derived here — every run carries the model's style.

        With no window (a headless host, or before ``__enter__``) there is
        nothing to animate: the buffer takes the model's line at once.
        """
        if frame.current != self._shown:
            if not frame.current:
                self._append_stop.set()
                self._streaming_active = False
                self._shown = ()
                self._set(self._field_en, "")
            elif AppKit is None or self._field_en is None:
                self._shown = frame.current
            else:
                self._reveal(frame.current)
        if frame.prev:
            self._set_attr(self._field_en_prev,
                           self._attributed(frame.prev, PREV_FONT_PT, _PREV_WHITE))
        else:
            self._set(self._field_en_prev, "")
        # the newest committed source line (the window has one row for the history;
        # the whole list travels in the Layout), then the live source row
        self._set(self._field_zh, frame.history[-1] if frame.history else "")
        self._set(self._field_partial, frame.source)

    def _reveal(self, target: Tuple[Run, ...]) -> None:
        """Type a grown line onto the active row at a readable pace.

        The steps are ``reveal_steps``' (pure, tested); this only paces them on a
        daemon thread and keeps the frame buffer in step, so the next frame knows
        what is already on screen. A line that is not a growth is one step — it
        simply appears."""
        if self._streaming_active and self._streaming_target == target:
            return  # already typing toward this line (the clock ticks every 100ms)
        steps = reveal_steps(self._shown, target)
        self._append_stop.set()  # cancel any reveal in flight
        self._streaming_active = False
        self._streaming_target = target
        if len(steps) <= 1:
            self._shown = target
            self._set_attr(self._field_en, self._attributed(target, TARGET_FONT_PT, _TARGET_WHITE))
            return
        self._append_stop = threading.Event()
        stop = self._append_stop
        # readable pacing: ~0.08s per step for short deltas, the whole reveal
        # bounded at ~1.8s so a large single-event append still tracks the speech
        step_sec = min(0.08, 1.8 / len(steps))
        self._streaming_active = True

        def _type() -> None:
            for step in steps:
                if stop.is_set():
                    break
                self._shown = step
                self._set_attr(self._field_en,
                               self._attributed(step, TARGET_FONT_PT, _TARGET_WHITE))
                time.sleep(step_sec)
            if self._append_stop is stop:  # a newer reveal did not supersede this one
                self._streaming_active = False

        threading.Thread(target=_type, daemon=True, name="ov-append").start()

    # ---- callback contract (source text in, display text to the model) ----
    def partial(self, label: str, text: str) -> None:
        """The rolling ASR tail. The model owns it — monotonic within a sentence,
        dropped when a commit lands or the row goes stale — and ``layout`` renders
        it as the source row."""
        self._model.set_partial(text)

    def final(self, label: str, segments: list) -> None:
        """A committed source clause: the row the reader was reading retires into
        the source history, and the model clears it.

        The committed segments are not re-assembled into a line: the model's own
        ``partial`` is the accumulated row the reader watched, while a commit
        carries one ASR segment of it (``我们今天`` of a sentence the row showed
        whole). Expiry is not a commit — a row the model drops after a silence
        was never committed, so it leaves no history line.
        """
        current = self._model.state().partial
        if current:
            self._source_history.append(current)
        self._model.clear_partial()

    def translation(self, label: str, segments: list) -> None:
        """A committed translation: the caption text the reader keeps."""
        if self._overlay_mode == "source":
            return
        self._model.translation(_segments_text(segments))

    def preview(self, label: str, segments: list) -> None:
        """Live provisional translation of the in-progress utterance."""
        if self._overlay_mode == "source":
            return
        self._model.preview(_segments_text(segments))

    def state(self):
        """The display model's current state without advancing its clock."""
        return self._model.state()

    def flush_pending(self) -> None:
        """Release any buffered finals when translation is disabled at runtime (model load
        failed). The overlay has no pending buffer (finals display immediately), so this is
        a no-op that satisfies the cli.py callback contract."""
        return

    # ---- helpers ----
    def _set(self, field: AppKit.NSTextField | None, value: str) -> None:
        """Update a field's text on the MAIN thread. AppKit is not thread-safe;
        setStringValue_ from a worker thread causes flicker, stale renders, and
        out-of-order updates. Dispatch async (waitUntilDone=False) so the
        drainer never blocks on the main run loop."""
        if field is None:
            return
        field.performSelectorOnMainThread_withObject_waitUntilDone_(
            "setStringValue:", value, False
        )

    def _attributed(self, runs: Sequence[Run], size: float, whites: dict):
        """Runs -> a styled NSAttributedString, each run in its own style's
        colour. ``whites`` maps a resolved style name to its calibrated white
        level (dim draft, bright committed). None when there is nothing to draw
        (no window, no runs)."""
        if not runs or AppKit is None:
            return None
        font = AppKit.NSFont.systemFontOfSize_weight_(size, AppKit.NSFontWeightBold)
        # the attributed string must carry the field's paragraph style — without
        # it the text falls back to left alignment (make_field centers)
        para = AppKit.NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(AppKit.NSCenterTextAlignment)
        mut = AppKit.NSMutableAttributedString.alloc().init()
        for run in runs:
            attrs = {
                "NSFont": font,
                "NSColor": AppKit.NSColor.colorWithCalibratedWhite_alpha_(
                    whites[run.style], 1.0),
                "NSParagraphStyle": para,
            }
            mut.appendAttributedString_(
                AppKit.NSAttributedString.alloc().initWithString_attributes_(run.text, attrs)
            )
        return mut

    def _set_attr(self, field: AppKit.NSTextField | None, attr) -> None:
        """Update a field with an attributed string on the MAIN thread."""
        if field is None or attr is None:
            return
        field.performSelectorOnMainThread_withObject_waitUntilDone_(
            "setAttributedStringValue:", attr, False
        )
