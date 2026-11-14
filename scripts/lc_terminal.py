#!/usr/bin/env python3
"""In-process captioning on WhisperLiveKit — terminal output OR native overlay.

In-process: no server, no WebSocket. Builds the pipeline through
``TestHarness`` with the two in-process MLX backends:

  --backend mlx-qwen3-asr   pure-MLX Qwen3-ASR streaming ASR
  --translation-backend      mlx-llm-mt (generic decoder-LLM MT via mlx-lm)

Two display paths, both consuming the same session:

  --overlay OFF  the print-based terminal sink (``TerminalSink``): committed
                 source lines and their translation, plus a ``--mem`` status
                 line on stderr.
  --overlay ON   the native macOS caption window (``OverlayRenderer``), fed
                 from the caption event stream (``--overlay-mode target`` shows
                 the target rows only). The terminal keeps printing through the
                 same print-based sink.

The overlay path is the production target:

    uv run --frozen --extra opencc --extra listen --extra mlx-llm-mt \\
      --extra overlay --extra mlx-qwen3-asr scripts/lc_terminal.py \\
      --backend mlx-qwen3-asr --source mic --no-second-pass \\
      --mlx-qwen3-asr-model mlx-community/Qwen3-ASR-0.6B-8bit \\
      --mlx-llm-mt-model hy-mt2-1.8b-8bit --simultaneous --simul-commit mass \\
      --overlay --overlay-mode target \\
      --opencc s2twp --target-language en --mem

Flags that this base cannot support fail loudly rather than silently doing
nothing: ``--second-pass`` (this ASR backend has no two-pass re-decode, so
``--no-second-pass`` is the honest default) and ``--opencc-mt`` (MT-input
conversion is a pipeline change, not a display one).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import signal
import sys
import threading
import time

# Silence startup noise BEFORE importing anything that pulls HF/transformers/mlx:
#  - transformers prints rope warnings for Hy-MT2's dynamic rope.
#  - mlx_audio prints "MLX Whisper not found" (a harmless optional-dep notice).
import warnings as _warnings

_warnings.filterwarnings("ignore", message=".*Unrecognized keys in .rope_parameters.*")
_warnings.filterwarnings("ignore", message=".*clean_up_tokenization_spaces.*")
_warnings.filterwarnings("ignore", message=".*destructive for BPE.*")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.modeling_rope_utils").setLevel(logging.ERROR)
logging.getLogger("transformers.tokenization_utils_tokenizers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
# The optional-dep notice from backend_support ("MLX Whisper not found ...") fires
# on every startup via the simul_whisper import; irrelevant for the backends used
# here, so silence that one logger without hiding real whisperlivekit warnings.
logging.getLogger("whisperlivekit.backend_support").setLevel(logging.ERROR)

from whisperlivekit.src_buffer import ends_sentence  # noqa: E402
from whisperlivekit.test_harness import TestHarness  # noqa: E402

# ---------------------------------------------------------------------------
# OpenCC converter helpers
# ---------------------------------------------------------------------------

def _make_opencc(config_name):
    """Create an OpenCC converter, or None if the package is missing."""
    try:
        import opencc
        return opencc.OpenCC(config_name)
    except Exception as e:  # noqa: BLE001 -- reported, then the driver exits
        print(f"OpenCC '{config_name}' failed: {e}", file=sys.stderr)
        return None


def _fix_sentence_spacing(text: str) -> str:
    """Insert a space between a sentence terminator and a following Latin letter.

    Hunyuan MT joins consecutive sentences without one ("...tissue.Reduce
    damage..."). Display-path only; the transcript keeps the raw MT bytes."""
    return re.sub(r"([.!?])([A-Z])", r"\1 \2", text)


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
        "pause_segmentation_seconds": float(os.environ.get("LC_PAUSE", "0.35")),
        "mlx_llm_mt_simul_soft_max_s": float(os.environ.get("LC_SOFT_MAX", "4.0")),
        "mlx_llm_mt_simul_hard_max_s": float(os.environ.get("LC_HARD_MAX", "20.0")),
        "mlx_qwen3_asr_model": args.mlx_qwen3_asr_model,
        # Simultaneous MT: AlignAtt commit policy over the calibrated heads.
        "mlx_llm_mt_simultaneous": bool(args.simultaneous),
        "mlx_llm_mt_simul_commit": args.simul_commit,
        "mlx_llm_mt_simul_frontier": args.simul_frontier,
        "mlx_llm_mt_simul_hold_back_s": args.simul_hold_back,
        # Single-presenter use case: no speaker diarization, so no [S1] markers.
        "diarization": False,
    }
    # Hotwords: a static --hotwords list becomes the recognizer's initial context.
    if args.hotwords:
        kw["mlx_qwen3_asr_context"] = args.hotwords
    # --event-log: the AudioProcessor opens the JSONL sink itself and fans the
    # caption event stream out to it alongside the display consumer.
    if args.event_log:
        kw["event_log"] = args.event_log
    return kw


# ---------------------------------------------------------------------------
# Sinks (terminal print + overlay)
# ---------------------------------------------------------------------------

class StatsTracker:
    """Live status line on stderr: ASR/MT latency EWMA, MLX memory, commit/emit counts.

    Prints one line per second using ``\\r`` (carriage-return overwrite) so the status
    stays in place without scrolling the caption text above it. Enabled by ``--stats``
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
    """Print-based sink: one line per committed source clause and per translation.

    Driven from ``TestHarness.on_update`` (the FrontData snapshot path), so it
    works with or without a display consumer on the event stream. Line text
    grows cumulatively inside one utterance, hence the appended-sentence rule:
    the new suffix prints as its own line once it ends a sentence, instead of
    waiting for the whole utterance (CL: 'missing the 1st of the second
    sentence').

    When *stats* is provided, records ASR/MT latency samples and commit/emit
    counts on each state update; the StatsTracker thread prints a live status
    line to stderr. When *opencc* is set, converts ASR text for display. When
    *target_opencc* is set, converts MT output for display (zh-family targets).
    """

    def __init__(self, stats=None, opencc_conv=None, target_opencc=None):
        self._seen_transl = set()
        self._printed_line = set()   # cumulative zh already printed
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
        for line in state.lines:
            txt = (line.get("text") or "").strip()
            tr = (line.get("translation") or "").strip()
            if txt:
                # FrontData line text GROWS cumulatively; print once complete,
                # then print only appended sentence(s) as they land (they must
                # not vanish into the seen-set — CL: missing-sentence bug)
                if txt not in self._printed_line and not any(
                        txt.startswith(p) for p in self._printed_line):
                    self._printed_line.add(txt)
                    if self._stats is not None:
                        self._stats.on_commit()
                    print(f"\n[zh] {self._cc_src(txt)}")
                else:
                    prev = next((p for p in self._printed_line
                                 if txt.startswith(p)), "")
                    if len(txt) > len(prev):
                        suffix = txt[len(prev):]
                        if ends_sentence(suffix):
                            # replace the printed set with the grown cumulative
                            self._printed_line = {
                                p for p in self._printed_line if p != prev}
                            self._printed_line.add(txt)
                            if self._stats is not None:
                                self._stats.on_commit()
                            print(f"\n[zh] {self._cc_src(suffix)}")
            if tr and tr not in self._seen_transl:
                self._seen_transl.add(tr)
                if self._stats is not None:
                    self._stats.on_emit()
                print(f"[{self._lang}] {self._cc_target(tr)}")


class OverlaySink:
    """``EventSink``: feed the overlay renderer from the caption event stream.

    The renderer owns a ``CaptionDisplay`` and takes plain text, so this adapter
    flattens each event's payload to text and routes it to the renderer's
    call-shaped API. OpenCC conversion happens here, on the display path only:
    the window shows Taiwan Traditional while MT still reads the raw ASR output
    (``--opencc-mt`` would be a pipeline change, not a display one — see
    ``main``). ``TestHarness`` reads ``state()`` off whatever object it was
    given as the display consumer.
    """

    def __init__(self, renderer, opencc_conv=None, target_opencc=None):
        self._r = renderer
        self._opencc = opencc_conv
        self._target_opencc = target_opencc

    def _cc_src(self, text):
        return self._opencc.convert(text) if (self._opencc and text) else text

    def _cc_target(self, text):
        if not text:
            return text
        out = self._target_opencc.convert(text) if self._target_opencc else text
        return _fix_sentence_spacing(out)

    def emit(self, event) -> None:
        if event.type == "transcription_provisional":
            self._r.partial("", self._cc_src(event.text))
        elif event.type == "transcription_final":
            self._r.final("", [(None, self._cc_src(event.text))])
        elif event.type == "translation_provisional":
            self._r.preview("", [(None, self._cc_target(event.text))])
        elif event.type == "translation_final":
            self._r.translation("", [(None, self._cc_target(event.text))])

    def state(self):
        """The renderer's display state (snapshot, no clock advance)."""
        return self._r.state()


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

async def run_file(args, caption_display=None, on_state=None, stop_event=None):
    import contextlib
    kwargs = _make_engine_kwargs(args)
    async with TestHarness(caption_display=caption_display, **kwargs) as h:
        if on_state is not None:
            h.on_update(on_state)
        feed_task = asyncio.ensure_future(h.feed(args.audio, speed=1.0))
        # ^C-clean without a helper thread: poll the stop event while the feed
        # runs. A to_thread(Event.wait) waiter would outlive the loop (Event.wait
        # is not interruptible), and the executor's shutdown then joined it for
        # 300s — the process never exited after a normal completion.
        while not feed_task.done():
            if stop_event is not None and stop_event.is_set():
                print("\n[file] interrupt: flushing and exiting", file=sys.stderr, flush=True)
                feed_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await feed_task
                await h.drain(1.0)
                await h.finish(timeout=15)
                return
            await asyncio.wait({feed_task}, timeout=0.1)
        await feed_task
        await h.drain(8.0)
        await h.finish(timeout=180)


async def run_mic(args, caption_display=None, on_state=None, stop_event=None):
    import sounddevice as sd

    SAMPLE_RATE = 16000
    CHUNK = int(SAMPLE_RATE * 0.5)
    kwargs = _make_engine_kwargs(args)
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    # Pause toggle: 'space' pauses the ASR feed (drops audio chunks; the
    # recognizer keeps its state). A daemon thread reads stdin in cbreak mode so
    # a single space keypress toggles without Enter.
    paused = threading.Event()
    key_reader_stop = threading.Event()

    def _key_reader():
        import termios
        import tty
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
        except Exception:  # noqa: BLE001 -- key controls are best-effort
            pass
        finally:
            if old is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                except Exception:  # noqa: BLE001
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
        if status:
            print(f"[mic-diag] stream status: {status}", file=sys.stderr, flush=True)
        # Amplitude probe: silent input (wrong device / missing TCC) delivers
        # chunks that never trigger VAD -> zero tokens with a live heartbeat.
        if _mic_chunks[0] % 10 == 0:
            peak = float(abs(indata).max()) if indata.size else 0.0
            print(f"[mic-diag] chunk {_mic_chunks[0]} peak={peak:.3f}", file=sys.stderr, flush=True)

    async def _heartbeat():
        # Event-loop liveness probe: if this stops printing, the loop is
        # blocked (not the mic). Prints every 5s to stderr.
        for i in range(1, 100000):
            await asyncio.sleep(5)
            print(f"[hb] loop alive {i*5}s · mic_cb={_mic_chunks[0]} chunks", file=sys.stderr, flush=True)

    async with TestHarness(caption_display=caption_display, **kwargs) as h:
        if on_state is not None:
            h.on_update(on_state)
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                           blocksize=CHUNK, callback=audio_cb):
            # Ready signal on stderr so the StatsTracker status line (also
            # stderr) doesn't clobber it, and so it's unambiguous that the mic
            # stream is open and accepting audio.
            _dev_idx = sd.default.device[0]
            _dev = sd.query_devices(_dev_idx)
            print(f"[mic-diag] default input device: {_dev['name']} "
                  f"(host API: {sd.query_hostapis(_dev['hostapi'])['name']}, "
                  f"{_dev['default_samplerate']:.0f}Hz)", file=sys.stderr, flush=True)
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
            hb_task.cancel()
        await h.drain(3.0)
        await h.finish(timeout=60)
        key_reader_stop.set()


def _run_source(args, caption_display, on_state, stop_event):
    """The coro for the selected --source."""
    if args.source == "file":
        return run_file(args, caption_display, on_state, stop_event)
    return run_mic(args, caption_display, on_state, stop_event)


def _print_banner(args, src_config, tgt_config) -> None:
    """Print a compact one-time config summary to stderr before the pipeline starts."""
    lines: list[str] = []
    lines.append(f"ASR: {args.backend} \u00b7 {args.mlx_qwen3_asr_model}")
    lines.append("ASR finalize: streaming only (this base has no two-pass re-decode)")
    mt_mode = "simultaneous" if args.simultaneous else "serial"
    lines.append(f"MT: {args.mlx_llm_mt_model} \u00b7 {mt_mode}")
    if args.simultaneous:
        lines.append(f"Simul commit policy: {args.simul_commit} \u00b7 frontier: {args.simul_frontier}")

    # Simul availability: the engine hard-fails without a bundled calibration
    # for the (model, direction); detect that here and warn early instead.
    from whisperlivekit.translation_profiles import MT_MODEL_PROFILES
    mt_cfg = MT_MODEL_PROFILES.get(args.mlx_llm_mt_model)
    cal = None
    if mt_cfg is not None:
        try:
            from whisperlivekit.simul_mt_calibration import load_calibration
            cal = load_calibration(None, mt_cfg.repo, args.language, args.target_language)
        except (FileNotFoundError, ValueError):
            cal = None
    if cal is not None:
        top_l, top_h = cal.heads[0]
        lines.append(f"Simul: available ({len(cal.heads)} heads, top L{top_l} H{top_h})")
    else:
        if args.simultaneous:
            print("WARNING: --simultaneous passed but no calibration exists for "
                  f"({args.mlx_llm_mt_model}, {args.language}, {args.target_language}). "
                  "The engine will fail at startup.", file=sys.stderr)
        model_repr = mt_cfg.repo if mt_cfg else args.mlx_llm_mt_model
        lines.append(f"Simul: unavailable \u2014 no calibration for ({model_repr}, "
                     f"{args.language}, {args.target_language})")

    if src_config is not None and tgt_config is not None:
        lines.append(f"OpenCC: source {src_config} \u00b7 target {tgt_config}")
    elif src_config is not None:
        lines.append(f"OpenCC: source {src_config}")
    elif tgt_config is not None:
        lines.append(f"OpenCC: target {tgt_config}")
    else:
        lines.append("OpenCC: off")

    if args.source == "file":
        lines.append(f"Source: file \u00b7 {args.audio}")
    else:
        lines.append("Source: microphone")
    print("\n".join(lines), file=sys.stderr, flush=True)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="in-process captioning on WhisperLiveKit")
    p.add_argument("--audio", help="audio file path (--source file)")
    p.add_argument("--source", choices=["mic", "file"], default="file")
    p.add_argument("--language", default="zh", help="ASR source language (default zh)")
    p.add_argument("--target-language", default="en", help="MT target language (default en)")
    p.add_argument("--backend", choices=["mlx-qwen3-asr"], default="mlx-qwen3-asr",
                   help="ASR backend (this driver supports the pure-MLX mlx-qwen3-asr adapter)")
    p.add_argument("--mlx-qwen3-asr-model", default="mlx-community/Qwen3-ASR-0.6B-8bit",
                   help="ASR model id for --backend mlx-qwen3-asr "
                        "(default mlx-community/Qwen3-ASR-0.6B-8bit)")
    p.add_argument("--mlx-llm-mt-model", default="hy-mt2-1.8b-8bit",
                   help="in-process MLX MT model (default hy-mt2-1.8b-8bit)")
    p.add_argument("--hotwords", default="", metavar="TERMS",
                   help="static hotword list (space-separated) for ASR biasing")

    # --- display ---
    p.add_argument("--overlay", action="store_true",
                   help="display captions in a native always-on-top macOS overlay window")
    p.add_argument("--overlay-mode", choices=["both", "target", "source"], default="both",
                   help="overlay only: which rows to show. 'both' = source + target, "
                        "'target' = translation only, 'source' = source only")
    p.add_argument("--overlay-hold", type=float, default=3.5,
                   help="minimum seconds a finalized target caption stays before "
                        "replacement (default 3.5)")

    # --- OpenCC ---
    p.add_argument("--opencc", default=None, metavar="CONFIG",
                   help="convert ASR text via OpenCC before display (e.g. s2twp for "
                        "Simplified -> Taiwan Traditional). Values: s2t, s2twp, s2hk, t2s, ...")
    p.add_argument("--opencc-mt", action="store_true", default=False,
                   help="also feed OpenCC-converted text to MT (not supported: the MT "
                        "input is built from ASR tokens inside the pipeline)")

    # --- stats ---
    p.add_argument("--stats", action="store_true",
                   help="print a live status line (ASR/MT latency, MLX memory, "
                        "commit/emit counts) to stderr")
    p.add_argument("--mem", action="store_true",
                   help="alias for --stats (MLX memory readout + latency EWMA)")

    # --- ASR finalization ---
    p.add_argument("--second-pass", action=argparse.BooleanOptionalAction, default=False,
                   help="two-pass re-decode at utterance finalization. NOT AVAILABLE on "
                        "this backend: --no-second-pass (the default) states the fact; "
                        "--second-pass fails")

    # --- simultaneous MT ---
    p.add_argument("--simultaneous", action="store_true", default=False,
                   help="use the simultaneous-MT variant (AlignAtt commit policy over the "
                        "calibrated zh->en heads)")
    p.add_argument("--simul-commit", choices=["argmax", "mass", "paper"], default="paper",
                   help="simul commit policy: argmax (brittle on the unstable tail), "
                        "mass (commit once the majority of attention mass is on committed "
                        "source), or paper (stabilized argmax; the engine default)")
    p.add_argument("--simul-frontier", choices=["auto", "text", "time"], default="auto",
                   help="accessible-frontier source: time (source words behind the audio "
                        "cursor; resolves from auto), text (ASR-committed prefix), or auto")
    p.add_argument("--simul-hold-back", type=float, default=0.0,
                   help="hold-back for the time frontier, in seconds (0 = the paper's 0ms)")

    p.add_argument("--event-log", default=None, metavar="PATH",
                   help="record the canonical caption event stream (JSONL) for replay")
    return p


def main() -> None:
    # Pre-import modules that call logger.setLevel(DEBUG) at import time, so the
    # WARNING override below runs AFTER their module-level setup.
    import whisperlivekit.asr_mlx_qwen3  # noqa: F401
    import whisperlivekit.audio_processor  # noqa: F401

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    logging.getLogger().setLevel(logging.WARNING)
    for h in logging.getLogger().handlers:
        h.setLevel(logging.WARNING)
    for _noisy in ("transformers", "mlx_lm", "tokenizers", "httpx", "openai", "urllib3",
                   "whisperlivekit.audio_processor", "whisperlivekit.asr_mlx_qwen3"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)

    p = _build_parser()
    args = p.parse_args()

    if args.source == "file" and not args.audio:
        p.error("--audio is required for --source file")
    if args.second_pass:
        p.error("--second-pass is not available: this ASR backend (mlx-qwen3-asr) has no "
                "two-pass re-decode. Drop the flag (--no-second-pass is the honest default).")
    if args.opencc_mt:
        p.error("--opencc-mt is not available: the MT input is built from ASR tokens "
                "inside the pipeline, so there is no display-side MT-input conversion "
                "hook. Drop the flag; --opencc still converts the display path.")

    show_stats = args.stats or args.mem

    # OpenCC: the display path converts source (and target when the target is zh).
    # MT keeps the raw ASR text — that is what the calibration heads were measured
    # against, and converting MT input is a pipeline change, not a display one.
    tgt_lang = (args.target_language or "").lower()
    opencc_conv = None
    target_opencc = None
    src_config = args.opencc
    if src_config is not None:
        opencc_conv = _make_opencc(src_config)
        if opencc_conv is None:
            sys.exit(1)
        print(f"OpenCC {src_config} on source: ASR display -> Taiwan Traditional",
              file=sys.stderr)
    tgt_config = args.opencc if (args.opencc is not None and tgt_lang.startswith("zh")) else None
    if tgt_config is not None:
        target_opencc = _make_opencc(tgt_config)
        if target_opencc is not None:
            print(f"OpenCC {tgt_config} on target: MT output -> Taiwan Traditional",
                  file=sys.stderr)

    _print_banner(args, src_config, tgt_config)

    # The terminal print path runs in both modes (--overlay adds the window), and
    # --mem's status line is the same StatsTracker in both: the window has no
    # status line of its own, and the caption event stream carries no
    # per-utterance start time for the view to measure latency from.
    stats = None
    if show_stats:
        stats = StatsTracker()
        stats.start()
    printer = TerminalSink(stats=stats, opencc_conv=opencc_conv, target_opencc=target_opencc)

    try:
        if not args.overlay:
            # Terminal-only: the print sink is the only display consumer, and the
            # event tap stays unallocated (no display model in this mode).
            stop_event = threading.Event()
            _prev = signal.signal(signal.SIGINT, lambda *_: stop_event.set())
            try:
                asyncio.run(_run_source(args, None, printer, stop_event))
            finally:
                signal.signal(signal.SIGINT, _prev)
            return

        # Overlay: the NSWindow run loop must own the main thread, so the pipeline
        # asyncio loop runs in a worker thread and the caption event stream feeds
        # the window through OverlaySink.
        from whisperlivekit.overlay import OverlayRenderer
        renderer = OverlayRenderer(overlay_mode=args.overlay_mode,
                                   hold_sec=args.overlay_hold)
        caption_display = OverlaySink(renderer, opencc_conv=opencc_conv,
                                      target_opencc=target_opencc)
        stop_event = threading.Event()     # Ctrl-C: stop the session
        session_done = threading.Event()   # the session ended on its own (file EOF)
        exit_event = threading.Event()     # what the AppKit pump loop waits on
        coro = _run_source(args, caption_display, printer, stop_event)
        worker_error: list = []

        def worker():
            try:
                asyncio.run(coro)
            except Exception as exc:  # noqa: BLE001 -- re-raised on the main thread
                worker_error.append(exc)
            finally:
                session_done.set()

        def watch_session():
            session_done.wait()
            exit_event.set()

        def on_sigint(*_args):
            stop_event.set()
            exit_event.set()

        with renderer:  # creates the NSWindow on the main thread
            t = threading.Thread(target=worker, daemon=True, name="wlk-asr")
            t.start()
            threading.Thread(target=watch_session, daemon=True, name="lc-session").start()
            _prev = signal.signal(signal.SIGINT, on_sigint)
            try:
                renderer.run_until(exit_event)  # pumps the AppKit run loop (main thread)
            finally:
                signal.signal(signal.SIGINT, _prev)
            # Give the pipeline its drain/finish time before the window closes (a
            # file run ends here, and its last translations land during the drain);
            # the daemon thread plus a short join is enough. If it hangs, force-exit.
            session_done.wait(timeout=15)
            t.join(timeout=5)
            if t.is_alive():
                os._exit(0)
        if worker_error:
            raise worker_error[0]
    finally:
        if stats is not None:
            stats.stop()


if __name__ == "__main__":
    main()
