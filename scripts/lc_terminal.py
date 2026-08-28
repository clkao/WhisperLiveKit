#!/usr/bin/env python3
"""In-process captioning tool on WhisperLiveKit — terminal OR native overlay.

In-process (no server, no WebSocket). Uses the two new backends:
  --backend mlx-qwen3-asr            (pure-MLX Qwen3-ASR, moona3k)
  --translation-backend mlx-llm-mt   (generic decoder-LLM MT via mlx-lm, in-process)

With --overlay: drives the native macOS caption window (always-on-top NSWindow,
ported from the overlay module). The WLK asyncio loop runs in a worker
thread; the overlay NSWindow run loop runs on the main thread (pyobjc requires
this); the on_update callback marshals text to the overlay fields.

Without --overlay: prints to the terminal.

Features ported from the reference implementation:
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
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime

# Silence startup noise BEFORE importing anything that pulls HF/transformers/mlx_audio:
#  - huggingface_hub re-checks cached-file etags over the network and prints
#    "Fetching N files" progress bars even on full cache hits; HF_HUB_OFFLINE=1
#    makes it use the cache with zero network and zero progress bars.
#  - transformers prints rope/rope_parameters warnings for Hy-MT2's dynamic rope.
#  - mlx_audio prints "MLX Whisper not found" (a harmless optional-dep notice).
#  - joblib warns "Operation not permitted ... serial mode" under the sandbox.
import warnings as _warnings
_warnings.filterwarnings("ignore", message=".*joblib will operate in serial mode.*")
_warnings.filterwarnings("ignore", message=".*Unrecognized keys in .rope_parameters.*")
_warnings.filterwarnings("ignore", message=".*clean_up_tokenization_spaces.*")
_warnings.filterwarnings("ignore", message=".*destructive for BPE.*")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
logging.getLogger("transformers").setLevel(logging.ERROR)
# Set the specific child loggers that emit the rope + BPE-cleanup warnings
# directly (the parent 'transformers' level gets reset on transformers import).
logging.getLogger("transformers.modeling_rope_utils").setLevel(logging.ERROR)
logging.getLogger("transformers.tokenization_utils_tokenizers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
# The optional-dep notice from backend_support ("MLX Whisper not found ...") fires
# on every startup via the simul_whisper import; irrelevant for the mlx-qwen3/
# nemotron backends we actually use, so silence it without hiding real
# whisperlivekit warnings from other modules.
logging.getLogger("whisperlivekit.backend_support").setLevel(logging.ERROR)
try:
    import mlx_audio  # noqa: F401  (import to attach the filter below)
except Exception:  # noqa: BLE001
    pass
# Suppress the "MLX Whisper not found" notice from mlx_audio.stt (it's a
# harmless optional-dependency hint, not an error).
for _n in ("mlx_audio.stt", "mlx_audio"):
    logging.getLogger(_n).setLevel(logging.WARNING)

from whisperlivekit.test_harness import TestHarness
from whisperlivekit.tui import TuiRenderer, MultiRenderer


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
        # Single-presenter use case: disable speaker diarization so the TUI
        # does not render [S1]/[S2] speaker markers on the partial line.
        "diarization": args.diarize,
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


def _fix_sentence_spacing(text: str) -> str:
    """Insert a space between a sentence terminator and a following Latin letter.

    Hunyuan MT joins consecutive sentences without one ("...tissue.Reduce
    damage..."). Display-path only; the transcript keeps the raw MT bytes."""
    return re.sub(r"([.!?])([A-Z])", r"\1 \2", text)



class OverlaySink:
    """Drives the OverlayRenderer from WLK stream state.

    Maps WLK's per-update TestState -> overlay.partial / overlay.translation:
      buffer_transcription (live rolling ASR) -> overlay partial line
      lines[].translation (committed per-utterance MT)  -> overlay translation line
      lines[].text (committed clean ASR)               -> overlay finalized zh line
    """

    def __init__(self, renderer, opencc_conv=None, opencc_mt_conv=None, target_opencc=None):
        self._r = renderer
        self._last_final = ""
        self._last_transl = ""
        self._last_prov = ""   # stash the provisional so the final can diff against it
        self._opencc = opencc_conv      # source-side converter (display)
        self._opencc_mt = opencc_mt_conv  # whether MT gets converted text
        self._target_opencc = target_opencc  # target-side converter (zh-tw output)

    def _cc_src(self, text):
        return self._opencc.convert(text) if (self._opencc and text) else text

    def _cc_target(self, text):
        if not text:
            return text
        out = self._target_opencc.convert(text) if self._target_opencc else text
        # Hunyuan MT joins consecutive sentences without a space after the period
        # ("...tissue.Reduce damage..."). Insert one on the display path when a
        # sentence terminator is followed directly by a Latin letter.
        return _fix_sentence_spacing(out)

    def __call__(self, state):
        # live partial: the rolling ASR buffer (converted for display)
        partial = (state.buffer_transcription or "").strip()
        if partial:
            self._r.partial("", self._cc_src(partial), datetime.now())
        # Provisional translation (simul MT draft): forward as preview so the
        # overlay shows it before the final arrives; stash it for the final's diff.
        prov = (state.buffer_translation or "").strip()
        if prov:
            self._last_prov = prov
            self._r.preview("", [(None, self._cc_target(prov))], datetime.now())
        # committed lines: finalized zh + translation
        for line in state.lines:
            txt = (line.get("text") or "").strip()
            tr = (line.get("translation") or "").strip()
            if txt and txt != self._last_final:
                self._last_final = txt
                self._r.final("", [(None, self._cc_src(txt))], datetime.now())
            if tr and tr != self._last_transl:
                self._last_transl = tr
                # inline diff vs the stashed provisional: struck gray old + green new
                from whisperlivekit.inline_diff import inline_diff
                shown = self._cc_target(tr)
                diff = inline_diff(self._last_prov, [shown])[0] if self._last_prov else None
                self._r.translation("", [(None, shown, diff)], datetime.now())


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
            print("\r" + " " * 120 + "\r", end="", flush=True, file=sys.stderr)

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
            # Pad to clear trailing chars from a previous longer line.
            # Terminal width is typically 80+; 120 is a safe pad ceiling.
            pad = max(0, 120 - len(line))
            print(f"\r{line}{' ' * pad}", end="", flush=True, file=sys.stderr)


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
        if not text:
            return text
        out = self._target_opencc.convert(text) if self._target_opencc else text
        return _fix_sentence_spacing(out)

    def __call__(self, state):
        partial = (state.buffer_transcription or "").strip()
        if partial:
            if self._stats is not None:
                self._stats.on_partial(partial)
            print(f"\r[zh*] {self._cc_src(partial)[:100]}", end="", flush=True)
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


class TuiSink:
    """Adapts WLK TestState → TuiRenderer / MultiRenderer contract.

    Maps:
      buffer_transcription → partial(label="mic", started_at=now, speaker=None)
      lines[].text         → final(segments=[(speaker, text)], started_at=now)
      lines[].translation  → translation(zh_segments=[(speaker, translation)])

    Tracks per-line started_at so a translation arriving in a later update
    matches the pending final entry (TuiRenderer pairs them by label+started_at).
    """

    def __init__(self, renderer, opencc_conv=None, target_opencc=None, diarization=False):
        self._r = renderer
        self._seen_finals: set[int] = set()
        self._seen_transls: set[int] = set()
        self._final_started_at: dict[int, datetime] = {}
        self._last_prov = ""   # stash the provisional so the final can diff against it
        self._opencc = opencc_conv
        self._target_opencc = target_opencc
        self._diarization = diarization

    def _cc_src(self, text):
        return self._opencc.convert(text) if (self._opencc and text) else text

    def _cc_target(self, text):
        if not text:
            return text
        out = self._target_opencc.convert(text) if self._target_opencc else text
        return _fix_sentence_spacing(out)

    def set_ocr_text(self, text):
        self._r.set_ocr_text(text)

    def __call__(self, state):
        partial = (state.buffer_transcription or "").strip()
        if partial:
            self._r.partial("mic", self._cc_src(partial), datetime.now(), speaker=None)
        # Provisional translation (simul MT draft): forward as preview so the
        # TUI shows it under the partial before the final arrives; stash for diff.
        prov = (state.buffer_translation or "").strip()
        if prov:
            self._last_prov = self._cc_target(prov)
            self._r.preview("mic", [(None, self._cc_target(prov))], datetime.now())
        for i, line in enumerate(state.lines):
            txt = (line.get("text") or "").strip()
            tr = (line.get("translation") or "").strip()
            spk = line.get("speaker")
            # With diarization off, WLK assigns every line the default speaker 1
            # (tokens_alignment._speaker_for_token returns 1 when there are no
            # diarization segments). Drop it so the TUI doesn't render [S2] on
            # every line. With diarization on, keep real speaker IDs (>=1).
            if spk is not None and (spk <= 0 or (not self._diarization and spk == 1)):
                spk = None
            if txt and i not in self._seen_finals:
                self._seen_finals.add(i)
                started_at = datetime.now()
                self._final_started_at[i] = started_at
                self._r.final("mic", [(spk, self._cc_src(txt))], started_at)
            if tr and i not in self._seen_transls:
                self._seen_transls.add(i)
                started_at = self._final_started_at.get(i, datetime.now())
                shown = self._cc_target(tr)
                # inline diff vs the stashed provisional: struck gray old + bold green
                # new, same rendering as the ASR two-pass diff.
                from whisperlivekit.inline_diff import inline_diff
                diff = (inline_diff(self._last_prov, [shown])[0]
                        if self._last_prov else None)
                self._last_prov = ""  # consumed
                self._r.translation("mic", [(spk, shown, diff)], started_at)


# ---------------------------------------------------------------------------
# Screen OCR hotword auto-refresh
# ---------------------------------------------------------------------------

def _start_ocr_loop(args, engine, on_hotwords=None, log=None):
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
        log=log or (lambda m: print(m, file=sys.stderr)),
        on_hotwords=on_hotwords,
    )
    ocr_loop.start()
    return ocr_loop


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

async def run_file(args, sink, ocr_loop=None, on_hotwords=None):
    kwargs = _make_engine_kwargs(args)
    async with TestHarness(**kwargs) as h:
        h.on_update(sink)
        if ocr_loop is not None:
            _start_ocr_loop(args, h._processor, on_hotwords=on_hotwords)
        await h.feed(args.audio, speed=1.0)
        await h.drain(8.0)
        await h.finish(timeout=180)


async def run_mic(args, sink, ocr_loop=None, stop_event=None, on_hotwords=None):
    import sounddevice as sd

    SAMPLE_RATE = 16000
    CHUNK = int(SAMPLE_RATE * 0.5)
    kwargs = _make_engine_kwargs(args)
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    # Pause toggle: 'space' pauses ASR feed (drops audio chunks; the recognizer
    # keeps its state). A daemon thread reads stdin in cbreak mode so a single
    # space keypress toggles without Enter.
    paused = threading.Event()
    key_reader_stop = threading.Event()

    def _key_reader():
        import tty, termios
        try:
            fd = sys.stdin.fileno()
        except (ValueError, OSError):
            return  # stdin is not a tty (e.g. piped); no key controls
        old = None
        try:
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            while not key_reader_stop.is_set():
                ch = sys.stdin.read(1)
                if ch == " ":
                    if paused.is_set():
                        paused.clear()
                        print("\r[asr] resumed", end="", flush=True)
                    else:
                        paused.set()
                        print("\r[asr] paused (press space to resume)", end="", flush=True)
        except Exception:
            pass
        finally:
            if old is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                except Exception:
                    pass

    key_thread = threading.Thread(target=_key_reader, daemon=True, name="lc-keys")
    key_thread.start()

    _mic_chunks = [0]  # diagnostic: count chunks reaching the processor
    def audio_cb(indata, frames, time_info, status):
        if stop.is_set():
            raise sd.CallbackStop
        if paused.is_set():
            return  # drop the chunk; ASR keeps its state, nothing is fed
        _mic_chunks[0] += 1
        pcm = (indata[:, 0] * 32767).astype("int16").tobytes()
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(h._processor.process_audio(pcm))
        )

    async def _heartbeat():
        # Event-loop liveness probe: if this stops printing, the loop is
        # blocked (not the mic). Prints every 5s to stderr.
        for i in range(1, 100000):
            await asyncio.sleep(5)
            print(f"[hb] loop alive {i*5}s · mic_cb={_mic_chunks[0]} chunks", file=sys.stderr, flush=True)

    async with TestHarness(**kwargs) as h:
        h.on_update(sink)
        if ocr_loop is not None:
            _start_ocr_loop(args, h._processor, on_hotwords=on_hotwords)
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                           blocksize=CHUNK, callback=audio_cb):
            # Ready signal on stderr so the StatsTracker status line (also
            # stderr) doesn't clobber it, and so it's unambiguous that the mic
            # stream is open and accepting audio.
            print("\n✓ Ready — speak now.\n", file=sys.stderr, flush=True)
            print(f"Listening ({args.language} -> {args.target_language}). Ctrl-C to stop.",
                  flush=True)
            hb_task = asyncio.ensure_future(_heartbeat())
            if stop_event is not None:
                # Bridge the threading stop_event (set by the signal handler on the
                # main thread) to the asyncio stop event (awaited here) so Ctrl-C
                # actually wakes this coro.
                await asyncio.to_thread(stop_event.wait)
                stop.set()
            else:
                try:
                    await stop.wait()
                except KeyboardInterrupt:
                    stop.set()
        await h.drain(3.0)
        await h.finish(timeout=60)
        key_reader_stop.set()


async def run_system(args, sink, ocr_loop=None, stop_event=None, on_hotwords=None):
    """System audio source: capture the meeting's speaker output via audiotee
    (a Core Audio process tap; built binary at livecaption/bin/audiotee).

    Mirrors run_mic's pause/space handling. audiotee emits raw s16le PCM on stdout;
    a supervisor thread restarts it if the tap dies (e.g. default output device
    changes). Needs macOS 'System Audio Recording Only' TCC permission for the
    terminal app — without it, Core Audio silently returns a zero stream.
    """
    import contextlib, select, os, time as _time
    import numpy as np

    SAMPLE_RATE = 16000
    kwargs = _make_engine_kwargs(args)
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()
    proc_holder: list = [None]  # [subprocess.Popen | None]
    stop_supervisor = threading.Event()

    # Pause toggle (same as run_mic).
    paused = threading.Event()
    key_reader_stop = threading.Event()

    def _key_reader():
        import tty, termios
        try:
            fd = sys.stdin.fileno()
        except (ValueError, OSError):
            return
        old = None
        try:
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            while not key_reader_stop.is_set():
                ch = sys.stdin.read(1)
                if ch == " ":
                    if paused.is_set():
                        paused.clear()
                        print("\r[asr] resumed", end="", flush=True)
                    else:
                        paused.set()
                        print("\r[asr] paused (press space to resume)", end="", flush=True)
        except Exception:
            pass
        finally:
            if old is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                except Exception:
                    pass

    threading.Thread(target=_key_reader, daemon=True, name="lc-keys").start()

    def _spawn():
        import subprocess
        cmd = [args.audiotee_path, "--sample-rate", str(SAMPLE_RATE)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        _time.sleep(0.3)
        if proc.poll() is not None:
            err = (proc.stderr.read() or b"").decode("utf-8", "replace")[:500]
            raise RuntimeError(f"audiotee failed to start (exit {proc.returncode}): {err.strip()}")
        proc_holder[0] = proc
        return proc

    def _pump(proc):
        """Forward one audiotee process's PCM to the processor until it ends."""
        fd = proc.stdout.fileno()
        remainder = b""
        frames_seen = 0
        saw_audio = False
        zero_warned = False
        last_data = _time.monotonic()
        STALL_SEC = 6.0
        while not stop_supervisor.is_set() and not stop.is_set():
            ready, _, _ = select.select([fd], [], [], 0.5)
            if not ready:
                if _time.monotonic() - last_data >= STALL_SEC:
                    return f"stalled (no data for {STALL_SEC:.0f}s)"
                continue
            buf = os.read(fd, 4096)
            if not buf:
                return "stream ended (audiotee exited)"
            last_data = _time.monotonic()
            buf = remainder + buf
            n = len(buf) - (len(buf) % 2)
            chunk, remainder = buf[:n], buf[n:]
            if not chunk:
                continue
            pcm = np.frombuffer(chunk, dtype="<i2")
            if not saw_audio:
                if int(np.abs(pcm).max(initial=0)) > 30:
                    saw_audio = True
                else:
                    frames_seen += len(pcm)
                    if not zero_warned and frames_seen > SAMPLE_RATE * 8:
                        zero_warned = True
                        print("\n[warn] ~8s of system audio is all silence. If sound is "
                              "playing, the terminal app lacks System Audio Recording "
                              "permission. System Settings > Privacy & Security > Screen & "
                              "System Audio Recording; on macOS 15+ use the 'System Audio "
                              "Recording Only' sub-section (NOT the top one).", file=sys.stderr)
            if not paused.is_set():
                loop.call_soon_threadsafe(
                    lambda p=pcm: asyncio.ensure_future(h._processor.process_audio(p.tobytes()))
                )
        return "stopped"

    def _supervise():
        failures = 0
        while not stop_supervisor.is_set() and not stop.is_set():
            proc = proc_holder[0]
            if proc is None:
                try:
                    proc = _spawn()
                except Exception as e:
                    failures += 1
                    if failures >= 3:
                        print(f"\n[warn] could not start audiotee ({e}); system track stopped.",
                              file=sys.stderr)
                        stop.set()
                        return
                    _time.sleep(2.0)
                    continue
            reason = _pump(proc)
            if stop.is_set() or stop_supervisor.is_set():
                break
            with contextlib.suppress(Exception):
                proc.terminate(); proc.wait(timeout=2)
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()
            print(f"\n[warn] system audio {reason}; restarting audiotee.", file=sys.stderr)
            proc_holder[0] = None
            failures = 0

    async with TestHarness(**kwargs) as h:
        h.on_update(sink)
        if ocr_loop is not None:
            _start_ocr_loop(args, h._processor, on_hotwords=on_hotwords)
        try:
            _spawn()  # raises early on a bad path / instant crash
        except Exception as e:
            print(f"[system] {e}", file=sys.stderr)
            return
        threading.Thread(target=_supervise, daemon=True, name="audiotee-sup").start()
        print(f"Listening (system audio -> {args.target_language}). Ctrl-C / space to control.",
              flush=True)
        if stop_event is not None:
            await asyncio.to_thread(stop_event.wait)
            stop.set()
        else:
            try:
                await stop.wait()
            except KeyboardInterrupt:
                stop.set()
        stop_supervisor.set()
        await h.drain(3.0)
        await h.finish(timeout=60)
        key_reader_stop.set()


def _print_banner(args, src_config, tgt_config) -> None:
    """Print a compact one-time config summary to stderr before the TUI starts."""
    lines: list[str] = []
    # ASR backend + model
    if args.backend == "mlx-qwen3-asr":
        lines.append(f"ASR: mlx-qwen3-asr \u00b7 {args.mlx_qwen3_asr_model}")
    elif args.backend == "qwen3-vllm-metal":
        lines.append(f"ASR: qwen3-vllm-metal ({args.qwen3_vllm_metal_audio_backend}) \u00b7 {args.qwen3_vllm_metal_tower_checkpoint}")
    else:
        lines.append(f"ASR: {args.backend}")

    # MT model + mode
    mt_mode = "simultaneous" if args.simultaneous else "serial"
    lines.append(f"MT: {args.mlx_llm_mt_model} \u00b7 {mt_mode}")

    # Simul availability
    from whisperlivekit.translation_mlx_llm_mt import MTX_MODEL_CONFIGS
    from whisperlivekit.simul_mt_capture import lookup_calibration
    mt_cfg = MTX_MODEL_CONFIGS.get(args.mlx_llm_mt_model)
    if mt_cfg is not None:
        cal = lookup_calibration(mt_cfg.repo, args.language, args.target_language)
    else:
        cal = None
    if cal is not None:
        top_l, top_h = cal.top_head
        lines.append(f"Simul: available ({len(cal.heads)} heads, top L{top_l} H{top_h})")
    else:
        if args.simultaneous:
            print("WARNING: --simultaneous passed but no calibration exists for "
                  f"({args.mlx_llm_mt_model}, {args.language}, {args.target_language}). "
                  "Falling back to serial MT.", file=sys.stderr)
        model_repr = mt_cfg.repo if mt_cfg else args.mlx_llm_mt_model
        lines.append(f"Simul: unavailable \u2014 no calibration for ({model_repr}, {args.language}, {args.target_language}); running serial MT")

    # VAD params (only if non-default)
    vad_parts = []
    if args.vad_threshold is not None:
        vad_parts.append(f"threshold {args.vad_threshold}")
    if args.vad_min_silence_ms is not None:
        vad_parts.append(f"min-silence {args.vad_min_silence_ms}ms")
    if vad_parts:
        lines.append(f"VAD: {' \u00b7 '.join(vad_parts)}")
    else:
        lines.append("VAD: defaults")

    # OpenCC config
    if src_config is not None and tgt_config is not None:
        lines.append(f"OpenCC: source {src_config} \u00b7 target {tgt_config}")
    elif src_config is not None:
        lines.append(f"OpenCC: source {src_config}")
    elif tgt_config is not None:
        lines.append(f"OpenCC: target {tgt_config}")
    else:
        lines.append("OpenCC: off")

    # Source mode
    if args.source == "file":
        lines.append(f"Source: file \u00b7 {args.audio}")
    elif args.source == "system":
        lines.append(f"Source: system audio \u00b7 {args.audiotee_path}")
    else:
        lines.append("Source: microphone")

    print("\n".join(lines), file=sys.stderr, flush=True)


def main() -> None:
    # Pre-import modules that call logger.setLevel(DEBUG) at import time, so
    # our WARNING override below runs AFTER their module-level setup.
    import whisperlivekit.audio_processor  # noqa: F401
    import whisperlivekit.asr_mlx_qwen3      # noqa: F401

    # Quiet library loggers so they don't spam the TUI (rich.Live owns the terminal).
    # INFO-level library logs (transformers' clean_up_tokenization warning, mlx_lm
    # loader chatter, etc.) go to stderr and interleave the live region. Surface only
    # WARNING+ from libraries; keep lc_terminal's own prints (OpenCC-on, [asr] paused)
    # since those are one-time init / user-action status.
    #
    # audio_processor.py calls logging.basicConfig(level=INFO) + logger.setLevel(DEBUG)
    # at import time — the pre-import above runs that first, then we override here.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    logging.getLogger().setLevel(logging.WARNING)
    for h in logging.getLogger().handlers:
        h.setLevel(logging.WARNING)
    for _noisy in ("transformers", "mlx_lm", "tokenizers", "httpx", "openai", "urllib3",
                   "whisperlivekit.audio_processor", "whisperlivekit.asr_mlx_qwen3"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)
    p = argparse.ArgumentParser(description="in-process captioning on WLK")
    p.add_argument("--audio", help="audio file path (file mode)")
    p.add_argument("--source", choices=["mic", "file", "system"], default="file")
    p.add_argument("--audiotee-path", default=None,
                   help="path to the audiotee binary (system audio tap); defaults to shutil.which('audiotee')")
    p.add_argument("--language", default="zh")
    p.add_argument("--target-language", default="en")
    p.add_argument("--backend", choices=["mlx-qwen3-asr", "qwen3-vllm-metal", "nemotron-mlx-asr"], default="mlx-qwen3-asr",
                   help="ASR backend: mlx-qwen3-asr (windowed, pure MLX) or qwen3-vllm-metal (causal, native MLX via the fork) or nemotron-mlx-asr (transducer, native timestamps)")
    p.add_argument("--mlx-qwen3-asr-model", default="mlx-community/Qwen3-ASR-0.6B-8bit")
    p.add_argument("--mlx-llm-mt-model", default="hy-mt2-1.8b-8bit")
    p.add_argument("--qwen3-vllm-metal-audio-backend", choices=["standard", "causal"], default="causal",
                   help="qwen3-vllm-metal audio backend: 'causal' (append-only KV, flat-cost) or 'standard' (re-encode window)")
    p.add_argument("--qwen3-vllm-metal-tower-checkpoint", default="qfuxa/qwen3-asr-0.6b-streaming",
                   help="tower checkpoint for the causal audio encoder")
    p.add_argument("--overlay", action="store_true",
                   help="display captions in a native always-on-top macOS overlay window")
    p.add_argument("--diarize", action="store_true", default=False,
                   help="enable speaker diarization (off by default; the TUI shows [S1]/[S2] markers only when on)")
    p.add_argument("--overlay-mode", choices=["both", "target", "source"], default="both",
                   help="overlay only: which text to show. 'both' = source + target, 'target' = translation only, 'source' = source only")
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
    if args.source == "system":
        import shutil
        audiotee_path = args.audiotee_path or shutil.which("audiotee")
        if audiotee_path is None:
            # fall back to the livecaption built binary if present
            import os
            lc_bin = os.path.join(os.path.dirname(__file__), "..", "..", "livecaption", "bin", "audiotee")
            audiotee_path = lc_bin if os.path.isfile(lc_bin) else None
        if audiotee_path is None:
            p.error("--source system needs the audiotee binary; pass --audiotee-path, build it (livecaption/scripts/build_audiotee.sh), or install it on PATH")
        args.audiotee_path = audiotee_path

    # --mem is an alias for --stats
    show_stats = args.stats or args.mem

    # OpenCC converters. Aligned with livecaption: when the source language is zh,
    # default to s2twp (Simplified -> Taiwan Traditional) on the source/display side
    # without requiring --opencc. An explicit --opencc overrides the source config.
    # Target-side: when the target language is zh (any variant), auto-apply s2twp to
    # the MT output. An explicit --opencc also applies to the target when the target
    # is zh (so `--opencc s2twp --target-language zh` converts the zh MT output).
    src_lang = (args.language or "").lower()
    tgt_lang = (args.target_language or "").lower()
    src_is_zh = src_lang.startswith("zh")
    tgt_is_zh = tgt_lang.startswith("zh")
    opencc_conv = None
    target_opencc = None
    src_config = args.opencc if args.opencc is not None else ("s2twp" if src_is_zh else None)
    if src_config is not None:
        opencc_conv = _make_opencc(src_config)
        if opencc_conv is None and args.opencc is not None:
            sys.exit(1)
        if opencc_conv is not None:
            how = " (explicit --opencc)" if args.opencc is not None else " (auto: source is zh)"
            print(f"OpenCC {src_config} on source{how}: ASR display -> Taiwan Traditional", file=sys.stderr)
    # Target side: explicit --opencc wins for a zh target; otherwise auto-apply s2twp
    # for any zh target (plain zh, zh-tw, zh-hant, ...).
    tgt_config = args.opencc if (args.opencc is not None and tgt_is_zh) else ("s2twp" if tgt_is_zh else None)
    if tgt_config is not None:
        target_opencc = _make_opencc(tgt_config)
        if target_opencc:
            how = " (explicit --opencc)" if args.opencc is not None else " (auto: target is zh)"
            print(f"OpenCC {tgt_config} on target{how}: MT output -> Taiwan Traditional", file=sys.stderr)

    # Pre-create OCR loop placeholder (started after engine init)
    ocr_loop = True if args.ocr_display is not None else None

    # One-time startup banner (stderr) before the TUI takes over the terminal.
    _print_banner(args, src_config, tgt_config)

    if not args.overlay:
        # terminal mode: TuiRenderer (rich.Live three-region) replaces print-based TerminalSink.
        # The renderer's own status line handles MLX memory + latency (show_mem=show_stats),
        # so the separate StatsTracker is no longer needed here.
        with TuiRenderer(theme="auto", show_mem=show_stats, translate=True,
                         show_ocr=(ocr_loop is not None)) as renderer:
            sink = TuiSink(renderer, opencc_conv=opencc_conv, target_opencc=target_opencc, diarization=args.diarize)
            on_hotwords = renderer.set_ocr_text if ocr_loop else None
            coro = (run_file(args, sink, ocr_loop, on_hotwords=on_hotwords)
                    if args.source == "file"
                    else run_system(args, sink, ocr_loop, on_hotwords=on_hotwords)
                    if args.source == "system"
                    else run_mic(args, sink, ocr_loop, on_hotwords=on_hotwords))
            asyncio.run(coro)
        return

    # overlay mode: NSWindow run loop must be on the main thread.
    # Run the WLK asyncio loop in a worker thread; drive BOTH the terminal TUI
    # and the overlay window from it via MultiRenderer (fan-out).
    import whisperlivekit.overlay as _ov
    _ov.MIN_HOLD_SEC = args.overlay_hold
    from whisperlivekit.overlay import OverlayRenderer

    terminal = TuiRenderer(theme="auto", show_mem=show_stats, translate=True,
                            show_ocr=(ocr_loop is not None))
    overlay = OverlayRenderer(theme="auto", show_mem=False, translate=True,
                              suppress_mem_stderr=True,
                              overlay_mode=args.overlay_mode)
    renderer = MultiRenderer(terminal=terminal, overlay=overlay)
    sink = TuiSink(renderer, opencc_conv=opencc_conv, target_opencc=target_opencc, diarization=args.diarize)
    on_hotwords = renderer.set_ocr_text if ocr_loop else None

    stop_event = threading.Event()
    coro = (run_file(args, sink, ocr_loop, on_hotwords=on_hotwords)
            if args.source == "file"
            else run_system(args, sink, ocr_loop, stop_event=stop_event, on_hotwords=on_hotwords)
            if args.source == "system"
            else run_mic(args, sink, ocr_loop, stop_event=stop_event, on_hotwords=on_hotwords))
    worker_error: list = []

    def worker():
        try:
            asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001
            worker_error.append(exc)
        finally:
            stop_event.set()

    with renderer:  # enters TuiRenderer + creates the NSWindow on the main thread
        t = threading.Thread(target=worker, daemon=True, name="wlk-asr")
        t.start()
        import signal
        def _on_sigint(signum, frame):
            stop_event.set()
        _prev = signal.signal(signal.SIGINT, _on_sigint)
        try:
            renderer.run_until(stop_event)  # MultiRenderer forwards to overlay's run_until
        finally:
            signal.signal(signal.SIGINT, _prev)
        # The worker coro awaits an asyncio.Event (``stop`` in run_mic) that is
        # separate from ``stop_event`` (threading). Wake it: the mic's
        # audio_cb checks stop.is_set() and raises CallbackStop once the
        # asyncio event is set, but that event is internal to the coro. The
        # daemon thread + a short join is enough; if it hangs, force-exit.
        t.join(timeout=3)
        if t.is_alive():
            import os
            os._exit(0)
    if worker_error:
        raise worker_error[0]


if __name__ == "__main__":
    main()
