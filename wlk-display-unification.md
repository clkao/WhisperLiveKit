---
title: "A2: unify caption display semantics behind one model (overlay + TUI as views)"
status: backlog
score: 0.85
id: c9l3n4o5p6q7r8s9t0u1v2w3
worktree: .
---

# Task B (A2) — unify WLK display semantics behind one caption display model

## Context

The display work (sentence-partitioned captions, queue survival, in-place
promotion, dim/bright grammar, monotonic holds) landed on the integration
branch in `whisperlivekit/overlay_model.py` — but the terminal renderer
(`whisperlivekit/tui.py`, 395 lines, local-only) implements its OWN display
logic against the same renderer contract. Only the overlay got the
sentence-queue guarantees; the TUI almost certainly still exhibits the fixed
bug class (sentences lost at segment boundaries, queued finals superseded,
dim→bright identical-content retype). Two renderers, duplicated semantics,
one fixed.

Upstream main has NEITHER file (display surface is `web/live_transcription.js`
+ failure-reporting commits #440-445 that touch display concerns).

## Work

1. On a branch cut from origin/main, port the caption display model as THE
   display-semantics layer: event-stream consumer (the `caption_events`
   contract from the integration branch), sentence partitioning, hold queue,
   in-place promotion, monotonic display, dim/bright grammar.
2. Port the overlay and the TUI as thin views over that model (the TUI keeps
   its rich three-region layout, loses its independent display logic).
3. Port the regression suite: sentence partition, queue survival, no-retype,
   drained-replay test over a checked-in golden stream.
4. Reconcile with upstream #440-445 display-adjacent changes (failure
   reporting, final-snapshot drain).
5. Demonstrate with upstream's harness fields (first-visible-text pacing)
   where practical.

## Acceptance

- [ ] Overlay + TUI render identically (modulo styling) on the same event
      stream; the sentence guarantees hold for BOTH.
- [ ] Drained-replay regression test green on a checked-in golden stream;
      fails on the pre-port TUI logic (verify before deleting it).
- [ ] Suite counts vs upstream baseline: zero new failures.

## Notes

- Review sequence: B first, then D+G (D's PR description cites B's
  guarantees). Goldens (`zh_long_time_frontier.jsonl`, caption-event goldens)
  pin to this task.
- C (wlk-tui package) consumes this task's contract.
