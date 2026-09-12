#!/usr/bin/env python3
"""Three-way FLEURS board via the upstream BenchmarkRunner (the `wlk bench` path).

Drives each backend through the same audio pipeline as clients (TestHarness),
with per-sample language routing, real-time feed pacing (speed=1), and the
harness's own wer/cer normalization — the protocol nemotron's #444 row used.
Subset: first 10 recordings per language from the pinned fleurs-90 manifest.
"""
import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from whisperlivekit.benchmark.datasets import load_manifest  # noqa: E402
from whisperlivekit.benchmark.runner import BenchmarkRunner  # noqa: E402

MANIFEST = REPO / "benchmarks" / "corpora" / "fleurs-90.json"
VOXTRAL_MODEL = "mlx-community/Voxtral-Mini-4B-Realtime-2602-4bit"
QWEN_MODEL = "mlx-community/Qwen3-ASR-0.6B-8bit"
N_CLIPS = 10


def subset():
    samples = load_manifest(str(MANIFEST))
    by_lang = {}
    for s in samples:
        by_lang.setdefault(s.language, []).append(s)
    return by_lang["zh"][:N_CLIPS] + by_lang["en"][:N_CLIPS]


async def run(backend, engine_kwargs, tag):
    runner = BenchmarkRunner(backend=backend, samples=subset(), speed=1,
                             warmup=True, engine_kwargs=engine_kwargs)
    report = await runner.run()
    rows = [r.to_dict() for r in report.results]
    out = Path(__file__).parent / f"harness_{tag}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
    ok = [r for r in rows if r.get("status") == "ok"]
    print(f"[{tag}] {len(ok)}/{len(rows)} ok; "
          f"zh wer={_mean(r['wer'] for r in ok if r['language']=='zh'):.4f} "
          f"cer={_mean(r['cer'] for r in ok if r['language']=='zh'):.4f} "
          f"en wer={_mean(r['wer'] for r in ok if r['language']=='en'):.4f}", flush=True)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


async def main():
    models = __import__("os").environ.get("EVAL_MODELS", "voxtral,qwen3").split(",")
    if "voxtral" in models:
        await run("voxtral-mlx", {"model_dir": VOXTRAL_MODEL}, "voxtral")
    if "qwen3" in models:
        await run("mlx-qwen3-asr", {"mlx_qwen3_asr_model": QWEN_MODEL}, "qwen3")


if __name__ == "__main__":
    asyncio.run(main())
