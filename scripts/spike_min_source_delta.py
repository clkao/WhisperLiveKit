#!/usr/bin/env python3
"""Spike: test MIN_SOURCE_DELTA thresholds for en->zh nemotron.

Counts MT draft calls and provisional timing at different thresholds to
confirm the over-triggering hypothesis. One run per threshold (separate
subprocess for GPU memory).
"""
import json, subprocess, sys, time

AUDIO = "/Users/clkao/git/asr/_work/demo_en_30s.wav"
THRESHOLDS = [15, 30, 45, 60]

RUNNER = r'''
import time, numpy as np, json
from mlx_audio.stt.utils import load_audio
from whisperlivekit.asr_nemotron_mlx import NemotronMLXASR, NemotronMLXOnlineProcessor
from whisperlivekit.translation_mlx_llm_mt_simul import MlxLlmTranslationSimul
from whisperlivekit.timed_objects import HypothesisTail

audio = np.asarray(load_audio({AUDIO!r}, 16000), dtype=np.float32)
CH = 8000
delta = {delta!r}

asr = NemotronMLXOnlineProcessor(NemotronMLXASR(lan="en", nemotron_mlx_asr_model="mlx-community/nemotron-3.5-asr-streaming-0.6b"))
mt = MlxLlmTranslationSimul(model_id="hy-mt2-1.8b-8bit", target_language="zh", source_language="en", commit_mode="mass", mass_threshold=0.5)
mt._MIN_SOURCE_DELTA = delta  # override

first_prov=None; first_final=None; n_prov=0; n_final=0
t0 = time.perf_counter()
for off in range(0, len(audio), CH):
    asr.insert_audio_chunk(audio[off:off+CH], (off+CH)/16000)
    toks, end = asr.process_iter()
    items = list(toks)
    buf = asr.get_buffer()
    tail = getattr(buf, "text", "") or ""
    if tail.strip():
        items.append(HypothesisTail(start=None, end=getattr(buf,"end",end), text=tail))
    if items:
        mt.insert_tokens(items)
    tr, buf = mt.process()
    if tr is not None and tr.text and tr.text.strip():
        n_final += 1
        if first_final is None: first_final = time.perf_counter()-t0
    elif buf is not None and getattr(buf,"text","") and getattr(buf,"text","").strip():
        n_prov += 1
        if first_prov is None: first_prov = time.perf_counter()-t0
toks, end = asr.finish()
if toks: mt.insert_tokens(list(toks))
tr, buf = mt.process()
if tr is not None and tr.text and tr.text.strip():
    n_final += 1
    if first_final is None: first_final = time.perf_counter()-t0
elif buf is not None and getattr(buf,"text","") and getattr(buf,"text","").strip():
    n_prov += 1
    if first_prov is None: first_prov = time.perf_counter()-t0

wall = time.perf_counter()-t0
try:
    import mlx.core as mx; mx.metal.clear_cached_memory()
except: pass
print("RESULT:" + json.dumps(dict(delta=delta, wall=wall, rtf=wall/(len(audio)/16000),
    mt_calls=mt._mt_call_count, n_final=n_final, n_prov=n_prov,
    first_prov=first_prov, first_final=first_final)))
'''

print(f"audio: {AUDIO}  (en->zh nemotron)\n")
print(f"{'delta':>6} {'wall':>7} {'RTF':>6} {'mt_calls':>9} {'finals':>7} {'provs':>6} {'firstProv':>9} {'firstFinal':>10}")
for d in THRESHOLDS:
    code = RUNNER.format(AUDIO=AUDIO, delta=d)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    for line in r.stdout.splitlines():
        if line.startswith("RESULT:"):
            o = json.loads(line[7:])
            fp = f"{o['first_prov']:.1f}s" if o['first_prov'] else "n/a"
            ff = f"{o['first_final']:.1f}s" if o['first_final'] else "n/a"
            print(f"{o['delta']:>6} {o['wall']:>7.1f} {o['rtf']:>6.2f} {o['mt_calls']:>9} {o['n_final']:>7} {o['n_prov']:>6} {fp:>9} {ff:>10}")
            break
    else:
        print(f"{d:>6} FAILED  {r.stderr[-200:]}")
    time.sleep(5)
