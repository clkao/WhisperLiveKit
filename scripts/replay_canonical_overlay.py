#!/usr/bin/env python3
"""Replay a recorded caption event stream through the display model and print
the reader-visible caption sequence.

This is the model-level replay instrument: it drives ``CaptionDisplay`` through
its ``EventSink`` entry point (``emit``) with the recorded events, on a
deterministic clock, and traces the two caption lines as the hold-drain
releases queued sentences. Use it to check what a viewer would see: sentence
pacing, dim/bright transitions, and whether completed sentences display before
the stream ends. No view code and no real time involved, so the trace is
reproducible.

A captured stream (``--event-log``) and the display tests
(``tests/test_caption_display.py``, ``tests/test_overlay_replay.py``) are the
regression pair: the tests assert the rules, this script shows the sequence.

Usage:
  python scripts/replay_canonical_overlay.py [events.jsonl] [--hold SECONDS]
      [--pace SECONDS] [--drain SECONDS]

The default events file is the checked-in ``tests/golden/zh_long_canonical.jsonl``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from whisperlivekit.caption_display import (
    PROVISIONAL,
    CaptionDisplay,
    DisplayState,
    load_caption_events,
)

DEFAULT_EVENTS = Path(__file__).resolve().parent.parent / "tests" / "golden" / "zh_long_canonical.jsonl"


class _Clock:
    """Deterministic seconds counter: the replay advances it per event."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _line(state: DisplayState) -> str:
    """Render one display state as the trace line (current + history above)."""
    current = "".join(span.text for span in state.current)
    previous = "".join(span.text for span in state.prev)
    if not current:
        tag = "empty "
    elif all(span.style == PROVISIONAL for span in state.current):
        tag = "dim   "
    else:
        tag = "BRIGHT"
    line = f"[{tag}] {current!r}"
    if previous:
        line += f"  (above: {previous!r})"
    if state.partial:
        line += f"  (src: {state.partial!r})"
    return line


def replay(path, hold: float = 3.5, pace: float = 0.3, drain_seconds: float = 30.0):
    """Replay `path` and return the (elapsed, event type, line) trace.

    Every event is emitted, then the drainer is ticked; after the stream ends
    the drainer keeps running for `drain_seconds` — the reader's clock does not
    stop, so queued sentences must still surface.
    """
    clock = _Clock()
    model = CaptionDisplay(hold_sec=hold, clock=clock)
    trace = []

    def tick(event_type: str) -> None:
        model.tick()
        trace.append((clock.now, event_type, _line(model.state())))

    for event in load_caption_events(path):
        clock.advance(pace)
        model.emit(event)
        tick(event.type)

    steps = int(drain_seconds / pace)
    for _ in range(steps):
        clock.advance(pace)
        tick("drain")

    return trace


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("events", nargs="?", default=str(DEFAULT_EVENTS),
                        help="recorded caption event JSONL (default: the checked-in golden)")
    parser.add_argument("--hold", type=float, default=3.5,
                        help="caption hold in seconds (default: 3.5)")
    parser.add_argument("--pace", type=float, default=0.3,
                        help="replay seconds advanced per event (default: 0.3)")
    parser.add_argument("--drain", type=float, default=30.0,
                        help="seconds of drainer after the last event (default: 30)")
    args = parser.parse_args(argv)

    path = Path(args.events)
    if not path.exists():
        print(f"no such event stream: {path}", file=sys.stderr)
        return 1

    trace = replay(path, hold=args.hold, pace=args.pace, drain_seconds=args.drain)

    print(f"=== reader-visible caption sequence: {path} ===")
    last = None
    for elapsed, event_type, line in trace:
        if line == last:
            continue  # the reader sees no change: skip it in the trace
        last = line
        print(f"  [+{elapsed:7.2f}] {event_type:24s} {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
