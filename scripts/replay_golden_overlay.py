#!/usr/bin/env python3
"""Replay a golden/captured caption event stream through the real overlay
display model and dump what the overlay shows after each event.

Ground-truth check: not what generation emits, but what the OVERLAY would
show on screen at every event — the DOM (styled spans) of the current line,
history line, and ASR source partial.

Usage:
  .venv/bin/python scripts/replay_golden_overlay.py tests/golden/zh_long_ideal.jsonl
"""
import sys
from datetime import datetime, timedelta

from whisperlivekit.caption_events import EventLog
from whisperlivekit.overlay_model import OverlayDisplayModel

EPOCH = datetime(2026, 1, 1)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, s: float) -> None:
        self.now += s


def main():
    path = sys.argv[1]
    events = EventLog.load(path).events
    clk = FakeClock()
    model = OverlayDisplayModel(hold_sec=3.5, clock=clk)
    print(f"=== {len(events)} events from {path} ===\n")
    for i, e in enumerate(events):
        t = e.type
        if t == "transcription_provisional":
            model.set_partial(e.text)
        elif t == "transcription_final":
            model.clear_partial()
        elif t == "translation_provisional":
            # started_at: approximate the utterance start from the audio time
            model.preview([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        elif t == "translation_final":
            model.translation([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        clk.advance(0.2)
        model.tick()
        snap = model.state()
        cur = "".join(sp.text for sp in snap.current)
        styles = "/".join(sp.style for sp in snap.current)
        prev = "".join(s.text for s in snap.prev)
        note = ""
        if e.type == "translation_final":
            note = "  <== FINAL lands"
        elif e.type == "translation_provisional":
            note = "  (fresh draft)" if e.fresh else "  (free release)"
        print(f"[{e.audio_t:6.2f}] {e.type:26} "
              f"cur={cur[:48]!r:52} [{styles}] "
              f"prev={prev[:30]!r} zh={snap.partial[:24]!r}{marker if (marker := '') else ''}")
        if e.type == "translation_final":
            print(f"{'':>66}^^^ final lands")


if __name__ == "__main__":
    main()
