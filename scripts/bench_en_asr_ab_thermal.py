#!/usr/bin/env python3
"""Simplistic en ASR A/B: qwen3-asr vs nemotron, thermal-safe.

- Interleaved A/B (not batched) so thermal state doesn't favor one backend.
- First run of each backend is warmup (discarded).
- Short sleep between runs for thermal relaxation.
- One model per subprocess (GPU memory freed between runs).
- Reports median of the measured trials.

Usage: python scripts/bench_en_asr_ab_thermal.py [audio_path] [trials_per_backend]
"""
import json, subprocess, sys, os, time, statistics

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "/Users/clkao/git/asr/_work/demo_en_30s.wav"
TRIALS = int(sys.argv[2]) if len(sys.argv) > 2 else 3  # per backend; first is warmup
SLEEP_S = 3.0  # thermal relaxation between runs

RUNNER = r'''
import time, numpy as np, json, sys
from mlx_audio.stt.utils import load_audio

audio = np.asarray(load_audio({AUDIO!r}, 16000), dtype=np.float32)
CH = 8000
backend = {backend!r}

def drain(proc, t0):
    first = None
    n = 0
    for off in range(0, len(audio), CH):
        proc.insert_audio_chunk(audio[off:off+CH], (off+CH)/16000)
        toks, _ = proc.process_iter()
        if toks and first is None:
            first = time.perf_counter() - t0
        n += len(toks)
    toks, _ = proc.finish()
    n += len(toks)
    return first, n

if backend == "qwen3":
    from whisperlivekit.asr_mlx_qwen3 import MlxQwen3AsrOnlineProcessor
    from whisperlivekit.asr_commit import StableCommitTransform
    from whisperlivekit.asr_wrapper import AsrWrapper
    import types
    cfg = types.SimpleNamespace(
        model_id="mlx-community/Qwen3-ASR-0.6B-8bit", language="en",
        hotwords="", chunk_size_sec=2.0, max_context_sec=30.0,
        finalization_mode="accuracy", sep="", two_pass=False, backend="mlx-qwen3-asr",
    )
    class _Shared:
        def __init__(self, c):
            for k,v in c.__dict__.items(): setattr(self,k,v)
    t0 = time.perf_counter()
    proc = MlxQwen3AsrOnlineProcessor(_Shared(cfg))
    proc = AsrWrapper(proc, transforms=[StableCommitTransform(hold_back_units=6, stable_iterations=2)])
    load = time.perf_counter() - t0
    t0 = time.perf_counter()
    first, n_commits = drain(proc, t0)
    wall = time.perf_counter() - t0
    out = dict(load=load, first=first, wall=wall, rtf=wall/(len(audio)/16000), n_commits=n_commits)
elif backend == "nemotron":
    from whisperlivekit.asr_nemotron_mlx import NemotronMLXASR, NemotronMLXOnlineProcessor
    t0 = time.perf_counter()
    asr = NemotronMLXASR(lan="en", nemotron_mlx_asr_model="mlx-community/nemotron-3.5-asr-streaming-0.6b")
    proc = NemotronMLXOnlineProcessor(asr)
    load = time.perf_counter() - t0
    t0 = time.perf_counter()
    first, n_commits = drain(proc, t0)
    wall = time.perf_counter() - t0
    out = dict(load=load, first=first, wall=wall, rtf=wall/(len(audio)/16000), n_commits=n_commits)
print("RESULT:" + json.dumps(out))
'''

def run(backend):
    code = RUNNER.format(AUDIO=AUDIO, backend=backend)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT:"):
            return json.loads(line[7:])
    print("STDERR:", r.stderr[-800:]); return None

# Interleaved: q, n, q, n, q, n ... (first of each = warmup)
backends = ["qwen3", "nemotron"]
sequence = []
for i in range(TRIALS):
    for b in backends:
        sequence.append(b)

print(f"audio: {AUDIO}")
print(f"trials per backend: {TRIALS} (first is warmup), interleaved, {SLEEP_S}s sleep between")
print(f"sequence: {sequence}\n")

results = {b: [] for b in backends}
for i, b in enumerate(sequence):
    tag = "warmup" if i < 2 else "measured"
    print(f"[{i+1}/{len(sequence)}] {b} ({tag})...", end=" ", flush=True)
    res = run(b)
    if res:
        first = f"{res['first']:.1f}s" if res['first'] is not None else "n/a"
        print(f"wall={res['wall']:.1f}s RTF={res['rtf']:.2f} first={first} commits={res['n_commits']}")
        if i >= 2:  # skip warmups
            results[b].append(res)
    else:
        print("FAILED")
    if i < len(sequence) - 1:
        time.sleep(SLEEP_S)

print("\n=== summary (warmup discarded, median of measured) ===")
for b in backends:
    trials = results[b]
    if not trials:
        print(f"{b}: no measured trials"); continue
    walls = [t["wall"] for t in trials]
    rtfs = [t["rtf"] for t in trials]
    firsts = [t["first"] for t in trials if t["first"] is not None]
    nc = [t["n_commits"] for t in trials]
    med = statistics.median
    first_med = f"{med(firsts):.1f}s" if firsts else "n/a"
    print(f"{b:10}: wall={med(walls):.1f}s  RTF={med(rtfs):.2f}  first-commit={first_med}  commits={med(nc):.0f}  (n={len(trials)})")
    print(f"{'':>12} walls={[f'{w:.1f}' for w in walls]}  rtfs={[f'{r:.2f}' for r in rtfs]}")
