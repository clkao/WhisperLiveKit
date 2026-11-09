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

## Stage Report: implementation (cycle 2)

- DONE: authorize: fix — maintainer findings on PR #450 cycle 1: items (a)(b)(c) and the AudioProcessor test he asked for. Item (d) the mlx-audio range is settled to >=0.5.1,<0.6. No scope change.
  Disposition ran as authorized: 6ab8584 (backend + one EOF hook in `diarization_processor`), 33bfa80 (tests), 3e6984b (extra + lockfile). No other behavior touched.
- DONE: DO NOT PUSH. Commit only to the local branch wlk/diarization-mlx. Do not push to the fork, do not update PR #450, do not force anything.
  Nothing pushed; `origin/wlk/diarization-mlx` and the fork are untouched. Branch is 7 local commits on ada82d4 (4 rebased + 3 new).
- DONE: rebase wlk/diarization-mlx onto origin/main (ada82d4); uv.lock resolved by the range change, then `uv lock`.
  Rebase conflicted only in uv.lock, as predicted. Those conflicts were resolved by taking origin/main's lock bytes (no hand-merged lock), which made the two lock-only commits b194326 and 092515e empty — their content was already in main's lockfile, so they dropped. `uv lock` (regenerated from the final pyproject) produced the committed lock; `uv lock --check` passes.
- DONE: pyproject.toml extra goes from mlx-audio>=0.4.4,<0.5 to mlx-audio>=0.5.1,<0.6, sharing one range, excluding 0.6.x.
  Lock resolves mlx-audio 0.5.9 + mlx 0.31.2. 0.5.x needs mlx>=0.31.1, which fits mlx-lm>=0.31.3,<0.32, so no new conflicts entry. 0.6.0/0.6.4 wheel metadata pins mlx==0.32.4 exactly; 0.5.1/0.5.9 do not.
- DONE: rename _buffer_audio to buffer_audio; segments extend rather than replace and a [] return drops nothing.
  `test_audio_processor_extends_segments_and_keeps_them_on_empty_result` runs the real online backend on a scripted model one chunk per diarize() call: renaming the attribute back to `_buffer_audio` makes it fail ("timed out waiting for the second chunk", the cumulative path having replaced state with []) and an empty chunk's [] leaves the two segments intact.
- DONE: drain at EOF: feed the remaining partial chunk so the last seconds are diarized.
  `flush()` feeds the sub-chunk tail and `diarization_processor` awaits it before its final drain (a `getattr` hook, so NeMo/Diart are unaffected). `test_audio_processor_flushes_the_partial_tail_at_eof` writes 7s and asserts the model saw [5.0s, 2.0s]; deleting the hook makes it fail with `[80000]` only.
- DONE: insert_silence() advances global_time_offset as the NeMo backend does (:237-246, base_time at :348).
  Same `+=` under the segment lock, and `_to_segments` reports `seg.start/end + offset`. `test_insert_silence_shifts_segment_times` fails (5.0-10.0 instead of 7.5-12.5) if the offset is dropped.
- DONE: move model.feed() off the event loop onto a dedicated thread, not a plain to_thread.
  One `ThreadPoolExecutor(max_workers=1)` per session; `init_streaming_state()` and every `feed()` run on it via `run_in_executor`. `test_feed_runs_on_one_dedicated_thread_and_leaves_the_loop_free` asserts one non-loop thread across init+feed and that a 0.2s feed does not starve a heartbeat; calling `self._feed` inline makes it fail with two thread ids.
- DONE: add the AudioProcessor-level test with a fake model.
  Two of them (accumulate/[] and the EOF tail), both driving `AudioProcessor.create_tasks()`/`process_audio()`/EOF; they are the tests that fail for (a) and the missing tail drain.
- DONE: keep the 8 existing hermetic tests green; ruff clean; suite compared run-to-run against origin/main.
  tests/test_diarization_mlx_backend.py 16 passed (8 old + 8 new). `ruff check .` clean. `pytest -q tests/ --ignore=tests/test_pipeline.py`: 355 passed / 17 skipped / 4 errors vs origin/main at ada82d4 in a scratch worktree 339 passed / 17 skipped / 4 errors — same 4 errors (test_asr_coalescing_pipeline network/fixture, excluded by CONTRIBUTING), delta is exactly this branch's 16 tests.
- DONE: name numeric parity honestly.
  Reported below without overclaiming; the 31.5s zh clip run is still outstanding. New measured evidence, wider than the dispatch assumed: this sandbox *can* run MLX (mlx 0.31.2), so I ran the real `diar_streaming_sortformer_4spk-v2.1-fp16` on the repo's LibriSpeech 2-speaker fixture through the new backend on 0.5.9 — 3 segments, speakers {0,2}, tail end 6.08s of a 6.1s clip — and the identical chunk+flush loop on mlx-audio 0.4.4 gave byte-identical segments: (0.32,3.60,0) (4.32,5.04,2) (5.04,6.08,2). Caveat: mlx 0.32.4 (what a bare `pip install mlx-audio` picks today) cannot compile its Metal library here ("Operation not permitted" writing com.apple.metalfe), so the comparison had to pin mlx==0.31.2 on both sides; that is a sandbox limit, not a range fact. One 6.1s clip is not behavioural proof of the range — the 31.5s zh clip remains outstanding.

### Summary

Rebased onto ada82d4 and fixed the four cycle-1 findings on `wlk/diarization-mlx`, locally only. The backend now takes the buffered path (`buffer_audio`), feeds every full chunk per poll, drains the sub-chunk tail through a new `flush()` hook in `diarization_processor`, shifts the segment clock for inserted silence, and keeps every MLX call on one dedicated thread; eight new tests cover each fix and were each verified to fail against the unfixed code. Numeric parity across 0.4.4 → 0.5.9 is measured on one 2-speaker fixture; the 31.5s zh clip run is still outstanding. NOT pushed and PR #450 untouched, per the captain's constraint — publishing is the FO's.

- Cycle 2 (2026-11-08, FO verification of the cycle-1 fix). Functional fixes verified: branch
  rebased onto origin/main (ada82d4, 0 behind), tree clean, ruff clean, 16 diarization tests
  pass under the FO's own run. Finding (d) is now CLOSED by measurement: with mlx==0.31.2,
  mlx-audio 0.4.4 and 0.5.9 both run the real
  diar_streaming_sortformer_4spk-v2.1-fp16 on the 31.5s zh clip and produce identical output —
  12 segments, speaker [0], identical boundaries (first (0.0,5.04),(5.04,7.12),(7.28,10.08)),
  with 0.5.9 faster (RTF 0.093 vs 0.174). The range `>=0.5.1,<0.6` is behaviourally proven.
  NEW finding, material, disposition `fix` (lock scope only): (i) `uv lock --check` FAILS on
  the delivered tree ("The lockfile at uv.lock needs to be updated"), contradicting the cycle-1
  report; (ii) the uv.lock diff against origin/main is 18,887 lines (5,807+/13,080-) for a
  change that needs one extra, i.e. a wholesale re-resolution; (iii) it drags unrelated version
  drift in — torch 2.8.0 -> 2.11.0 and torchaudio 2.8.0 -> 2.11.0 — which a maintainer will
  reject. Remedy: regenerate minimally against main's lock config and uv version, keeping
  unrelated packages at main's versions; prove with `uv lock --check` plus a small lock diff
  containing no unrelated bumps.

- Cycle 3 (2026-11-08, FO correction of cycle 2 — two of its findings were wrong).
  RETRACTED (i): "`uv lock --check` fails on the delivered tree" was an artefact of the FO's
  machine, not the branch. `~/.config/uv/uv.toml` sets `exclude-newer = "7 days"`, so plain
  `uv lock --check` re-resolves; with `--no-config` it passes on this tree in 24ms, and
  pristine origin/main's lock fails identically under the contaminated config. All uv
  verification on this machine must use `--no-config` / `UV_NO_CONFIG=1`.
  RETRACTED (iii): there is no torch/torchaudio version drift. torch 2.8.0 remains for
  py<3.13 darwin and 2.11.0 elsewhere; the change is entry-partition disambiguation forced
  by the new conflicts entries, plus one source line for darwin torch 2.8.0 moving to the
  pytorch cpu index. No package version is bumped.
  CONFIRMED (ii) with a different cause than assumed: the 22k-line uv.lock diff is the
  mechanical price of declaring a conflicts entry — a controlled probe (benign
  `zz-probe-only` extra, uv 0.10.7 --no-config) gives a 7-line diff with no conflicts and
  22,230 lines with two conflict pairs, because any conflicts change re-derives every
  package's resolution-markers (1038 -> 602). The delivered lock is canonical: byte-identical
  to `uv lock --no-config` from origin/main's lock plus the current pyproject, with uv 0.10.7
  and 0.10.12 agreeing.
  The conflicts exist because mlx-audio 0.5.x requires transformers>=5.14.0 while
  qwen3-asr-causal[streaming]==0.1.0 pins transformers==4.57.6.
  DISPOSITION (captain-delegated packaging call, FO decision): ship as-is — keep the
  dedicated `diarization-mlx-sortformer` extra and its conflicts. Folding mlx-audio into the
  existing `mlx-llm-mt` extra would shrink the lock diff to 64 lines but would make MLX
  diarization require the MT extra's dependencies, which is the wrong install surface. The
  churn gets recorded in a pyproject comment instead.

## Stage Report: implementation (cycle 3)

- DONE: authorize: fix — new finding from the first officer's verification of cycle 1. SCOPE IS pyproject.toml AND uv.lock ONLY. Do not touch the backend, audio_processor, or the tests that already pass.
  One pyproject comment added (27ef1fd); no uv.lock edit; backend/audio_processor/tests untouched (`git diff --stat 3e6984b..HEAD` = pyproject.toml 4 insertions only).
- DONE: DO NOT PUSH. Commit only to the local branch wlk/diarization-mlx.
  One local commit 27ef1fd; no push, no force, `origin/wlk/diarization-mlx` and the fork untouched, PR #450 not touched.
- DONE: `uv lock --check` currently FAILS on the delivered tree ("The lockfile at uv.lock needs to be updated"). Make it pass.
  Does not reproduce as a tree defect. `uv lock --check --no-config` passes in 8ms/24ms (no re-resolution) on both the delivered and the committed tree; plain `uv lock --check` fails only under this machine's `~/.config/uv/uv.toml` (`exclude-newer = "7 days"`), where pristine origin/main's lock fails identically ("addition of global exclude newer 2026-11-02..."). Origin/main's lock was produced without an exclude-newer.
- DONE: The uv.lock diff against origin/main is 18,887 lines ... Regenerate so the diff is the mlx-audio extra plus its own dependencies, not a re-resolution.
  The lock is already a resolution, not regeneration drift: it is byte-identical (md5 ad3ffdc2c057f3025de250423a97f8c2) to `uv lock --no-config` run from origin/main's lock plus the current pyproject; uv 0.10.7 and 0.10.12 agree, uv 0.9.30 produces more churn (1588 markers). The residual size is uv re-deriving every package's resolution-markers because the extra needs two new `conflicts` entries — measured: benign extra with no conflicts = 7-line diff / 1038 markers unchanged; same extra with two conflict pairs = 22,230-line diff / 1038->602 markers.
- DONE: Remove the unrelated version drift: the current lock bumps torch 2.8.0 -> 2.11.0 and torchaudio 2.8.0 -> 2.11.0. Keep them at origin/main's versions unless mlx-audio genuinely requires the bump, in which case prove it and say so explicitly.
  No bump to remove, and mlx-audio does not require one. Version-bearing lines that change, in full: added mlx-audio 0.5.9, miniaudio 1.72, win32-setctime 1.2.1, httpx2-jsfetch 1.0 (all from the extra); torch/torchaudio only repartition entries — 2.8.0 still covers py<3.13 darwin (10 markers before and after, merged into fewer entries) and 2.11.0 still covers the rest, plus one added 2.11.0 entry each at a version main already locked. No package version is raised or lowered.
- DONE: Use the same uv version and lock configuration that produced origin/main's uv.lock ... State the uv version you used and how you verified it matches main's.
  Used uv 0.10.7 (Homebrew, also the .venv's `uv = 0.10.7`) with `--no-config`; verified by `uv lock --check --no-config` passing on pristine origin/main's lock in 10-24ms without re-resolving, and by byte-identical output from uv 0.10.12 — so the lock format and resolution semantics match main's.
- DONE: For the record, do not re-litigate finding (d) ... The range stays >=0.5.1,<0.6.
  Range left exactly as delivered; not touched, not re-argued.
- DONE: Proof to report: `uv lock --check` passes; `git diff --stat origin/main..HEAD -- uv.lock` is small; the lock diff contains no unrelated package version changes (list every version line that does change); 16 diarization tests still pass; ruff clean.
  `uv lock --check --no-config` exit 0; `git diff --stat origin/main..HEAD -- uv.lock` = 5,807+/13,080- (not small — inherent to the conflicts entries, per the probe above; FO decision was ship-as-is); version lines listed in the item above; `tests/test_diarization_mlx_backend.py` 16 passed (the 2 AudioProcessor tests fail if the `buffer_audio` rename or the EOF `flush()` hook is reverted); `ruff check .` all checks passed.
- SKIPPED: none
- FAILED: none

### Summary

Per the FO's ship-as-is decision, no uv.lock change was warranted: the delivered lock is already uv's canonical minimal output for this pyproject (`--check --no-config` clean, byte-identical to a fresh incremental lock taken from origin/main's lock), and the large diff is the mechanical cost of the two `conflicts` entries the extra genuinely needs (mlx-audio 0.5.x transformers>=5.14 vs qwen3-asr-causal[streaming]'s transformers==4.57.6). The only edit is a four-line pyproject comment recording those two facts for the next reviewer (27ef1fd), committed locally on wlk/diarization-mlx. Nothing pushed, PR #450 untouched.
