#!/usr/bin/env python3
"""en ASR A/B: qwen3-asr (via StableCommitTransform wrapper) vs nemotron.

Uses the real wrapper chain (AsrWrapper + StableCommitTransform) so qwen3's
simulated provisional emission is exercised — not the bare processor.
One model per subprocess so GPU memory is fully freed between runs.
Usage: python scripts/bench_en_asr_ab.py [audio_path]
"""
import json, subprocess, sys, os

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "/Users/clkao/git/asr/_work/demo_en_30s.wav"

RUNNER = r'''
import time, numpy as np, json, sys
from mlx_audio.stt.utils import load_audio

audio = np.asarray(load_audio({AUDIO!r}, 16000), dtype=np.float32)
CH = 8000
backend = {backend!r}

def drain(proc, label, t0):
    """Run the streaming loop, record first-commit time and committed text."""
    first = None
    committed = []
    for off in range(0, len(audio), CH):
        proc.insert_audio_chunk(audio[off:off+CH], (off+CH)/16000)
        toks, _ = proc.process_iter()
        if toks and first is None:
            first = time.perf_counter() - t0
        committed.extend(toks)
    toks, _ = proc.finish()
    committed.extend(toks)
    return first, committed

if backend == "qwen3":
    # Use the REAL wrapper chain from online_factory (StableCommitTransform).
    from whisperlivekit.asr_mlx_qwen3 import MlxQwen3AsrOnlineProcessor
    from whisperlivekit.asr_commit import StableCommitTransform
    from whisperlivekit.asr_wrapper import AsrWrapper
    import types
    cfg = types.SimpleNamespace(
        model_id="mlx-community/Qwen3-ASR-0.6B-8bit", language="en",
        hotwords="", chunk_size_sec=0.5, max_context_sec=30.0,
        finalization_mode="accuracy", sep="", two_pass=False,
        backend="mlx-qwen3-asr",
        mlx_qwen3_asr_hold_back_units=6, mlx_qwen3_asr_stable_iterations=2,
    )
    # Build a shared backend object with the cfg baked in (online_factory shape).
    class _Shared:
        def __init__(self, c): 
            for k,v in c.__dict__.items(): setattr(self,k,v)
    t0 = time.perf_counter()
    proc = MlxQwen3AsrOnlineProcessor(_Shared(cfg))
    proc = AsrWrapper(proc, transforms=[StableCommitTransform(
        hold_back_units=6, stable_iterations=2)])
    load = time.perf_counter() - t0
    t0 = time.perf_counter()
    first, committed = drain(proc, "qwen3", t0)
    wall = time.perf_counter() - t0
    text = "".join(getattr(t, "text", str(t)) for t in committed)
    # count commits during streaming (before finish)
    n_stream = sum(1 for t in committed)
    out = dict(load=load, first=first, wall=wall, rtf=wall/(len(audio)/16000),
               text=text, n_commits=n_stream,
               first_tokens=[(round(getattr(t,"start",0),2), getattr(t,"text",str(t))) for t in committed[:6]])
elif backend == "nemotron":
    from whisperlivekit.asr_nemotron_mlx import NemotronMLXASR, NemotronMLXOnlineProcessor
    t0 = time.perf_counter()
    asr = NemotronMLXASR(lan="en", nemotron_mlx_asr_model="mlx-community/nemotron-3.5-asr-streaming-0.6b")
    proc = NemotronMLXOnlineProcessor(asr)
    load = time.perf_counter() - t0
    t0 = time.perf_counter()
    first, committed = drain(proc, "nemotron", t0)
    wall = time.perf_counter() - t0
    text = "".join(getattr(t, "text", str(t)) for t in committed)
    n_stream = sum(1 for t in committed)
    out = dict(load=load, first=first, wall=wall, rtf=wall/(len(audio)/16000),
               text=text, n_commits=n_stream,
               first_tokens=[(round(getattr(t,"start",0),2), getattr(t,"text",str(t))) for t in committed[:6]])
print("RESULT:" + json.dumps(out))
'''

def run(backend):
    code = RUNNER.format(AUDIO=AUDIO, backend=backend)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT:"):
            return json.loads(line[7:])
    print("STDERR:", r.stderr[-1000:]); return None

print(f"audio: {AUDIO}\n")
for b in ["qwen3", "nemotron"]:
    print(f"=== {b} (en, with wrapper chain) ===")
    res = run(b)
    if res:
        first = res["first"]
        first_s = f"{first:.1f}s" if first is not None else "n/a"
        print(f"  load: {res['load']:.1f}s  first-commit: {first_s}  wall: {res['wall']:.1f}s  RTF: {res['rtf']:.2f}")
        print(f"  commits: {res['n_commits']}")
        print(f"  text: {res['text'][:240]}")
        print(f"  first 6 commits: {res['first_tokens']}")
    print()
