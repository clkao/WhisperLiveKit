#!/usr/bin/env python3
"""Visualize a caption event stream as a timeline strip.

Renders a horizontal timeline (audio_t on x-axis) with one row per event
type, showing each event as a glyph + truncated text. The goal is to make
the generation sequence scannable: you can see drafts grow into finals,
spot fragment-final flicker, and see where drafts and finals land in time.

Usage:
  .venv/bin/python scripts/visualize_events.py /tmp/zh_en_events.jsonl
  .venv/bin/python scripts/visualize_events.py /tmp/zh_en_events.jsonl --golden tests/golden/zh_long_ideal.jsonl
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from whisperlivekit.caption_events import EventLog

# Row order (top to bottom). translation_provisional split into call/release would add a row.
ROWS = ["transcription_partial", "transcription_final", "translation_provisional", "translation_final"]
GLYPH = {"transcription_partial": "·", "transcription_final": "▌", "translation_provisional": "○", "translation_final": "█"}


def truncate(s: str, n: int = 22) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def render(events, width: int = 120, label: str = "") -> None:
    if not events:
        print(f"{label}(no events)")
        return
    t_min = min(e.audio_t for e in events)
    t_max = max(e.audio_t for e in events) or 1.0
    span = t_max - t_min
    print(f"=== {label or 'events'} ({len(events)} events, {t_min:.1f}-{t_max:.1f}s) ===")
    for row in ROWS:
        row_events = [e for e in events if e.type == row]
        if not row_events:
            continue
        # Build a line: position glyphs by audio_t, then stack text labels.
        line = [" "] * width
        labels = []  # (col, text)
        for e in row_events:
            col = int((e.audio_t - t_min) / span * (width - 1))
            col = max(0, min(width - 1, col))
            line[col] = GLYPH.get(row, "?")
            labels.append((col, truncate(e.text)))
        # Collapse the glyph line, then print labels below it on a sub-line.
        glyph_line = "".join(line)
        print(f"{row:10} {glyph_line}")
        # Labels: place each at its column, skipping overlaps naively.
        if labels:
            label_line = [" "] * width
            occupied_until = -100
            for col, txt in sorted(labels, key=lambda x: x[0]):
                start = max(col, min(occupied_until + 1, width - len(txt)))
                if start + len(txt) > width:
                    start = width - len(txt)
                if start < 0:
                    continue
                label_line[start : start + len(txt)] = list(txt)
                occupied_until = start + len(txt) + 1
            print(f"{'':10} {(''.join(label_line)).rstrip()}")
    print(f"{'':10} {'─'*width}")
    # x-axis ticks
    axis = [" "] * width
    for s in range(int(t_min), int(t_max) + 1, max(1, int(span // 6))):
        col = int((s - t_min) / span * (width - 1))
        if 0 <= col < width:
            axis[col] = "|"
    print(f"{'audio_t (s)':10} {''.join(axis)}")
    print(f"{'legend':10} · transcription_partial  ▌ transcription_final  ○ translation_provisional  █ translation_final")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--golden", default=None)
    ap.add_argument("--width", type=int, default=120)
    args = ap.parse_args()
    events = EventLog.load(args.path).events
    render(events, args.width, label=args.path.split("/")[-1])
    if args.golden:
        print()
        golden = EventLog.load(args.golden).events
        render(golden, args.width, label=args.golden.split("/")[-1] + " (golden)")


if __name__ == "__main__":
    main()
