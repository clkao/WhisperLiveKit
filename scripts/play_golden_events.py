#!/usr/bin/env python3
"""Play a golden event stream through the actual TUI/overlay renderers.

Feeds the ideal events directly to the renderer methods (partial/preview/
final/translation), paced by audio_t so it plays in real time. This shows
what the IDEAL output looks like in the real display surfaces — decoupled
from generation (no ASR/MT running, just the golden events driving the
display). The point: see the target UX, compare to what the live pipeline
produces.

Usage:
  .venv/bin/python scripts/play_golden_events.py tests/golden/zh_long_ideal.jsonl
  .venv/bin/python scripts/play_golden_events.py tests/golden/demo_en_30s_ideal.jsonl --overlay
"""
from __future__ import annotations
import argparse, sys, time
from datetime import datetime

def play(path: str, overlay: bool, speed: float = 1.0, plain: bool = False) -> None:
    from whisperlivekit.caption_events import EventLog
    events = EventLog.load(path).events
    if not events:
        print("no events"); return

    if plain:
        _play_plain(events, speed, path)
        return

    # Build the renderer (TUI, optionally + overlay via MultiRenderer).
    from whisperlivekit.tui import TuiRenderer, MultiRenderer
    tui = TuiRenderer()
    renderer = tui
    if overlay:
        try:
            from whisperlivekit.overlay import OverlayRenderer
            ov = OverlayRenderer()
            renderer = MultiRenderer(terminal=tui, overlay=ov)
        except Exception as e:
            print(f"(overlay unavailable: {e}; TUI only)", file=sys.stderr)

    print(f"=== playing {len(events)} ideal events from {path} ===", file=sys.stderr)
    print(f"(paced by audio_t at {speed}x; Ctrl-C to stop)", file=sys.stderr)

    t0_audio = events[0].audio_t
    t0_wall = time.perf_counter()
    for e in events:
        target = t0_wall + (e.audio_t - t0_audio) / speed
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
        started_at = datetime.now()
        if e.type == "transcription_provisional":
            renderer.partial("mic", e.text, started_at)
        elif e.type == "transcription_final":
            renderer.final("mic", [(None, e.text)], started_at)
        elif e.type == "translation_provisional":
            renderer.preview("mic", [(None, e.text)], started_at)
        elif e.type == "translation_final":
            renderer.translation("mic", [(None, e.text)], started_at)
    time.sleep(1.0)
    print("\n=== done ===", file=sys.stderr)


def _play_plain(events, speed: float, path: str) -> None:
    """Plain-text render: print the display state after each event.

    Shows what the display SHOULD render at each step — the partial lines
    (rolling) and the accumulated finals — without a TTY/rich dependency.
    """
    from whisperlivekit.display_adapter import DisplayAdapter
    ad = DisplayAdapter()
    t0_audio = events[0].audio_t
    t0_wall = time.perf_counter()
    print(f"=== ideal output: {path} ({len(events)} events, {speed}x) ===\n")
    for e in events:
        target = t0_wall + (e.audio_t - t0_audio) / speed
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
        ad.feed(e)
        # Render: finals (one per line), then the current provisional.
        print(f"\r[{e.audio_t:5.1f}s] {e.type:26} ", end="")
        tag = ""
        if e.type == "translation_provisional":
            tag = f" (fresh={e.fresh})"
        print(f"{e.text[:48]!r}{tag}")
        # Show the display state: accumulated finals + current provisional.
        for i, fl in enumerate(ad.state.final_lines, 1):
            print(f"         final {i}: {fl[:70]}")
        if ad.state.partial_translation:
            print(f"         [prov] {ad.state.partial_translation[:70]}")
        if ad.state.partial_transcription:
            print(f"         [asr]   {ad.state.partial_transcription[:70]}")
    print("\n=== done ===")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--overlay", action="store_true", help="also drive the overlay (needs AppKit/main thread)")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--plain", action="store_true", help="plain-text render (no TTY/rich)")
    args = ap.parse_args()
    play(args.path, args.overlay, args.speed, args.plain)

if __name__ == "__main__":
    main()
