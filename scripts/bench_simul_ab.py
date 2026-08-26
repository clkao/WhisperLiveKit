#!/usr/bin/env python3
"""Simultaneous-MT A/B benchmark on the WLK pipeline (base vs simul).

Measures on real zh audio, through the real ASR + MT pipeline:
  - first-translation-time: wall-clock from feed start to the first EN line arriving.
  - MT-call-count: how many MT generate calls each variant made.
  - provisional-before-final: did the simul variant emit a provisional EN before the final?

This is the validation evidence: first-translation-time and MT-call-count
on real audio. The unit tests prove the mechanism; this proves the outcome
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
    """Run the full pipeline on one wav, return timing + call-count + RTF metrics."""
    from whisperlivekit.test_harness import TestHarness
    import os

    _mt_calls["count"] = 0
    first_translation_at: list[float] = []
    first_provisional_at: list[float] = []
    lines_seen = 0
    committed_text_parts: list[str] = []
    t0 = time.monotonic()

    def on_update(state: Any) -> None:
        nonlocal lines_seen
        for line in state.lines:
            tr = (line.get("translation") or "").strip()
            txt = (line.get("text") or "").strip()
            if tr and not first_translation_at:
                first_translation_at.append(time.monotonic() - t0)
            if txt:
                lines_seen += 1
                committed_text_parts.append(txt)
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
    wall_start = time.perf_counter()
    async with TestHarness(**kwargs) as h:
        h.on_update(on_update)
        await h.feed(audio_path, speed=0, chunk_duration=0.5)
        await h.drain(8.0)
        await h.finish(timeout=180)
    wall_elapsed = time.perf_counter() - wall_start

    # RTF = processing wall time / audio duration. speed=0 feeds as fast as the
    # pipeline accepts, so wall_elapsed is the true processing cost (not bound by
    # real-time playback).
    import soundfile as sf
    info = sf.info(audio_path)
    audio_duration = info.duration if info.duration > 0 else 1.0
    rtf = wall_elapsed / audio_duration

    return {
        "variant": "simul" if simultaneous else "serial",
        "lines": lines_seen,
        "committed_text": " ".join(committed_text_parts),
        "first_translation_s": first_translation_at[0] if first_translation_at else None,
        "first_provisional_s": first_provisional_at[0] if first_provisional_at else None,
        "mt_calls": _mt_calls["count"],
        "provisional_before_final": (
            bool(first_provisional_at and first_translation_at
                 and first_provisional_at[0] < first_translation_at[0])
        ),
        "rtf": rtf,
        "wall_s": wall_elapsed,
        "audio_s": audio_duration,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Simultaneous-MT A/B benchmark (base vs simul)")
    p.add_argument("audio", nargs="?", default=os.environ.get("ZH_BENCH_WAV", ""))
    p.add_argument("--model", default="hy-mt2-1.8b-8bit")
    p.add_argument("--reference", default=None, help="reference transcript for WER (one line of text). Omit to skip WER.")
    args = p.parse_args()

    print(f"Audio: {args.audio}")
    print(f"MT model: {args.model}")
    if args.reference:
        print(f"Reference: {args.reference}")
    print("-" * 64)

    results = []
    for simul in (False, True):
        label = "simul" if simul else "serial"
        print(f"\nRunning {label} ...")
        r = asyncio.run(run_one(args.audio, simultaneous=simul, model_id=args.model))
        # WER against the reference (ASR quality; same for both variants since the
        # ASR backend is identical — the simul flag only changes the MT path).
        if args.reference:
            from whisperlivekit.metrics import compute_wer
            wer = compute_wer(args.reference, r["committed_text"])["wer"]
            r["wer"] = wer
        results.append(r)
        print(f"  lines:               {r['lines']}")
        print(f"  first translation:   {r['first_translation_s']:.2f}s" if r['first_translation_s'] else "  first translation:   (none)")
        print(f"  first provisional:   {r['first_provisional_s']:.2f}s" if r['first_provisional_s'] else "  first provisional:   (none)")
        print(f"  MT calls:            {r['mt_calls']}")
        print(f"  provisional<final:   {r['provisional_before_final']}")
        print(f"  RTF:                 {r['rtf']:.2f}  (wall {r['wall_s']:.1f}s / audio {r['audio_s']:.1f}s)")
        if "wer" in r:
            print(f"  WER (ASR):           {r['wer']*100:.1f}%")

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
    print(f"  RTF:                 A={a['rtf']:.2f}  B={b['rtf']:.2f}")
    if "wer" in a and "wer" in b:
        print(f"  WER (ASR):           A={a['wer']*100:.1f}%  B={b['wer']*100:.1f}%  (same ASR; must match)")


if __name__ == "__main__":
    main()
