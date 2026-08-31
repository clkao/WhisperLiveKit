#!/usr/bin/env python3
"""E2E ASR+MT benchmark: qwen3-asr vs nemotron, en→zh and zh→en.

Drives the real pipeline: ASR backend (with StableCommitTransform for qwen3)
feeds committed ASRTokens + HypothesisTail to MlxLlmTranslationSimul (AlignAtt
commit policy). Records provisional/final MT timing and text.

Thermal-safe: interleaved A/B, warmup discarded, sleep between runs.
One (ASR, MT) combo per subprocess so GPU memory is freed.

Usage: python scripts/bench_e2e_asr_mt.py [trials_per_combo]
"""
import json, subprocess, sys, os, time, statistics

TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 3  # per combo; first is warmup
SLEEP_S = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0  # thermal relaxation between runs

# (label, audio, src_lang, tgt_lang)
COMBOS = [
    ("en->zh qwen3",    "/Users/clkao/git/asr/_work/demo_en_30s.wav", "en", "zh", "qwen3"),
    ("en->zh nemotron", "/Users/clkao/git/asr/_work/demo_en_30s.wav", "en", "zh", "nemotron"),
    ("zh->en qwen3",    "/Users/clkao/git/asr/_work/zh_long.wav",    "zh", "en", "qwen3"),
    ("zh->en nemotron", "/Users/clkao/git/asr/_work/zh_long.wav",    "zh", "en", "nemotron"),
]

RUNNER = r'''
import time, numpy as np, json, sys
from mlx_audio.stt.utils import load_audio
from whisperlivekit.timed_objects import ASRToken, HypothesisTail, Transcript

audio = np.asarray(load_audio({AUDIO!r}, 16000), dtype=np.float32)
CH = 8000
backend = {backend!r}
src = {src!r}
tgt = {tgt!r}

# --- build ASR ---
if backend == "qwen3":
    from whisperlivekit.asr_mlx_qwen3 import MlxQwen3AsrOnlineProcessor
    from whisperlivekit.asr_commit import StableCommitTransform
    from whisperlivekit.asr_wrapper import AsrWrapper
    import types
    cfg = types.SimpleNamespace(
        model_id="mlx-community/Qwen3-ASR-0.6B-8bit", language=src,
        hotwords="", chunk_size_sec=2.0, max_context_sec=30.0,
        finalization_mode="accuracy", sep="", two_pass=False, backend="mlx-qwen3-asr",
    )
    class _Shared:
        def __init__(self, c):
            for k,v in c.__dict__.items(): setattr(self,k,v)
    asr = AsrWrapper(MlxQwen3AsrOnlineProcessor(_Shared(cfg)),
        transforms=[StableCommitTransform(hold_back_units=6, stable_iterations=2)])
elif backend == "nemotron":
    from whisperlivekit.asr_nemotron_mlx import NemotronMLXASR, NemotronMLXOnlineProcessor
    asr = NemotronMLXOnlineProcessor(NemotronMLXASR(lan=src, nemotron_mlx_asr_model="mlx-community/nemotron-3.5-asr-streaming-0.6b"))

# --- build MT (simul) ---
from whisperlivekit.translation_mlx_llm_mt_simul import MlxLlmTranslationSimul
mt = MlxLlmTranslationSimul(model_id="hy-mt2-1.8b-8bit", target_language=tgt,
    source_language=src, commit_mode="mass", mass_threshold=0.5)
simul_active = getattr(mt, "_simul_active", False)

provisionals = []
finals = []
first_prov_t = None
first_final_t = None

t0 = time.perf_counter()
for off in range(0, len(audio), CH):
    asr.insert_audio_chunk(audio[off:off+CH], (off+CH)/16000)
    toks, end = asr.process_iter()
    # Build items: committed tokens + hypothesis tail
    items = list(toks)
    buf = asr.get_buffer()  # Transcript with unstable tail
    tail_text = getattr(buf, "text", "") or ""
    if tail_text.strip():
        items.append(HypothesisTail(start=None, end=getattr(buf,"end",end), text=tail_text))
    if items:
        mt.insert_tokens(items)
    tr, buf = mt.process()
    if tr is not None and tr.text and tr.text.strip():
        # final
        finals.append((round(time.perf_counter()-t0,2), tr.text))
        if first_final_t is None:
            first_final_t = time.perf_counter() - t0
    elif buf is not None and getattr(buf, "text", "") and getattr(buf,"text","").strip():
        # provisional (translation=None, buffer has the draft)
        provisionals.append((round(time.perf_counter()-t0,2), buf.text))
        if first_prov_t is None:
            first_prov_t = time.perf_counter() - t0

# finalize
toks, end = asr.finish()
if toks:
    mt.insert_tokens(list(toks))
tr, buf = mt.process()
if tr is not None and tr.text and tr.text.strip():
    finals.append((round(time.perf_counter()-t0,2), tr.text))
    if first_final_t is None:
        first_final_t = time.perf_counter() - t0
elif buf is not None and getattr(buf, "text", "") and getattr(buf,"text","").strip():
    provisionals.append((round(time.perf_counter()-t0,2), buf.text))
    if first_prov_t is None:
        first_prov_t = time.perf_counter() - t0

wall = time.perf_counter() - t0
# Free GPU memory before the subprocess exits so the next run starts clean.
try:
    import mlx.core as _mx
    _mx.metal.clear_cached_memory()
except Exception:
    pass
out = dict(
    wall=wall, rtf=wall/(len(audio)/16000),
    simul_active=simul_active,
    n_finals=len(finals), n_provs=len(provisionals),
    first_final=first_final_t, first_prov=first_prov_t,
    finals=[(t, x[:80]) for t,x in finals[:4]],
    provs=[(t, x[:80]) for t,x in provisionals[:4]],
    asr_text="".join(getattr(t,"text","") for t in toks)[-120:],
)
print("RESULT:" + json.dumps(out))
'''

def run(combo):
    label, audio, src, tgt, backend = combo
    code = RUNNER.format(AUDIO=audio, backend=backend, src=src, tgt=tgt)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT:"):
            return json.loads(line[7:])
    print("STDERR:", r.stderr[-1200:]); return None

# Interleaved: round-robin across combos; first round = warmup
sequence = []
for i in range(TRIALS):
    for c in COMBOS:
        sequence.append(c)

print(f"trials per combo: {TRIALS} (first is warmup), interleaved, {SLEEP_S}s sleep")
print(f"sequence: {[c[0] for c in sequence]}\n")

results = {c[0]: [] for c in COMBOS}
for i, combo in enumerate(sequence):
    tag = "warmup" if i < len(COMBOS) else "measured"
    label = combo[0]
    print(f"[{i+1}/{len(sequence)}] {label} ({tag})...", end=" ", flush=True)
    res = run(combo)
    if res:
        sa = "simul" if res["simul_active"] else "serial"
        fp = f"{res['first_prov']:.1f}s" if res["first_prov"] else "n/a"
        ff = f"{res['first_final']:.1f}s" if res["first_final"] else "n/a"
        print(f"wall={res['wall']:.1f}s RTF={res['rtf']:.2f} [{sa}] finals={res['n_finals']} prov={res['n_provs']} firstProv={fp} firstFinal={ff}")
        if i >= len(COMBOS):
            results[label].append(res)
    else:
        print("FAILED")
    if i < len(sequence) - 1:
        time.sleep(SLEEP_S)

print("\n=== summary (warmup discarded, mean ± stdev of measured) ===")
for label, audio, src, tgt, backend in COMBOS:
    trials = results[label]
    if not trials:
        print(f"{label}: no measured trials"); continue
    mean = statistics.mean
    stdev = statistics.stdev if len(trials) > 1 else lambda x: 0.0
    walls = [t["wall"] for t in trials]
    rtfs = [t["rtf"] for t in trials]
    ffs = [t["first_final"] for t in trials if t["first_final"]]
    fps = [t["first_prov"] for t in trials if t["first_prov"]]
    sa = trials[0]["simul_active"]
    ff = f"{mean(ffs):.1f}±{stdev(ffs):.1f}s" if ffs else "n/a"
    fp = f"{mean(fps):.1f}±{stdev(fps):.1f}s" if fps else "n/a"
    nf = mean([t["n_finals"] for t in trials])
    mode = "simul" if sa else "serial"
    print(f"{label:18} [{mode}] wall={mean(walls):.1f}±{stdev(walls):.1f}s RTF={mean(rtfs):.2f}±{stdev(rtfs):.2f} finals={nf:.1f} firstProv={fp} firstFinal={ff}")
    print(f"{'':>20} walls={[f'{w:.1f}' for w in walls]}  rtfs={[f'{r:.2f}' for r in rtfs]}")
    if trials and trials[0]["provs"]:
        print(f"{'':>20} first prov:  {trials[0]['provs'][0][1][:70]}")
