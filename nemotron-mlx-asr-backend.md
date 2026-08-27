---
title: "nemotron-mlx ASR backend (transducer; AlignAtt time-based frontier)"
source: PR3 research — _work/nemotron_transducer_alignatt_research.md
score: 0.8
id: n5g2sjy16zzy9rhdk8d1zn1p
status: backlog
gates:
    version: 1
    records:
        - id: gate:n5g2sjy16zzy9rhdk8d1zn1p:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:n5g2sjy16zzy9rhdk8d1zn1p-backlog-1
              briefing:
                id: briefing:n5g2sjy16zzy9rhdk8d1zn1p:backlog:attempt-1:revision-1
                digest: sha256:6c35c01023fdc2b61f3fea41a241a74c7103313d2b6285bd3d417a585a7a2a69
                request-digest: sha256:a870d5ef7b2bb1b44305abeb7483f3ac9387778e297fef6b7d9d051bb7ac219e
                room-ref: ./nemotron-mlx-asr-backend/review/backlog/briefing-1
---

# nemotron-mlx ASR backend + AccessibleBoundary adapter (time-based frontier)

## Goal

Add the `nemotron-3.5-asr-streaming-0.6b` transducer as a WhisperLiveKit ASR backend via mlx-audio (pure MLX, no nemo_toolkit/ONNX). The transducer emits per-token `AlignedToken.start` audio-time timestamps DURING the greedy RNN-T decode (monotonic, append-only — no token revision), giving a principled accessible boundary for AlignAtt that qwen3-asr's `stable_text` proxy cannot.

This is the research-enabling backend: it unlocks the `AccessibleBoundary` adapter (qwen3-stable + nemotron-time implementations) so both ASR backends drive the same AlignAtt runtime, and the nemotron+AlignAtt comparison (compaction next step #2).

## Why

- **Transducer + AlignAtt is an untried combination** (novelty gap): AlignAtt4LLM (IWSLT 2026) uses Qwen3-ASR + a separate ForcedAligner; NeMo IWSLT 2026 uses a transducer but LCP/local-agreement, not AlignAtt. The transducer's append-only commit + native timestamps is architecturally a BETTER fit for AlignAtt than qwen3's heuristic stable prefix.
- **Three source-frontier implementations** become visible: qwen3-stable (proxy, free, current PR2), qwen3-forced-align (AlignAtt4LLM's, expensive), nemotron-time (principled, free — this task).
- **Do NOT switch production ASR to nemotron**: nemotron's Mandarin is zh-CN/mainland, measurably weaker than qwen3's native Taiwan vocab for zh-tw. The comparison is research; production stays qwen3 unless nemotron's zh-tw quality is shown acceptable.

## What ships

- `whisperlivekit/asr_nemotron_mlx.py` — the backend. Ports `livecaption/asr.py`'s `_StreamingEncoder` + `_decode_chunk` (cache-aware FastConformer-RNNT, push-based stepper). The decode loop populates `self._hypothesis` with `AlignedToken(pred_token, start, duration, text)` per non-blank token. Needs neither the wrapper layer's Job 1 (monotonic, no revision) nor Job 2 (native timestamps).
- Registration: `_do_init` + `online_factory` branches; `nemotron_mlx_asr_*` config knobs; `--nemotron-mlx-asr-*` flags; the `nemotron_mlx_asr_backend_available` check; BACKENDS entry.
- The `nemotron-mlx-asr` extra in pyproject.toml (`mlx-audio` + the nemotron model).

## Out of scope (research — NOT this PR)

- The `AccessibleBoundary` adapter abstraction + the nemotron+AlignAtt comparison. These run as research (research-log + subagent review + debrief), not the dev workflow — per compaction note: "Do NOT commission a spacedock dev workflow for the research part." This task ships the backend; the adapter + comparison consume it.

## Acceptance criteria

- AC-1: `wlk serve --backend nemotron-mlx-asr --language zh` transcribes Mandarin in-process, no torch/transformers/nemo_toolkit/WebSocket sidecar.
- AC-2: per-token timestamps (`AlignedToken.start`) are populated during the decode, not just at finalization (verifiable via a test that inspects `_hypothesis` mid-utterance).
- AC-3: the backend coexists with mlx-lm and the mlx-llm-mt backend on the same transformers 5.x.
- AC-4: a second language (en, or auto) transcribes correctly (the model is multilingual, 40 locales).

## Test plan

Unit tests for the decode loop + AlignedToken population (mock the model; no live model load). Live zh-tw WER comparison vs qwen3 on CL's Mac (the known gap to measure).

## Notes

- Reference: `livecaption/livecaption/asr.py` (`_StreamingEncoder`, `_decode_chunk`, `_finalize`, `_hypothesis` AlignedToken). The mlx-audio port is at `mlx_audio.stt.models.nemotron_asr` + `mlx_audio.stt.models.nemo.alignment`.
- Research brief: `_work/nemotron_transducer_alignatt_research.md`.
- zh-tw caveat: nemotron is zh-CN; expect lower zh-tw content accuracy than qwen3. OpenCC fixes script, not acoustic/vocab gaps.
