#!/usr/bin/env python3
"""Diagnostic: feed a wav file through mlx-qwen3-asr's streaming API directly
(no WLK wrapper, no audio_processor). Run on the Mac:

  .venv/bin/python scripts/diag_asr_feed.py /path/to/zh.wav

If this produces text, the model + streaming API work; the bug is in the
WLK backend wrapper (asr_mlx_qwen3.py / asr_commit.py / asr_wrapper.py).
If this produces no text, the issue is the model or the streaming API itself.
"""
import sys
import numpy as np
import soundfile as sf
from mlx_qwen3_asr import load_model
from mlx_qwen3_asr.streaming import init_streaming, feed_audio, finish_streaming

MODEL = "mlx-community/Qwen3-ASR-0.6B-8bit"
LANG = "Chinese"

def main():
    wav = sys.argv[1] if len(sys.argv) > 1 else "/Users/clkao/git/asr/_work/zh_long.wav"
    print(f"Loading model {MODEL} ...", flush=True)
    model_obj, cfg = load_model(MODEL)
    print(f"Model loaded. dtype={getattr(model_obj, 'dtype', '?')}", flush=True)

    audio, sr = sf.read(wav)
    if audio.ndim > 1:
        audio = audio[:, 0]
    audio = audio.astype(np.float32)
    print(f"Audio: {len(audio)/sr:.1f}s, sr={sr}", flush=True)

    print("init_streaming ...", flush=True)
    state = init_streaming(
        model=MODEL,
        context="",
        chunk_size_sec=2.0,
        max_context_sec=30.0,
        language=LANG,
        finalization_mode="accuracy",
    )
    state.forced_language = LANG
    print("State created. Feeding 0.5s chunks ...", flush=True)

    chunk = sr // 2  # 0.5s
    for i in range(0, len(audio), chunk):
        c = audio[i:i+chunk]
        state = feed_audio(c, state, model=model_obj)
        t = (state.text or "").strip()
        st = (state.stable_text or "").strip()
        if t:
            print(f"  t={i/sr:.1f}s text={t[:100]!r} stable={st[:60]!r}", flush=True)

    print("finish_streaming ...", flush=True)
    state = finish_streaming(state, model=model_obj)
    print(f"FINAL text={state.text!r}", flush=True)

if __name__ == "__main__":
    main()
