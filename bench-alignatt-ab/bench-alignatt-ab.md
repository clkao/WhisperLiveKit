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

## Demo success definition (revised 2026-08-25)

The demo wires the AlignAtt-ready `mlx-qwen3-asr` backend to the existing
AlignAtt translator (the `AlignAttRemoteEngine` sidecar client in
`translation_alignatt.py`), and compares against the default cascade. This
validates the end-to-end simultaneous-MT seam on real audio.

### The two cascades

- **Demo cascade (simultaneous MT):** `wlk serve --backend mlx-qwen3-asr
  --translation-backend alignatt --alignatt-url <sidecar> --language <src>`.
  The ASR feeds committed tokens + `HypothesisTail` (the unstable tail, after
  the `get_buffer` fix) to the AlignAtt engine. The sidecar (an
  `alignatt-mt-server` running Gemma on CUDA) runs the AlignAtt commit policy
  and returns the simultaneous translation.
- **Default cascade (baseline):** `wlk serve --backend qwen3-causal-vllm
  --translation-backend nllb --language <src>`. NLLB translates on utterance
  close (no simultaneous overlap). This is the non-simultaneous baseline.

### Heads

Use whatever heads ship with the AlignAtt4LLM repo (the sidecar loads them):
`google/gemma-4-E4B-it` heads cover en→{cs,de,fr,it,zh} and cs→en. No zh→en
heads ship. The demo direction must be one of these (e.g., en→de for a
well-resourced European pair). Pick the direction that best matches available
test audio.

### Runtime requirement (BLOCKER)

The `alignatt-mt-server` requires CUDA/vLLM (the Q/K observer hooks vLLM CUDA
attention). It cannot run on this Mac. The demo needs:
1. A CUDA box running `alignatt-mt-server` (from Alignatt4LLM) with a shipped
   Gemma head for the chosen direction.
2. This Mac running the WLK client (`mlx-qwen3-asr` + `AlignAttRemoteEngine`
   pointing at the CUDA box).

Without a CUDA box, the demo is blocked. Confirm CUDA availability before
starting this task.

### What the demo proves

- The `mlx-qwen3-asr` `get_buffer` fix (Finding 1) works end-to-end: the
  AlignAtt sidecar receives the unstable tail and drafts over it.
- The simultaneous-MT seam (ASR committed + unstable tail → AlignAtt commit
  policy → translation tracks ASR commit latency, not adds to it) works with
  a real Gemma MT model, not just our Hunyuan port.
- The latency win: the demo cascade's translation appears before the default
  cascade's (which waits for utterance close).

## Acceptance criteria

- AC-1: `mlx-qwen3-asr` (AlignAtt-ready, after the `get_buffer` fix) wired to
  `--translation-backend alignatt`; the sidecar receives the unstable tail and
  produces translation output. Verified by: the demo cascade emits EN
  translation text before utterance close.
- AC-2: The default cascade (`qwen3-causal-vllm` + `nllb`) runs the same audio
  and produces translation on utterance close. Verified by: the baseline
  emits EN translation only after the ASR commits the utterance.
- AC-3: Side-by-side latency comparison shows the demo cascade's first
  translation arrives before the default's. Verified by: a timestamped log or
  table showing the demo cascade's first-translation-time < default's.
- AC-4: The demo uses a shipped Gemma head (en→{cs,de,fr,it,zh} or cs→en), not a
  custom-calibrated head. Verified by: the sidecar's `--heads-path` points at a
  file in `Alignatt4LLM/data/alignatt_heads/translation_heads_google_gemma-*`.

## Out of scope

- Quality comparison (latency-only). Batch mode. The Tier B implementation
  itself (this demo uses the existing sidecar, not an in-process port).
- zh→en (no shipped Gemma heads; our Hunyuan zh→en is a separate track).
- Porting the Q/K observer to MLX (that's the in-process Tier B path, a
  separate task if the sidecar demo proves the win).

## Dependencies

- `mlx-qwen3-asr-backend` re-implementation (the `get_buffer` fix) — must land
  first so the ASR emits the unstable tail correctly.
- A CUDA box running `alignatt-mt-server`. BLOCKER until confirmed.
