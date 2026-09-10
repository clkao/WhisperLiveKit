feat: MLX-native sortformer diarization backend (pure MLX, no NeMo)

## Summary

The existing `sortformer` diarization backend requires NeMo plus a `.nemo`
model download, which is heavy and fails offline. This PR adds
`mlx-sortformer`: the same streaming Sortformer model running through
mlx-audio's MLX conversion
(`mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16`), entirely on
Apple Silicon, with no NeMo, no ONNX, and no network access after the
first cache.

The backend mirrors the NeMo backend's contract exactly
(`insert_audio_chunk` / `insert_silence` / `diarize` / `get_segments` /
`close`), so the pipeline's diarization loop treats it as a peer. It is
selected with `--diarization-backend mlx-sortformer` and wired in the same
two places as the other backends (engine init and the per-session
factory). Speaker capping (`sortformer_max_speakers`) works the same as
for the NeMo backend.

mlx-audio is an optional extra (`diarization-mlx-sortformer`, Apple
Silicon only) and is imported inside the model loader, so the package
imports cleanly without it.

## User impact

- New backend choice; no existing behavior changes. `sortformer` and
  `diart` behave exactly as before, including the `sortformer_max_speakers`
  validation (now also accepting `mlx-sortformer`, since the MLX backend
  applies the same cap).
- On Apple Silicon with the extra installed, diarization runs fully
  offline on MLX.

## Validation

- New tests (`tests/test_diarization_mlx_backend.py`, hermetic: the
  mlx-audio import boundary is faked, no model download): the streaming
  contract (chunk accumulation, feed at chunk size, segment accumulation,
  max-speaker filter, close), the lazy-import property, config validation
  parity, and the factory wiring. 8 tests.
- Live smoke on Apple Silicon with the real model: the full 31.5s zh→en
  test clip processed at RTF 0.024 through the ported contract, 12
  segments, single speaker correctly identified end to end.
- `uv run pytest -q tests/ --ignore=tests/test_pipeline.py`: failure and
  error set identical to `main` (compared run-to-run in the same checkout;
  the pre-existing canary, deepgram, and qwen3-shim failures are
  environmental). The new tests all pass.
- `ruff check .`: passes.

## Checklist

- [x] I added or updated tests for behavior changes.
- [ ] I updated documentation for user-facing changes. (The backend is
      discoverable through `--diarization-backend --help`; a README mention
      can follow.)
- [x] I ran `ruff check .`.
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or
      private data.
