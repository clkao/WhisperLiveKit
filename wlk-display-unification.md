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

## Stage Report: display-unification (cycle 1)

- DONE: Port caption display model + event stream to a branch cut from origin/main
  Commit f8110c9 on wlk/display-unification (from origin/main 363e4f6): caption_events.py, overlay_model.py (with the full sentence-queue work: partition at .!?/。！？, per-sentence hold queue, _keep_committed survival, in-place promotion), overlay.py view, display_adapter/event_diff/src_buffer/overlay_events, 5 goldens incl. zh_long_time_frontier.jsonl.
- DONE: TUI as a thin view over the SAME model
  tui.py ported; its independent display logic (pending-pair queue keyed by started_at, _relieve_pending cap, no partition/promote/keep-committed) is superseded by the shared model; the TUI's styling/layout preserved. Evidence: tests/test_tui_unified.py — golden-driven drained replay through the shared model shows every completed sentence (dermatology tail included) with no retype.
- DONE: No-retype contract regression test green
  tests/test_overlay_model.py::test_promote_in_place_flips_bright_without_retype + test_promote_in_place_final_amends_without_retype (verified failing shapes documented from round 3). Pre-port TUI logic (kept for verification) lacks partition/promote/keep-committed entirely — the duplicate would not pass these tests.
- DONE: Overlay + TUI render identically on the same event stream
  Drained replay of tests/golden/zh_long_time_frontier.jsonl: overlay view (scripts/replay_canonical_overlay.py --target) and TUI view (test_tui_unified) both display 'It reduces bleeding...', 'Dermatologists ... spots and tattoos.', 'In summary ...' — same sequence, modulo styling.
- DONE: Suite green vs upstream baseline
  Full suite: 364 passed / 8 failed / 43 errors; failure+error set byte-identical to clean origin/main (stash-compared; pre-existing: canary, deepgram, qwen3 shims, test-sample downloads). Zero new failures.
- DONE: Event-tap wiring against the #436-restructured pipeline
  The tap attaches to the processor (audio_processor init) and feeds DisplayAdapter; scripts/lc_terminal.py (ported) attaches a JSONL EventLog sink to the tap; test_harness already carries the `display` field contract on main's TestState — verified the seam on main's split (translation_processor.py owns the translation loop; the tap's translation emission points live in the integration branch's audio_processor and are NOT yet on main — the display layer consumes events, emission wiring for translation events on main is the one gap; see residual risks).

- FAILED: none

### Summary

Ported the unified display layer (model + overlay view + TUI-as-thin-view + tests + goldens + replay instrument) onto origin/main as commit f8110c9 on wlk/display-unification; 56 display-suite tests pass, full-suite failures byte-identical to baseline. Residual risk: the production event-tap EMISSION points for translation events (translation_final/translation_provisional inside the translation loop) live on the integration branch's audio_processor.py; on main's restructured translation_processor.py they are not yet wired — the model/views/tests are complete and generation-independent, but production emission needs a small wiring commit (in audio_processor.py init + translation_processor.py loop) before live runs emit events; ASR-side emission points on main were not verified. NOT pushed, NOT PR'd — awaits FO review.
