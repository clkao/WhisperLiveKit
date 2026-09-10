---
title: "MLX-native Sortformer diarization backend"
status: backlog
source: "Probed and verified on integration branch: mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16 via mlx-audio streaming API"
score: 0.8
id: dgx5v2br6xbg8rqx2v15b2ke
---

# MLX-native Sortformer diarization backend

## Summary
Add `mlx-sortformer` as a diarization backend using mlx-audio's MLX conversion of nvidia/diar_streaming_sortformer_4spk-v2.1. Pure MLX, no NeMo, no ONNX, works offline on Apple Silicon.

## Context
- Existing `sortformer` backend requires NeMo + .nemo download — heavy, not MLX-native, fails offline.
- mlx-audio ships an MLX conversion with streaming: `model.init_streaming_state()` → `model.feed(chunk, state)` → `result.segments`.
- Probe: 3.6s load, RTF 0.13, 12 segments on zh_long.wav, single speaker correctly detected.
- `insert_audio_chunk`/`insert_silence`/`diarize()` contract implemented and tested.

## Scope
- `whisperlivekit/diarization/sortformer_mlx_backend.py` — SortformerMLXDiarization (shared holder) + SortformerMLXDiarizationOnline (per-session: buffer in insert_audio_chunk, feed in 5s chunks via model.feed() in diarize(), return SpeakerSegment list).
- `whisperlivekit/core.py` — wire mlx-sortformer in _do_init + online_diarization_factory.
- `whisperlivekit/config.py` — sortformer_mlx_model default + diarization_backend choices.
- `whisperlivekit/parse_args.py` — add mlx-sortformer to --diarization-backend choices.
- `scripts/lc_terminal.py` — --diarization-backend flag + passthrough.
- `pyproject.toml` — add mlx-audio to appropriate extra.
- Tests: unit test with stub model (no MLX needed for collection); integration test insert_audio_chunk/diarize() contract.

## Acceptance criteria
- `--diarize --diarization-backend mlx-sortformer` works end-to-end via lc_terminal.
- No AttributeError from audio_processor diarization loop.
- Speaker markers appear in TUI/overlay when multiple speakers detected.
- uv lock --check passes. ruff check clean. Tests pass without MLX installed.
- No NeMo dependency required.
