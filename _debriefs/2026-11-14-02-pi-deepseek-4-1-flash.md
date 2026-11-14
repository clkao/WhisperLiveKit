---
session-date: 2026-11-14
sequence: 2
first-commit: 67972ff
last-commit: 9a8f0ae
duration: ~23h elapsed (interleaved with a concurrent session)
---

# Session Debrief — 2026-11-14 #02

One entity, one PR, one long detour: PR #425 (`mlx-qwen3-asr-backend`) went from
rejected-on-quality to approved-awaiting-merge, with the maintainer measuring the branch
himself and saying he is happy to merge. Almost half the session's cost went on correcting
my own decision to build on the integration branch rather than on a branch cut from main.

## Shipped

- **n5** `nemotron-mlx-asr-backend` — [#426](https://github.com/QuentinFuxa/WhisperLiveKit/pull/426). Native Nemotron MLX transducer backend through upstream streaming caches; merged 10:19Z and archived by the concurrent session, not this one.

## Filed (backlog)

None.

## Non-PR commits (workflow-only)

State transitions and scaffolding that don't belong to a PR:

- `50a1055`, `8dcc7ac`, `2c46da3`, `9378f95` — `mlx-qwen3-asr-backend` validation cycle 6: zh 11.15% CER, en 13.89% WER, fr 14.39% WER, invariant derivation, chunk-1.0 s exploration kept out of the PR evidence.
- `00da66a`, `c2e1c37`, `0aa4816` — implementation cycle 6: the mlx-qwen3-asr 0.4.4 adaptation, the carve pointer, and the run repro.
- `8568e72` — validation cycle 5, deadline-partial: real-audio pause evidence with no FLEURS number.
- `0d84b9c`, `ed5df58`, `fa4bf78`, `23fd37a`, `4e7df1d`, `0ac0059`, `49e793b` — nemotron cycles 2 to 6, from the concurrent session.
- `a4dc434`, `546e655` — dropped a stale flat entity file and corrected the nemotron scope.

## Decisions

_(none recorded)_

## Issues — Workflow

- **Wrong base.** The implementation worktree was cut from `wlk/integration-2` instead of a branch based on the PR's target. Cost: a 148-file base, a carve branch, a rebase attempt that silently dropped three maintainer commits before I noticed, and three force-pushes to a co-maintainer's branch.
- **Disk.** Running the whole `pytest tests/` re-downloaded a 5.9 GB checkpoint twice and killed a benchmark run with ENOSPC, twice. Benchmarks need model-free test selection.
- **Verification blind spot.** A local green proved nothing: the shared venv's editable install resolved `whisperlivekit.caption_events` from the other checkout while the branch did not contain it. CI caught the import error. The method that works is a `sitecustomize` guard that raises when any module resolves outside the tree under test.
- **Unreproducible maintainer cases.** `audio_tests/` is not in the repository, so his 7-of-30 French duplication could not be reproduced locally. My first two duplication detectors were false positives on legitimate repeats such as "ce n'est pas vrai … ce n'est pas une carte".
- **Report overstatement.** The first cycle-6 report claimed three FLEURS languages at three passes while zh was one pass. The adversarial review caught it, not me.

## Issues — Spacedock

- **pi-subagents dropped the task body on five of six spawns**, retries included. Every dispatch began with a supervisor reply or a steer; one worker adopted another entity's dispatch file and had to be redirected before it wrote anything.
- **Working as intended:** `merge guard` refused to finalize on an open PR and named the sentinel to record (`pr=pr-merge:425`). That refusal was the most useful framework behaviour of the session.
- **Minor:** intercom cannot bind its socket in this sandbox (`EPERM`), so the FO's own model identity cannot be read from the host.

## Observations

_(none recorded)_

## Agent Testimonial

- Date: 2026-11-14
- Harness/runtime: pi
- Model: lunaroute/deepseek-4.1-flash
- Model version/build: unknown
- Session scale: 1 task touched; 6 workers dispatched plus 2 revivals; 2 PRs touched or merged

Spacedock gave the work a spine: an entity, a stage, a gate, and a refusal I could not argue past. The merge guard stopping on an open PR was the single most useful thing the framework did. The cost sat in the surrounding first-officer layer: five dropped spawn bodies meant every dispatch opened with a recovery conversation, and the contract made me ask permission to post a comment while I force-pushed a maintainer's branch three times. My own failures compounded it — starting on the integration branch, squashing the wrong thing, treating "verified" as a status instead of a claim with a blind spot — but the bookkeeping had no grip on any of those until the captain forced the issue.

## What's Next

- **p0 `mlx-qwen3-asr-backend`** — validated and approved, `approved-awaiting-merge`. When `gh` reports #425 merged: record `pr=pr-merge:425`, then re-run `merge guard --verdict passed`. The maintainer still owes one confirmation on his own recordings that segment-start revisions no longer duplicate.
- **Gates waiting on the captain:** `wlk-caption-display` (0.85), `mlx-sortformer-diarization` (0.8).
- **In implementation:** `qwen-asr-tf5-compat-fork`, `wlk-display-unification`, `canary-mlx-backend`, `apple-speech-backend`.
- **Ten entities at `needs-preparation`** in backlog; highest scores `qwen-asr-deep-tf5-port` (0.85) and `wlk-simul-time-frontier-pr` (0.85).
- **Deferred from this session:** the `--mlx-qwen3-asr-max-context-sec 4` confirmation of the decode-horizon hypothesis is measured (+3.0 pp WER for a 7.5x smaller window) but not posted to #425; a `--continuous` run for en and fr was not done.
