---
title: "mlx-llm-mt Tier B: simultaneous MT via AlignAtt commit policy (in-process, no sidecar)"
status: backlog
source: prototype — port livecaption's simultaneous MT into mlx-llm-mt as the stable test path
score: 0.8
id: ksxw8mezhk10fzx2yw7mfvj7
---

Port livecaption's `simul_mt.py` simultaneous-MT mechanism into the
`mlx-llm-mt` backend as an in-process Tier B variant. This is the stable
test path for the AlignAtt simultaneous-MT demo: it runs on this Mac (no
CUDA sidecar), uses our calibrated zh→en Hunyuan heads, and reuses the
portable AlignAtt commit policy.

## Motivation

The `bench-alignatt-ab` demo has two candidate MT paths: (1) the existing
`alignatt-mt-server` sidecar (CUDA/vLLM Gemma), or (2) this in-process
mlx-llm-mt Tier B. The sidecar's viability on vllm-metal is under probe
(run `9a9bf5dc`); if it fails, this Tier B port is the fallback stable
path. Either way, the in-process Tier B is the production-relevant path
for our zh→en use case (the sidecar is en→X, demo-grade).

## What ships

A `MlxLlmTranslationSimul` subclass (or `--simultaneous` flag on the base)
that:

- Sets `wants_hypothesis_tail = True` (the base now accepts the tail; this
  variant uses it).
- Reads `self._tail.text` (the unstable ASR tail) to draft a translation
  ahead of the committed prefix — the simultaneous-MT mechanism.
- Applies the AlignAtt commit policy: commit only target tokens whose
  attention argmax (over the source span) lands on a source token the ASR
  has committed; hold the rest. Release held tokens when the ASR commits
  the corresponding source, without a new MT call.
- Uses the calibrated zh→en heads for `tencent/Hy-MT2-1.8B` (the 8
  production head indices + TS scores from
  `_work/simul_mt_calibration_verdict.md`, already hardcoded in
  livecaption's `simul_mt.py`).
- Reuses the portable AlignAtt commit policy (`alignment/base.py`,
  `source_frontier.py`, `emission.py` — stdlib+numpy, no vLLM) from
  AlignAtt4LLM, not a reimplementation.
- Implements the MLX Q/K capture by hooking `hunyuan_v1_dense.Attention`
  (the pattern livecaption's `CapturedAttention` already proves —
  manual softmax(QK^T) so attention weights are capturable for the
  alignment heads).

## Acceptance criteria

- AC-1: `wlk serve --backend mlx-qwen3-asr --translation-backend mlx-llm-mt
  --simultaneous --target-language en --language zh` runs on a zh audio file
  and emits EN translation. The `wants_hypothesis_tail=True` flag reaches the
  backend; the tail is drafted over (not dropped).
- AC-2: The simultaneous variant's first translation for a multi-sentence
  utterance arrives BEFORE the Tier A variant's (which waits for utterance
  close). Verified by a timestamped log showing earlier first-translation-time.
- AC-3: The commit policy commits only against the committed ASR prefix;
  held target tokens release when the ASR commits the tail, without a new
  MT call. Verified by an MT-call counter (Tier B makes fewer MT calls
  than Tier A on the same audio).
- AC-4: The 8 calibrated zh→en heads load and the top head (L9, H5) drives
  the commit decision. Verified by a log line naming the heads in use.
- AC-5: Forward-compatible: the base `MlxLlmTranslation` (Tier A) is
  unchanged; the Tier B variant is a subclass or flag, not a fork. The
  base's `self._tail` storage (landed in the signature fix) is the seam.
  Verified by the 24 existing tests still passing (12 mlx-llm-mt + 12
  alignatt).

## Out of scope

- The AlignAtt sidecar path (separate; under probe).
- New head calibration (reuse the 8 production heads from
  `_work/simul_mt_calibration_verdict.md`).
- The mlx-qwen3-asr `get_buffer` fix (prerequisite, tracked on
  `mlx-qwen3-asr-backend`).

## Dependencies

- `mlx-qwen3-asr-backend` re-implementation (the `get_buffer` fix) — must
  land first so the ASR emits the unstable tail the Tier B variant drafts
  over.
- The mlx-llm-mt signature fix (landed: commit `9d55984`) — the base now
  accepts `HypothesisTail`; this task uses it.

## Notes

livecaption's `simul_mt.py` is the reference implementation. The
`CapturedAttention` class (manual softmax over QK^T, capture for the 8
head indices) + the `submit_simul` commit policy are the two pieces to
port. The portable AlignAtt policy (source_frontier, emission) is
stdlib+numpy and reusable as-is.
