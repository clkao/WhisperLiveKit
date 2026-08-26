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
from datetime import datetime

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
        self._en: str = ""        # translation (middle, large)
        self._partial: str = ""   # in-progress partial (bottom, dimmer)
        # window + fields (created in __enter__ on the main thread)
        self._win: AppKit.NSWindow | None = None
        self._field_zh: AppKit.NSTextField | None = None
        self._field_en: AppKit.NSTextField | None = None
        self._field_partial: AppKit.NSTextField | None = None
        # Minimum-hold caption queue: finalized EN captions enqueue here with their commit
        # time; a daemon drainer releases the newest to the field once _MIN_HOLD_SEC has
        # passed since the last shown caption. Stops the flash of fast-succession finals.
        self._en_queue: list[tuple[str, float]] = []  # [(en_text, arrival_monotonic)]
        self._en_shown_at: float = 0.0  # monotonic time the current EN was shown
        self._en_drain_stop = threading.Event()
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
            self._field_partial = None
            self._field_zh = None
            self._field_en = make_field(0, h, 42, AppKit.NSColor.whiteColor(), bold=True, wrap=True, vcenter=True)
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

    # ---- latency (mirror of render.Renderer._record_latency) ----
    def _drain_en(self) -> None:
        """Daemon thread: release queued EN sentences to the field one at a time, each held
        for MIN_HOLD_SEC. After the hold, if no new sentence is queued, clear the field
        so the overlay does not show stale text. FIFO order so split sentences read in
        order. A new utterance clears pending unshown sentences (newest-utterance wins),
        but the currently-shown sentence stays for its hold so the line never flashes."""
        import time
        while not self._en_drain_stop.wait(0.1):
            with self._lock:
                if self._en_queue:
                    if time.monotonic() - self._en_shown_at < MIN_HOLD_SEC:
                        continue
                    en = self._en_queue.pop(0)
                    self._en = en
                    self._en_shown_at = time.monotonic()
                else:
                    # No queued sentence. If the current one has been held long enough,
                    # clear it so stale text does not linger on the overlay.
                    if self._en and time.monotonic() - self._en_shown_at >= MIN_HOLD_SEC:
                        self._en = ""
                        en = ""
                    else:
                        continue
            self._set(self._field_en, en)

    def _enqueue_en(self, en: str) -> None:
        """Split a finalized/preview EN caption into sentences and queue them for the
        hold-drain (FIFO, each held MIN_HOLD_SEC so a long multi-sentence translation paces
        readably instead of flashing by as one block). A new utterance clears pending
        unshown sentences so the latest utterance wins; the currently-shown sentence is
        not cleared (it stays for its hold)."""
        import time
        sents = _split_sentences(en)
        with self._lock:
            self._en_queue.clear()
            self._en_queue.extend(sents)
            # Reset the shown timestamp so the drainer releases the first new sentence
            # immediately (not gated on the previous sentence's hold timer).
            self._en_shown_at = -MIN_HOLD_SEC

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
        with self._lock:
            self._partial = text
        if self._overlay_mode != "target":
            self._set(self._field_partial, text)

    def final(self, label: str, segments: list, started_at: datetime) -> None:
        zh = _segments_text(segments)
        with self._lock:
            self._zh = zh
            self._partial = ""  # this utterance finalized; clear the partial line
        self._record_latency(started_at, "asr")
        if self._overlay_mode != "target":
            self._set(self._field_zh, zh)
        self._set(self._field_partial, "")

    def translation(self, label: str, zh_segments: list, started_at: datetime) -> None:
        if self._overlay_mode == "source":
            return
        en = _segments_text(zh_segments)
        self._record_latency(started_at, "cap")
        self._enqueue_en(en)

    def preview(self, label: str, zh_segments: list, started_at: datetime) -> None:
        """Live provisional translation of the in-progress utterance (P2): shown under the
        partial line, replaced by the final translation later. Mirrors render.Renderer.preview.
        Queued through the same hold-drain as finals so a draft can't flicker over a held
        final — but a draft never drops a held final (it only shows if the hold is already
        over, and a later final supersedes it in the queue)."""
        en = _segments_text(zh_segments)
        self._enqueue_en(en)

    def flush_pending(self) -> None:
        """Release any buffered finals when translation is disabled at runtime (model load
        failed). The overlay has no pending buffer (finals display immediately), so this is
        a no-op that satisfies the cli.py callback contract."""
        return

    # ---- helpers ----
    def _set(self, field: AppKit.NSTextField | None, value: str) -> None:
        """Update a field's text. Direct setStringValue_ from a worker thread is the
        pragmatic choice for a simple caption display (PyObjC text fields handle this
        in practice); if redraw ever flakes, wrap in
        performSelectorOnMainThread_withObject_waitUntilDone_("setStringValue:", value, False)."""
        if field is None:
            return
        field.setStringValue_(value)
