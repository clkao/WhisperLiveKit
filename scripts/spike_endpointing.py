"""Prototype: rule2-softmax + rule3 endpointing with MT flush (zh->en).

Direct loop (not wrapper chain) for clarity. Endpointing fires
mt.validate_buffer_and_reset() to flush the open utterance as a final.
"""
import numpy as np, types, time
from mlx_audio.stt.utils import load_audio
from whisperlivekit.asr_mlx_qwen3 import MlxQwen3AsrOnlineProcessor
from whisperlivekit.asr_commit import StableCommitTransform
from whisperlivekit.asr_wrapper import AsrWrapper
from whisperlivekit.translation_mlx_llm_mt_simul import MlxLlmTranslationSimul
from whisperlivekit.timed_objects import HypothesisTail, ASRToken

PUNCT = set("。！？.!?")
SOFT_MAX = 8.0   # rule2-softmax: cut at sentence punct after this many seconds
HARD_MAX = 20.0  # rule3: force-cut

audio = np.asarray(load_audio("/Users/clkao/git/asr/_work/zh_long.wav", 16000), dtype=np.float32)
CH = int(2.0*16000)
cfg = types.SimpleNamespace(model_id="mlx-community/Qwen3-ASR-0.6B-8bit", language="zh",
    hotwords="", chunk_size_sec=2.0, max_context_sec=30.0, finalization_mode="accuracy",
    sep="", two_pass=False, backend="mlx-qwen3-asr")
proc = MlxQwen3AsrOnlineProcessor(cfg)
wrapped = AsrWrapper(proc, transforms=[StableCommitTransform()])

# Disable MT's punctuation-triggered finals; endpointing owns finalization.
ASRToken.has_punctuation = lambda self: False
mt = MlxLlmTranslationSimul(model_id="hy-mt2-1.8b-8bit", target_language="en",
    source_language="zh", commit_mode="mass", mass_threshold=0.5)

t0 = time.perf_counter()
utt_start = 0.0
committed_text = ""
n_finals=0; n_provs=0; prev_prov=""
for i in range(len(audio)//CH):
    off=i*CH; t_audio=(off+CH)/16000
    wrapped.insert_audio_chunk(audio[off:off+CH], t_audio)
    toks, end = wrapped.process_iter()
    for t in toks:
        committed_text += t.text
    items = list(toks)
    buf = wrapped.get_buffer()
    tail = getattr(buf,"text","") or ""
    if tail.strip():
        items.append(HypothesisTail(start=None, end=getattr(buf,"end",end), text=tail))
    if items:
        mt.insert_tokens(items)

    # Endpointing: rule2-softmax / rule3. Check the FULL stable_text (not just
    # the last delta) for sentence-ending punctuation.
    stable = (proc._stable_text or "")
    utt_dur = t_audio - utt_start
    ends_sentence = bool(stable.rstrip() and stable.rstrip()[-1] in PUNCT)
    fire = (utt_dur >= HARD_MAX) or (utt_dur >= SOFT_MAX and ends_sentence)
    if fire:
        # Flush MT open utterance as a final (silence-boundary path).
        mt.validate_buffer_and_reset()
        committed_text = ""
        utt_start = t_audio

    tr, buf = mt.process()
    if tr is not None and tr.text and tr.text.strip():
        n_finals += 1
        print(f"[{t_audio:4.1f}s] FINAL #{n_finals} (utt {utt_dur:.1f}s): {tr.text[:65]!r}")
    elif buf is not None and getattr(buf,"text","") and getattr(buf,"text","").strip() and buf.text != prev_prov:
        n_provs += 1
        prev_prov = buf.text
        print(f"[{t_audio:4.0f}s] prov #{n_provs}:   {buf.text[:55]!r}")
toks, end = wrapped.finish()
if toks: mt.insert_tokens(list(toks))
tr, buf = mt.process()
if tr is not None and tr.text and tr.text.strip():
    n_finals += 1
    print(f"[end ] FINAL #{n_finals}: {tr.text[:65]!r}")
print(f"\ntotal: {n_finals} finals, {n_provs} distinct provisionals")
