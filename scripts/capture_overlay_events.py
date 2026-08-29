#!/usr/bin/env python3
"""Capture the overlay event stream from zh_long.wav and replay it frame-by-frame.

Runs the WLK pipeline (qwen3-asr + simul MT) on zh_long.wav as a file source,
captures provisional/final events into an OverlayEventLog, then replays them
showing what the overlay SHOULD render at each step (the desired frame-by-frame
rendering). This is the reference for tuning the overlay display logic.

Usage:
  .venv/bin/python scripts/capture_overlay_events.py
  .venv/bin/python scripts/capture_overlay_events.py --replay /tmp/zh_en_events.jsonl
"""
from __future__ import annotations
import argparse, json, sys, time
from datetime import datetime
from pathlib import Path

import numpy as np


def capture(out_path: str, audio_path: str = "/Users/clkao/git/asr/_work/zh_long.wav") -> None:
    """Run the pipeline on the wav and capture events."""
    from mlx_audio.stt.utils import load_audio
    audio = np.asarray(load_audio(audio_path, 16000), dtype=np.float32)

    from whisperlivekit.overlay_events import OverlayEventLog
    from whisperlivekit.overlay_model import OverlayDisplayModel, PROVISIONAL, FINAL_SAME, FINAL_ADD

    log = OverlayEventLog()
    hold = 3.5
    model = OverlayDisplayModel(hold_sec=hold, clock=time.monotonic)

    # We need to drive the ASR + MT and feed events to the model.
    # Use the TestHarness (same as lc_terminal's file path).
    import asyncio, types

    async def run():
        from whisperlivekit.test_harness import TestHarness

        class CaptureSink:
            """Sink that feeds events into the overlay model + event log."""
            def __init__(self):
                self._log = log
                self._model = model
                self._seen_finals: set = set()  # deduplicate finals by (text, idx)
                self._last_prov = ""

            def __call__(self, state):
                partial = (state.buffer_transcription or "").strip()
                if partial:
                    self._model.set_partial(partial)
                prov = (state.buffer_translation or "").strip()
                if prov and prov != self._last_prov:
                    self._last_prov = prov
                    now = datetime.now()
                    self._log.record_preview([(None, prov)], now)
                    self._model.preview([(None, prov)], now)
                for i, line in enumerate(state.lines):
                    tr = (line.get("translation") or "").strip()
                    if tr and (i, tr) not in self._seen_finals:
                        self._seen_finals.add((i, tr))
                        now = datetime.now()
                        self._log.record_final([(None, tr)], now)
                        self._model.translation([(None, tr)], now)

            def on_update(self, state):
                self(state)

        kwargs = {
            "lan": "zh", "pcm_input": True, "backend": "mlx-qwen3-asr",
            "target_language": "en", "translation_backend": "mlx-llm-mt",
            "mlx_llm_mt_model": "hy-mt2-1.8b-8bit",
            "mlx_llm_mt_simultaneous": True,
            "mlx_llm_mt_simul_commit": "mass",
            "pause_segmentation_seconds": 0.1,
            "diarization": False,
            "mlx_qwen3_asr_model": "mlx-community/Qwen3-ASR-0.6B-8bit",
            "mlx_qwen3_asr_second_pass": True,
        }
        async with TestHarness(**kwargs) as h:
            sink = CaptureSink()
            h.on_update(sink)
            await h.feed(audio_path, speed=1.0)
            await h.drain(3.0)
            await h.finish(timeout=60)

    asyncio.run(run())
    log.save(out_path)
    print(f"captured {len(log.events())} events -> {out_path}", file=sys.stderr)

    # replay
    replay(out_path)


def common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def replay(log_path: str) -> None:
    events = []
    for line in Path(log_path).read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    if not events:
        print("no events"); return

    t0 = events[0]["wallclock"]
    hold = 3.5
    # two-layer state (what the viewer sees)
    current_text = ""      # what's on the current row
    current_is_final = False
    prev_text = ""         # the prev (history) row
    prev_at = 0.0
    shown_provisional = ""

    print(f"=== replaying {len(events)} events from {log_path} ===\n")
    for e in events:
        dt = e["wallclock"] - t0
        kind = e["kind"]
        plain = e["plain"]
        if plain.startswith("[S"):
            plain = plain.split("] ", 1)[1] if "] " in plain else plain

        if kind == "provisional":
            if plain == shown_provisional:
                continue  # skip-render
            tag = "APPEND" if shown_provisional and plain.startswith(shown_provisional) else "REWRITE"
            shown_provisional = plain
            current_text = plain
            current_is_final = False
            color = "dim"
        else:  # final
            tag = "FINAL"
            if current_text and not current_is_final:
                # provisional -> final: same utterance, replace in place
                tag = "FINAL(promote)"
            elif current_text and current_is_final:
                # new utterance: scroll current up to prev
                prev_text = current_text
                prev_at = e["wallclock"]
            current_text = plain
            current_is_final = True
            shown_provisional = ""
            color = "white/green"

        # what the viewer sees
        print(f"+{dt:5.2f}s {tag:16s} | [{color}] {current_text[:80]}")
        if prev_text:
            print(f"         {'':16s} | [prev]   {prev_text[:80]}")

    print(f"\n=== done ===")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--replay", default=None, help="replay an existing JSONL log")
    p.add_argument("--out", default="/tmp/zh_en_events.jsonl")
    args = p.parse_args()
    if args.replay:
        replay(args.replay)
    else:
        capture(args.out)
