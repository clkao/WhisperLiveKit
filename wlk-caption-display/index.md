---
title: "B: caption display model + overlay/TUI as thin views (PR-B for #449)"
status: implementation
score: 0.85
source: "split out of wlk-display-unification (A2) on 2026-11-08 when the entity was rescoped to PR #449 only. Material is parked on branch wlk/caption-display @ 513b6fa (the pre-trim state of the #449 branch)."
id: 5m8t81vcnbbvafnjz2mehdjc
worktree: .worktrees/wlk-caption-display
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

## Stage Report: implementation

- DONE: authorize: fix (derivation) — re-derive PR-B on top of PR #449's published head. Captain directed this.
  Re-derived from scratch: files restored from `513b6fa`, then adapted to the #449 API (commit `c8dce70`, parent `db143d3`).
- DONE: DO NOT PUSH. Commit only to the local branch wlk/caption-display-prb. Do not touch PR #449 and do not open a new PR.
  `c8dce70` on `wlk/caption-display-prb` only; nothing pushed, no PR opened, #449 untouched.
- DONE: This branch starts at PR #449's head (db143d3) ... Do not modify or rewrite that commit.
  `git log --oneline -2` = `c8dce70`, `db143d3`; `db143d3` unchanged (fast-forward parent).
- DONE: Restore from the parked pre-trim state at branch wlk/caption-display (commit 513b6fa), taking ONLY these files ...
  Restored: `whisperlivekit/caption_display.py`, `tests/test_caption_display.py`, `tests/test_overlay_replay.py`, `scripts/replay_canonical_overlay.py`, and all five `tests/golden/*.jsonl`. Nothing else taken from `513b6fa`.
- DONE: You must adapt them to PR #449's API ... Choose the simplest shape that keeps --event-log working, and state your choice in the report.
  Fan-out = one private 8-line `_FanOutSink` in `audio_processor.py` (the wiring site), used only when a display consumer AND `--event-log` both ask; one sink or none wraps nothing, and `caption_events.py` stays exactly as #449 shipped it. Rationale below.
- DONE: Re-add the display field the harness lost, so a consumer can read the display state again.
  `TestState.display` restored; set from `CaptionDisplay.state()` on every collected snapshot; `TestHarness(caption_display=...)` requests it (`tests/test_caption_display.py::test_harness_exposes_the_display_state_to_its_consumer`).
- DONE: Adapt the display code to the current CaptionEvent payload and emission points. Do not reintroduce the unconditional accumulator ...
  `emit()` is the EventSink mapping (4 kinds); `CaptionLineAccumulator` stays deleted; the model exists only when `AudioProcessor(caption_display=...)` is given one (`test_no_display_state_without_a_consumer` asserts `caption_display is None` and `event_tap._sink is None`).
- DONE: Do NOT write any view, overlay, or terminal client ...
  No view/overlay/TUI code in the diff; the model publishes readable `DisplayState` (+ `load_caption_events` for replay) as the contract Task C consumes.
- DONE: Proof: both display suites green, replay instrument on a checked-in golden, event/emission suites green, ruff clean, suite parity, one-rule mutation.
  59 passed across the four named suites; instrument runs on `tests/golden/zh_long_canonical.jsonl`; ruff `All checks passed`; full suite 3 failed/401 passed/12 skipped vs the same base commit `db143d3` 3 failed/360 passed/12 skipped — IDENTICAL failure set (the 3 are pre-existing on `origin/main` too); mutation below.
- DONE: Report: which files came back, the fan-out shape you chose and why, every adaptation the new API forced, and the mutation result.
  All four below.

### Files that came back (from 513b6fa)

`whisperlivekit/caption_display.py`, `tests/test_caption_display.py`, `tests/test_overlay_replay.py`, `scripts/replay_canonical_overlay.py`, `tests/golden/{zh_long_canonical,zh_long_ideal,zh_long_time_frontier,zh_ja_fallback,demo_en_30s_ideal}.jsonl`. Wiring touched `whisperlivekit/audio_processor.py` and `whisperlivekit/test_harness.py`; `caption_events.py` (PR #449's file) is untouched.

### Fan-out shape and why

`EventTap` keeps exactly one sink. `AudioProcessor` builds the sink list from the two independent consumers that can want the stream — the caller's display model and the optional `--event-log` JSONL recording — and wraps them in a private `_FanOutSink` only when both are present (1 sink → the sink itself, 0 → `None`). Placed in `audio_processor.py` because that is where the wiring decision lives, and because re-adding a public `FanOutSink` to `caption_events.py` would reopen PR #449's file for a 8-line dispatcher. It now exists for a real pairing (render + record), not the pre-trim shape where one of its two sinks was a consumer nobody read.

### Adaptations the new API forced

1. **Payload is plain text.** `CaptionEvent` carries `text` only — no segments, speaker markers or caller diff spans — so `_segments_plain`/`_segments_to_spans`/`_spans_after` are gone; `preview(text)`/`translation(text)` build spans from the text and the model keeps its own `_diff_spans` for reworded sentences (green `add`, bright `same`, `del` omitted).
2. **The commit is an event, not a length.** There is no stable/tail split in the payload, so `set_partial(text, committed_len)` → `set_partial(text)` and `DisplayState.partial_committed_len` is dropped; the monotonic hold is released by `transcription_final` (→ `clear_partial`) instead of a changed committed-length. This is the only state field removed.
3. **Utterance identity is gone.** `started_at`/`_utt`/`utt_t` had no equivalent in the stream; the rule they enforced is kept as "a final supersedes any shown provisional; drafts never scroll into history".
4. **No read side on `EventLog`.** The sink is write-only now, so `load_caption_events(path)` (in `caption_display.py`) parses a recording back for the instrument and the golden tests.
5. **Accumulator removed.** `CaptionLineState`/`CaptionLineAccumulator` (and their unbounded `final_lines` growth) are not restored — the display model's `DisplayState` is the readable state.
6. **Instrument made deterministic.** `replay_canonical_overlay.py` now drives `emit` on an injected clock, no `time.sleep`, no private `_en_*` reads, defaults to a checked-in golden, and prints only lines the reader would see change.
7. **`_update_fragment` delta fixed.** The parked call passed the *new* full draft as `prev_draft`, making the append delta always empty (line text and spans could disagree); it now gets the previous draft, and the growth tests cover it.

### Falsifiability (one line per claim group)

- Provisional dims/never expires/no churn: `test_preview_is_dimmed_*`, `test_preview_persists_after_hold_no_final`, `test_preview_unchanged_skips` — red if `preview` brightens a draft, if provisional expiry is added, or if identical drafts re-render.
- Final shows, holds, scrolls, expires: `test_final_single_sentence_shows_immediately`, `test_two_consecutive_finals_scroll_up`, `test_final_expires_after_hold`, `test_prev_expires_on_own_timer` — red on a missing MIN_SHOW wait, a missing final/prev expiry, or scrolling a draft up.
- Sentence partition + queue: `test_multi_sentence_final_queues_each_sentence`, `test_commit_crossing_terminator_*`, `test_new_final_enqueues_behind_pending_sentences_fifo`, `test_pending_sentences_survive_next_utterance_draft`, `test_dermatology_tail_*`, `test_promote_in_place_*` — red if the terminator split is dropped, a draft wipes queued committed sentences, a final jumps the queue, or a promote re-types identical text.
- Monotonic source: `test_set_partial_holds_on_pure_shrink` (red if the shrink hold is removed), `test_transcription_final_releases_the_held_tail`, `test_partial_expires_after_hold_with_no_activity`.
- Stream contract: `test_emit_drives_one_utterance_through_the_display` (red if any event kind stops mapping), `test_emit_ignores_an_unknown_event_kind`, `test_placeholder_artifact_never_reaches_the_display`.
- Golden drained replay: `test_drained_replay_displays_every_completed_sentence` (time_frontier) and `test_canonical_stream_every_final_sentence_reaches_the_line` (zh_long_canonical) — red if any queued sentence is dropped or a final is swallowed; `test_canonical_stream_never_scrolls_a_draft_into_history` — red if history ever carries a dim span.
- Wiring: `test_no_display_state_without_a_consumer`, `test_display_consumer_receives_the_stream`, `test_event_log_and_display_both_receive_the_stream`, `test_harness_exposes_the_display_state_to_its_consumer` — red if the processor builds display state unasked, if `caption_display=` is not fed, if the fan-out drops one sink, or if the harness forgets `.display`.

### Mutation result

Mutated the prev-line expiry rule (`now - self._en_prev_at >= self._hold` → `and False and`): **exactly one** test went red — `test_caption_display.py::test_prev_expires_on_own_timer` (1 failed, 39 passed). Restored; md5 matched the pre-mutation file and the same selection returned 40 passed.

### Summary

PR-B is re-derived on #449's head as a model-only consumer of the caption event stream: `CaptionDisplay.emit()` is the EventSink, fan-out to `--event-log` is deliberate and minimal, the harness exposes `TestState.display`, and nothing view-shaped landed. Ruff clean, four named suites 59 passed, full-suite parity with `origin/main`/`db143d3` failure-for-failure. Open: the consumer choice (our terminal client vs the maintainer's Swift consumer) is untouched, so no view was written and AC-1's "both view adapters" half belongs to Task C.
