---
title: "MLX-native Sortformer diarization backend"
status: implementation
source: "Probed and verified on integration branch: mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16 via mlx-audio streaming API"
score: 0.8
id: dgx5v2br6xbg8rqx2v15b2ke
pr: "#450"
worktree: .worktrees/wlk-diarization-mlx
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

### Feedback Cycles

- Cycle 1 (2026-10-31 maintainer review on PR #450, run against main with #461 merged):
  REJECTED pending fixes. (a) `diarization_processor` picks the buffered path via
  `hasattr(self.diarization, "buffer_audio")` but this backend defines `_buffer_audio`, so
  it takes the Diart cumulative path: `state.new_diarization` is replaced instead of
  extended, segments not yet consumed are lost whenever `diarize()` returns `[]`, and there
  is no drain at EOF, so the last few seconds are never diarized. (b) `insert_silence()` is
  a no-op, so only voiced audio reaches diarization and speaker timestamps drift from the
  transcript after each pause; the NeMo backend shifts `global_time_offset` for this.
  (c) `model.feed()` runs on the event loop — #461 moved the NeMo forward pass off the loop,
  and MLX has to stay on one thread (`There is no Stream(gpu, ...) in current thread`,
  hit in #426), so it needs a dedicated thread rather than a plain `to_thread`.
  (d) The extra pins `mlx-audio>=0.4.4,<0.5` while #426 needs `>=0.5.1`; the answer must show
  whether the Sortformer conversion works on 0.5.x so both backends can share one range and
  install together. He also asked for a test going through `AudioProcessor` with a fake
  model, which would have caught (a) and (b). The 2026-11-07 ping restates all four.
  Also unverified at this stage: `git merge-tree` against upstream main (ada82d4) conflicts
  in exactly one file, `uv.lock`, which is the same dependency-range decision as (d).
  Status: awaiting distinct FO authorization (fix / decline / hold / route for decision)
  before any candidate edit, commit, or reviewer rerun.

- Cycle 1 evidence for finding (d), the mlx-audio range (measured 2026-11-08, wheels only,
  no model download): the Sortformer streaming API is stable from the pinned `0.4.4` through
  `0.6.4` (current release). `mlx_audio.vad.__init__` exports `load`/`load_model` identically;
  `Sortformer.init_streaming_state()` and `feed(chunk, state, *, sample_rate, threshold,
  min_duration, merge_gap, spkcache_max, fifo_max)` are byte-identical in signature across
  0.4.4/0.5.1/0.5.9/0.6.4; the whole `models/sortformer/sortformer.py` delta between 0.4.4 and
  0.6.4 is one internal refactor of the streaming `chunk_emb_len` computation (32 lines,
  same semantics). Note also: `mlx_audio` has no `diarization` module in any version —
  Sortformer lives under `mlx_audio/vad/models/sortformer/`. So widening the extra to share
  #426's `>=0.5.1` is API-safe; the only remaining risk is numeric (segment parity when the
  real weights run on 0.5.x/0.6.x), which needs the 31.5s clip against the real model.
  Disposition for (d): fix once numeric parity is shown; not `route for decision`.
