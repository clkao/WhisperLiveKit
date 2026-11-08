---
title: "canary-mlx ASR backend: Canary-1B-v2 through mlx-audio on Apple Silicon"
status: implementation
score: 0.8
id: c7x9y2z3a4b5c6d7e8f9g0h1
worktree: .worktrees/wlk-canary-mlx
---

# canary-mlx ASR backend

## Context

Upstream main landed a Canary-1B-v2 backend (`whisperlivekit/canary_backend.py`)
that is NeMo-only. NeMo is half-broken on this machine (hydra errors; the
canary tests fail environmentally). mlx-audio ships a pure-MLX canary
implementation (`mlx_audio.stt.models.canary`, present from 0.4.8) with
community MLX checkpoints covering the same 25 languages.

## Key finding: timestamps

The mlx-audio canary prompts with `<|notimestamp|>` (hardcoded in the
tokenizer's prompt builder) and returns text only — no word or segment
timing. The backend therefore derives stamps proportionally to word length
across the transcribed window: monotonic, order-preserving, spanning the
window. Adequate for LocalAgreement and the display assembly; NOT
model-attention timestamps (the NeMo backend stays the reference for those).

## Contract

`CanaryMLXASR` mirrors `CanaryASR` (NeMo): `sep=""`,
`transcribe()/ts_words()/segments_end_ts()`, `use_vad()` no-op; the shared
`canary_words_to_tokens`/`canary_segment_end_ts` helpers are reused so both
canary backends emit identical ASRToken shapes. No LID on the MLX side:
explicit `--language` required, validated against the shared 25-language
set at startup.

## Dependency conflict (documented in pyproject)

mlx-audio >=0.4.8 (canary-capable) requires transformers>=5.14.0; the
qwen3-streaming/vllm extras pin transformers==4.57.6 through
qwen-asr==0.0.6. Declared via `[tool.uv] conflicts` (canary-mlx vs
qwen3-streaming / qwen3-vllm / qwen3-vllm-metal): the lock resolves, the
extras are mutually exclusive per environment.

## Stage Report: implementation (cycle 1)

- DONE: Timestamp verification (STEP ONE)
  mlx-audio canary: prompt hardcodes `<|notimestamp|>` (tokenizer.py:119),
  STTOutput has no timing fields, no alignment machinery. Proportional
  derivation chosen and implemented; documented in the module docstring.
- DONE: Backend ported and routed
  whisperlivekit/canary_mlx_backend.py (CanaryMLXASR + CanaryMLXHypothesis);
  core.py branch `backend == "canary-mlx"` (explicit-language validation,
  warmup); config field canary_mlx_model (default
  Mediform/canary-1b-v2-mlx-q8); parse_args backend choice + flag; pyproject
  extra canary-mlx (mlx-audio>=0.4.8, darwin/arm64) with the conflicts
  declaration.
- DONE: Hermetic tests
  tests/test_canary_mlx_backend.py: 10 tests — stamp properties
  (monotonic/span/proportional/degenerate), hypothesis shape, ts_words
  tokens (space-prefixed, sep=""), session-language propagation, empty-text
  None, language requirement (auto/zh rejected, de accepted), language-set
  parity with the NeMo backend, missing-mlx-audio install hint.
- DONE: Suite + lint
  Failure/error set identical to origin/main baseline (canary x2 via NeMo
  env, deepgram, coalescing errors); NOTE the qwen3 shim failures present
  on main disappear in this worktree when the submodule is initialized.
  ruff clean.
- DONE: Live smoke (Apple Silicon, demo_en_30s.wav, 30.0s)
  RTF 0.048 (1.45s transcribe), 78 words, stamps monotonic over [0, 30.0],
  segment end 30.0. Transcript accurate.
- SKIPPED: AST path
  Separate exploration task (ast-exploration.md in this folder).
- FAILED: none

### Summary

Full-peer backend shipped with derived timestamps and an explicit-language
requirement; the dependency conflict with the qwen3 extras is declared, not
hidden. PR body drafted (pr.md). Branch wlk/canary-mlx, not pushed.
