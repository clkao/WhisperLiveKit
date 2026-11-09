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

**AC-1 — The display model turns a recorded caption event stream into a
deterministic display state: the same stream produces the identical line
sequence on every replay.**
Verified by: replaying every checked-in golden (`tests/golden/*.jsonl`) through
`load_caption_events` into `CaptionDisplay` on a stepped fake clock twice and
comparing the full line sequences — identical for all five today
(`zh_long_canonical` 369 events/22 distinct lines, `zh_long_time_frontier`
352/14, `zh_long_ideal` 360/20, `zh_ja_fallback` 353/19,
`demo_en_30s_ideal` 360/16) — plus `python scripts/replay_canonical_overlay.py`
producing a byte-identical trace on two consecutive runs; both go red as soon as
a display decision reads the real clock (`CaptionDisplay` takes
`clock=time.monotonic` by default and tests inject a counter) or unordered state.

**AC-2 — The sentence rules hold in that state: captions partition into
sentences, a finished sentence is held and shown, a provisional promotes to
final in place, and final text never shrinks or rewords.**
Verified by: `test_multi_sentence_final_queues_each_sentence` and
`test_commit_crossing_terminator_freezes_completed_sentence` (partition — red if
the terminator split is dropped);
`test_final_single_sentence_shows_immediately`,
`test_dermatology_tail_displays_before_next_caption` and
`test_drained_replay_displays_every_completed_sentence` (held and shown — red if
a queued sentence is dropped or a draft wipes the backlog);
`test_promote_in_place_flips_bright_without_retype` and
`test_final_replaces_provisional_in_place` (promotion — red if the promote
re-types identical text or scrolls a draft into history);
`test_reworded_final_amends_only_current_sentence` and
`test_set_partial_holds_on_pure_shrink` (no shrink/reword — red if a revision
retracts text the reader has already seen).

**AC-3 — No display object is created when nothing consumes the stream.**
Verified by: `tests/test_caption_display.py::test_no_display_state_without_a_consumer`
asserts `AudioProcessor(...).caption_display is None` and
`processor.event_tap._sink is None` for a processor built with no consumer — red
if the processor constructs a display model or an event sink unasked.

**AC-4 — No new suite failures versus `origin/main` at the same commit.**
Verified by: exporting the base commit (`git archive origin/main | tar -x -C
<tmp>`) and running the documented suite command
(`uv run pytest -q tests/ --ignore=tests/test_pipeline.py
--ignore=tests/test_asr_coalescing_pipeline.py`) in both trees, then comparing the
failed-test ID sets — 8 failed/335 passed/13 skipped on `origin/main` (`ada82d4`)
versus 8 failed/395 passed/13 skipped on this branch (`c8dce70`), the same eight
IDs on both sides; red on any failing ID that appears only on the branch.

## Test plan

Unit tests for the model (sentence partition, hold, in-place promotion,
monotonicity), the replay instrument run over the checked-in goldens to prove
determinism, and suite parity against `origin/main` at the same commit. Goldens:
`zh_long_time_frontier.jsonl` plus the caption-event goldens, both parked on
`wlk/caption-display`.

## Out of scope

- The caption event stream itself (`--event-log`, the typed events, the backend
  `provides_drafts`/`progress()` contract): that is PR #449, entity
  `wlk-display-unification` (`6y`).
- The standalone terminal package: Task C, `wlk-tui-package` (`42`), which
  consumes this task's contract.
- The overlay and terminal views, and view-parity between them, belong to the
  consumer task that ships once the captain answers the consumer question —
  this task delivers the display model and its readable state only.

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

## Stage Report: implementation (authorize: AC rescope to delivered scope — dispatch wlk-caption-display-implementation)

- DONE: authorize: rescope acceptance criteria to the delivered scope. State-only body edit; no code.
  `## Acceptance` now carries exactly AC-1..AC-4 (criterion text verbatim + a `Verified by:` clause naming a reproducible check that can fail); `## Out of scope` gained the consumer-task line. `git diff` touches only those two spans (+47/-19): frontmatter, Work, Context, Test plan, Notes and the prior stage report are byte-identical.
- DONE: DO NOT PUSH CODE. Do not touch PR #449.
  No file under `.worktrees/wlk-caption-display` was modified (`git status --short` empty, HEAD still `c8dce70`); nothing pushed, no PR opened.

### The four AC lines now in the body

- AC-1 The display model turns a recorded caption event stream into a deterministic display state: the same stream produces the identical line sequence on every replay.
- AC-2 The sentence rules hold in that state: captions partition into sentences, a finished sentence is held and shown, a provisional promotes to final in place, and final text never shrinks or rewords.
- AC-3 No display object is created when nothing consumes the stream.
- AC-4 No new suite failures versus `origin/main` at the same commit.

### Proof re-run for each clause (not re-read)

- AC-1: all five `tests/golden/*.jsonl` replayed twice through `load_caption_events` + `CaptionDisplay(clock=<counter>)` → identical full line sequences (canonical 369 events/22 lines, time_frontier 352/14, ideal 360/20, zh_ja_fallback 353/19, demo_en_30s 360/16); `scripts/replay_canonical_overlay.py` run twice → `diff` clean. Reddens if a decision reads the real clock or unordered state.
- AC-2/AC-3: the ten cited tests in `tests/test_caption_display.py` exist and pass together (10 passed, 27 deselected); each clause names the change that reddens its group (dropped terminator split, dropped queue, re-typed promote, retracted text, unasked sink/model).
- AC-4: documented suite command run in three trees — `origin/main` `ada82d4` 8 failed/335 passed/13 skipped, branch base `db143d3` 8 failed/354 passed/13 skipped, branch `c8dce70` 8 failed/395 passed/13 skipped — the same eight failure IDs on all three (canary backend ×2, deepgram SDK ×1, qwen3 shims ×5; environment-dependent, present upstream). Reddens on any branch-only failure ID.

### Summary

The entity was filed while the overlay and TUI were still expected here; the captain stopped the derivation at the display model plus readable state, so AC-1/AC-2 named view adapters no validator could satisfy. The criteria now state the delivered scope, and every `Verified by:` clause was re-run instead of asserted (determinism replay, ten named model tests, three-tree failure-ID comparison). No code changed, no code pushed. Deliberately left untouched and flagged for an authorized follow-up: `## Test plan` still promises "adapter-level replay tests for both views over the checked-in goldens", which no longer exists.

## Stage Report: implementation (authorize: Test plan correction — dispatch wlk-caption-display-implementation)

- DONE: authorize: one-line correction in the entity's "## Test plan" section, which you flagged. State-only body edit; no code.
  `## Test plan` now reads: "Unit tests for the model (sentence partition, hold, in-place promotion, monotonicity), the replay instrument run over the checked-in goldens to prove determinism, and suite parity against `origin/main` at the same commit. Goldens: `zh_long_time_frontier.jsonl` plus the caption-event goldens, both parked on `wlk/caption-display`." `git diff` is a single hunk (+5/-4) inside that section; frontmatter, Context, Work, Acceptance, Out of scope, Notes and both prior stage reports are byte-identical (no trailer change on the last line).
- DONE: The Test plan still promises "adapter-level replay tests for both views over the checked-in goldens". Both views are out of scope now, so that sentence describes work this task does not do.
  The view-adapter clause and the separate "one drained-replay regression" clause are gone; the drained replay is now stated where it actually lives (the replay instrument over the goldens), and the model clause gained the two properties the earlier wording omitted — `hold` and in-place promotion, both carried by real tests (`test_golden_final_survives_its_hold`, `test_promote_in_place_flips_bright_without_retype`).
- DONE: DO NOT PUSH CODE.
  No file under `.worktrees/wlk-caption-display` modified (`git status --short` empty, HEAD still `c8dce70`, branch `wlk/caption-display-prb`); nothing pushed, PR #449 untouched.

### Each new clause checked against an artifact that exists

- Model unit tests: `tests/test_caption_display.py` exists with 36 `test_` functions; partition (`test_multi_sentence_final_queues_each_sentence`), hold (`test_golden_final_survives_its_hold`, `test_final_expires_after_hold`), in-place promotion (`test_promote_in_place_flips_bright_without_retype`), monotonicity (`test_set_partial_holds_on_pure_shrink`) are all present by name.
- Replay instrument over the goldens: `scripts/replay_canonical_overlay.py` + all five `tests/golden/*.jsonl` are checked in; determinism was re-run for AC-1 (two replays, identical traces).
- Suite parity: AC-4's `Verified by:` already records the three-tree run (`origin/main` `ada82d4`, branch base `db143d3`, branch `c8dce70`) with an identical eight-ID failure set — the parity claim names the same commit-scoped comparison, not a new one.

### Summary

The last stale promise in the body is corrected: the Test plan no longer describes view-adapter replay tests for overlay/TUI views this task deliberately does not ship, and instead names the three things it does prove — display-model unit tests (partition, hold, in-place promotion, monotonicity), the replay instrument over the checked-in goldens for determinism, and suite parity against `origin/main` at the same commit. One section, one hunk, no code changed, no code pushed.

## Stage Report: validation

Fresh validator. Reproduced every `Verified by:` clause from the branch
`wlk/caption-display-prb` @ `c8dce70` (parent `db143d3`, merge-base `ada82d4`),
using the shared interpreter `/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python`
with `PYTHONPATH=.` in the worktree (the worktree's own `.venv` is not needed).
No product code was edited outside one restored mutation; nothing pushed.

**Verdict: REJECTED (AC-2).** AC-1, AC-3, AC-4 pass with evidence. AC-2's four
rules reproduce and all ten named tests pass, but the rule it states — "a
finished sentence is held and shown" — does NOT hold at the shipped defaults:
committed `translation_final` sentences are silently dropped when they arrive
faster than the hold-drain releases them. Finding F-1 below is the blocker;
F-2/F-3 are recorded but not blocking on their own.

### AC-1 — PASS (deterministic replay), with a numbering nit (F-3)

- Replayed all five `tests/golden/*.jsonl` twice through
  `load_caption_events` → `CaptionDisplay(hold_sec=1.2, clock=<stepped counter>)`
  with a 30s drain (`/tmp/validate-5m/replay2.py`): `identical=True` for all
  five, both on the reader-visible line sequence and (second script,
  `fulltrace.py`) on the full per-tick `(spans, styles, prev, partial)` trace:
  `360 / 353 / 369 / 360 / 352` ticks, all `identical=True`.
- `PYTHONPATH=. python scripts/replay_canonical_overlay.py` run twice → both
  runs `rc=0`, `diff` clean, `md5 78b73062eace639801a54761b705f2dd` on both
  (43 trace lines).
- Falsifiability reproduced: making `tick()` read the real clock
  (`now = self._clock()` → `now = time.monotonic()`) reddens
  `tests/test_overlay_replay.py` 3 failed / 1 passed
  (`test_reword_retraction_held`, `test_canonical_stream_every_final_sentence_reaches_the_line`,
  `test_canonical_stream_never_scrolls_a_draft_into_history`). File restored
  (md5 back to `e0bfb210f0ca41d1f7c442f292f0d097`).
- F-3 (nit, non-blocking): the parenthetical figures in AC-1 are mislabeled. The
  `369 / 352 / 360 / 353 / 360` numbers are *tick* counts (events + 300 drain
  ticks), not event counts; the goldens hold `69 / 52 / 60 / 53 / 60` events.
  The "distinct lines" figures do not reproduce under any single counting rule I
  tried: distinct line *texts* are `15 / 13 / 18 / 17 / 13`
  (canonical / time_frontier / ideal / zh_ja / demo), distinct
  `(styles, text)` pairs `15 / 14 / 18 / 17 / 16`, and the test helper's own
  `_replay()` returns `shown 15/13/18/17/13` — so 14 and 16 reproduce, 22/20/19
  do not. Determinism, the property AC-1 states, is unaffected.
- Nit: the AC's command `python scripts/replay_canonical_overlay.py` fails from
  the repo root with `ModuleNotFoundError: No module named 'whisperlivekit'`
  (the package is not installed in the venv and `sys.path[0]` is `scripts/`).
  `PYTHONPATH=. python scripts/replay_canonical_overlay.py` works.

### AC-2 — FAIL (F-1): a committed sentence can be silently dropped

What passes (reproduced, not read):

- All ten named tests exist and pass together:
  `pytest -q tests/test_caption_display.py::test_multi_sentence_final_queues_each_sentence …::test_set_partial_holds_on_pure_shrink`
  → `10 passed in 4.00s`.
- Direct probes of the four rules (`/tmp/validate-5m/ac2.py`, `ac2b.py`,
  `ac2c.py`):
  partition — `translation("First sentence. Second sentence. Third sentence.")`
  drains as exactly those three lines; hold — shown at `t=0.05 / 1.05 / 2.05`
  with `hold=1.0`, i.e. one full hold each, FIFO; promotion in place — dim
  `'Hello there.'` → final `'Hello there.'` flips to `['same']` in one tick with
  no empty/retype frame; promotion at a terminator — `prev='Dentists also use
  laser technology for oral surgery.'`, `current='This reduces'`, sentence never
  enqueued, line never cleared; no shrink — a shorter ASR partial leaves
  `tick() -> None` and the long partial intact; reworded final — amends to
  `['same','add','same','add']` without blanking, `prev` untouched.
- Golden drained replay (`/tmp/validate-5m/ac2_golden.py`, hold=1.2): every
  complete sentence of every `translation_final` reaches the line for
  `zh_long_canonical` (12/12), `zh_long_ideal` (6/6), `zh_long_time_frontier`
  (8/8), `demo_en_30s_ideal` (6/6); `zh_ja_fallback` misses one
  (`出血や汗、痛みを減らす。`) — see F-2.

**F-1 (material, blocker) — committed captions are dropped at the shipped
hold.** `hold_sec=3.5` is the default of `scripts/replay_canonical_overlay.py`
and of its `--hold` flag, and `tick()` releases a queued item only every
`min(self._hold, max(1.0, self._hold / 2))` = 1.75s, while the queue is capped at
three items (`caption_display.py:452` `del self._queue[:-3]`,
`:606` `self._queue = (kept + new_items)[-3:]`, `:687` `del self._queue[:-3]`).
When committed sentences arrive faster than 1.75s the cap evicts the *oldest
committed, never-displayed* item:

```
# /tmp/validate-5m/dense_repro2.py — distinct single-sentence finals, 10fps view
hold=3.5 arrival=0.9s -> 3/12 committed sentences never displayed:
   ['Delta is here.', 'Foxtrot is here.', 'Hotel is here.']
hold=3.5 arrival=1.2s -> 1/12 committed sentences never displayed: ['Golf is here.']
hold=3.5 arrival=1.6s -> 0/12;  hold=2.0 arrival=0.9s -> 0/12;  hold=1.2 -> 0/12
```

Mechanism confirmed (`/tmp/validate-5m/capfix_dense.py`): with the three cap
sites raised in memory the same stream loses nothing —
`shipped cap=3 → ['Delta is here.', 'Foxtrot is here.', 'Hotel is here.']` vs
`cap=64 → []`. It also shows up in the shipped instrument at its own defaults
(`--hold 3.5 --pace 0.3`, `/tmp/validate-5m/dropcheck.py`): never-displayed
sentences `zh_long_canonical` 2, `zh_ja_fallback` 4, `zh_long_time_frontier` 1
(vs 0/0/0 for `zh_long_ideal` and `demo_en_30s_ideal`).

This contradicts AC-2's stated rule, and it contradicts the model's own
invariant in the same file ("FINALS ACCUMULATE — a queued final is committed
content and must display", `:682`). The AC-2 test that is supposed to be red
here, `test_drained_replay_displays_every_completed_sentence`, spot-checks only
three sentences of one golden at hold 1.2, so it stays green while committed
sentences are dropped.

Concrete fixes (either satisfies the AC; the first is smallest):
1. Stop evicting unshown committed items: bound the queue by *displayed/expired*
   entries (or drop only `provisional` drafts), so a backlog drains instead of
   being discarded — the three cap sites above are the whole change.
2. Or raise/removal of the cap together with a drain that keeps up
   (e.g. release immediately when the queue length exceeds N while pinning the
   newest), and document the resulting pacing.
   Either way add a regression that replays **all five goldens at the
   instrument's default hold** and asserts every complete sentence of every
   `translation_final` is displayed at least once (the current test's
   3-sentence spot-check is not enough).

**F-2 (polish/deferred) — the final is not authoritative for an
already-routed sentence.** With the recorded wall clock as the pacing clock and
a 30fps view (`/tmp/validate-5m/wall_t_replay.py`), `zh_long_time_frontier` at
hold ≤ 2.0 never displays the final's wording `'It reduces bleeding, sweating,
and pain.'` (the reader saw the draft wording `'This reduces …'` first), and
`zh_long_ideal` / `demo_en_30s_ideal` never display three / two final wordings
because the draft-routed text is displayed and the final's rewrite for an
already-routed sentence is not re-rendered. No content is lost in these cases —
this is the "authoritative final" rule bending, not retraction. Promote to
material only if a consumer needs the final's exact wording on screen.

**F-2b (deferred risk, not observed in the goldens)** — a `translation_final`
that arrives before any view tick has displayed the draft-routed sentences
discards them outright (`/tmp/validate-5m/minrepro.py`: `preview("Alpha one. Beta
two. Gamma thre")` then `translation(...)` with no tick in between → `'Alpha
one.'` and `'Beta two.'` never shown, at any hold; one `tick()` in between fixes
it). No adjacent provisional→final pair exists in any golden (measured: `n=0`
for all five), so this needs a producer that emits a draft and its final inside
one view frame. Promote to material if a consumer ticks slower than the
producer's draft→final gap.

### AC-3 — PASS

`test_no_display_state_without_a_consumer` passes, and I rebuilt the wiring
independently (`/tmp/validate-5m/ac3.py`, real `AudioProcessor` over a stub
`TranscriptionEngine`):

```
no-consumer:  caption_display is None | event_tap._sink = None | has _FanOutSink: False
no-consumer:  tap accepted events with no sink (no exception)
eventlog-only: caption_display is None | sink type = EventLog
consumer:     caption_display is the one I passed: True | sink is model: True
```

So neither a display model nor a fan-out exists when nothing consumes the
stream, and `--event-log` alone still holds a single `EventLog` sink.

### AC-4 — PASS (recorded comparison + independent targeted re-check)

The AC's own comparison is recorded in the two implementation reports
(`origin/main ada82d4` 8 failed/335 passed/13 skipped, branch `c8dce70` 8
failed/395 passed/13 skipped, same eight IDs). I did not re-run the whole suite
(disk-constrained, and instructed not to); instead I re-ran the only files where
failures occur, in both trees:

- Branch: `pytest -q tests/test_canary_backend.py tests/test_deepgram_compat.py
  tests/test_qwen3_backend_shims.py` → `8 failed, 95 passed` with exactly the
  eight recorded IDs (canary ×2, deepgram ×1, qwen3 shims ×5).
- `origin/main` export (`git archive origin/main whisperlivekit tests
  pyproject.toml | tar -x -C /tmp/validate-5m/origin-main`) → the **same eight
  IDs**, `8 failed, 95 passed`. Environment-dependent, pre-existing, not
  branch-only.
- Nine shared suites touched or adjacent (`test_backends`,
  `test_asr_coalescing_boundaries`, `test_pause_segmentation`,
  `test_translation_alignatt`, `test_translation_mlx`, `test_speaker_boundaries`,
  `test_session_context`, `test_retention`, `test_server`): branch
  `136 passed, 2 skipped`; `origin/main` `136 passed, 2 skipped`.
- The four suites this task adds
  (`tests/test_caption_display.py tests/test_overlay_replay.py
  tests/test_caption_events.py tests/test_translation_emission.py`):
  `59 passed in 3.82s`.

### Scope check — PASS

`git diff --name-only db143d3 HEAD` = `scripts/replay_canonical_overlay.py`, the
five `tests/golden/*.jsonl`, `tests/test_caption_display.py`,
`tests/test_overlay_replay.py`, `whisperlivekit/{caption_display.py,
audio_processor.py, test_harness.py}`. A grep of the whole diff for
`appkit|nsview|nswindow|urwid|textual|curses|tui|pywebview|tkinter` hits one
line — a test docstring saying "No view, AppKit, or real time is involved".
No view, overlay or TUI code, and no consumer-task file, is on this branch.

### Mutation (required check) — one test red, restored byte-for-byte

Mutated the placeholders rule of my own choosing: `_strip_hy_placeholder()` made
a no-op (`return text`), i.e. the model would let the Hunyuan
`<|…|>` template marker reach a view.

- Red, **exactly one** test:
  `pytest -q` over the four suites → `1 failed, 58 passed`,
  `FAILED tests/test_caption_display.py::test_placeholder_artifact_never_reaches_the_display`
  (`AssertionError: + <|im_start|>Hello there`).
- Restored with `git checkout -- whisperlivekit/caption_display.py`; md5
  `e0bfb210f0ca41d1f7c442f292f0d097` matches the pre-mutation value; the same
  selection went back to `59 passed in 2.94s`. `git status --short` empty,
  HEAD still `c8dce70`, nothing staged, no remote branch contains `c8dce70`.

### What must change before this gate can pass

1. F-1: keep committed, unshown sentences (or document the drop and let the
   captain rescope AC-2 — that is not my call), plus a golden-wide drained
   replay at the default hold as the regression.
2. F-3: correct AC-1's figures (tick counts, and distinct-line counts that
   reproduce) and the `python scripts/…` invocation (needs `PYTHONPATH=.`).
