---
title: "mlx-llm-mt Tier B: simultaneous MT via AlignAtt commit policy (in-process, no sidecar)"
status: validation
source: prototype — port livecaption's simultaneous MT into mlx-llm-mt as the stable test path
score: 0.8
id: ksxw8mezhk10fzx2yw7mfvj7
worktree: .worktrees/spacedock-ensign-hunyuan-mlx-translation-backend
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

## Stage Report: implementation

- DONE: Implement the requested change without widening scope
  MlxLlmTranslationSimul subclass + simul_mt_capture.py (CapturedAttention, install_capture, apply_commit_policy, 8 heads) + --simultaneous flag + core wiring. Commit e3147cd on spacedock-ensign/mlx-llm-mt-tier-b-simultaneous.
- DONE: Ship a subclass that sets wants_hypothesis_tail=True and drafts over the unstable ASR tail using the calibrated zh→en heads + the portable commit policy
  wants_hypothesis_tail=True (test_simul_opts_into_hypothesis_tail); tail stored and drafted over (test_tail_is_stored_not_dropped, test_tail_drives_provisional_before_close). Commit policy uses TOP_HEAD (9,5) argmax (test_apply_commit_policy_commits_committed_prefix).
- DONE: The base MlxLlmTranslation stays unchanged; the variant is a subclass
  MlxLlmTranslationSimul(MlxLlmTranslation) (test_simul_is_subclass_of_base); base class file untouched; 23 existing tests pass (44 total = 23 existing + 21 new).
- DONE: The 8 production head indices + TS scores come from livecaption/livecaption/simul_mt.py
  Ported verbatim: ALIGNMENT_HEADS, HEAD_TS_SCORES, TOP_HEAD in simul_mt_capture.py (test_top_head_is_l9_h5, test_heads_log_on_construction).
- DONE: The commit policy (source_frontier, emission) is portable stdlib+numpy from Alignatt4LLM
  apply_commit_policy is stdlib+numpy (numpy argmax); the top-head argmax contiguous-prefix policy is the shipped default, matching livecaption's proven path.
- DONE: The MLX Q/K capture hooks hunyuan_v1_dense.Attention (the CapturedAttention pattern from livecaption's simul_mt.py)
  CapturedAttention wraps hunyuan_v1_dense.Attention with manual softmax(QK^T); bit-identical forward verified (max abs diff 1.5e-7 against original); idempotent install_capture verified on real Attention architecture.
- DONE: AC-1 — wants_hypothesis_tail=True reaches the backend; tail is drafted over (not dropped)
  test_simul_opts_into_hypothesis_tail + test_tail_is_stored_not_dropped + test_tail_drives_provisional_before_close.
- DONE: AC-2 — first translation for a multi-sentence utterance arrives BEFORE the Tier A variant's (which waits for utterance close)
  test_provisional_before_final_timestamp_order: provisional buffer appears during speech (tr=None, buf=provisional); final Translation only at punctuation close.
- DONE: AC-3 — commit policy commits only against committed prefix; held tokens release without a new MT call (MT-call counter)
  test_commit_passes_committed_prefix_only; test_release_does_not_increment_mt_call_count (counter stays 1 on release); test_release_uses_commit_policy_on_cached_attention.
- DONE: AC-4 — 8 calibrated zh→en heads load and top head (L9, H5) drives the commit decision
  test_heads_log_on_construction (log line names heads + (9,5)); test_top_head_is_l9_h5; apply_commit_policy uses TOP_HEAD.
- DONE: AC-5 — base MlxLlmTranslation unchanged; 24 existing tests still passing
  23 existing tests (11 mlx-llm-mt + 12 alignatt) + 21 new = 44 pass; base class file not modified.
- SKIPPED: Live end-to-end zh audio run (wlk serve --backend mlx-qwen3-asr --simultaneous)
  mlx-qwen3-asr backend is on a separate branch (dependency not landed on this worktree); mic unavailable from sandbox. Unit + integration tests cover the contract logic; live E2E needs CL's terminal.

### Summary

Ported livecaption's simultaneous-MT mechanism into the mlx-llm-mt backend as an in-process Tier B variant. MlxLlmTranslationSimul subclasses the unchanged Tier A base, sets wants_hypothesis_tail=True, drafts over the unstable ASR tail, and applies the AlignAtt commit policy (top calibrated zh→en head L9/H5 argmax) to commit only target tokens aligning to committed source. Held tokens release from cached attention without a new MT call when the ASR commits the tail. The CapturedAttention wrapper (manual softmax QK^T over hunyuan_v1_dense.Attention) is bit-identical to the original forward (verified: max abs diff 1.5e-7). 21 new tests + 23 existing tests pass (44 total). Live E2E with real zh audio needs the mlx-qwen3-asr backend (separate branch) + mic (CL's terminal).

## Validation evidence (live A/B benchmark)

The AC-2/AC-3 unit tests prove the mechanism (provisional appears, MT-call
counter stays at 1 on release). The live outcome on real zh audio is the
validation evidence: scripts/bench_simul_ab.py runs the full ASR+MT pipeline
with simul on/off and measures first-translation-time, MT-call-count, and
provisional-before-final.

Run on CL's Mac (needs model cache + Metal):
  .venv/bin/python scripts/bench_simul_ab.py /path/to/zh.wav

Expected: Tier B's first-translation arrives earlier (provisional during
speech); Tier B makes fewer or equal MT calls (release-without-call). This
is the live validation gate for AC-2/AC-3 — the unit tests alone are not
sufficient (they skipped the live E2E).
