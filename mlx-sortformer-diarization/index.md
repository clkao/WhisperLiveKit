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

- **AC-1 (buffered Sortformer contract)**: `SortformerMLXDiarizationOnline` exposes
  `buffer_audio` — the exact attribute `AudioProcessor.diarization_processor` tests
  (`whisperlivekit/audio_processor.py:823`) to pick the extend path over Diart's cumulative
  replace path — so segments accumulate across `diarize()` calls, one `diarize()` call feeds
  every buffered full chunk rather than only one, and a `diarize()` that returns `[]` leaves
  the pending segments in `get_segments()` instead of discarding them.
  **Verified by:** `tests/test_diarization_mlx_backend.py::test_buffer_audio_is_public_for_the_buffered_processor_path`,
  `::test_diarize_feeds_every_buffered_chunk_and_extends` (two 5s chunks in one poll → both
  segments, `[(0.0,1),(5.0,2)]`), `::test_diarize_keeps_segments_when_a_chunk_yields_none`,
  and `::test_audio_processor_extends_segments_and_keeps_them_on_empty_result` (drives the real
  `AudioProcessor.create_tasks()`/`process_audio()` loop, one chunk per `diarize()` call).
  Falsified if: renaming `buffer_audio` back to `_buffer_audio` does not make the processor-level
  test fail with `timed out waiting for the second chunk`, or an empty-chunk `diarize()` returns
  non-empty, or `get_segments()` shrinks after a `[]` return.

- **AC-2 (insert_silence advances the diarization clock)**: `insert_silence(d)` adds `d` to
  `global_time_offset` under the segment lock and `_to_segments()` adds that offset to every
  segment start/end, keeping speaker segment times aligned with the transcript across pauses;
  silence itself is never fed to the model.
  **Verified by:** `tests/test_diarization_mlx_backend.py::test_insert_silence_shifts_segment_times`
  — a 5s chunk yields a segment at 0.0, then `insert_silence(2.5)` makes the next chunk's
  segment report 7.5–12.5. Falsified if: dropping the offset from `_to_segments()` (or making
  `insert_silence()` a no-op) does not make that test report 5.0–10.0.
  Evidence gap: no test drives a `Silence` item through `AudioProcessor.diarization_processor`,
  so the asserted boundary is the backend method, not the processor's silence path.

- **AC-3 (no model call on the event loop; one thread per session)**: every model call for a
  session — `init_streaming_state()` and each `feed()` — runs through
  `loop.run_in_executor()` on that session's single `ThreadPoolExecutor(max_workers=1)`, never
  inline on the loop and never via `asyncio.to_thread()`, because MLX resolves its GPU stream
  per thread (#426: `There is no Stream(gpu, ...) in current thread`).
  **Verified by:** `tests/test_diarization_mlx_backend.py::test_feed_runs_on_one_dedicated_thread_and_leaves_the_loop_free`
  — the union of threads that ran init + feed has exactly one member, that member is not the
  event-loop thread, and a 5ms heartbeat ticks more than 5 times while a 200ms feed is in
  flight. Falsified if: calling `self._feed` inline (or through `asyncio.to_thread`) does not
  make it fail on two thread ids / a starved heartbeat.

- **AC-4 (sub-chunk tail diarized at end of stream)**: `SortformerMLXDiarizationOnline.flush()`
  feeds the remaining buffer when it is shorter than `CHUNK_DURATION_SECONDS`, and
  `AudioProcessor.diarization_processor` awaits it via a `getattr` hook before its final drain,
  so the last seconds of a stream are diarized instead of dropped (NeMo/Diart unaffected).
  **Verified by:** `tests/test_diarization_mlx_backend.py::test_flush_feeds_the_partial_tail`
  (a 3s tail reaches the model only through `flush()`, buffer left empty) and
  `::test_audio_processor_flushes_the_partial_tail_at_eof` (7s written through `process_audio()`
  plus EOF → model saw chunk sizes `[16000*5, 16000*2]`). Falsified if: deleting the `flush`
  hook from `whisperlivekit/audio_processor.py` does not leave the processor-level test seeing
  `[80000]` only.

- **AC-5 (one mlx-audio range with #426; lockfile canonical for it)**: the
  `diarization-mlx-sortformer` extra pins
  `mlx-audio>=0.5.1,<0.6; sys_platform == "darwin" and platform_machine == "arm64"`
  (`pyproject.toml:106`), the same range as #426's `nemotron-mlx-asr` extra, so both extras
  install into one environment; `uv.lock` resolves `mlx-audio 0.5.9` and declares the
  `conflicts` entries the extra needs.
  **Verified by:** `git show fork/spacedock-ensign/nemotron-mlx-asr-backend-rebased:pyproject.toml`
  showing the identical specifier for `nemotron-mlx-asr`; `uv lock --check --no-config` exiting 0
  on the branch (`--no-config` is required: this machine's `~/.config/uv/uv.toml` sets
  `exclude-newer = "7 days"`, which makes plain `uv lock --check` re-resolve and also fails on
  pristine `origin/main`); and `grep -A1 'name = "mlx-audio"' uv.lock` reading
  `version = "0.5.9"`. Falsified if: `--check --no-config` exits non-zero, or the two extras'
  specifiers stop matching, or the lock resolves a version outside `>=0.5.1,<0.6`.
  Scope note: the ~22k-line `uv.lock` diff is the measured mechanical cost of the two `conflicts`
  entries, not resolution drift (Feedback Cycles cycle 3 probe: 7 lines with no conflicts, 22,230
  with two pairs). Behavioural range parity was measured separately — mlx-audio 0.4.4 vs 0.5.9,
  mlx 0.31.2, 31.5s zh clip, identical 12 segments — and is recorded in Feedback Cycles; it is
  not a criterion these tests re-run.

- **AC-6 (no new suite failures versus origin/main at the same commit)**: the branch introduces
  no test failure beyond the set `origin/main` already has at the merge base `ada82d4`.
  **Verified by:** `/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python -m pytest -q tests/ --ignore=tests/test_pipeline.py`
  run on the branch and on a scratch worktree of `origin/main` at `ada82d4`, comparing
  failing/erroring node ids (cycle-2 evidence: 355 passed/17 skipped/4 errors vs 339/17/4 — the
  delta is exactly this branch's 16 tests, and the 4 errors are `test_asr_coalescing_pipeline`'s
  network/fixture cases that CONTRIBUTING excludes), plus
  `pytest -q tests/test_diarization_mlx_backend.py` reporting 16 passed. Falsified if: any failing
  node id on the branch is absent from main's set, or the diarization file reports fewer than 16
  passed. Note: the baseline comparison is a run-to-run procedure, not a committed script — an
  independent check needs the disk for a scratch worktree of `ada82d4`.

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

## Stage Report: implementation (cycle 4)

- DONE: authorize: acceptance-criteria drafting for entity dg. State-only body edit; no code, no push.
  Only `mlx-sortformer-diarization/index.md` touched (79+/5-); no code worktree edit, no install,
  no model download, no branch change (`wlk/diarization-mlx` still at 27ef1fd).
- DONE: DISK: this machine has ~2 GiB free. Do not install anything, no venv, no model downloads; tests only via the shared venv on tests/test_diarization_mlx_backend.py.
  Ran nothing but `pytest -q tests/test_diarization_mlx_backend.py` (16 passed in 2.92s) and
  `ruff check .` (clean) with `/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python`; no sync/install.
- DONE: Replace the free-form bullets with numbered **AC-N** + `Verified by:` criteria covering AC-1..AC-6.
  Five prose bullets replaced by six criteria at index.md:31: buffered contract (AC-1), silence clock
  (AC-2), off-loop single thread (AC-3), EOF tail (AC-4), shared mlx-audio range + canonical lock
  (AC-5), no new suite failures (AC-6); each carries `Verified by:` plus `Falsified if:`.
- DONE: Name the real test ids on the branch for each clause; say so where evidence is missing; do not claim unrun parity work.
  Every cited id exists and passes at 27ef1fd: `test_buffer_audio_is_public_for_the_buffered_processor_path`,
  `test_diarize_feeds_every_buffered_chunk_and_extends`, `test_diarize_keeps_segments_when_a_chunk_yields_none`,
  `test_audio_processor_extends_segments_and_keeps_them_on_empty_result` (AC-1);
  `test_insert_silence_shifts_segment_times` (AC-2);
  `test_feed_runs_on_one_dedicated_thread_and_leaves_the_loop_free` (AC-3);
  `test_flush_feeds_the_partial_tail`, `test_audio_processor_flushes_the_partial_tail_at_eof` (AC-4).
  AC-5 and AC-6 name commands, not tests (no test asserts a lockfile or a suite diff). Parity is cited
  as Feedback Cycles evidence (mlx 0.31.2, 31.5s zh clip, 0.4.4 vs 0.5.9 → identical 12 segments),
  not as a re-run criterion.
- DONE: Leave Work, Context, End value, all Stage Reports and Feedback Cycles untouched.
  `git diff` is confined to the Acceptance criteria section: 5 bullet lines removed, criteria added.
- DONE: Append your stage report line, commit path-scoped, report the criteria written plus any clause lacking current evidence.
  This section; committed path-scoped to the state checkout.
- SKIPPED: push the state branch.
  The same dispatch's authorize line and the parent assignment both say "no push" (explicit constraint
  this session); the state commit is local-only, so peers will not see it until the FO pushes
  `dev-state`.
- FAILED: none

### Summary

Rewrote the PR #450 acceptance criteria as six numbered, falsifiable criteria in this workflow's
shape, each grounded in a test id or command that exists on `wlk/diarization-mlx` at 27ef1fd. Two
clauses name commands rather than tests (AC-5 lockfile/range, AC-6 suite diff — the branch has no
test for either), and AC-2 records that its evidence stops at the backend boundary: no test drives
`Silence` through `AudioProcessor.diarization_processor`. The five replaced bullets also claimed
lc_terminal end-to-end, TUI/overlay speaker markers, and "no NeMo required"; those are not in the
FO's six-clause set, so they are now unstated rather than asserted — flagging it in case the FO
wants them as AC-7..AC-9. State commit is local-only per the no-push constraint.

## Stage Report: validation (fresh validator, PR #450)

Branch `wlk/diarization-mlx` at **27ef1fd**, 8 commits on `origin/main` (`ada82d4`), tree clean,
no staged files, nothing pushed (`origin/wlk-diarization-mlx` and the fork untouched). All runs used
`/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python`; nothing installed, no venv, no model
download; `--no-config` on every uv call (cycle-3 machine artefact).

**Verdict: AC-1 through AC-5 PASS, reproduced independently. AC-6 PARTIAL — its 16-passed clause
reproduces; its suite-diff clause was NOT re-run because this dispatch caps test runs to
`tests/test_diarization_mlx_backend.py` plus a cited test and the box has 2.6 GiB free (AC-6 itself
says an independent check needs a scratch worktree of `ada82d4`). No FAILED condition was found in
the branch: every named test exists, every named test passes, every falsification clause I
attempted fires, and the diff is confined to the backend + wiring + the four maintainer fixes +
`pyproject.toml`/`uv.lock`.**

- DONE: AC-1 buffered Sortformer contract — PASS.
  `pytest -q tests/test_diarization_mlx_backend.py` → `16 passed in 1.55s`; `--collect-only` lists
exactly the 16 ids, including all four AC-1 ids. Grounding checked in source:
`audio_processor.py:823` is literally `has_buffer = hasattr(self.diarization, 'buffer_audio')`, and
the backend exposes `self.buffer_audio` (`sortformer_mlx_backend.py:71`), so the extend path is
taken by construction. `test_diarize_feeds_every_buffered_chunk_and_extends` really puts 10s in the
buffer and asserts `[(0.0, 1), (5.0, 2)]` from one `diarize()` (both chunks fed);
`test_diarize_keeps_segments_when_a_chunk_yields_none` returns `[]` for the second chunk and still
reports `[(0.0, 5.0, 1)]`; the processor-level test writes one 5s chunk at a time with a wait
between writes, so each is its own `diarize()` call. All four falsification clauses were exercised
(the `buffer_audio` rename is mutation 3 below).

- DONE: AC-2 insert_silence advances the diarization clock — PASS (backend boundary, as the AC
  declares). `test_insert_silence_shifts_segment_times` passes: after `insert_silence(2.5)` the next
  chunk reports `(7.5, 12.5)`. Falsification reproduced exactly: dropping the offset from
  `_to_segments()` yields `assert [(5.0, 10.0)] == [(7.5, 12.5)]` (mutation 1 below). Verified the
  silence path in source too: `audio_processor.py:829-831` consumes a `Silence` item, calls
  `insert_silence(item.duration)` and `continue`s, so silence is never fed to the model. The AC's
  declared evidence gap is accurate: `grep -rn Silence tests/` shows no test drives `Silence`
  through `diarization_processor`, so the assertion stops at the backend method. Noted, not a fail —
  the AC states it.

- DONE: AC-3 off-loop, one thread per session — PASS.
  `test_feed_runs_on_one_dedicated_thread_and_leaves_the_loop_free` passes: one non-loop thread
  across init+feed, heartbeat > 5 ticks against a 200ms feed. Source: one
  `ThreadPoolExecutor(max_workers=1)` per session (`:77`), `feed()` via
  `await loop.run_in_executor(self._mlx_executor, self._feed, chunk)` (`:165`), and
  `grep -n to_thread` hits only the explanatory comment at `:75` (no `asyncio.to_thread` anywhere).
  One wording imprecision, not a defect: `init_streaming_state()` goes through
  `self._mlx_executor.submit(...).result()` (`:81-83`) rather than `loop.run_in_executor`, because
  it runs in the synchronous constructor where no loop exists. Same executor, same single thread,
  which is what the test asserts and what #426 needs; the AC's "via run_in_executor" is true of
  every `feed()` and of init only in substance. Suggest re-wording at acceptance, no code change.

- DONE: AC-4 sub-chunk tail diarized at EOF — PASS.
  `test_flush_feeds_the_partial_tail` passes (3s tail reaches the model only through `flush()`,
  `buffer_audio.size == 0` after, second `flush()` returns `[]`) and
  `test_audio_processor_flushes_the_partial_tail_at_eof` passes with
  `[c.size for c in model.received_chunks] == [16000*5, 16000*2]`. Falsification reproduced exactly:
  deleting the `getattr(self.diarization, "flush", None)` hook yields `assert [80000] == [80000,
  32000]` (mutation 2 below). Confirmed the hook cannot touch the other backends: it sits inside
  `if has_buffer:`, and `getattr(..., "flush", None)` is `None` for NeMo's `sortformer_backend.py`
  (which has `buffer_audio` but no `flush`) and for Diart (no `buffer_audio` at all).

- DONE: AC-5 one mlx-audio range with #426, canonical lock — PASS, all three clauses.
  (i) `git show fork/spacedock-ensign/nemotron-mlx-asr-backend-rebased:pyproject.toml | grep -n
  'mlx-audio>='` → line 75 `'mlx-audio>=0.5.1,<0.6; sys_platform == "darwin" and
  platform_machine == "arm64"',`; branch `pyproject.toml:106` is the byte-identical line. (ii)
  `uv lock --check --no-config` → `Resolved 407 packages in 9ms`, `EXIT=0` (uv 0.10.7). (iii)
  `grep -A1 'name = "mlx-audio"' uv.lock` → `version = "0.5.9"`, inside `>=0.5.1,<0.6`; the lock's
  requirement entry is `{ name = "mlx-audio", marker = "platform_machine == 'arm64' and sys_platform
  == 'darwin' and extra == 'diarization-mlx-sortformer'", specifier = ">=0.5.1,<0.6" }`, and the two
  new conflicts pairs (`qwen3-streaming` / `qwen3-vllm` × `diarization-mlx-sortformer`,
  `pyproject.toml:168-175`) show up in the lock as
  `extra != 'extra-14-whisperlivekit-diarization-mlx-sortformer'` markers. Version-line audit of
  `git diff origin/main..HEAD -- uv.lock | grep '^[+-]version = '`: added `0.5.9` (mlx-audio), `1.72`
  (miniaudio), `1.2.1` (win32-setctime), `1.0` (httpx2-jsfetch), plus one `+2.11.0` entry; removed
  one `2.8.0` line — the darwin-torch entry repartition cycle 3 described, no package bumped or
  lowered. Parity re-running was out of scope per the dispatch and not attempted.

- PARTIAL: AC-6 no new suite failures versus origin/main — its 16-passed clause PASSES, its
  suite-diff clause is NOT INDEPENDENTLY REPRODUCED. `pytest -q
  tests/test_diarization_mlx_backend.py` → `16 passed` (AC-6 requires ≥16). The full-suite
  node-id comparison needs `pytest -q tests/ --ignore=tests/test_pipeline.py` on this branch plus a
  scratch worktree of `ada82d4`, which exceeds both this dispatch's test-run cap and the 2.6 GiB
  free. In its place I bounded the risk structurally and with the only pre-existing tests that
  cover the two shared paths this branch edits:
  `pytest -q tests/test_sortformer_event_loop.py tests/test_sortformer_max_speakers.py` → `19
  passed in 1.98s`. The bound: outside the new module and new tests, the branch's non-lock diff is
  (i) additive arms in `core.py` (`_do_init`, `online_diarization_factory`) reachable only for the
  new backend name, (ii) `parse_args.py` one extra choice, (iii) `config.py` a widened validation
  guard plus one new default, (iv) the `hasattr`-gated EOF hook. The concrete follow-up if the FO
  wants AC-6 fully closed is the two-run node-id diff AC-6 already names; it is a run-to-run
  procedure, not a defect in the tree.

- DONE: mutation exercise — three mutations, each restored byte-for-byte, green again after each.
  Baseline hashes: `sortformer_mlx_backend.py`
  `286960894aba3dfb5d934a9a0abf9a053b13771c63822a6bb47cfc12c757da42`, `audio_processor.py`
  `317a8520658009d90835ed3178f59ac188977bf3bd44010dcf03efcb0bfac619`; restored tree `git status
  --porcelain` empty and hashes re-matching, `16 passed` again.
  1. **AC-2** (required exactly-one-red): removed the `+ offset` from both lines of `_to_segments()`
     → `1 failed, 15 passed`; the only red is `test_insert_silence_shifts_segment_times`, failing
     `assert [(5.0, 10.0)] == [(7.5, 12.5)]` — the exact value AC-2's falsification clause predicts.
  2. **AC-4** (required exactly-one-red): deleted the three `flush` hook lines from
     `diarization_processor` → `1 failed, 15 passed`; the only red is
     `test_audio_processor_flushes_the_partial_tail_at_eof`, failing `assert [80000] == [80000,
     32000]` — the exact `[80000]`-only signature AC-4 predicts.
  3. **AC-1** (extra, check of the AC's named message): renamed `buffer_audio` → `_buffer_audio`
     (12 occurrences) → `4 failed, 12 passed`. As expected more than one red, because the rename
     also flips the `hasattr` guard and the EOF test; run alone, the processor-level test
     `test_audio_processor_extends_segments_and_keeps_them_on_empty_result` fails with exactly
     `AssertionError: timed out waiting for the second chunk` (`:338`), the message AC-1 names. So
     the processor-level test does discriminate the extend path from the cumulative one.

- DONE: scope check on the branch — nothing outside the backend + wiring + the four maintainer
  fixes + the dependency range. `git diff --stat origin/main..HEAD` = 8 files: `pyproject.toml`
  (+17), `uv.lock` (the conflicts-driven churn), `whisperlivekit/diarization/sortformer_mlx_backend.py`
  (+198), `core.py` (+12), `config.py` (6), `parse_args.py` (2), `audio_processor.py` (13),
  `tests/test_diarization_mlx_backend.py` (+404). Per commit: d6f715c backend+wiring, f66a449 extra,
  70ee9e7 first tests, 9aed68d conflicts, 6ab8584 fixes (a)(b)(c)+(a)'s EOF drain, 33bfa80 the eight
  new tests, 3e6984b range+lock, 27ef1fd pyproject comment. The only line not literally one of the
  four fixes is `config.py:235` widening the `sortformer_max_speakers` guard to accept
  `mlx-sortformer`; it ships in the feature commit (d6f715c), was declared in the branch-cut report
  as a deliberate 1-line peer-parity change, and is covered by
  `test_config_accepts_mlx_sortformer_with_max_speakers` /
  `test_config_still_rejects_max_speakers_for_other_backends`.
  Two Scope-section items are obsolete rather than missing: `scripts/lc_terminal.py` does not exist
  on `origin/main` (post-rebase the CLI surface is `parse_args.py`, verified end to end below), and
  the backend lives at `whisperlivekit/diarization/sortformer_mlx_backend.py` in main's package
  layout. `ruff check .` → `All checks passed!`.

- DONE: CLI→config wiring spot check (no model load, no network):
  `parse_args(['--diarization-backend','mlx-sortformer','--sortformer-max-speakers','2'])` →
  `backend: mlx-sortformer | model: mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16 |
  max_speakers: 2`, confirming `from_namespace` carries the flag into `WhisperLiveKitConfig` so both
  `_do_init` and `online_diarization_factory` see it.

- SKIPPED: AC-6's full-suite vs `ada82d4` comparison — dispatch test-run cap (only
  `tests/test_diarization_mlx_backend.py` plus a cited test) and 2.6 GiB free. Not a branch defect;
  the commands for the FO are AC-6's own.
- SKIPPED: re-running the mlx-audio version parity measurement — explicitly out of scope; it is
  Feedback Cycles cycle-2 evidence and not a criterion.
- FAILED: none.

### Summary

Fresh validation of PR #450 at 27ef1fd with the implementation report's claims ignored: AC-1 through
AC-5 reproduce from the tree alone (all 16 named tests exist and pass, `uv lock --check --no-config`
exits 0, mlx-audio 0.5.9 inside `>=0.5.1,<0.6`, specifier byte-identical to #426's), and three
mutations prove the tests can fail — dropping the silence offset reds exactly
`test_insert_silence_shifts_segment_times` with `(5.0, 10.0)` instead of `(7.5, 12.5)`, deleting
the EOF `flush` hook reds exactly `test_audio_processor_flushes_the_partial_tail_at_eof` with
`[80000]`, and renaming `buffer_audio` reds the processor-level test with the named `timed out
waiting for the second chunk`; each mutation was restored byte-for-byte (hashes re-verified) and the
file returned to 16 passed. AC-6 is PARTIAL only in its suite-diff half: the 16-passed clause holds
and the shared-path risk is bounded by 19 passing pre-existing NeMo-path tests plus a file-level
scope audit, but the full-suite node-id comparison is not runnable inside this dispatch's test-run
cap and disk. One wording fix suggested (AC-3's "via run_in_executor" covers `feed()` literally and
`init_streaming_state()` only in substance). No product code edited, no push, no staged files.
