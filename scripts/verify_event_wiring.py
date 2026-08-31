#!/usr/bin/env python3
"""End-to-end wiring check: the production pipeline emits caption events.

Runs the real AudioProcessor (via TestHarness) over an audio file with the
simul-MT layer, then verifies:
  1. The processor's EventTap produced events (display_adapter.state populated)
  2. The harness attached event-derived display state to TestState
  3. The final display state has accumulated finals (one per sentence, ideally)

Usage:
  .venv/bin/python scripts/verify_event_wiring.py [--audio PATH] [--lang zh] [--target en]
"""
import argparse
import asyncio
import json
import sys


async def run(audio: str, lang: str, target: str) -> int:
    from whisperlivekit.test_harness import TestHarness

    events = []

    def on_update(state):
        if state.display is not None:
            events.append((state.audio_position, state.display.render_summary()))

    kwargs = dict(pcm_input=True, lan=lang, target_language=target,
                  diarization=False, backend="mlx-qwen3-asr",
                  translation_backend="mlx-llm-mt", mlx_llm_mt_simultaneous=True)
    h = TestHarness(**kwargs)
    async with h:
        h.on_update(on_update)
        await h.feed(audio)
        await h.drain(3)
        await h.finish()

    st = h.state
    print("=== wiring check ===")
    print(f"processor has display_adapter: {getattr(h._processor, 'display_adapter', None) is not None}")
    print(f"processor has event_tap:       {getattr(h._processor, 'event_tap', None) is not None}")
    da = h._processor.display_adapter
    print(f"adapter state: {da.state.render_summary()}")
    print(f"final lines:   {len(da.state.final_lines)}")
    for src, tr in da.state.final_lines:
        print(f"  [src] {src[:60]}")
        print(f"  [tgt] {tr[:60]}")
    print(f"states with display attached: {sum(1 for s in h.history if s.display is not None)}/{len(h.history)}")
    if events:
        print(f"last 3 display summaries:")
        for pos, summ in events[-3:]:
            print(f"  [{pos:6.1f}s] {summ}")
    ok = len(da.state.final_lines) > 0
    print(f"\nverdict: {'WIRED' if ok else 'NOT WIRED (no finals accumulated)'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default="/Users/clkao/git/asr/_work/zh_long.wav")
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--target", default="en")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args.audio, args.lang, args.target)))


if __name__ == "__main__":
    main()
