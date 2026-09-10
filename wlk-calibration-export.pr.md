calibrations: add the zh→en translation-head calibration for the Hunyuan 8bit model

## Summary

Upstream ships one translation-head calibration for
`mlx-community/Hy-MT2-1.8B-8bit`: en→zh. The simultaneous-MT engine loads a
calibration at construction and raises when the file for the requested
direction is missing, so `--simultaneous` currently works for en→zh only.

This PR adds the zh→en calibration file in the same format, produced with the
same procedure as the en→zh file: alignment-head detection over translation
datasets, translation-score (TS) ranking, stability checks, and a promotion
gate. The heads were detected with the PyTorch bf16 reference
implementation and transferred to the 8bit MLX checkpoint; the transfer was
verified (the 8 calibrated heads are the top-8 by TS score on the MLX
checkpoint, and the attention matrices agree with the PyTorch eager
baseline). The file records the full provenance: pinned model revision,
quantization, source hashes, per-check stability flags, and the promotion
gate result.

## User impact

- `--simultaneous` with zh→en on `Hy-MT2-1.8B-8bit` works on a fresh
  install. Without this file the engine raises at startup.
- No existing behavior changes. The en→zh file is untouched; the loader,
  the engine, and the commit policy are unchanged.

## A question for the maintainer (separate decision)

On `main`, a missing calibration raises at engine construction. An earlier
design used silent deactivation instead: log a warning naming the missing
(model, direction) tuple, disable the simultaneous path, and fall back to
the base translate-on-close behavior. The simultaneous AlignAtt paper
hard-fails in the same situation. Both are defensible; the question is which
the project wants. This PR ships files only and does not change the behavior
either way.

## Calibration quality notes

- Top head: layer 9, head 5 (TS score 0.79 on the 8bit MLX checkpoint,
  0.79 on the PyTorch bf16 reference), the same primary head as the en→zh
  and ja→zh calibrations, which supports these being general alignment
  heads rather than direction-specific ones.
- 8 heads total, matching the en→zh file's head count.
- The test suite includes a golden-attention test: the heads are loaded
  from the bundled file and must reproduce the recorded commit decisions of
  the calibrated engine on real captured attention slices. A corrupted or
  reordered head list fails the test (verified with top-1 and top-3
  corruption).

## Validation

- New tests (`tests/test_simul_calibration_files.py`): the file loads
  through `load_calibration` with an exact prompt match; the engine
  constructs for zh→en where it raised before (negative control: a missing
  file still raises); the golden-attention reproduction test; the
  corruption-detection test.
- `uv run pytest -q tests/ --ignore=tests/test_pipeline.py`: same result as
  `main` apart from the new tests.
- `ruff check .`: passes.
- Live smoke on Apple Silicon (Qwen3 ASR + `Hy-MT2-1.8B-8bit`, zh→en,
  simultaneous): drafts release during speech; draft coverage 0.83 over four
  finals with the paper commit policy.

## Checklist

- [x] I searched for an existing issue or discussion and linked it when
      relevant. (Will link the display/event-stream issue if the maintainer
      prefers calibrations discussed there.)
- [x] I added or updated tests for behavior changes.
- [x] I updated documentation for user-facing changes. (The file itself
      documents provenance; no user-facing docs change.)
- [x] I ran `ruff check .`.
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or
      private data.
