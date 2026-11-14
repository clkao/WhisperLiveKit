"""Borderless always-on-top caption overlay (PyObjC / AppKit).

``OverlayRenderer`` is the native window view over the shared caption display
model. It owns a ``CaptionDisplay`` (``caption_display.py``) — the same model
the terminal view and the replay consumer render — and feeds it plain text:
committed source clauses, provisional translations, committed translations. All
display policy (hold-drain, draft-to-final promotion, sentence partitioning,
scroll-up, expiry) stays in the model; this module only moves the model's
``DisplayState`` onto ``NSTextField``s and animates the deltas.

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
import sys
import threading

from whisperlivekit.caption_display import (
    PROVISIONAL,
    CaptionDisplay,
    _common_prefix_len,
    _truncate_spans,
)
from whisperlivekit.src_buffer import SrcReadingBuffer

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


class OverlayRenderer:
    """The caption overlay window: a view over ``CaptionDisplay``.

    Feed it text (``partial`` / ``final`` / ``preview`` / ``translation``); the
    model it owns decides every display rule, the drain thread renders the
    resulting ``DisplayState``. ``--mem`` and the latency status line belong to
    the driver's ``StatsTracker``, not to the window: the caption event stream
    carries no per-utterance start time, so the view reports no latency.
    """

    def __init__(
        self,
        overlay_mode: str = "both",
        hold_sec: float = MIN_HOLD_SEC,
    ) -> None:
        self._overlay_mode = overlay_mode  # "both" | "target" | "source"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        # zh reading buffer: the src row shows committed clauses ACCUMULATED
        # plus the rolling tail; when the sentence completes (terminator) the
        # buffer freezes; the NEXT sentence's first words promote it to the zh
        # history field. The float happens when new words need the line.
        self._src = SrcReadingBuffer()    # src reading buffer (pure, tested)
        # window + fields (created in __enter__ on the main thread)
        self._win: AppKit.NSWindow | None = None
        self._field_zh: AppKit.NSTextField | None = None
        self._field_en: AppKit.NSTextField | None = None
        self._field_en_prev: AppKit.NSTextField | None = None  # two-row target mode only
        self._field_partial: AppKit.NSTextField | None = None
        # Display model: the pure, AppKit-free state machine (hold-drain, provisional
        # -> final replacement, scroll-up-to-history, expiry) in caption_display.py. The
        # renderer feeds committed/draft TEXT in; the drainer ticks the model and this
        # view reconciles the returned DisplayState onto the NSTextFields. Tests drive
        # the model directly with a fake clock (tests/test_caption_display.py).
        self._model = CaptionDisplay(hold_sec=hold_sec)
        self._en_drain_stop = threading.Event()
        self._append_stop = threading.Event()  # cancels a stale streaming thread
        self._src_stop = threading.Event()     # cancels the src-row reveal thread
        self._src_streaming = False
        self._src_streaming_target: str = ""
        self._shown_en_plain: str = ""  # plain text currently rendered on the current row
        self._shown_en_final: bool = False  # is the shown row in committed (bright) style
        self._streaming_target: str = ""  # what the streaming thread is streaming toward
        self._streaming_active = False  # is a streaming thread running
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
        """Advance the model one frame and render it; None if nothing changed.

        The frame clock's single step: all hold/expiry/scroll-up policy lives in
        the model (caption_display.py, unit-tested); this only moves the returned
        DisplayState to the screen. The drain thread calls it on a timer; a test
        can call it directly (AppKit-free: the field writes no-op when no window
        was created)."""
        state = self._model.tick()
        if state is not None:
            self._reconcile(state)
        return state

    def _reconcile(self, state) -> None:
        """Apply a DisplayState to the fields. The streaming effect lives HERE (the
        view), not in the model: when the new current text EXTENDS what's already
        rendered, reveal the delta word-by-word with a micro-delay (perceived
        continuity); on a rewrite or first show, hard-swap to the latest.

        The model handles hold/scroll/expiry/queue logic; the view handles the
        visual animation. All AppKit updates are dispatched to the main thread."""
        cur_plain = "".join(sp.text for sp in state.current)
        _prev_plain = "".join(s.text for s in state.prev)  # noqa: F841 — kept for the diff trace
        is_provisional = bool(state.current) and state.current[0].style == PROVISIONAL

        # Current row: stream on extends (appending), hard-swap on everything else
        # (new caption, rewrite, provisional→final). Typing a fresh large chunk
        # char-by-char is unreadable; only appending a small delta benefits from
        # the streaming effect.
        if cur_plain != self._shown_en_plain:
            if not cur_plain:
                self._set(self._field_en, "")
                self._shown_en_plain = ""
            elif (self._shown_en_plain and cur_plain.startswith(self._shown_en_plain)
                  and len(cur_plain) > len(self._shown_en_plain)):
                # extends: stream the delta word-by-word
                import os
                if os.environ.get("OV_DEBUG"):
                    print(f"[ov] extends: {self._shown_en_plain!r} -> {cur_plain!r}", file=sys.stderr, flush=True)
                self._stream_delta(self._shown_en_plain, cur_plain, is_provisional)
            else:
                # reword or new caption. A REWORD with a substantial common
                # prefix keeps the prefix on screen and streams the divergent
                # suffix (the MT self-corrected mid-draft — CL: non-appending
                # provisional); a genuinely new caption hard-swaps.
                cpl = _common_prefix_len(self._shown_en_plain, cur_plain)
                if (cpl >= 8
                        and cpl >= len(self._shown_en_plain) * 0.35
                        and self._shown_en_plain.startswith(cur_plain[:cpl])):
                    self._append_stop.set()
                    self._streaming_active = False
                    attr = self._spans_to_attributed(
                        _truncate_spans(state.current, cpl))
                    self._set_attr(self._field_en, attr)
                    self._shown_en_plain = cur_plain[:cpl]
                    self._shown_en_final = False
                    self._stream_delta(self._shown_en_plain, cur_plain, is_provisional)
                else:
                    # new caption: hard-swap (just appear, no typing)
                    import os
                    if os.environ.get("OV_DEBUG"):
                        print(f"[ov] hard-swap: {self._shown_en_plain!r} -> {cur_plain!r} (is_prov={is_provisional})", file=sys.stderr, flush=True)
                    self._append_stop.set()
                    self._streaming_active = False
                    attr = self._spans_to_attributed(state.current)
                    self._set_attr(self._field_en, attr)
                    self._shown_en_plain = cur_plain
                    self._shown_en_final = not is_provisional
        elif (cur_plain and not is_provisional
              and not getattr(self, "_shown_en_final", False)):
            # same text, provisional → final: flip to bright IN PLACE (no retype)
            # — the commit signal is the style change alone
            attr = self._spans_to_attributed(state.current)
            if attr is not None:
                self._set_attr(self._field_en, attr)
            self._shown_en_final = True

        # Prev row: hard-swap (no streaming — it's history)
        prev_attr = self._spans_to_attributed(state.prev) if state.prev else None
        if prev_attr is not None:
            self._set_attr(self._field_en_prev, prev_attr)
        elif not state.prev and self._field_en_prev is not None:
            self._set(self._field_en_prev, "")

        # src row: rendered from the model state (single writer, change-
        # detected). committed prefix stable, rolling tail dim — same
        # two-tone grammar as the EN row. The committed length is the reading
        # buffer's (the model carries one plain partial string: it renders
        # text, the view owns the two-tone split).
        if self._field_partial is not None:
            n = max(0, min(len(self._src.committed), len(state.partial)))
            self._set_src(state.partial[:n], state.partial[n:])

    def _set_src(self, committed: str, tail: str) -> None:
        """Render the source reading buffer with the committed/provisional split.
        Single font, color-only distinction (dim = provisional, bright =
        committed): mixed fonts reflow the line on every tail update — a
        flicker source. Change-detected: identical content never re-renders.
        Growth types out (CJK char pairs / Latin words); shrink or rewrite
        (commit, promote, hypothesis revision) hard-swaps."""
        if self._overlay_mode == "target" or self._field_partial is None:
            return
        key = (committed, tail)
        if key == getattr(self, "_last_src_key", None):
            return
        full = committed + tail
        prev_full = getattr(self, "_last_src_full", "")
        if (AppKit is not None and getattr(self, "_src_streaming", False)
                and getattr(self, "_src_streaming_target", None) == full):
            return  # a reveal thread is already typing toward this text
        if (prev_full and full.startswith(prev_full)
                and len(full) > len(prev_full)):
            # extends: type the appended units instead of snapping them in
            self._src_last_committed = committed
            self._stream_src_delta(full)
            return
        # reword (the hypothesis re-decoded): keep the common prefix on screen
        # and type the divergent suffix — same grammar as the EN row. Only when
        # the committed part is unchanged (the boundary text is stable).
        # reword (the hypothesis re-decoded): keep the common prefix on screen
        # and type the divergent suffix — same grammar as the EN row. The
        # committed part must be preserved (cpl >= committed) — EXCEPT for a
        # small boundary divergence (a premature tail terminator, e.g. the
        # hypothesis guessed '来进行。' and the commit continues '来进行口腔
        # 手术。'): allow the shown text to lose <= 2 boundary chars and still
        # type, otherwise every mid-sentence commit snaps (CL: typing only on
        # one sentence).
        _prev_full_eff = prev_full
        if prev_full and full:
            cpl = 0
            m = min(len(prev_full), len(full))
            while cpl < m and prev_full[cpl] == full[cpl]:
                cpl += 1
            boundary_stable = (cpl >= len(committed)
                               or (len(full) > len(prev_full)
                                   and cpl >= len(prev_full) - 2))
            if cpl >= 2 and boundary_stable and cpl != len(full):
                self._src_last_committed = committed
                self._src_streaming_target = ""
                self._src_streaming = False
                self._last_src_full = full[:cpl]
                self._last_src_key = (full[:len(committed)], full[len(committed):cpl])
                self._render_src_text(full[:cpl], len(committed))
                self._stream_src_delta(full)
                return
        # rewrite / shrink / first show: hard-swap (no typing)
        self._src_stop.set()
        self._src_streaming = False
        self._last_src_key = key
        self._last_src_full = full
        if AppKit is None:
            self._set(self._field_partial, full)
            return
        font = AppKit.NSFont.systemFontOfSize_weight_(19, AppKit.NSFontWeightRegular)
        # the attributed string must carry the field's paragraph style — without
        # it the text falls back to left alignment (make_field centers)
        para = AppKit.NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(AppKit.NSCenterTextAlignment)
        stable = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.85, 1.0)
        dim = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.5, 1.0)
        mut = AppKit.NSMutableAttributedString.alloc().init()
        if committed:
            mut.appendAttributedString_(
                AppKit.NSAttributedString.alloc().initWithString_attributes_(
                    committed, {"NSFont": font, "NSColor": stable, "NSParagraphStyle": para}))
        if tail:
            mut.appendAttributedString_(
                AppKit.NSAttributedString.alloc().initWithString_attributes_(
                    tail, {"NSFont": font, "NSColor": dim, "NSParagraphStyle": para}))
        self._field_partial.performSelectorOnMainThread_withObject_waitUntilDone_(
            "setAttributedStringValue:", mut, False)

    # ---- callback contract (source text in, display text to the model) ----
    def partial(self, label: str, text: str) -> None:
        # New rolling words arrive. If the buffer holds a COMPLETED sentence,
        # it floats up to the zh history field now — the float happens when
        # new words need the line, not at commit. The src ROW is rendered by
        # the drainer (_reconcile) from the model state — single writer.
        display = self._src.tail(text)
        promoted = self._src.consume_promotion()
        if promoted is not None and self._overlay_mode != "target":
            self._set(self._field_zh, promoted)
        self._model.set_partial(display)

    def final(self, label: str, segments: list) -> None:
        # The committed clause accumulates into the reading buffer (append);
        # a sentence-final terminator freezes the buffer. The zh history field
        # keeps the PREVIOUS sentence — no duplicate rows. The tail the commit
        # did not absorb stays on screen — the display text must not change at
        # commit time (CL: flickering prefix at every mid-sentence commit).
        self._src.commit(_segments_text(segments))
        self._model.set_partial(self._src.display)

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

    def _render_src_text(self, text: str, committed_len: int) -> None:
        """Two-tone render of the src row: committed bright, rest dim."""
        if AppKit is None:
            self._set(self._field_partial, text)
            return
        font = AppKit.NSFont.systemFontOfSize_weight_(19, AppKit.NSFontWeightRegular)
        para = AppKit.NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(AppKit.NSCenterTextAlignment)
        stable = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.85, 1.0)
        dim = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.5, 1.0)
        mut = AppKit.NSMutableAttributedString.alloc().init()
        n = min(committed_len, len(text))
        if n:
            mut.appendAttributedString_(
                AppKit.NSAttributedString.alloc().initWithString_attributes_(
                    text[:n], {"NSFont": font, "NSColor": stable, "NSParagraphStyle": para}))
        if len(text) > n:
            mut.appendAttributedString_(
                AppKit.NSAttributedString.alloc().initWithString_attributes_(
                    text[n:], {"NSFont": font, "NSColor": dim, "NSParagraphStyle": para}))
        self._field_partial.performSelectorOnMainThread_withObject_waitUntilDone_(
            "setAttributedStringValue:", mut, False)

    def _stream_src_delta(self, target: str) -> None:
        """Type the src row's appended units (CJK char pairs / Latin words) —
        the same typing grammar as the EN row, applied to the ASR reading
        buffer. Cancels a stale reveal thread; the drainer's guard
        (_src_streaming_target) prevents tick-restarts."""
        from whisperlivekit.inline_diff import _DIFF_TOKEN_RE
        prev = getattr(self, "_last_src_full", "")
        committed_len = len(getattr(self, "_src_last_committed", "") or "")
        delta = target[len(prev):] if prev and target.startswith(prev) else target
        self._src_stop.set()
        self._src_stop = threading.Event()
        stop = self._src_stop
        self._src_streaming_target = target
        self._src_streaming = True
        def _stream(prev=prev, delta=delta, stop=stop, target=target,
                    committed_len=committed_len):
            import time as _t
            cur = prev
            units = _merge_cjk_pairs(_DIFF_TOKEN_RE.findall(delta))
            n_units = max(1, len(units))
            step = min(0.08, 1.8 / n_units)
            for w in units:
                if stop.is_set():
                    self._src_streaming = False
                    return
                needs_space = (cur and w and not w.startswith(" ")
                              and not cur.endswith(" ")
                              and not _is_cjk(w[0]) and not _is_cjk(cur[-1]))
                cur = (cur + " " + w) if needs_space else (cur + w)
                self._last_src_full = cur
                self._last_src_key = (cur[:committed_len], cur[committed_len:])
                self._render_src_text(cur, committed_len)
                _t.sleep(step)
            self._src_streaming = False
        threading.Thread(target=_stream, daemon=True, name="ov-src-type").start()

    def _stream_delta(self, shown: str, target: str, is_provisional: bool) -> None:
        """Stream from `shown` to `target` word-by-word at 0.05s intervals via a
        daemon thread. Cancels any stale streaming thread first. Updates
        _shown_en_plain incrementally so the next tick's check sees the growth.

        Tokenization is CJK-aware: each CJK char is its own token, Latin runs
        stay whole (reuses inline_diff._DIFF_TOKEN_RE so the streaming units
        match the diff units)."""
        # Don't re-trigger if already streaming toward the same target — the
        # drainer ticks at 100ms and would restart the streaming every tick,
        # creating a stuttering char-by-char effect.
        if self._streaming_active and self._streaming_target == target:
            return
        from whisperlivekit.inline_diff import _DIFF_TOKEN_RE
        delta = target[len(shown):] if shown and target.startswith(shown) else target
        self._append_stop.set()
        self._append_stop = threading.Event()
        stop = self._append_stop
        is_prov = is_provisional
        self._streaming_target = target
        self._streaming_active = True
        def _stream(shown=shown, delta=delta, stop=stop, is_prov=is_prov, target=target):
            import time as _t
            cur = shown if (shown and target.startswith(shown)) else ""
            if not target.startswith(shown):
                self._set(self._field_en, "")
            tokens = _DIFF_TOKEN_RE.findall(delta)
            words = _merge_cjk_pairs(tokens)
            # readable pacing: ~0.08s per unit for short deltas, total reveal
            # bounded at ~1.8s so a large single-event append still finishes
            # fast enough to track the speech (CL: a big append at 0.05s/unit
            # flashed by unreadably fast)
            n_units = max(1, len(words))
            step = min(0.08, 1.8 / n_units)
            for w in words:
                if stop.is_set():
                    self._streaming_active = False
                    return
                needs_space = (cur and w and not w.startswith(" ")
                              and not cur.endswith(" ")
                              and not _is_cjk(w[0]))
                cur = (cur + " " + w) if needs_space else (cur + w)
                self._shown_en_plain = cur
                attr = self._spans_to_attributed_simple(cur, is_prov)
                self._set_attr(self._field_en, attr)
                _t.sleep(step)
            self._streaming_active = False
        threading.Thread(target=_stream, daemon=True, name="ov-append").start()

    def _spans_to_attributed(self, spans: list) -> "AppKit.NSAttributedString | None":
        """Build a styled NSAttributedString from the model's DisplayState spans.
        Style → color: PROVISIONAL → dimmed, committed (FINAL_SAME and FINAL_ADD
        alike) → white. The overlay's only visual grammar is dim = provisional,
        bright = committed — no diff coloring (the draft already grew by
        append; green deltas were noise). Returns None for empty spans."""
        if not spans:
            return None
        if AppKit is None:
            return None
        font = AppKit.NSFont.systemFontOfSize_weight_(42, AppKit.NSFontWeightBold)
        para = AppKit.NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(AppKit.NSCenterTextAlignment)
        white = AppKit.NSColor.whiteColor()
        dimmed = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.55, 1.0)
        mut = AppKit.NSMutableAttributedString.alloc().init()
        for sp in spans:
            if sp.style == PROVISIONAL:
                color = dimmed
            else:  # FINAL_SAME, FINAL_ADD — committed is committed: bright
                color = white
            attrs = {"NSFont": font, "NSColor": color, "NSParagraphStyle": para}
            mut.appendAttributedString_(
                AppKit.NSAttributedString.alloc().initWithString_attributes_(sp.text, attrs)
            )
        return mut

    def _spans_to_attributed_simple(self, text: str, is_provisional: bool) -> "AppKit.NSAttributedString":
        """Build a single-style attributed string for the streaming thread (plain
        text, one color: dimmed for provisional, white for final)."""
        if AppKit is None:
            return None
        font = AppKit.NSFont.systemFontOfSize_weight_(42, AppKit.NSFontWeightBold)
        para = AppKit.NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(AppKit.NSCenterTextAlignment)
        color = (AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.55, 1.0)
                 if is_provisional else AppKit.NSColor.whiteColor())
        attrs = {"NSFont": font, "NSColor": color, "NSParagraphStyle": para}
        return AppKit.NSAttributedString.alloc().initWithString_attributes_(text, attrs)

    def _set_attr(self, field: AppKit.NSTextField | None, attr) -> None:
        """Update a field with an attributed string on the MAIN thread."""
        if field is None or attr is None:
            return
        field.performSelectorOnMainThread_withObject_waitUntilDone_(
            "setAttributedStringValue:", attr, False
        )
