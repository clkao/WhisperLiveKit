#!/usr/bin/env python3
"""livecaption-equivalent tool on WhisperLiveKit — terminal OR native overlay.

In-process (no server, no WebSocket). Uses the two new backends:
  --backend mlx-qwen3-asr            (pure-MLX Qwen3-ASR, moona3k)
  --translation-backend hunyuan-mlx  (Tencent Hy-MT2 via mlx-lm, in-process)

With --overlay: drives the native macOS caption window (always-on-top NSWindow,
ported from livecaption/overlay.py). The WLK asyncio loop runs in a worker
thread; the overlay NSWindow run loop runs on the main thread (pyobjc requires
this); the on_update callback marshals text to the overlay fields.

Without --overlay: prints to the terminal.

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
import threading
import time
from datetime import datetime

from whisperlivekit.test_harness import TestHarness


def _make_engine_kwargs(args) -> dict:
    return {
        "lan": args.language,
        "pcm_input": True,
        "backend": "mlx-qwen3-asr",
        "mlx_qwen3_asr_model": args.mlx_qwen3_asr_model,
        "target_language": args.target_language,
        "translation_backend": "hunyuan-mlx",
        "hunyuan_mlx_model": args.hunyuan_mlx_model,
        # WLK defaults to 5s pause-segmentation (too long — utterances merge into
        # one growing line). The VAD fires short silence events (0.1-0.3s), so the
        # threshold must be low to split at natural speech pauses.
        "pause_segmentation_seconds": 0.1,
    }


class OverlaySink:
    """Drives the livecaption OverlayRenderer from WLK stream state.

    Maps WLK's per-update TestState -> overlay.partial / overlay.translation:
      buffer_transcription (live rolling ASR) -> overlay partial line
      lines[].translation (committed per-utterance MT)  -> overlay translation line
      lines[].text (committed clean ASR)               -> overlay finalized zh line
    """

    def __init__(self, renderer):
        self._r = renderer
        self._last_final = ""
        self._last_transl = ""

    def __call__(self, state):
        # live partial: the rolling ASR buffer
        partial = (state.buffer_transcription or "").strip()
        if partial:
            self._r.partial("", partial, datetime.now())
        # committed lines: finalized zh + translation
        for line in state.lines:
            txt = (line.get("text") or "").strip()
            tr = (line.get("translation") or "").strip()
            if txt and txt != self._last_final:
                self._last_final = txt
                self._r.final("", [(None, txt)], datetime.now())
            if tr and tr != self._last_transl:
                self._last_transl = tr
                self._r.translation("", [(None, tr)], datetime.now())


class TerminalSink:
    """Prints to the terminal. Tracks seen text/translation separately so a line's
    text prints once and its translation prints once (when it arrives)."""

    def __init__(self):
        self._seen_text = set()
        self._seen_transl = set()
        self._lang = "en"

    def __call__(self, state):
        partial = (state.buffer_transcription or "").strip()
        if partial:
            print(f"\r[zh*] {partial[:100]}", end="", flush=True)
        for line in state.lines:
            txt = (line.get("text") or "").strip()
            tr = (line.get("translation") or "").strip()
            if txt and txt not in self._seen_text:
                self._seen_text.add(txt)
                print(f"\n[zh] {txt}")
            if tr and tr not in self._seen_transl:
                self._seen_transl.add(tr)
                print(f"[{self._lang}] {tr}")


async def run_file(args, sink):
    kwargs = _make_engine_kwargs(args)
    async with TestHarness(**kwargs) as h:
        h.on_update(sink)
        await h.feed(args.audio, speed=1.0)
        await h.drain(8.0)
        await h.finish(timeout=180)


async def run_mic(args, sink):
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
    p.add_argument("--mlx-qwen3-asr-model", default="Qwen/Qwen3-ASR-0.6B")
    p.add_argument("--hunyuan-mlx-model", default="hy-mt2-1.8b-8bit")
    p.add_argument("--overlay", action="store_true",
                   help="display captions in a native always-on-top macOS overlay window")
    p.add_argument("--overlay-hold", type=float, default=3.5,
                   help="minimum seconds a finalized EN caption stays before replacement")
    args = p.parse_args()

    if args.source == "file" and not args.audio:
        p.error("--audio is required for --source file")

    if not args.overlay:
        # terminal mode: simple async run
        sink = TerminalSink()
        coro = run_file(args, sink) if args.source == "file" else run_mic(args, sink)
        asyncio.run(coro)
        return

    # overlay mode: NSWindow run loop must be on the main thread.
    # Run the WLK asyncio loop in a worker thread; drive the overlay from it.
    import whisperlivekit.overlay as _ov
    _ov.MIN_HOLD_SEC = args.overlay_hold
    from whisperlivekit.overlay import OverlayRenderer

    renderer = OverlayRenderer(theme="auto", show_mem=False, translate=True)
    sink = OverlaySink(renderer)

    coro = run_file(args, sink) if args.source == "file" else run_mic(args, sink)
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
