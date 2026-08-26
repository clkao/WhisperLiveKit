#!/usr/bin/env python3
"""Simultaneous-MT A/B benchmark on the WLK pipeline (Tier A vs Tier B).

Measures on real zh audio, through the real ASR + MT pipeline:
  - first-translation-time: wall-clock from feed start to the first EN line arriving.
  - MT-call-count: how many MT generate calls each variant made.
  - provisional-before-final: did Tier B emit a provisional EN before the final?

This is the live validation evidence for the Tier B task's AC-2 and AC-3
(the ensign's unit tests prove the mechanism; this proves the outcome on
real audio).

Run on CL's Mac (needs the model cache + Metal):
  .venv/bin/python scripts/bench_simul_ab.py /path/to/zh.wav

Prereq: hand-install the working combo first:
  uv pip install --python .venv/bin/python 'huggingface_hub==1.18.0' 'transformers==5.11.0'
"""
from __future__ import annotations

import argparse
import asyncio
import time
from typing import Any

# Patch _translate_text to count MT calls before importing the backends.
import whisperlivekit.translation_mlx_llm_mt as _mt_base
import whisperlivekit.translation_mlx_llm_mt_simul as _mt_simul

_mt_calls = {"count": 0}
_orig_translate_text = _mt_base.MlxLlmTranslation._translate_text


def _counting_translate_text(self, text, **kw):
    _mt_calls["count"] += 1
    return _orig_translate_text(self, text, **kw)


_mt_base.MlxLlmTranslation._translate_text = _counting_translate_text


async def run_one(audio_path: str, simultaneous: bool, model_id: str) -> dict:
    """Run the full pipeline on one wav, return timing + call-count metrics."""
    from whisperlivekit.test_harness import TestHarness

    _mt_calls["count"] = 0
    first_translation_at: list[float] = []
    first_provisional_at: list[float] = []
    lines_seen = 0
    t0 = time.monotonic()

    def on_update(state: Any) -> None:
        nonlocal lines_seen
        # A "line" with a translation is a finalized EN caption.
        for line in state.lines:
            tr = (line.get("translation") or "").strip()
            txt = (line.get("text") or "").strip()
            if tr and not first_translation_at:
                first_translation_at.append(time.monotonic() - t0)
            if txt:
                lines_seen += 1
        # buffer_translation is the live provisional (Tier B drafts over the tail).
        bt = (getattr(state, "buffer_translation", "") or "").strip()
        if bt and not first_provisional_at:
            first_provisional_at.append(time.monotonic() - t0)

    kwargs = {
        "lan": "zh",
        "pcm_input": True,
        "backend": "mlx-qwen3-asr",
        "mlx_qwen3_asr_model": "mlx-community/Qwen3-ASR-0.6B-8bit",
        "target_language": "en",
        "translation_backend": "mlx-llm-mt",
        "mlx_llm_mt_model": model_id,
        "mlx_llm_mt_simultaneous": simultaneous,
        "diarization": False,
    }
    async with TestHarness(**kwargs) as h:
        h.on_update(on_update)
        await h.feed(audio_path, speed=0, chunk_duration=0.5)
        await h.drain(8.0)
        await h.finish(timeout=180)

    return {
        "variant": "Tier B (simul)" if simultaneous else "Tier A (serial)",
        "lines": lines_seen,
        "first_translation_s": first_translation_at[0] if first_translation_at else None,
        "first_provisional_s": first_provisional_at[0] if first_provisional_at else None,
        "mt_calls": _mt_calls["count"],
        "provisional_before_final": (
            bool(first_provisional_at and first_translation_at
                 and first_provisional_at[0] < first_translation_at[0])
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Simultaneous-MT A/B benchmark (Tier A vs Tier B)")
    p.add_argument("audio", nargs="?", default="/Users/clkao/git/asr/_work/zh_long.wav")
    p.add_argument("--model", default="hy-mt2-1.8b-8bit")
    args = p.parse_args()

    print(f"Audio: {args.audio}")
    print(f"MT model: {args.model}")
    print("-" * 64)

    results = []
    for simul in (False, True):
        label = "Tier B (simul)" if simul else "Tier A (serial)"
        print(f"\nRunning {label} ...")
        r = asyncio.run(run_one(args.audio, simultaneous=simul, model_id=args.model))
        results.append(r)
        print(f"  lines:               {r['lines']}")
        print(f"  first translation:   {r['first_translation_s']:.2f}s" if r['first_translation_s'] else "  first translation:   (none)")
        print(f"  first provisional:   {r['first_provisional_s']:.2f}s" if r['first_provisional_s'] else "  first provisional:   (none)")
        print(f"  MT calls:            {r['mt_calls']}")
        print(f"  provisional<final:   {r['provisional_before_final']}")

    print("\n" + "=" * 64)
    print("COMPARISON")
    print("=" * 64)
    a, b = results
    if a["first_translation_s"] and b["first_translation_s"]:
        delta = a["first_translation_s"] - b["first_translation_s"]
        print(f"  first-translation:  A={a['first_translation_s']:.2f}s  B={b['first_translation_s']:.2f}s  (B is {delta:+.2f}s vs A)")
    if a["mt_calls"] and b["mt_calls"]:
        print(f"  MT calls:            A={a['mt_calls']}  B={b['mt_calls']}  (B is {b['mt_calls'] - a['mt_calls']:+d} vs A)")
    print(f"  provisional-before-final: A={a['provisional_before_final']}  B={b['provisional_before_final']}")


if __name__ == "__main__":
    main()
