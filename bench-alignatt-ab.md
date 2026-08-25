---
title: "A/B benchmark: with and without simultaneous MT (AlignAtt)"
status: backlog
source: prototype — measure the simultaneous-MT latency win
score: 0.7
id: eqej2ksxzg8wzvg52m5d72eg
---

The simultaneous MT (Tier B, AlignAtt pattern) overlaps MT with the ASR tail to cut caption latency. We measured a ~1.4s win in livecaption. Once mlx-llm-mt ships Tier B, we need a simple A/B compare Tier A (translate-on-close) vs Tier B (simultaneous) on the same audio. This task depends on the mlx-llm-mt Tier B work; it stays in backlog until Tier B lands.

## Proposed approach

A benchmark script that runs the same Mandarin audio through both modes and prints a side-by-side latency table. Tier A: --translation-backend mlx-llm-mt (wants_hypothesis_tail=False). Tier B: --translation-backend mlx-llm-mt --simultaneous (wants_hypothesis_tail=True). Measures per-utterance ASR commit, MT start, MT end, total latency. Interleaved A/B only (batched is thermally contaminated).

## Acceptance criteria

- AC-1: script runs same audio through Tier A and Tier B. Verified by: output shows two runs with same input, different mode flags.
- AC-2: script prints per-utterance latency for both modes. Verified by: output table has columns for ASR, MT, total latency in both modes, with delta.
- AC-3: script does not require a live mic. Verified by: accepts a WAV file path (interleaved A/B).

## Out of scope

- Quality comparison (latency-only). Batch mode. The Tier B implementation itself.
