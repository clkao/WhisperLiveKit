---
id: sd-bench-alignatt-ab
title: "A/B benchmark: with and without simultaneous MT (AlignAtt)"
status: backlog
source: prototype — measure the simultaneous-MT latency win
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
---

# A/B benchmark: with and without simultaneous MT (AlignAtt)

## Problem

The simultaneous MT (Tier B, AlignAtt pattern) overlaps MT with the ASR tail
to cut caption latency. We measured a ~1.4s win in livecaption's `simul_mt.py`.
Once the `mlx-llm-mt` backend ships Tier B (the `CapturedAttention` MLX Q/K
observer + calibrated heads + commit policy), we need a simple way to A/B
compare Tier A (translate-on-close) vs Tier B (simultaneous) on the same audio,
so the operator can see the latency difference and decide whether to enable
Tier B.

## Proposed approach

A benchmark script that runs the same Mandarin audio through both modes and
prints a side-by-side latency table:

- Tier A: `--translation-backend mlx-llm-mt` (wants_hypothesis_tail=False).
- Tier B: `--translation-backend mlx-llm-mt --simultaneous` (wants_hypothesis_tail=True).

The script measures per-utterance: ASR commit time, MT start time, MT end time,
and total caption latency (audio in to English text out). It prints the EWMA
for each metric and the delta between Tier A and Tier B.

This task depends on the `mlx-llm-mt` Tier B work (the `hunyuan-mlx-translation-backend`
task, amended to `mlx-llm-mt`). It stays in backlog until Tier B lands.

## Risk evidence

The latency EWMA instrumentation already works in livecaption's `render.py`.
The benchmark script reuses it. The risk is that Tier B is not yet wired into
the WLK backend; the script is filed now so it is ready when Tier B lands.

## Expected surface and tolerance

Estimate: +120 net LOC across 1 file (`scripts/bench_alignatt_ab.py`),
tolerance ±30.
Semantics this may change: none (a benchmark script, not a runtime change).

## Acceptance criteria

**AC-1 — The script runs the same audio through Tier A and Tier B.**
Verified by: the script output shows two runs with the same input audio and
different mode flags.

**AC-2 — The script prints per-utterance latency for both modes.**
Verified by: the output table has columns for ASR, MT, and total latency in
both modes, with the delta.

**AC-3 — The script does not require a live mic.**
Verified by: the script accepts a WAV file path (interleaved A/B, not batched —
batched runs are thermally contaminated).

## Test plan

- Run against a Mandarin WAV; confirm both modes produce output and the table
  shows the latency delta.
- Sanity: Tier B total latency should be less than or equal to Tier A (the
  simultaneous overlap can only help or tie, not hurt, on latency).

## Out of scope

- Quality comparison (this is latency-only; quality is a separate A/B).
- Batch mode (interleaved A/B only; batched runs are thermally contaminated).
- The Tier B implementation itself (this task consumes it, does not build it).
