# Standing ops rules for model-touching ensign tasks (WhisperLiveKit)

Learned 2026-09-12: an eval ensign ran two 3-4GB models while MLX wired
caches accumulated — the machine hit 13.7GB of 15GB swap (near-unusable)
and disk hit 345MB. Every dispatch involving model loads MUST include:

## Memory rules (hard)

1. ONE model loaded at a time. Between models: `del model`,
   `mx.metal.clear_cache()`, and `gc.collect()` — never two model
   workloads alive in one process.
2. At eval start, cap the MLX cache: `mx.metal.set_cache_limit(...)` (e.g.
   4GB) — do not let it grow unbounded.
3. Monitor `memory_pressure` between clips/models; ABORT if system free
   memory drops below 20%. Record partial results and stop — do not push
   through.
4. No background/parallel model processes. Sequential only.

## Disk rules (hard)

5. Check `df -h /` before starting and before/after every download.
6. HARD FLOOR 5GB: if free disk drops under 5GB, stop, delete
   re-downloadable caches (never production-model caches: nemotron 0.6b,
   Voxtral-2602-4bit, Hy-MT2-1.8B-8bit, mlx-community Qwen3-ASR-0.6B-8bit/4bit,
   qfuxa qwen3-asr-0.6b-streaming), and resume only above 8GB.

## Thermal rules (for any latency/RTF measurement)

7. Interleaved A/B or cold baseline — single sequential runs are
   noise-dominated (documented: RTF 0.76-1.86 on identical code).
8. Quality (WER/CER) runs are thermal-insensitive; latency columns are not.

## Keep vs delete cache discipline

- KEEP: the production models listed above + any model a live demo or
  pending measurement still needs.
- DELETE: exploration-only checkpoints after their measurement is recorded
  in an artifact (e.g. canary-1b-v2, translate-gemma, Hy-MT2 bf16 when
  only the -8bit is production).
