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

## Stage Report: branch cut (implementation — port to origin/main)

- DONE: Backend slotted into main's diarization/ package structure
  Branch wlk/diarization-mlx (3 commits on origin/main: e5786b9 backend +
  wiring, 3e5bd93 pyproject extra, 4a6fdbb tests). The backend module is
  the c87e4ba-era final version (API mirrors the NeMo backend); main's
  audio_processor diarization loop already uses the same contract
  (insert_audio_chunk/insert_silence/diarize), so c87e4ba's substance is
  satisfied by construction on main's restructured pipeline.
- DONE: mlx-audio optional + lazy-import verified
  Extra diarization-mlx-sortformer added (darwin/arm64 marker, matching the
  source commit f9b5768); the module imports with mlx_audio absent
  (test_module_import_is_lazy); loader import is inside __init__.
- DONE: Tests green vs baseline; contract test present
  8 new hermetic tests pass. Full suite failure set run-to-run identical to
  origin/main in the same checkout (canary x2, deepgram, qwen3-shim x5 —
  environmental; note: the qwen3-shim failures appear on pristine main in
  this worktree, so they predate this change). ruff clean.
- DONE: Live smoke with the real model
  31.5s zh_long.wav clip: RTF 0.024, 12 segments, single speaker correctly
  identified end to end through the ported contract (matches the original
  integration-branch probe: loads in ~6.6s, single-speaker zh clip).
- SKIPPED: none
- FAILED: none

### Summary

Ported the MLX sortformer diarization backend onto origin/main as a peer
backend in whisperlivekit/diarization/. One deliberate 1-line parity
change beyond the source commits: sortformer_max_speakers validation now
accepts mlx-sortformer (the source predates that validation; the MLX
backend applies the same cap, so peer parity is the intent). pr.md drafted
in this folder for FO review. NOT pushed — awaits FO review.
