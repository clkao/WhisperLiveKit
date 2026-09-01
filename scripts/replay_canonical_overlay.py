#!/usr/bin/env python3
"""Replay a captured canonical caption event stream through the REAL overlay
view (OverlayRenderer + OverlayDisplayModel), recording every src-row state at
the drainer's tick rate, and detect flicker:

  - shrink:   the display loses text (the model holds pure shrinks, so a
              rendered shrink means a commit/promote/reset resolved it)
  - reappear: text that vanished comes back later within the same sentence

A healthy stream shows only growth, commit flips, and promote resets.

Usage: .venv/bin/python scripts/replay_canonical_overlay.py <events.jsonl>
"""
from __future__ import annotations
import sys
from datetime import datetime

from whisperlivekit.overlay import OverlayRenderer
from whisperlivekit.overlay_model import OverlayDisplayModel
from whisperlivekit.caption_events import EventLog


def replay_canonical(path: str, hold: float = 3.5, pace: float = 0.15) -> None:
    events = EventLog.load(path).events

    r = OverlayRenderer(overlay_mode="both")

    class C:
        now = 0.0

        def __call__(self):
            return self.now

        def advance(self, s):
            self.now += s

    clk = C()
    r._model = OverlayDisplayModel(hold_sec=hold, clock=clk)

    frames = []  # (event_type, src_display, committed_len)

    def feed(e):
        now = datetime.now()
        if e.type == "transcription_provisional":
            r.partial("mic", e.text, now)
        elif e.type == "transcription_final":
            r.final("mic", [(None, e.text)], now)
        elif e.type == "translation_provisional":
            r.preview("mic", [(None, e.text)], now)
        elif e.type == "translation_final":
            r.translation("mic", [(None, e.text)], now)
        st = r._model.tick()
        if st is not None:
            frames.append((e.type, st.partial, st.partial_committed_len))
        elif frames:
            frames.append((e.type + "*", frames[-1][1], frames[-1][2]))

    for e in events:
        clk.advance(pace)
        feed(e)

    print(f"=== {len(frames)} rendered src frames from {path} ===")
    flickers = 0
    prev_full = ""
    for i in range(len(frames)):
        ty, full, _cl = frames[i]
        if not (prev_full and full and len(full) < len(prev_full)
                and prev_full.startswith(full)):
            if full:
                prev_full = full
            continue
        # shrank by losing a suffix — if that suffix re-appears soon, flicker
        vanished = prev_full[len(full):].lstrip()
        for ty2, full2, _ in frames[i + 1:i + 8]:
            if len(full2) > len(full) and (
                    full2 == prev_full or full2[len(full):].startswith(vanished)):
                print(f"  [{ty}] {prev_full!r} -> {full!r} -> reappeared as {full2!r}")
                flickers += 1
                break
        if full:
            prev_full = full
    print("src flicker events:", flickers)


if __name__ == "__main__":
    replay_canonical(sys.argv[1] if len(sys.argv) > 1 else "/tmp/canonical_zh_long_qwen3.jsonl")
