#!/usr/bin/env python3
"""Frame-by-frame event capture: ASR draft/final + MT draft/final, decoupled from display.

Captures the raw generation event stream from the ASR+MT pipeline as JSONL,
one event per line, tagged by type and timestamped. No display logic — just
what each layer actually emitted, when. The replay/analysis is separate so
we can judge (1) whether generation produces a coherent sequence and
(2) whether display renders that sequence correctly, independently.

Event schema (one JSON object per line):
  {"t": <wall_sec>, "audio_t": <sec>, "type": "transcription_provisional"|"transcription_final"|"translation_provisional"|"translation_final",
   "text": "<str>", "committed": "<str>" (translation_provisional only, what AlignAtt released against),
   "source": "<str>" (translation_provisional only, full source the MT saw),
   "n_mt_calls": <int> (translation_provisional only)}

Usage:
  .venv/bin/python scripts/capture_frame_events.py [--audio PATH] [--lang zh] [--target en]
  .venv/bin/python scripts/capture_frame_events.py --replay /tmp/zh_en_events.jsonl
"""
from __future__ import annotations
import argparse, json, sys, time, os
from datetime import datetime

def capture(out_path: str, audio_path: str, lang: str, target: str, backend: str) -> None:
    import numpy as np
    from mlx_audio.stt.utils import load_audio
    audio = np.asarray(load_audio(audio_path, 16000), dtype=np.float32)
    CH = 8000  # 0.5s frames

    if backend == "qwen3":
        import types
        from whisperlivekit.asr_mlx_qwen3 import MlxQwen3AsrOnlineProcessor
        from whisperlivekit.asr_commit import StableCommitTransform
        from whisperlivekit.asr_wrapper import AsrWrapper
        cfg = types.SimpleNamespace(
            model_id="mlx-community/Qwen3-ASR-0.6B-8bit", language=lang,
            hotwords="", chunk_size_sec=2.0, max_context_sec=30.0,
            finalization_mode="accuracy", sep="", two_pass=True, backend="mlx-qwen3-asr",
        )
        asr = AsrWrapper(MlxQwen3AsrOnlineProcessor(cfg),
            transforms=[StableCommitTransform()])
    else:
        from whisperlivekit.asr_nemotron_mlx import NemotronMLXASR, NemotronMLXOnlineProcessor
        asr = NemotronMLXOnlineProcessor(NemotronMLXASR(lan=lang,
            nemotron_mlx_asr_model="mlx-community/nemotron-3.5-asr-streaming-0.6b"))

    from whisperlivekit.translation_mlx_llm_mt_simul import MlxLlmTranslationSimul
    from whisperlivekit.timed_objects import HypothesisTail
    mt = MlxLlmTranslationSimul(model_id="hy-mt2-1.8b-8bit",
        target_language=target, source_language=lang,
        commit_mode="mass", mass_threshold=0.5)

    from whisperlivekit.caption_events import EventLog, EventTap
    import time as _time
    t0 = _time.perf_counter()
    log = EventLog()
    tap = EventTap(sink=log, clock=lambda: _time.perf_counter()-t0)

    for off in range(0, len(audio), CH):
        chunk = audio[off:off+CH]
        audio_t = (off+CH)/16000
        asr.insert_audio_chunk(chunk, audio_t)
        # ASR draft (unstable tail)
        buf = asr.get_buffer()
        tail = getattr(buf, "text", "") or ""
        tap.transcription_provisional(audio_t, tail)
        # ASR final (committed tokens from process_iter)
        toks, end = asr.process_iter()
        if toks:
            txt = "".join(t.text for t in toks)
            tap.transcription_final(audio_t, txt)
        # Feed MT
        items = list(toks)
        if tail.strip():
            items.append(HypothesisTail(start=None, end=getattr(buf,"end",audio_t), text=tail))
        if items:
            mt.insert_tokens(items)
        # MT final / provisional
        calls_before = mt._mt_call_count
        tr, buf = mt.process()
        if tr is not None and tr.text and tr.text.strip():
            tap.translation_final(audio_t, tr.text)
        elif buf is not None and getattr(buf, "text", "") and getattr(buf,"text","").strip():
            compute = mt._mt_call_count > calls_before
            tap.translation_provisional(audio_t, buf.text, mt._committed_text(), mt._source_text(), compute)
    # finalize
    toks, end = asr.finish()
    if toks:
        txt = "".join(t.text for t in toks)
        tap.transcription_final(len(audio)/16000, txt)
    if toks: mt.insert_tokens(list(toks))
    calls_before = mt._mt_call_count
    tr, buf = mt.process()
    if tr is not None and tr.text and tr.text.strip():
        tap.translation_final(len(audio)/16000, tr.text)
    elif buf is not None and getattr(buf, "text", "") and getattr(buf,"text","").strip():
        compute = mt._mt_call_count > calls_before
        tap.translation_provisional(len(audio)/16000, buf.text, mt._committed_text(), mt._source_text(), compute)

    log.save(out_path)
    print(f"captured {len(log.events)} events -> {out_path}", file=sys.stderr)
    by_type = {}
    for e in log.events:
        by_type[e.type] = by_type.get(e.type, 0) + 1
    print(by_type, file=sys.stderr)


def replay(log_path: str) -> None:
    """Print the event stream frame-by-frame for human review."""
    from pathlib import Path
    events = [json.loads(l) for l in Path(log_path).read_text().splitlines() if l.strip()]
    if not events:
        print("no events"); return
    print(f"=== {len(events)} events from {log_path} ===\n")
    cur_transcription_provisional = ""; cur_mt = ""; last_translation_final = ""
    for e in events:
        t = e["t"]; at = e.get("audio_t", 0); typ = e["type"]; txt = e["text"]
        if typ == "transcription_provisional":
            cur_transcription_provisional = txt
            print(f"[{t:6.2f} a={at:5.1f}] asr draft : {txt[:50]!r}")
        elif typ == "transcription_final":
            cur_transcription_provisional = ""
            print(f"[{t:6.2f} a={at:5.1f}] ASR FINAL : {txt[:50]!r}")
        elif typ == "translation_provisional":
            cur_mt = txt
            com = e.get("committed","")[:25]
            print(f"[{t:6.2f} a={at:5.1f}] mt  draft : {txt[:50]!r}  [com={com!r}]")
        elif typ == "translation_final":
            print(f"[{t:6.2f} a={at:5.1f}] MT  FINAL : {txt[:50]!r}")
            last_translation_final = txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default="/Users/clkao/git/asr/_work/zh_long.wav")
    ap.add_argument("--out", default="/tmp/zh_en_events.jsonl")
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--target", default="en")
    ap.add_argument("--backend", default="qwen3", choices=["qwen3","nemotron"])
    ap.add_argument("--replay", default=None)
    args = ap.parse_args()
    if args.replay:
        replay(args.replay)
    else:
        capture(args.out, args.audio, args.lang, args.target, args.backend)
        replay(args.out)

if __name__ == "__main__":
    main()
