---
title: SimulST eval harness — MLX IWSLT anchor + flagship compare
status: backlog
worktree: ""
id: 8zdhkj86eqshqypzzme2v6ss
gates:
    version: 1
    records:
        - id: gate:8zdhkj86eqshqypzzme2v6ss:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-backlog-1
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:backlog:attempt-1:revision-1
                digest: sha256:f27ce53e5ca2e7f8638a80912e575eb26bf38dc7f3d735b6bc9bc6b0187e8315
                request-digest: sha256:41f947b510293c408f37c049ec6753d2a0cc6737305baae64c1f5b59d828f61e
                room-ref: ./simulst-eval-harness/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:backlog:1
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-27T19:46:33.81354Z"
                decision: approve
                reason: 'Captain direction: file and dispatch. Emitter is simple (timestamp per emitted word). Baseline anchor + flagship compare is the eval purpose.'
              application:
                target-stage: ideation
                state: pending
---

A SimulST evaluation harness that runs our MLX ASR+MT cascade over the
AlignAtt4LLM IWSLT 2026 devset and scores it with XCOMET-XL + LongYAAL via the
existing `alignatt-eval` scorer. Two purposes:

1. **Baseline anchor** — one reproducible entry on the IWSLT devset (en→zh) so
   our results connect to what others benchmark. Not a full reproduction of the
   paper's numbers; a comparable entry on the same devset + same scorer.
2. **Flagship compare** — once the anchor exists, run our flagship setup
   (nemotron-mlx transducer + Hy-MT2-1.8B simul-MT with en→zh heads) on the same
   devset and compare against the anchor + the paper's reference anchors.

## Why this is small (the pieces already exist)

The existing `alignatt-batch` harness is its own CUDA cascade (forced-align
ASR + vLLM MT) and does NOT drive our WLK/MLX stack. But its pieces are already
ported or available in MLX:

- **MT (AlignAtt simul)** — PR2 (`translation_mlx_llm_mt_simul.py` +
  `simul_mt_capture.py`) is the MLX port of the AlignAtt commit policy +
  bit-identical Q/K capture. Done.
- **ASR (forced-align, time frontier)** — `mlx-community/Qwen3-ForcedAligner-0.6B-4bit`
  + `mlx_audio.stt.models.qwen3_asr.qwen3_forced_aligner` is a native MLX port
  of the exact forced-aligner the paper uses. Loadable now. (The nemotron-mlx
  transducer — separate entity, in implementation — gives a time-based frontier
  too, via `AlignedToken.start`; complementary, not required for the anchor.)
- **Scoring** — `alignatt-eval` (AlignAtt4LLM) wraps `omnisteval.evaluate_instances`
  + `resegment` + `write_evaluation_outputs`, defaulting to `Unabel/XCOMET-XL`.
  Scores `hypothesis.jsonl` → XCOMET-XL (quality) + LongYAAL (latency). No port
  needed; MLX-agnostic.
- **IWSLT devset refs** — `AlignAtt4LLM/data/devset/ref/{en,zh,it,de}.txt`
  (919 lines each, aligned) + `audio-segments.yaml` are tracked. Audio files
  (`*.wav`) are NOT tracked (gitignored); must be sourced from the IWSLT 2026
  shared task.

## The one real gap — hypothesis emitter (simple)

`alignatt-eval` scores a `hypothesis.jsonl` (one record per audio). The record
shape (from `alignatt4llm/artifacts.py:build_asr_hypothesis_record`):

```json
{
  "source": ["OiqEWDVtWk.wav"],
  "source_length": 12345.0,
  "prediction": "the full transcription or translation text",
  "delays": [ms per word at which the system emitted it],
  "elapsed": [normalized wallclock ms per word],
  "elapsed_semantics": "ca_compatible_incremental"
}
```

The emitter hooks our cascade's per-word emission: for each committed word,
record (a) the audio-processed-time at emission (`delays`, in ms) and (b) the
wallclock at emission (`elapsed`, in ms). The cascade already emits words; we
just timestamp them. The normalizer
(`normalize_computation_aware_timestamps`) + the builder both live in
`alignatt4llm.artifacts` — importable, no rewrite.

So the emitter is: run our MLX ASR+MT over each devset audio, timestamp each
emitted word, call `build_asr_hypothesis_record` (or write the dict directly),
emit one `hypothesis.jsonl` per run + a `manifest.json`. Then `alignatt-eval`.

## Acceptance criteria

- AC-1: A `hypothesis.jsonl` emitter exists and round-trips through
  `alignatt-eval` producing non-null XCOMET-XL + LongYAAL on one devset audio.
  Verified by: a single-audio smoke run producing a scored `evaluation.json`.
- AC-2: The anchor run (en→zh, forced-aligner ASR + Hy-MT2-1.8B simul-MT) scores
  on the full 919-line devset. Verified by: `alignatt-eval` over all devset
  audios producing a devset-level score.
- AC-3: The emitter works for both ASR-only (transcribe) and ASR+MT (translate)
  modes. Verified by: two `hypothesis.jsonl` files, one per mode, both scored.
- AC-4: The flagship run (nemotron-mlx + Hy-MT2-1.8B simul-MT, en→zh heads)
  drops into the same harness. Verified by: swapping the ASR frontend in the
  runner and producing a scored devset run.

## Open dependencies

- **IWSLT devset audio** — refs + segmentation tracked in `AlignAtt4LLM/data/devset/`;
  audio wavs gitignored, must be sourced (IWSLT 2026 shared task download).
- **en→zh heads for Hy-MT2-1.8B** — backgrounded (separate slow task); the
  anchor can run with zh→en heads' mirror or fall back to serial MT if en→zh
  heads aren't calibrated yet. Flagship compare needs them.
- **nemotron-mlx** — in implementation (separate entity); flagship compare
  needs it. Anchor uses the forced-aligner, not blocked.
