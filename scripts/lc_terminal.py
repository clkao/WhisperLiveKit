#!/usr/bin/env python3
"""livecaption-equivalent tool on WhisperLiveKit — terminal OR native overlay.

In-process (no server, no WebSocket). Uses the two new backends:
  --backend mlx-qwen3-asr            (pure-MLX Qwen3-ASR, moona3k)
  --translation-backend mlx-llm-mt   (generic decoder-LLM MT via mlx-lm, in-process)

With --overlay: drives the native macOS caption window (always-on-top NSWindow,
ported from livecaption/overlay.py). The WLK asyncio loop runs in a worker
thread; the overlay NSWindow run loop runs on the main thread (pyobjc requires
this); the on_update callback marshals text to the overlay fields.

Without --overlay: prints to the terminal.

Ported from livecaption (livecaption/cli.py + livecaption/screen_ocr.py):
  --opencc / --opencc-mt     OpenCC text conversion (s2twp etc.)
  --ocr-display / --ocr-lang / --ocr-interval   Screen OCR hotword auto-refresh
  --hotwords                Static hotword list
  --vad-threshold / --vad-min-silence-ms        Silero VAD tuning
  --second-pass / --no-second-pass              Two-pass re-decode toggle
  --mem                     MLX memory readout (alias for --stats)
  --simultaneous            Simultaneous-MT variant (AlignAtt commit policy)

Usage:
    # terminal output:
    .venv/bin/python scripts/lc_terminal.py --audio /path/to/zh.wav

    # native overlay window:
    .venv/bin/python scripts/lc_terminal.py --audio /path/to/zh.wav --overlay

    # mic + overlay (needs a real terminal with mic TCC, e.g. Terminal.app):
    .venv/bin/python scripts/lc_terminal.py --source mic --overlay
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import time
from datetime import datetime

from whisperlivekit.test_harness import TestHarness


# ---------------------------------------------------------------------------
# OpenCC converter helpers
# ---------------------------------------------------------------------------

_TARGET_ZH_TW_CODES = {"zh-tw", "zh-hant", "zh-hk", "zh-mo"}


def _make_opencc(config_name):
    """Create an OpenCC converter, or None if the package is missing."""
    try:
        import opencc
        return opencc.OpenCC(config_name)
    except Exception as e:
        print(f"OpenCC '{config_name}' failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Engine kwargs builder
# ---------------------------------------------------------------------------

def _make_engine_kwargs(args) -> dict:
    kw = {
        "lan": args.language,
        "pcm_input": True,
        "backend": args.backend,
        "target_language": args.target_language,
        "translation_backend": "mlx-llm-mt",
        "mlx_llm_mt_model": args.mlx_llm_mt_model,
        # WLK defaults to 5s pause-segmentation (too long — utterances merge into
        # one growing line). The VAD fires short silence events (0.1-0.3s), so the
        # threshold must be low to split at natural speech pauses.
        "pause_segmentation_seconds": 0.1,
    }
    if args.backend == "mlx-qwen3-asr":
        kw["mlx_qwen3_asr_model"] = args.mlx_qwen3_asr_model
        # Hotwords: static --hotwords take priority; OCR loop updates the
        # recognizer's .hotwords live (via the ASR backend instance), but the
        # initial context comes from this kwarg.
        if args.hotwords:
            kw["mlx_qwen3_asr_context"] = args.hotwords
    elif args.backend == "qwen3-vllm-metal":
        kw["qwen3_vllm_metal_audio_backend"] = args.qwen3_vllm_metal_audio_backend
        kw["qwen3_vllm_metal_tower_checkpoint"] = args.qwen3_vllm_metal_tower_checkpoint
    # Two-pass toggle
    kw["mlx_qwen3_asr_second_pass"] = args.second_pass
    # VAD tuning (None = keep defaults)
    if args.vad_threshold is not None:
        kw["vad_threshold"] = args.vad_threshold
    if args.vad_min_silence_ms is not None:
        kw["vad_min_silence_ms"] = args.vad_min_silence_ms
    # Simultaneous MT
    if args.simultaneous:
        kw["mlx_llm_mt_simultaneous"] = True
    return kw


# ---------------------------------------------------------------------------
# Sinks (terminal + overlay)
# ---------------------------------------------------------------------------

class OverlaySink:
    """Drives the livecaption OverlayRenderer from WLK stream state.

    Maps WLK's per-update TestState -> overlay.partial / overlay.translation:
      buffer_transcription (live rolling ASR) -> overlay partial line
      lines[].translation (committed per-utterance MT)  -> overlay translation line
      lines[].text (committed clean ASR)               -> overlay finalized zh line
    """

    def __init__(self, renderer, opencc_conv=None, opencc_mt_conv=None, target_opencc=None):
        self._r = renderer
        self._last_final = ""
        self._last_transl = ""
        self._opencc = opencc_conv      # source-side converter (display)
        self._opencc_mt = opencc_mt_conv  # whether MT gets converted text
        self._target_opencc = target_opencc  # target-side converter (zh-tw output)

    def _cc_src(self, text):
        return self._opencc.convert(text) if (self._opencc and text) else text

    def _cc_target(self, text):
        return self._target_opencc.convert(text) if (self._target_opencc and text) else text

    def __call__(self, state):
        # live partial: the rolling ASR buffer (converted for display)
        partial = (state.buffer_transcription or "").strip()
        if partial:
            self._r.partial("", self._cc_src(partial), datetime.now())
        # committed lines: finalized zh + translation
        for line in state.lines:
            txt = (line.get("text") or "").strip()
            tr = (line.get("translation") or "").strip()
            if txt and txt != self._last_final:
                self._last_final = txt
                self._r.final("", [(None, self._cc_src(txt))], datetime.now())
            if tr and tr != self._last_transl:
                self._last_transl = tr
                self._r.translation("", [(None, self._cc_target(tr))], datetime.now())


class StatsTracker:
    """Live status line on stderr: ASR/MT latency EWMA, MLX memory, commit/emit counts.

    Prints one line per second using ``\r`` (carriage-return overwrite) so the status
    stays in place without scrolling the caption text above it.  Enabled by ``--stats``
    or ``--mem``; off by default (no output, no thread).
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        # MLX unified-memory readout (optional — degrades to latency-only if mlx absent)
        self._mx = None
        try:
            import mlx.core as mx
            self._mx = mx
        except Exception:  # noqa: BLE001
            self._mx = None
        # latency EWMA (exponential moving average, same semantics as overlay.py)
        self._lat_asr: float | None = None
        self._lat_mt: float | None = None
        self._lat_alpha = 0.3
        # utterance timing anchors (monotonic seconds)
        self._partial_started: float | None = None   # when current partial first appeared
        self._commit_time: float | None = None       # when last commit landed (for MT delta)
        # counters
        self._commits = 0
        self._emits = 0

    # ---- lifecycle ----
    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="stats")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            # clear the status line so the shell prompt lands on a fresh line
            print(file=sys.stderr, flush=True)

    # ---- hooks (called from the sink on each state update) ----
    def on_partial(self, _text: str) -> None:
        with self._lock:
            if self._partial_started is None:
                self._partial_started = time.monotonic()

    def on_commit(self) -> None:
        with self._lock:
            if self._partial_started is not None:
                lat = time.monotonic() - self._partial_started
                self._lat_asr = lat if self._lat_asr is None else self._lat_asr + self._lat_alpha * (lat - self._lat_asr)
                self._partial_started = None
            self._commit_time = time.monotonic()
            self._commits += 1

    def on_emit(self) -> None:
        with self._lock:
            if self._commit_time is not None:
                lat = time.monotonic() - self._commit_time
                self._lat_mt = lat if self._lat_mt is None else self._lat_mt + self._lat_alpha * (lat - self._lat_mt)
                self._commit_time = None
            self._emits += 1

    # ---- status line ----
    def _line(self) -> str:
        with self._lock:
            lat_asr = self._lat_asr
            lat_mt = self._lat_mt
            commits = self._commits
            emits = self._emits
        parts: list[str] = []
        if self._mx is not None:
            g = 1 / 1e9
            parts.append(
                f"MLX active {self._mx.get_active_memory() * g:.2f}G"
                f" cache {self._mx.get_cache_memory() * g:.2f}G"
                f" peak {self._mx.get_peak_memory() * g:.2f}G"
            )
        if lat_asr is not None:
            parts.append(f"asr {lat_asr:.2f}s")
        if lat_mt is not None:
            parts.append(f"mt {lat_mt:.2f}s")
        parts.append(f"commit {commits} emit {emits}")
        return " · ".join(parts)

    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            line = self._line()
            print(f"\r{line}", end="", flush=True, file=sys.stderr)


class TerminalSink:
    """Prints to the terminal. Tracks seen text/translation separately so a line's
    text prints once and its translation prints once (when it arrives).

    When *stats* is provided, records ASR/MT latency samples and commit/emit counts
    on each state update; the StatsTracker thread prints a live status line to stderr.

    When *opencc* is set, converts ASR text for display. When *target_opencc* is set,
    converts MT output for display (zh-tw family targets)."""

    def __init__(self, stats=None, opencc_conv=None, target_opencc=None):
        self._seen_text = set()
        self._seen_transl = set()
        self._lang = "en"
        self._stats = stats
        self._opencc = opencc_conv
        self._target_opencc = target_opencc

    def _cc_src(self, text):
        return self._opencc.convert(text) if (self._opencc and text) else text

    def _cc_target(self, text):
        return self._target_opencc.convert(text) if (self._target_opencc and text) else text

    def __call__(self, state):
        partial = (state.buffer_transcription or "").strip()
        if partial:
            if self._stats is not None:
                self._stats.on_partial(partial)
            print(f"\r[zh*] {self._cc_src(partial)[:100]}", end="", flush=True)
        for line in state.lines:
            txt = (line.get("text") or "").strip()
            tr = (line.get("translation") or "").strip()
            if txt and txt not in self._seen_text:
                self._seen_text.add(txt)
                if self._stats is not None:
                    self._stats.on_commit()
                print(f"\n[zh] {self._cc_src(txt)}")
            if tr and tr not in self._seen_transl:
                self._seen_transl.add(tr)
                if self._stats is not None:
                    self._stats.on_emit()
                print(f"[{self._lang}] {self._cc_target(tr)}")


# ---------------------------------------------------------------------------
# Screen OCR hotword auto-refresh
# ---------------------------------------------------------------------------

def _start_ocr_loop(args, engine):
    """Start the ScreenOcrLoop if --ocr-display is set. Returns the loop or None.

    The loop updates the ASR backend's .hotwords live (the ASR worker reads it
    at the next utterance onset, so the refresh lands at a sentence boundary).
    """
    if args.ocr_display is None:
        return None
    if args.backend != "mlx-qwen3-asr":
        print("[ocr] --ocr-display requires --backend mlx-qwen3-asr; skipping", file=sys.stderr)
        return None
    try:
        from whisperlivekit.screen_ocr import ScreenOcrLoop
    except ImportError as e:
        print(f"[ocr] screen_ocr import failed: {e}", file=sys.stderr)
        return None

    # Get the ASR backend instance from the engine; the loop writes .hotwords.
    asr = getattr(engine, "asr", None)
    if asr is None:
        print("[ocr] engine has no .asr; cannot wire OCR hotwords", file=sys.stderr)
        return None

    ocr_loop = ScreenOcrLoop(
        recognizer=asr,
        display_index=args.ocr_display,
        interval=args.ocr_interval,
        languages=[l.strip() for l in args.ocr_lang.split(",") if l.strip()],
        log=lambda m: print(m, file=sys.stderr),
    )
    ocr_loop.start()
    return ocr_loop


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

async def run_file(args, sink, ocr_loop=None):
    kwargs = _make_engine_kwargs(args)
    async with TestHarness(**kwargs) as h:
        h.on_update(sink)
        if ocr_loop is not None:
            _start_ocr_loop(args, h._processor._engine)
        await h.feed(args.audio, speed=1.0)
        await h.drain(8.0)
        await h.finish(timeout=180)


async def run_mic(args, sink, ocr_loop=None):
    import sounddevice as sd

    SAMPLE_RATE = 16000
    CHUNK = int(SAMPLE_RATE * 0.5)
    kwargs = _make_engine_kwargs(args)
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    def audio_cb(indata, frames, time_info, status):
        if stop.is_set():
            raise sd.CallbackStop
        pcm = (indata[:, 0] * 32767).astype("int16").tobytes()
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(h._processor.process_audio(pcm))
        )

    async with TestHarness(**kwargs) as h:
        h.on_update(sink)
        if ocr_loop is not None:
            _start_ocr_loop(args, h._processor._engine)
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                           blocksize=CHUNK, callback=audio_cb):
            print(f"Listening ({args.language} -> {args.target_language}). Ctrl-C to stop.",
                  flush=True)
            try:
                await stop.wait()
            except KeyboardInterrupt:
                stop.set()
        await h.drain(3.0)
        await h.finish(timeout=60)


def main() -> None:
    p = argparse.ArgumentParser(description="livecaption-equivalent on WLK (in-process)")
    p.add_argument("--audio", help="audio file path (file mode)")
    p.add_argument("--source", choices=["mic", "file"], default="file")
    p.add_argument("--language", default="zh")
    p.add_argument("--target-language", default="en")
    p.add_argument("--backend", choices=["mlx-qwen3-asr", "qwen3-vllm-metal"], default="mlx-qwen3-asr",
                   help="ASR backend: mlx-qwen3-asr (windowed, pure MLX) or qwen3-vllm-metal (causal, native MLX via the fork)")
    p.add_argument("--mlx-qwen3-asr-model", default="Qwen/Qwen3-ASR-0.6B")
    p.add_argument("--mlx-llm-mt-model", default="hy-mt2-1.8b-8bit")
    p.add_argument("--qwen3-vllm-metal-audio-backend", choices=["standard", "causal"], default="causal",
                   help="qwen3-vllm-metal audio backend: 'causal' (append-only KV, flat-cost) or 'standard' (re-encode window)")
    p.add_argument("--qwen3-vllm-metal-tower-checkpoint", default="qfuxa/qwen3-asr-0.6b-streaming",
                   help="tower checkpoint for the causal audio encoder")
    p.add_argument("--overlay", action="store_true",
                   help="display captions in a native always-on-top macOS overlay window")
    p.add_argument("--overlay-hold", type=float, default=3.5,
                   help="minimum seconds a finalized EN caption stays before replacement")

    # --- OpenCC ---
    p.add_argument("--opencc", default=None, metavar="CONFIG",
                   help="Convert ASR text via OpenCC before display (e.g. s2twp for Simplified→Taiwan Traditional). "
                        "Values: s2t, s2twp, s2hk, t2s, tw2s, tw2sp, ...")
    p.add_argument("--opencc-mt", action="store_true", default=False,
                   help="Also feed OpenCC-converted text to MT (default off: MT gets raw ASR text, display gets converted)")

    # --- Screen OCR ---
    p.add_argument("--ocr-display", type=int, default=None, metavar="N",
                   help="Capture display N, Vision OCR, extract hotwords, feed to ASR recognizer (mlx-qwen3-asr only)")
    p.add_argument("--ocr-lang", default="zh-Hant",
                   help="Vision recognition language(s), comma-separated (default zh-Hant)")
    p.add_argument("--ocr-interval", type=float, default=5.0,
                   help="Screen capture interval in seconds (default 5.0)")

    # --- Hotwords ---
    p.add_argument("--hotwords", default="", metavar="TERMS",
                   help="Static hotword list (comma-separated) for ASR biasing (mlx-qwen3-asr only)")

    # --- VAD tuning ---
    p.add_argument("--vad-threshold", type=float, default=None,
                   help="Silero speech-probability threshold (default 0.5; 0.6 safe, 0.7 aggressive)")
    p.add_argument("--vad-min-silence-ms", type=int, default=None,
                   help="Trailing silence (ms) to wait before separating speech (default 100)")

    # --- Two-pass toggle ---
    p.add_argument("--second-pass", action=argparse.BooleanOptionalAction, default=True,
                   help="Re-decode the whole utterance offline at finalization for accuracy (default on; --no-second-pass trades accuracy for latency)")

    # --- Stats / Memory ---
    p.add_argument("--stats", action="store_true",
                   help="print a live status line (ASR/MT latency, MLX memory, commit/emit counts) to stderr")
    p.add_argument("--mem", action="store_true",
                   help="alias for --stats (MLX memory readout + latency EWMA)")

    # --- Simultaneous MT ---
    p.add_argument("--simultaneous", action="store_true", default=False,
                   help="Use the simultaneous-MT variant (AlignAtt commit policy, calibrated zh→en Hunyuan heads)")

    args = p.parse_args()

    if args.source == "file" and not args.audio:
        p.error("--audio is required for --source file")

    # --mem is an alias for --stats
    show_stats = args.stats or args.mem

    # OpenCC converters
    opencc_conv = None
    target_opencc = None
    if args.opencc is not None:
        opencc_conv = _make_opencc(args.opencc)
        if opencc_conv is None:
            sys.exit(1)
        # Target-side OpenCC: when target language is zh-tw family, auto-apply s2twp
        if args.target_language.lower() in _TARGET_ZH_TW_CODES:
            target_opencc = _make_opencc("s2twp")
            if target_opencc:
                print("OpenCC s2twp on target (zh-tw): MT output -> Taiwan Traditional", file=sys.stderr)

    # Pre-create OCR loop placeholder (started after engine init)
    ocr_loop = True if args.ocr_display is not None else None

    if not args.overlay:
        # terminal mode: simple async run
        stats = StatsTracker() if show_stats else None
        if stats is not None:
            stats.start()
        sink = TerminalSink(stats=stats, opencc_conv=opencc_conv, target_opencc=target_opencc)
        coro = run_file(args, sink, ocr_loop) if args.source == "file" else run_mic(args, sink, ocr_loop)
        try:
            asyncio.run(coro)
        finally:
            if stats is not None:
                stats.stop()
        return

    # overlay mode: NSWindow run loop must be on the main thread.
    # Run the WLK asyncio loop in a worker thread; drive the overlay from it.
    import whisperlivekit.overlay as _ov
    _ov.MIN_HOLD_SEC = args.overlay_hold
    from whisperlivekit.overlay import OverlayRenderer

    renderer = OverlayRenderer(theme="auto", show_mem=False, translate=True)
    sink = OverlaySink(renderer, opencc_conv=opencc_conv, target_opencc=target_opencc)

    coro = run_file(args, sink, ocr_loop) if args.source == "file" else run_mic(args, sink, ocr_loop)
    stop_event = threading.Event()
    worker_error: list = []

    def worker():
        try:
            asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001
            worker_error.append(exc)
        finally:
            stop_event.set()

    with renderer:  # creates the NSWindow on the main thread
        t = threading.Thread(target=worker, daemon=True, name="wlk-asr")
        t.start()
        try:
            renderer.run_until(stop_event)  # blocks on the main thread
        except KeyboardInterrupt:
            stop_event.set()
        t.join(timeout=5)
    if worker_error:
        raise worker_error[0]


if __name__ == "__main__":
    main()
