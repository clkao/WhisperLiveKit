feat: MLX-native Canary-1B-v2 backend (canary-mlx, Apple Silicon)

## Summary

The `canary` backend added recently runs NVIDIA Canary-1B-v2 through NeMo,
which is a heavy dependency and fails offline. This PR adds `canary-mlx`:
the same model through mlx-audio's pure-MLX implementation
(`mlx_audio.stt.models.canary`), entirely on Apple Silicon, with community
MLX checkpoints (8-bit by default: `Mediform/canary-1b-v2-mlx-q8`; full
precision `qfuxa/canary-mlx` selectable). No NeMo, no CUDA, no network
after the first model cache.

The backend implements the same LocalAgreement contract as the NeMo canary
backend (`transcribe()` / `ts_words()` / `segments_end_ts()`), reusing the
shared stamp-to-token helpers so both backends emit identical token shapes.
It is selected with `--backend canary-mlx` and configured with
`--canary-mlx-model`. mlx-audio is an optional extra (`canary-mlx`, Apple
Silicon only) and is imported lazily inside the loader.

Two deliberate differences from the NeMo backend:

1. **Explicit language required.** The NeMo backend auto-detects language
   through an AmberNet speaker model; no MLX language-ID equivalent exists
   yet. `canary-mlx` validates `--language` against Canary's 25 supported
   codes at startup and fails fast on `auto`.
2. **Timestamps are derived, not model-emitted.** mlx-audio's canary
   prompts with `<|notimestamp|>` and returns text only. Word and segment
   stamps are allocated proportionally to word length across the
   transcribed window: monotonic, order-preserving, spanning the window.
   Adequate for LocalAgreement and caption assembly; the NeMo backend
   remains the reference for model-native timing.

## User impact

- New backend choice on Apple Silicon; no existing behavior changes.
- The `canary-mlx` extra is mutually exclusive with the `qwen3-streaming`,
  `qwen3-vllm`, and `qwen3-vllm-metal` extras in the same environment:
  mlx-audio's canary-capable versions require transformers>=5.14, while
  those extras pin transformers==4.57.6 (declared via `[tool.uv]
  conflicts`, so the lock resolves and installing both together is
  rejected with a clear error).

## Validation

- New tests (`tests/test_canary_mlx_backend.py`, hermetic: mlx-audio is
  faked at the import boundary): derived-stamp properties (monotonic,
  span, proportionality, degenerate windows), hypothesis shape, ts_words
  token shape, session-language propagation, empty-text handling, the
  language requirement, language-set parity with the NeMo backend, and the
  install-hint error path.
- Live smoke on Apple Silicon (`demo_en_30s.wav`, 30.0s): transcribe in
  1.45s (RTF 0.048), 78 words, stamps monotonic over the full window.
- `uv run pytest -q tests/ --ignore=tests/test_pipeline.py`: failure and
  error set identical to `main` (pre-existing canary/NeMo environment
  failures, deepgram, ffmpeg-dependent collection). The new tests pass.
- `ruff check .`: passes. `uv lock --check`: passes.

## Checklist

- [x] I searched for an existing issue or discussion and linked it when
      relevant. (No existing issue covers an MLX-native canary backend.)
- [x] I added or updated tests for behavior changes.
- [x] I updated documentation for user-facing changes. (Backend
      discoverable through `--backend --help` and `--canary-mlx-model`;
      the derived-timestamp caveat is documented in the module docstring.)
- [x] I ran `ruff check .`.
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or
      private data.
