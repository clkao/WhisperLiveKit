"""Borderless always-on-top caption overlay (PyObjC / AppKit).

An OverlayRenderer implements the same callback contract as render.Renderer
(partial / final / translation) but sinks to a transparent borderless NSWindow
that floats over the screen instead of the terminal. The whole
ASR + MT pipeline; this file only owns the display.

Design:
- One NSWindow, borderless, transparent, ignores mouse, level = .statusBar (above
  the main menu), collectionBehavior includes .canJoinAllSpaces + .stationary +
  .fullScreenAuxiliary so it can appear over a fullscreen Space (see
  scripts/test_overlay_fullscreen.py for the load-bearing fullscreen check).
- Three stacked NSTextFields: finalized zh (small, muted) + EN translation
  (large, white, bold) + live partial zh (small, italic, dimmer). Updates arrive
  from the ASR/MT worker threads; we mutate the fields under a lock.
- The AppKit run loop is pumped on a daemon thread (cli.py's main thread is
  blocked on stop_event.wait); NSApplication + window are created on the main
  thread in __enter__ (a PyObjC requirement). Activation policy = accessory so no
  dock icon appears and Keynote keeps focus.
- Latency (asr/cap EWMA) is printed to stderr on each final/translation so the
  launching terminal shows it even though the terminal Renderer is not in use.

Fullscreen caveat: if the overlay does NOT appear over true-fullscreen Keynote,
bump OVERLAY_LEVEL (try a high raw NSInteger above NSMainMenuWindowLevel, e.g.
2147483623). See scripts/test_overlay_fullscreen.py.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from datetime import datetime

from whisperlivekit.overlay_model import PROVISIONAL, FINAL_SAME, FINAL_ADD

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
# final. Tunable at runtime via --overlay-hold (cli.py mutates this before construction).
MIN_HOLD_SEC = 3.5

# Split a caption into readable sentences so a long multi-sentence translation paces as
# separate held lines instead of flashing by as one wall of text. Handles both Latin
# (.!?) and CJK (。！？) terminators; a no-punctuation caption stays one unit.
_SENT_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")

# CJK range for tokenization (mirrors inline_diff._CJK subset).
_CJK_CHARS = set("　-〿㐀-翿一-鿿豈-﫿＀-￯")


def _is_cjk(ch: str) -> bool:
    return ch in _CJK_CHARS


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


def _split_sentences(text: str) -> list[str]:
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    return sents or [text]

# Flattening helper (mirrors render._segments_text): drop the diff spans, keep
# inline [S1]/[S2] speaker markers so multi-speaker utterances still read right.
def _segments_text(segments: list) -> str:
    parts = []
    for seg in segments:
        speaker, text = seg[0], seg[1]
        parts.append(f"[S{speaker + 1}] {text}" if speaker is not None else text)
    return "  ".join(parts)


class OverlayRenderer:
    """Drop-in replacement for render.Renderer that displays captions in an overlay window."""

    def __init__(
        self,
        theme: str = "auto",
        show_mem: bool = False,
        translate: bool = True,
        suppress_mem_stderr: bool = False,
        overlay_mode: str = "both",
    ) -> None:
        self._translate = translate
        self._overlay_mode = overlay_mode  # "both" | "target" | "source"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pump_thread: threading.Thread | None = None
        # optional MLX unified-memory readout to stderr (mirrors render.Renderer._mem_line).
        # The overlay window has no status line, so --mem prints MLX active/cache/peak + asr/cap
        # to the launching terminal on a 1s timer (same contract as the terminal renderer).
        self._show_mem = show_mem
        # When the overlay co-exists with the terminal TUI (MultiRenderer), the TUI's
        # bottom status line already shows MLX mem; the overlay's stderr print would spam
        # new lines into the terminal. Suppress the stderr print in that mode.
        self._suppress_mem_stderr = suppress_mem_stderr
        self._mx = None
        self._mem_stop = threading.Event()
        self._mem_thread: threading.Thread | None = None
        # latency EWMA (same semantics as render.Renderer): experienced lag from
        # utterance start to callback arrival. Printed to stderr, not the window.
        self._lat_asr: float | None = None
        self._lat_cap: float | None = None
        self._lat_alpha = 0.3
        # current displayed state
        self._zh: str = ""        # finalized source (top, small)
        self._en: str = ""        # last finalized translation text (legacy, display is model-driven)
        self._partial: str = ""   # in-progress partial (bottom, dimmer)
        # window + fields (created in __enter__ on the main thread)
        self._win: AppKit.NSWindow | None = None
        self._field_zh: AppKit.NSTextField | None = None
        self._field_en: AppKit.NSTextField | None = None
        self._field_en_prev: AppKit.NSTextField | None = None  # two-row target mode only
        self._field_partial: AppKit.NSTextField | None = None
        # Display model: the pure, AppKit-free state machine (hold-drain, provisional
        # -> final replacement, scroll-up-to-history, expiry) in overlay_model.py. The
        # renderer feeds events in; the drainer ticks the model and this view
        # reconciles the returned DisplayState onto the NSTextFields. Tests drive the
        # model directly with a fake clock (tests/test_overlay_model.py).
        from whisperlivekit.overlay_model import OverlayDisplayModel
        self._model = OverlayDisplayModel(hold_sec=MIN_HOLD_SEC)
        self._event_log = None  # optional OverlayEventLog for replay/tuning
        self._en_drain_stop = threading.Event()
        self._append_stop = threading.Event()  # cancels a stale streaming thread
        self._shown_en_plain: str = ""  # plain text currently rendered on the current row
        self._en_drain_thread: threading.Thread | None = None

    # ---- lifecycle (context manager, same shape as render.Renderer) ----
    def __enter__(self) -> "OverlayRenderer":
        self._create_window()
        # AppKit's run loop MUST run on the main thread for the window to display and
        # redraw. cli.py's main thread later calls renderer.run_until(stop_event) (in place
        # of stop_event.wait()), which pumps the AppKit loop on the main thread via a
        # Python-controlled loop — so SIGINT's handler actually gets control and Ctrl-C
        # exits reliably (a native app.run() would swallow SIGINT).
        self._en_drain_thread = threading.Thread(
            target=self._drain_en, daemon=True, name="en-hold-drain"
        )
        self._en_drain_thread.start()
        if self._show_mem:
            try:
                import mlx.core as mx

                self._mx = mx
            except Exception:  # noqa: BLE001 -- mlx optional; --mem degrades to latency-only
                self._mx = None
            self._mem_thread = threading.Thread(
                target=self._mem_loop, daemon=True, name="overlay-mem"
            )
            self._mem_thread.start()
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self._stop.set()
        self._en_drain_stop.set()
        self._mem_stop.set()
        if self._en_drain_thread is not None:
            self._en_drain_thread.join(timeout=2)
        if self._mem_thread is not None:
            self._mem_thread.join(timeout=2)
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
        """Daemon thread: tick the display model on a 100ms cadence and reconcile the
        returned DisplayState onto the AppKit fields. All hold/expiry/scroll-up policy
        lives in the model (overlay_model.py, unit-tested); this thread only moves
        state to the screen."""
        while not self._en_drain_stop.wait(0.1):
            state = self._model.tick()
            if state is not None:
                self._reconcile(state)

    def _reconcile(self, state) -> None:
        """Apply a DisplayState to the fields. The streaming effect lives HERE (the
        view), not in the model: when the new current text EXTENDS what's already
        rendered, reveal the delta word-by-word with a micro-delay (perceived
        continuity); on a rewrite or first show, hard-swap to the latest.

        The model handles hold/scroll/expiry/queue logic; the view handles the
        visual animation. All AppKit updates are dispatched to the main thread."""
        cur_plain = "".join(sp.text for sp in state.current)
        prev_plain = "".join(s.text for s in state.prev)
        is_provisional = bool(state.current) and state.current[0].style == PROVISIONAL

        # Current row: stream on extends, stream-from-empty on new caption
        if cur_plain != self._shown_en_plain:
            if not cur_plain:
                self._set(self._field_en, "")
                self._shown_en_plain = ""
            elif (self._shown_en_plain and cur_plain.startswith(self._shown_en_plain)
                  and len(cur_plain) > len(self._shown_en_plain)):
                # extends: stream the delta word-by-word
                import os
                if os.environ.get("OV_DEBUG"):
                    print(f"[ov] extends: {self._shown_en_plain!r} -> {cur_plain!r} delta={cur_plain[len(self._shown_en_plain):]!r}", file=sys.stderr, flush=True)
                self._stream_delta(self._shown_en_plain, cur_plain, is_provisional)
            else:
                # new caption or rewrite: clear + stream the whole text word-by-word
                import os
                if os.environ.get("OV_DEBUG"):
                    print(f"[ov] stream-new: {self._shown_en_plain!r} -> {cur_plain!r} (is_prov={is_provisional})", file=sys.stderr, flush=True)
                self._stream_delta("", cur_plain, is_provisional)

        # Prev row: hard-swap (no streaming — it's history)
        prev_attr = self._spans_to_attributed(state.prev) if state.prev else None
        if prev_attr is not None:
            self._set_attr(self._field_en_prev, prev_attr)
        elif not state.prev and self._field_en_prev is not None:
            self._set(self._field_en_prev, "")

        if state.partial is not None and self._field_partial is not None:
            self._set(self._field_partial, state.partial)

    # ---- latency (mirror of render.Renderer._record_latency) ----
    def _record_latency(self, started_at: datetime, which: str) -> None:
        lat = (datetime.now() - started_at).total_seconds()
        attr = "_lat_asr" if which == "asr" else "_lat_cap"
        prev = getattr(self, attr)
        setattr(self, attr, lat if prev is None else prev + self._lat_alpha * (lat - prev))
        # The _mem_loop thread prints the EWMA line on a 1s timer; no per-event print
        # (that spammed stderr on every simul preview).

    def _mem_line(self) -> str:
        """One stderr status line: MLX unified-memory + caption latency. Mirrors
        render.Renderer._mem_line but emits to stderr (the overlay window has no status
        line of its own). Memory getters are lightweight counter reads needing no MLX_LOCK."""
        parts = []
        if self._mx is not None:
            g = 1 / 1e9
            parts.append(
                f"MLX  active {self._mx.get_active_memory() * g:.2f} GB"
                f" · cache {self._mx.get_cache_memory() * g:.2f} GB"
                f" · peak {self._mx.get_peak_memory() * g:.2f} GB"
            )
        if self._lat_asr is not None:
            parts.append(f"asr {self._lat_asr:.1f}s")
        if self._lat_cap is not None:
            parts.append(f"cap {self._lat_cap:.1f}s")
        return "  ·  ".join(parts)

    def _mem_loop(self) -> None:
        """Print the MLX+latency line to stderr on a 1s timer so it ticks during silence
        (latency updates only fire when a sentence lands). Mirrors render.Renderer._mem_loop.
        Suppressed when co-existing with the terminal TUI (suppress_mem_stderr)."""
        if self._suppress_mem_stderr:
            return
        while not self._mem_stop.wait(1.0):
            line = self._mem_line()
            if line:
                print(line, file=sys.stderr, flush=True)

    # ---- callback contract (same as render.Renderer) ----
    def partial(self, label: str, text: str, started_at: datetime, speaker: int | None = None) -> None:
        self._model.set_partial(text)
        if self._overlay_mode != "target":
            self._set(self._field_partial, text)

    def final(self, label: str, segments: list, started_at: datetime) -> None:
        zh = _segments_text(segments)
        with self._lock:
            self._zh = zh
        self._model.clear_partial()
        self._record_latency(started_at, "asr")
        if self._overlay_mode != "target":
            self._set(self._field_zh, zh)
        self._set(self._field_partial, "")

    def translation(self, label: str, zh_segments: list, started_at: datetime) -> None:
        if self._overlay_mode == "source":
            return
        if self._event_log is not None:
            self._event_log.record_final(zh_segments, started_at)
        self._record_latency(started_at, "cap")
        self._model.translation(zh_segments, started_at)

    def preview(self, label: str, zh_segments: list, started_at: datetime) -> None:
        """Live provisional translation of the in-progress utterance."""
        if self._overlay_mode == "source":
            return
        if self._event_log is not None:
            self._event_log.record_preview(zh_segments, started_at)
        self._model.preview(zh_segments, started_at)

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

    def _set_en(self, field: AppKit.NSTextField | None, value: str, *, preview: bool = False) -> None:
        """Update the EN field's text + color on the MAIN thread (plain-text fallback;
        the diff-aware path uses _set_attr + _spans_to_attributed)."""
        if field is None:
            return
        text = value
        if preview:
            import re
            text = re.sub(r"<[\|｜][^\|｜]*[\|｜]>", "", value).strip()
            color = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.6, 0.9)
        else:
            color = AppKit.NSColor.whiteColor()
        field.performSelectorOnMainThread_withObject_waitUntilDone_(
            "setTextColor:", color, False
        )
        field.performSelectorOnMainThread_withObject_waitUntilDone_(
            "setStringValue:", text, False
        )

    def _stream_delta(self, shown: str, target: str, is_provisional: bool) -> None:
        """Stream from `shown` to `target` word-by-word at 0.05s intervals via a
        daemon thread. Cancels any stale streaming thread first. Updates
        _shown_en_plain incrementally so the next tick's check sees the growth.

        Tokenization is CJK-aware: each CJK char is its own token, Latin runs
        stay whole (reuses inline_diff._DIFF_TOKEN_RE so the streaming units
        match the diff units)."""
        from whisperlivekit.inline_diff import _DIFF_TOKEN_RE
        delta = target[len(shown):] if shown and target.startswith(shown) else target
        self._append_stop.set()
        self._append_stop = threading.Event()
        stop = self._append_stop
        is_prov = is_provisional
        def _stream(shown=shown, delta=delta, stop=stop, is_prov=is_prov):
            import time as _t
            cur = shown if (shown and target.startswith(shown)) else ""
            if not target.startswith(shown):
                self._set(self._field_en, "")
            # CJK-aware tokenization: group CJK chars into pairs for readability
            tokens = _DIFF_TOKEN_RE.findall(delta)
            # Merge consecutive single CJK chars into pairs so the streaming
            # reveals 2 chars at a time (1 char at 0.05s is too slow to read).
            words = _merge_cjk_pairs(tokens)
            for w in words:
                if stop.is_set():
                    return
                # preserve spacing: if the token doesn't start with space and cur
                # doesn't end with space, add one (Latin); CJK tokens have no space.
                needs_space = (cur and w and not w.startswith(" ")
                              and not cur.endswith(" ")
                              and not _is_cjk(w[0]))
                cur = (cur + " " + w) if needs_space else (cur + w)
                self._shown_en_plain = cur
                attr = self._spans_to_attributed_simple(cur, is_prov)
                self._set_attr(self._field_en, attr)
                _t.sleep(0.05)
        threading.Thread(target=_stream, daemon=True, name="ov-append").start()

    def _spans_to_attributed(self, spans: list) -> "AppKit.NSAttributedString | None":
        """Build a styled NSAttributedString from the model's DisplayState spans.
        Style → color: PROVISIONAL → dimmed, FINAL_SAME → white, FINAL_ADD → green.
        Returns None for empty spans (the caller skips the field update)."""
        if not spans:
            return None
        if AppKit is None:
            return None
        font = AppKit.NSFont.systemFontOfSize_weight_(42, AppKit.NSFontWeightBold)
        para = AppKit.NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(AppKit.NSCenterTextAlignment)
        white = AppKit.NSColor.whiteColor()
        green = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.3, 0.85, 0.4, 1.0)
        dimmed = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.55, 1.0)
        mut = AppKit.NSMutableAttributedString.alloc().init()
        for sp in spans:
            if sp.style == FINAL_ADD:
                color = green
            elif sp.style == PROVISIONAL:
                color = dimmed
            else:  # FINAL_SAME or anything else
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
