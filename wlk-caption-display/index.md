---
title: "B: caption display model + overlay/TUI as thin views (PR-B for #449)"
status: backlog
score: 0.85
source: "split out of wlk-display-unification (A2) on 2026-11-08 when the entity was rescoped to PR #449 only. Material is parked on branch wlk/caption-display @ 513b6fa (the pre-trim state of the #449 branch)."
id: 5m8t81vcnbbvafnjz2mehdjc
---

# Task B — caption display model, with the overlay and TUI as thin views

## Context

`6y wlk-display-unification` carried both halves of the display work: the caption
event stream that goes upstream as PR #449, and the display model that consumes
it. The maintainer's review of #449 found the model half had no consumer yet and
asked for a split, so #449 now ships the event stream alone and this task owns
the consumer half. It is the "task B" that `wlk-tui-package` (Task C) names as
its prerequisite contract.

## Work

1. Port the caption display model as THE display-semantics layer: event-stream
   consumer (the `caption_events` contract from PR #449), sentence partitioning,
   hold queue, in-place promotion, monotonic display, dim/bright provisional
   grammar.
2. Port the overlay and the TUI as thin views over that model (the TUI keeps its
   rich three-region layout, loses its independent display logic).
3. Port the regression suite: sentence partition, queue survival, no-retype,
   drained-replay test over a checked-in golden stream.
4. Reconcile with upstream #440-445 display-adjacent changes (failure reporting,
   final-snapshot drain).
5. Demonstrate with upstream's harness fields (first-visible-text pacing) where
   practical.
6. Ship it only with the consumer the maintainer asked for. Captain asked
   Quentin (2026-11-08) whether an in-repo TUI reference consumer is wanted; the
   answer decides whether the consumer ships here (wired to Task C's client) or
   this lands model-only.

## Acceptance

**AC-1 — Overlay and TUI render identically (modulo styling) from the same event
stream.**
Verified by: a test that replays one checked-in golden event stream through both
view adapters and compares the rendered line sequences; it fails on the pre-port
TUI logic.

**AC-2 — The sentence guarantees hold for both views.**
Verified by: the sentence-partition, no-retype, and queue-survival tests run
against each view adapter, plus one drained-replay test over a checked-in golden
stream.

**AC-3 — No per-session display state is allocated when nothing consumes the
stream.**
Verified by: constructing the processor without a display consumer and asserting
no accumulator object exists.

**AC-4 — Suite parity with upstream.**
Verified by: suite counts against `origin/main` at the same commit, with zero new
failures.

## Test plan

Unit tests for the model (sentence partition, queue, promotion, monotonicity),
adapter-level replay tests for both views over the checked-in goldens, and one
drained-replay regression. Goldens: `zh_long_time_frontier.jsonl` plus the
caption-event goldens, both parked on `wlk/caption-display`.

## Out of scope

- The caption event stream itself (`--event-log`, the typed events, the backend
  `provides_drafts`/`progress()` contract): that is PR #449, entity
  `wlk-display-unification` (`6y`).
- The standalone terminal package: Task C, `wlk-tui-package` (`42`), which
  consumes this task's contract.

## Notes

- Parked material: branch `wlk/caption-display` @ `513b6fa`. Everything this task
  needs was cut from #449 during the PR-A trim (commit `7394a9b` deleted
  `caption_display.py`, `test_caption_display.py`, the goldens,
  `scripts/replay_canonical_overlay.py`, `test_overlay_replay.py`).
- Review sequence: this task first, then D+G. D's PR description cites this
  task's guarantees.
- `wlk-tui-package` (C) consumes this task's contract and targets the
  integration branch until this clears upstream.
