---
title: "B: caption display model + overlay/TUI as thin views (PR-B for #449)"
status: validation
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
(`zh_long_canonical` 69 events/15 distinct caption lines, `zh_long_time_frontier`
52/13, `zh_long_ideal` 60/18, `zh_ja_fallback` 53/17, `demo_en_30s_ideal`
60/13, where a golden's event count is its JSONL line count and the line count
is what the checked-in `_replay()` helper in `tests/test_overlay_replay.py`
returns at hold 1.2, pace 0.3s/event, 30s drain) — plus `PYTHONPATH=. python
scripts/replay_canonical_overlay.py` producing a byte-identical trace on two
consecutive runs; both go red as soon as
a display decision reads the real clock (`CaptionDisplay` takes
`clock=time.monotonic` by default and tests inject a counter) or unordered state.

**AC-2 — The sentence rules hold in that state: captions partition into
sentences, a finished sentence is held and shown, a provisional promotes to
final in place, and final text never shrinks or rewords.**
Verified by: `test_multi_sentence_final_queues_each_sentence` and
`test_commit_crossing_terminator_freezes_completed_sentence` (partition — red if
the terminator split is dropped);
`test_final_single_sentence_shows_immediately`,
`test_dermatology_tail_displays_before_next_caption`,
`test_drained_replay_displays_every_completed_sentence`,
`test_committed_sentences_faster_than_the_release_interval_all_display` and
`test_no_committed_caption_leaves_the_queue_unshown` (held and shown — red if
a queued sentence is dropped or a draft wipes the backlog; the last two are red
on any queue bound that evicts an unshown committed caption, including the
shipped three-item cap, at the shipped hold);
`test_final_after_a_held_caption_displays_every_sentence` and
`test_golden_every_final_sentence_displays_verbatim` (held and shown — red if a
sentence is skipped before it is ever enqueued, which the queue tests cannot
see: the two-utterance case loses `'Beta one.'` at holds 3.5/5.0 if the previous
utterance's line index survives into the next final, and
`zh_long_time_frontier` at the shipped hold loses `'In ophthalmic surgery, lasers
are used to correct vision.'` in both the final and the draft wording);
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
versus 8 failed/420 passed/13 skipped on this branch (`d6def32`), the same eight
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

## Stage Report: implementation (authorize: fix — F-1 queue bound, dispatch wlk-caption-display-implementation)

- DONE: authorize: fix — validation rejected this entity on AC-2. The finding is material: committed captions can be dropped. Fix it; do not weaken the criterion.
  Code commit `5f3ebb7` on `wlk/caption-display-prb` (parent `c8dce70`). AC-2's four rules are unchanged; its Verified-by clause now names the two new regressions instead of relying on the three-sentence spot-check.
- DONE: F-1 (blocker) — committed captions must never be dropped by the queue bound.
  Invariant chosen: the hold queue is the reader's backlog; a completed caption in it is never evicted, and the only content a newer item supersedes is a DRAFT. All three cap sites removed (`_enqueue_sentence`, `translation`'s queue rebuild, `_enqueue_item`), with the invariant stated at the queue's declaration and at each enqueue site. No completed-item bound remains, so there is no eviction rule left to qualify; drafts stay bounded by `_keep_committed` (the newest in-progress fragment wins, which loses no content).
- DONE: F-1's own reproducers, re-run against the fixed model.
  `dense_repro2.py` at hold 3.5 / 0.9s arrival: 3/12 committed sentences dropped → 0/12 (0/12 for every hold/arrival pair it tries). `dropcheck.py` at the instrument's default hold: never-shown `zh_long_canonical` 2, `zh_ja_fallback` 4, `zh_long_time_frontier` 1 → 0 / 0 / 1, the remaining one being a different cause (F-2 below).
- DONE: red-before/green-after proof — a stream of committed sentences faster than the release interval all display, in order.
  `test_committed_sentences_faster_than_the_release_interval_all_display` (hold 3.5 → 1.75s release, finals every 0.9s, 10fps view): red before the fix (`['Echo is here.', 'Golf is here.', 'India is here.']` never displayed), green after; it fails if any bound discards an unshown committed item or reorders them.
- DONE: golden-wide regression at the shipped hold, covering both enqueue shapes.
  `test_no_committed_caption_leaves_the_queue_unshown[5 goldens × hold 3.5/1.2]` (10 cases) — red before the fix for `zh_long_canonical` (2) and `zh_ja_fallback` (4), including the sentence AC-2's spot-check missed; it fails if a committed item leaves the queue without being released. `test_new_multi_sentence_final_never_evicts_the_pending_backlog` — red if the final's queue rebuild keeps only the newest items.
- DONE: mutation results — each cap restored on its own.
  Cap back at `_enqueue_item` → 4 red (dense + `zh_ja_fallback` hold 3.5 + hold 1.2 + `zh_long_canonical` hold 3.5). Cap back at `translation()` → 1 red (the backlog test; this is why it was added). Restored each time; `caption_display.py` md5 `b0bf44013bd34eb697fc492ccd4e1301` before and after, `git status` clean.
- DONE: F-2 — does the fix cover `zh_ja_fallback`'s `出血や汗、痛みを減らす。`?
  Yes — it was a cap eviction at `_enqueue_item` (it displays under the fix, and mutation M1 above reddens exactly that golden/hold). Not covered: `zh_long_time_frontier`'s `In ophthalmic surgery, lasers are used to correct vision.` at hold 3.5 — different root cause: the draft-routed wording (`In eye surgery, …`) is displayed and `_amend_routed_sentence` leaves history alone, i.e. the validator's deferred "final is not authoritative for an already-routed sentence". No content is lost there.
- DONE: F-3 (nit) — AC-1's figures corrected in the body.
  Now `69 / 52 / 60 / 53 / 60` events and `15 / 13 / 18 / 17 / 13` distinct caption lines, with the counting rule named (`_replay()` in `tests/test_overlay_replay.py`, hold 1.2, 0.3s/event, 30s drain); the AC's command now reads `PYTHONPATH=. python scripts/replay_canonical_overlay.py`.
- DONE: proof run — the four named suites, ruff, the replay instrument.
  `tests/test_caption_display.py tests/test_overlay_replay.py tests/test_caption_events.py tests/test_translation_emission.py` → 71 passed (59 before + 12 new cases); `ruff check whisperlivekit/ tests/ scripts/` clean; `scripts/replay_canonical_overlay.py` twice → byte-identical (md5 `a7ed5390c6a2c27a03c8331926f823ce`, 44 trace lines vs 43 before: the caption that used to be dropped now shows).
- SKIPPED: push the state branch.
  The dispatch that launched this cycle says "Do not push"; the code branch `wlk/caption-display-prb` @ `5f3ebb7` stays local and unpushed.
- SKIPPED: AC-4's full-suite re-run.
  This cycle is restricted to the caption display and replay suites; AC-4's recorded branch figure (395 passed) predates these 12 cases.

### Notes for the gate

- Decided by the entity's authorizer, not by me: keeping committed captions means the backlog can grow deeper than the drainer during a fast stretch. Pacing degrades (the reader falls behind) instead of content being lost. A backlog-aware pacing change would be a design decision outside this cycle's authorized scope.
- `F-2b` (a final arriving before any view tick discards draft-routed sentences) still reproduces unchanged (`minrepro.py`, both holds); untouched, still deferred.
- The two draft fragments `牙医也使用` / `皮肤科用镭` no longer reach the line in `zh_ja_fallback` — they are the untranslated-source drafts the emission gate exists to remove, and they now lose to committed sentences instead of displacing them. No committed (bright) line is lost anywhere: comparing the pre/post distinct-line sets over all five goldens at hold 3.5 and 1.2, the only lines that disappear are those two dim drafts, and every difference on a committed line is an addition.

### Summary

Removed the three-item cap on the caption hold queue at all three enqueue sites so a committed sentence is never evicted in favour of a newer one; the queue is now the reader's backlog with drafts the only superseded content, documented where the queue is declared. Added twelve regression cases: the dense committed-stream test (red on three dropped sentences before the fix) and golden-wide "no committed item leaves the queue unreleased" cases over all five goldens at two holds, plus a backlog-preserving test for the final's queue rebuild. Both of the validator's reproducers re-run against the fixed model (dense arrivals and all five goldens) with zero committed captions lost, and AC-1's figures corrected to re-derivable numbers.

## Stage Report: validation (rerun after the F-1 fix)

Fresh validator: reproduced every criterion from the code and from my own
scripts, not from the implementation report or the previous validator's
conclusion (I read that conclusion only at the end, to say whether I agree).

Environment: branch `wlk/caption-display-prb` @ `5f3ebb7` (parent `c8dce70`,
merge-base / `origin/main` `ada82d4`), interpreter
`/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python` with `PYTHONPATH=.` in the
worktree. Every mutation/red run happened in throwaway copies under
`/tmp/valrecheck/` (`scratch`, `fixcheck`, `prefix` = `c8dce70`, `at5f3pre`,
`originmain`). The worktree was never mutated: `git status --short` empty, HEAD
`5f3ebb7`, nothing staged, nothing pushed.

**Verdict: FAILED (AC-2) — but F-1 is FIXED and independently verified.**
The gate's question — can an unshown committed caption still be evicted by the
hold queue's bound — answers **no**: no completed-item bound remains at any
enqueue site, and the invariant is proven behaviourally and by mutation (below).
A *different, pre-existing* path still drops a committed final sentence:
`translation()`'s in-place-amend bookkeeping starts its enqueue at a sentence
index whose predecessors were never displayed. It reproduces on a checked-in
golden at the shipped hold under the repo's own replay convention (finding R-1).
So AC-2's stated rule is still not true in general, while the specific rule F-1
broke now holds everywhere I could reach.

### F-1 — FIXED, verified (the finding under re-validation)

1. **No completed-item bound remains.** Every mutation site of `_queue` in
   `whisperlivekit/caption_display.py`: `:218` declaration, `:393-394`
   `_keep_committed` (keeps finals, drops drafts only), `:456-459` insert,
   `:480` lookup, `:557`/`:615` rebuild `kept + new_items`, `:695`/`:702`
   append, `:721` `pop(0)`. There is no slice and no length test that trims the
   queue: `grep -n "_queue\[-\|_queue\[:\|len(self._queue)"` returns only the
   finals-only filter (`:394`), the insert point (`:456`) and the rebuild
   (`:615`, no trim). The invariant is stated where the queue is declared
   (`:211-217`: "NOT capped — every completed caption in it must display … a
   producer that outruns the drainer deepens the backlog instead of losing
   captions. The only superseded content is a DRAFT") and at each enqueue site:
   `_enqueue_sentence` (`:447-449` "The insert is uncapped … no enqueue may
   evict an older unshown caption"), `translation()` rebuild (`:613-615`), and
   `_enqueue_item` (`:695` "uncapped — see __init__: never evicted").
2. **Behavioural proof at the shipped hold** (`hold=3.5`, release interval
   `min(3.5, max(1.0, 1.75)) = 1.75s`), my own script driving only the public
   API and reading the rendered `DisplayState` — 10 scenarios, every committed
   sentence must reach the line in order:
   `dense single-sentence finals` at 0.3 / 0.6 / 0.9 / 1.2 / 1.6s arrival →
   14/14 shown, order kept; `dense multi-sentence finals` (the `translation()`
   rebuild path) at 0.3 / 0.9 → 12/12; `draft+final pairs` (the
   `_enqueue_sentence` path) at 0.3 / 0.9 → 8/8; 30 sentences in one final →
   30/30. **OVERALL PASS.**
3. **Red before / green after, each site separately** (scratch copy, cap
   restored by exact-string mutation, then restored byte-for-byte):
   - cap at `_enqueue_sentence` alone → my 10 scenarios stay **green**; the
     repo's new tests stay green (16 passed). Not independently falsifiable:
     an item evicted there is a draft-routed provisional sentence that the same
     utterance's final re-supplies through the rebuild, so nothing is lost.
   - cap at the `translation()` rebuild → **red**: multi-sentence 4/12 and
     5/12, 30-sentence final 3/30; repo test
     `test_new_multi_sentence_final_never_evicts_the_pending_backlog` red.
   - cap at `_enqueue_item` → **red**: 5 of 10 scenarios; repo tests red:
     `test_committed_sentences_faster_than_the_release_interval_all_display`,
     `…leaves_the_queue_unshown[zh_ja_fallback-hold3.5]`, `[…-hold1.2]`,
     `[…zh_long_canonical-hold3.5]` (4 failed, 12 passed).
   - all three caps (the pre-fix `c8dce70` state) → **red**: 7 of 10 scenarios,
     5 repo tests (5 failed, 11 passed).
   - restore → md5 back to `b0bf44013bd34eb697fc492ccd4e1301`, all green.
   Cross-check in a real pre-fix tree (`c8dce70` package + `HEAD` tests):
   `5 failed, 11 passed` — the new regressions do pin the F-1 mechanism.
4. **Can a completed caption be superseded by a newer one?** No. Dense FIFO
   streams deliver in order with none lost, and the two cases where an item is
   replaced are (a) a draft (`_keep_committed`) and (b) a draft-routed
   provisional sentence replaced by its own final's wording — not by an older
   or newer caption.

### AC-1 — PASS (deterministic replay), figures now re-derive

- All five goldens replayed **twice** each through `load_caption_events` →
  `CaptionDisplay(hold=1.2, clock=stepped counter)`, 0.3s/event + 30s drain:
  identical reader-visible line sequence **and** identical full per-tick
  `(current spans+styles, prev spans+styles)` trace for every golden
  (ticks 360 / 353 / 369 / 360 / 352).
- Corrected figures reproduce exactly: events `69 / 52 / 60 / 53 / 60`
  (canonical / time_frontier / ideal / zh_ja / demo) and distinct caption lines
  `15 / 13 / 18 / 17 / 13`.
- `PYTHONPATH=. python scripts/replay_canonical_overlay.py` twice → both
  `rc=0`, `diff` clean, md5 `a7ed5390c6a2c27a03c8331926f823ce`, 44 trace lines.
- Falsifiability: `now = self._clock()` → `time.monotonic()` in `tick()`
  reddens 3 replay tests (`test_reword_retraction_held`,
  `test_canonical_stream_every_final_sentence_reaches_the_line`,
  `test_canonical_stream_never_scrolls_a_draft_into_history`).

### AC-2 — FAIL (queue-bound half now passes; a pre-existing drop path remains)

What passes (reproduced, not read): the ten named tests exist and pass together
(20 cases incl. the 10 parametrised, `20 passed`); direct probes give
partition `['First sentence.', 'Second sentence.', 'Third sentence.']`; hold
gaps exactly `1.0s` at `hold=1.0` (`0.05 / 1.05 / 2.05`); promote in place
`('Hello there.', ['provisional']) → ('Hello there.', ['same'])` in one tick
with no blank frame; a shorter partial does not retract the long one
(`tick() → None`, text intact); a reworded final amends the promoted sentence
in place (no blank line, reworded wording visible, nothing retracted);
golden-wide "no committed item leaves the queue unreleased" is green for all
5 goldens × holds 3.5/1.2 and red pre-fix for `zh_long_canonical` (hold 3.5)
and `zh_ja_fallback` (both holds).

**R-1 (material) — a committed final sentence can still be dropped, by a
different mechanism, at the shipped hold.** `translation()` chooses its enqueue
start index from `line_j` / `cur_i`; both are *utterance-local* sentence
indices, and `cur_i` is read from `self._en_current_sent` + `self._en_line_prov`
which are **not** invalidated when the utterance they describe ends. If the
line holds the previous utterance's draft-routed sentence *k*, a new final with
more than *k* sentences puts `sents[k]` on the line and enqueues only
`i > k`: sentences `0..k-1` of the new final are never enqueued and never
displayed. Minimal model-level reproducer (hold 3.5):

```python
m = CaptionDisplay(hold_sec=3.5, clock=clock)
m.preview("Alpha one. Alpha two."); pump(4.0)   # line ends on 'Alpha two.' (idx 1)
m.translation("Alpha one. Alpha two."); pump(1.0)
m.translation("Beta one. Beta two. Beta three."); pump(30.0)
# shown: ['Beta two.', 'Beta three.']  ->  'Beta one.' NEVER displayed
```

Measured on the checked-in stream: `tests/golden/zh_long_time_frontier.jsonl`
replayed with the repo's own convention (`_replay()` / the instrument:
advance-then-emit, 0.3s/event, one tick per event) at the shipped `hold=3.5`
never displays `'In ophthalmic surgery, lasers are used to correct vision.'` —
and **neither does its draft wording** `'In eye surgery, …'`: zero occurrences
in `state().current` or `state().prev` across the whole replay plus a 40s drain.
Hold sensitivity (same reproducer): `1.2` and `2.0` → nothing lost; `3.5` and
`5.0` → sentence dropped. Cadence sensitivity (golden): lost at 0.3s/event
advance-then-emit (1 or 4 ticks/event), shown at 0.1s and 0.6s/event and when
the clock advance follows the emit. It is **pre-existing**: the identical drop
occurs with the `c8dce70` package (`zh_long_time_frontier`, hold 3.5, and the
same minimal reproducer), so the F-1 fix neither caused nor fixed it.

Answering the gate's question 4 directly: the remaining `zh_long_time_frontier`
difference the implementation report attributes to `_amend_routed_sentence`
("the draft-routed wording is displayed … no content is lost") is **not wording
only** — in the cadence where it appears, neither wording ever reaches the line,
so the sentence's content is lost, and the actual mechanism is the stale
`_en_current_sent` index, not the history amend in `_amend_routed_sentence`.
AC-2's "final text never shrinks or rewords" is therefore **not satisfied** in
that cell: the line shows a strict *suffix* of the final
(`'They treat myopia and hyperopia.'`) after `5.40`'s sibling sentence, and the
final's first sentence is never shown. The *no-retraction* half of that clause
(a revision must not retract text the reader already saw) does hold — that is
what the two named tests check. F-2b (a final arriving before any view tick
discards the leading draft-routed sentences) also still reproduces unchanged
(`preview("Alpha one. Beta two. Gamma thre")` then `translation(...)` with no
tick → only `'Gamma three.'` ever displays); same bug class, same `line_j`
branch, not reachable from the shipped instrument because it ticks per event.

Concrete fix (one change covers R-1 and F-2b): in `translation()`, before
taking the `line_j` / `cur_i` in-place branch, account for the sentences
strictly before that index — enqueue any of `sents[0:min(line_j, cur_i)]` that
this utterance has not displayed yet (or, minimally, start the enqueue at the
first undisplayed index instead of `line_j + 1` / `cur_i + 1`), and invalidate
`_en_current_sent` / `_en_line_prov` when the utterance they describe ends
(the same place `_en_sent_texts`, `_en_prev_sent_idx` and `_en_line_sent` are
already reset). Regression to add: (a) the minimal two-utterance reproducer
above at holds 1.2 / 3.5 / 5.0 asserting every sentence of the second final
displays, and (b) a golden-wide "every sentence of every `translation_final`
displays verbatim" replay over all five goldens at hold 3.5 under the
instrument's own cadence — the current golden test only checks that queued
items are *released*, so it cannot see a sentence that is never enqueued.

### AC-3 — PASS

`test_no_display_state_without_a_consumer` passes, and my own wiring probe over
a real `AudioProcessor` (bare `TranscriptionEngine`) gives:
`no consumer → caption_display is None, event_tap._sink None, tap accepts an
event with no exception`; `--event-log only → caption_display None, sink
EventLog`; `caption_display=model → sink is the model`; both →
`_FanOutSink`. No display object, and no sink, exists unasked.

### AC-4 — PASS (criterion), one stale figure in the AC text

The documented command
(`pytest -q tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_asr_coalescing_pipeline.py`)
run in three trees:

- `origin/main` `ada82d4` → `8 failed, 335 passed, 13 skipped`
- branch head `5f3ebb7` → `8 failed, 407 passed, 13 skipped`
- branch `c8dce70` → `8 failed, 395 passed, 13 skipped`

The eight failing IDs are identical on all three (canary backend ×2, deepgram
SDK ×1, qwen3 shims ×5 — environment-dependent, present upstream). No
branch-only failure. Note: AC-4 quotes `395 passed` for "this branch
(`c8dce70`)"; at the gate's head the count is `407` (the F-1 commit added 12
cases). The number is decoration around the criterion (failure-ID parity), so
this is a documentation nit, not an AC failure — but the AC text should name
`5f3ebb7`/`407`.

### F-2 (`zh_ja_fallback`) — RESOLVED

Pre-fix `zh_ja_fallback` displayed 8/12 final sentences at hold 3.5 and 11/12 at
hold 1.2; post-fix 12/12 at both, including the cited
`出血や汗、痛みを減らす。`. It was a cap eviction at `_enqueue_item` and the cap
removal fixed it, as the implementation report says.

### Scope / hygiene

`git diff --name-only db143d3 HEAD` = `scripts/replay_canonical_overlay.py`, the
five `tests/golden/*.jsonl`, `tests/test_caption_display.py`,
`tests/test_overlay_replay.py`, `whisperlivekit/{caption_display.py,
audio_processor.py, test_harness.py}` — no view/overlay/TUI code. `ruff check
whisperlivekit/ tests/ scripts/` → `All checks passed!`. Worktree clean, nothing
staged, nothing pushed (`5f3ebb7` only local).

### Do I agree with the previous validator?

On F-1, yes: its reproducter (dense committed arrivals at the shipped hold) is
real, and the drop it found is gone after the fix (I reproduced the same class
independently and confirmed the red→green by mutation). On F-2/F-3 I agree it
was right to flag them; F-2 is now resolved and F-3 (AC-1 figures) is corrected
and reproduces. Where I disagree with the implementation report is one claim:
the residual `zh_long_time_frontier` miss is content loss, not a wording
difference, and its cause is the stale send index, not `_amend_routed_sentence`.

### Summary

F-1 verified fixed: the hold queue has no completed-item bound at any of its
three enqueue sites, the invariant is documented where it lives, and a dense
stream of committed captions arriving 2-6× faster than the 1.75s release
interval all display in order at the shipped hold — with each restored cap
turning that proof red and a byte-for-byte restore turning it green. AC-1, AC-3
and AC-4 reproduce with the corrected figures. AC-2 still fails on a distinct,
pre-existing path: `translation()` starts its enqueue after a stale
utterance-local sentence index, so one committed sentence of
`zh_long_time_frontier` never displays at the shipped hold under the repo's own
replay cadence (also reproducible at the model level in two utterances, holds
3.5/5.0). Fix and regressions are named above; F-2 is resolved.

## Stage Report: implementation (authorize: fix — stale utterance-local sentence index, R-1)

- DONE: authorize: fix — the fresh re-validation passed F-1 but reports a second, different mechanism that loses content. Fix it; do not weaken AC-2.
  Code commit `d6def32` on `wlk/caption-display-prb` (parent `5f3ebb7`). AC-2's four rules are byte-identical; its `Verified by:` clause now also names the two new regressions, and AC-4's stale branch figure is corrected. Nothing pushed.
- DONE: Reproduce the validator's two-utterance case FIRST and show it red on current code.
  `test_final_after_a_held_caption_displays_every_sentence[3.5]` and `[…-5.0]` fail on `5f3ebb7` (with the new tests present and only the source fix stashed): `['Beta one.']` never reaches the line — neither the final wording nor a draft wording. `[1.2]` passes, exactly the hold sensitivity the validator measured. Green after the fix at 1.2 / 2.0 / 3.5 / 5.0: `Alpha one. → Alpha two. → Beta one. → Beta two. → Beta three.`, in order.
- DONE: My previous claim that this cell was wording-only was WRONG — say so.
  It is content loss: at the shipped hold neither the final's `'In ophthalmic surgery, lasers are used to correct vision.'` nor the draft's `'In eye surgery, …'` ever reaches either line, and the actual mechanism is the stale utterance-local index, not `_amend_routed_sentence`. The F-1 commit neither caused nor fixed it (the drop reproduces with the `c8dce70` package).
- DONE: Define the boundary rule from signals the stream actually has, and justify it in the code comments.
  Rule below; stated in `_end_utterance_routing()`'s docstring and at the `cur_i` read site.
- DONE: After the fix the golden sentence reaches the line at the shipped hold.
  `zh_long_time_frontier` @ 3.5: `[+7.80] BRIGHT 'In ophthalmic surgery, lasers are used to correct vision.'` then `[+9.60] 'They treat myopia and hyperopia.'` (instrument trace); golden-wide, every sentence of every `translation_final` displays verbatim in all five goldens at holds 3.5 and 5.0 — zero missing.
- DONE: Add a test for it, keep the F-1 invariant test and the four suites green, ruff clean.
  13 new cases in `tests/test_caption_display.py`; four suites `84 passed` (was 71); `ruff check whisperlivekit/ tests/ scripts/` → `All checks passed!`; full documented suite `8 failed, 420 passed, 13 skipped` — the same eight pre-existing IDs as `origin/main`.
- SKIPPED: push.
  Dispatch says DO NOT PUSH; `d6def32` stays local, PR #449 untouched, no PR opened.

### The boundary rule (chosen, and why the other signals cannot do it)

`translation()` derives its enqueue start from `line_j` / `cur_i`, which are
sentence POSITIONS in the utterance's own translation. The state that produced
them (`_en_current_sent`, `_en_line_prov`, `_en_line_sent`,
`_en_prev_sent_idx`, `_en_sent_texts`) is utterance-local, and the stream has
no utterance identity, so it must die when the utterance does.

**Rule: a `translation_final` ends the utterance, so it ends the routing.** The
producer finalizes and resets the MT buffer at a segment boundary
(`translation_processor.run_translation` → `validate_buffer_and_reset` on
Silence / ChangeSpeaker / sentinel), so every translation event after a final
describes new text. Implemented as one private `_end_utterance_routing()`
called at both exits of `translation()`; it clears the five fields, so the next
utterance's sentences start unindexed at 0 and `start` can never step over
sentences this utterance has not displayed.

The other signals were checked and rejected as boundaries, on the recorded
streams:
- `transcription_final` fires several times INSIDE one MT utterance — in
  `zh_long_time_frontier` events 1/3/7/10/13/16 are all ASR commits of the
  utterance whose MT final is event 17. It marks source commits, not MT
  utterance ends (the MT sees a whole VAD segment).
- `translation_provisional.committed` / `.source` reset just as much inside an
  utterance as across one: `zh_long_canonical` events 6/7 have `committed=''`
  mid-utterance, and it is `''` on both sides of a real boundary (final at 22 →
  draft at 23). An empty `committed` means "a fresh segment", not "a new
  utterance", so keying on a reset both fires falsely and misses boundaries.
- `translation_provisional.fresh` is a cost flag (draft vs cached release), not
  an identity: `fresh=False` appears mid-utterance (`canonical` 7, 10, 12) and
  on the first draft of a new one (`canonical` 35).

### Red before the fix (only the source fix stashed; the new tests in place)

```
FAILED tests/test_caption_display.py::test_final_after_a_held_caption_displays_every_sentence[3.5]
FAILED tests/test_caption_display.py::test_final_after_a_held_caption_displays_every_sentence[5.0]
FAILED tests/test_caption_display.py::test_golden_every_final_sentence_displays_verbatim[zh_long_time_frontier-hold3.5]
3 failed, 63 passed
```
Independent reproducer (`/tmp/fix-r1/repro.py`, model-level, public API only)
agrees on both shapes: two-utterance case loses `'Beta one.'` at 3.5/5.0, and
the golden replay loses exactly one sentence at hold 3.5 (0 at 1.2/5.0).

### Green after the fix

- Four suites: `84 passed` (71 before: +3 parametrised cases +10 golden/hold
  cases).
- Documented full suite: `8 failed, 420 passed, 13 skipped` — the same eight
  environment-dependent IDs as `origin/main` `ada82d4` (canary ×2, deepgram ×1,
  qwen3 shims ×5), no branch-only failure.
- Instrument: `scripts/replay_canonical_overlay.py` twice → byte-identical,
  md5 `a7ed5390c6a2c27a03c8331926f823ce`, 44 lines — unchanged by this fix, so
  AC-1's determinism artifact still holds.
- No dim draft scrolls into history on any golden at holds 1.2/3.5/5.0 (0
  occurrences; checked directly, since that golden invariant is only pinned on
  `zh_long_canonical` by a test).

### What changes in the reader-visible trace (only `zh_long_time_frontier` @ 3.5)

Pre/post comparison of the shown-line lists for all five goldens at holds
1.2/3.5/5.0: the only delta is `zh_long_time_frontier` @ 3.5.
- Added (committed): `'In ophthalmic surgery, lasers are used to correct vision.'`
  and its dim draft `'In eye surgery, lasers are used to correct vision.'`.
- No longer shown: two DRAFT wordings, `'Dentists also use laser technology for
  this.'` (dim) and `'This reduces bleeding, sweating, and pain.'` (a
  draft-routed sentence, so it carried the bright style). Their sentences still
  display in the final's wording — `'Dentists also use laser technology for oral
  surgery.'` and `'It reduces bleeding, sweating, and pain.'` are both still in
  the trace, and the golden-wide assertion is on final wording, which now has
  zero gaps. So the delta is one recovered committed sentence plus one fewer
  wrong-worded draft, not a swap of one caption for another.

### Falsifiability (each mutation restored byte-for-byte; md5 `0d4c76b2…`)

- Drop BOTH `_en_current_sent = -1` and `_en_line_prov = False` from the helper
  (= the pre-fix tail) → the 3 new cases above red, nothing else. This is the
  atomic mutation point: `cur_i` needs `_en_is_final and _en_line_prov and
  _en_current_sent >= 0`, so dropping either field alone stays green (M1/M2
  verified green) — the pair is one increment, not two.
- Drop the `_end_utterance_routing()` call at the LEGACY exit only → green
  (M3). Honest status: not independently falsifiable today, because any state
  that can set `_en_current_sent` also fills `_en_sent_texts`, so a final that
  takes the legacy branch (`len(sents) <= 1 and not _en_sent_texts`) cannot
  carry stale routing. It is kept so the rule holds at every exit of
  `translation()` rather than at one of the two — the reviewer can drop it as
  one line if the redundancy is unwanted.

### Left open (unchanged, still deferred — no new claim)

- `F-2b` still reproduces exactly as the validator described: `preview("Alpha
  one. Beta two. Gamma thre")` then `translation(...)` with no tick in between
  displays only `'Gamma three.'` at holds 1.2/3.5/5.0. Different mechanism (the
  `line_j` branch drops the leading draft-routed QUEUE items, not a stale
  index), same-utterance, unreachable from the shipped instrument.
- The pacing note from the F-1 cycle still applies: with no bound on the queue,
  a producer that outruns the drainer deepens the backlog (the reader falls
  behind) instead of losing captions. This fix can add one item to that backlog
  in the cell above; it never removes one.

### Summary

`translation()`'s sentence routing (`_en_current_sent`, `_en_line_prov`,
`_en_line_sent`, `_en_prev_sent_idx`, `_en_sent_texts`) is utterance-local and
the caption stream carries no utterance identity, so a `translation_final` now
ends it: the producer finalizes and resets the MT buffer at a segment boundary
(`translation_processor.run_translation` → `validate_buffer_and_reset` on
Silence / ChangeSpeaker / sentinel), so every event after a final describes new
text. One private `_end_utterance_routing()` runs at both exits of
`translation()`, so the next utterance's sentences start unindexed at 0 and
`start` can no longer step over sentences this utterance has not displayed. The
other candidate signals were rejected on the recorded goldens, not by argument:
`transcription_final` fires six times inside the one MT utterance whose final is
`zh_long_time_frontier` event 17, `committed`/`source` resets as often inside an
utterance as across one (`zh_long_canonical` 6/7 empty mid-utterance, `''` on
both sides of the real boundary 22 → 23), and `fresh` is a cost flag that shows
up mid-utterance (7, 10, 12) and on the first draft of a new one (35). Red: with
only the source fix stashed and the new tests in place, exactly three cases fail
(two-utterance `[3.5]` and `[5.0]`, `zh_long_time_frontier-hold3.5`). Green:
holds 1.2 / 2.0 / 3.5 / 5.0 all show `Alpha one. → Alpha two. → Beta one. →
Beta two. → Beta three.` in order, and every sentence of every
`translation_final` displays verbatim across all five goldens at holds 3.5 and
5.0, zero missing. The earlier "wording only" characterisation of that cell was
wrong: it is content loss — at the shipped hold neither the final's wording nor
the draft's ever reached either line — and the mechanism is the stale
utterance-local index, not `_amend_routed_sentence`.

## Stage Report: validation (third fresh validation)

Third fresh validator. Everything below was re-derived from the code and from my
own scripts; the two earlier verdicts were read only to know which findings to
re-check, never as evidence. Environment: branch `wlk/caption-display-prb` @
`d6def32` (parent `5f3ebb7`, merge-base / `origin/main` `ada82d4`), interpreter
`/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python`, `PYTHONPATH=.` from the
worktree. Nothing pushed; no product code edited outside throwaway copies; the
worktree is clean (`git status --short` empty, HEAD `d6def32`, nothing staged).

**Verdict: PASSED.** AC-1, AC-2, AC-3 and AC-4 all reproduce with reproducible
evidence; F-1, F-2 and R-1 each re-verified fixed from scratch, with the pre-fix
shape restored in a throwaway copy going red and the shipped code going green
(byte-for-byte md5 restore). No sentence of any golden fails to display verbatim
at the shipped hold, and no *committed* caption is lost on any recorded stream or
constructible stage sequence I could build.

Two findings are disclosed and judged non-blocking: **F-2b** (the gate asked for
an explicit judgment — given below) and **F-4**, a new field-audit result
(`_queued_draft` has the same stale-lifetime shape as the two fixed bugs; it can
re-display a superseded draft fragment after its utterance ended, but it cannot
lose committed content).

Two environment traps are worth recording because they invalidate results
silently (both bit me before I caught them):

1. `PYTHONPATH=.` is load-bearing. Without it, `python scripts/…` and
   `python -m pytest` resolve `whisperlivekit` to the **main-repo editable
   install** (`/Users/clkao/git/asr/WhisperLiveKit/whisperlivekit`), i.e. a
   different checkout. Verified: bare
   `python scripts/replay_canonical_overlay.py` →
   `ImportError: cannot import name 'load_caption_events' from
   'whisperlivekit.caption_display' (…/WhisperLiveKit/whisperlivekit/…)`.
2. pytest inserts the **rootdir of the target path** ahead of `PYTHONPATH`, so a
   mutated package placed only on `PYTHONPATH` is *not* the one under test. My
   first mutation pass looked green for that reason. Every mutation below ran in
   a throwaway *tree* (`/tmp/val3-5m/tree` = copies of `whisperlivekit/`,
   `tests/`, `pyproject.toml`), with the imported module path printed on each
   run (`/tmp/val3-5m/tree/whisperlivekit/caption_display.py` + a "cap present"
   probe of `_enqueue_item`'s source).

### AC-1 — PASS (deterministic replay), figures re-derive

`/tmp/val3-5m/ac1_replay.py` replays each golden twice through
`load_caption_events` → `CaptionDisplay(hold_sec=1.2, clock=<stepped counter>)`
with the repo convention (advance 0.3 → emit → one tick, then a 30s drain) and
compares both the reader-visible line sequence and the full per-tick
`(current spans+styles, prev spans+styles)` trace:

```
zh_long_canonical      events= 69 ticks=369 distinct_lines=15 identical_lines=True identical_full_trace=True
zh_long_time_frontier  events= 52 ticks=352 distinct_lines=13 identical_lines=True identical_full_trace=True
zh_long_ideal          events= 60 ticks=360 distinct_lines=18 identical_lines=True identical_full_trace=True
zh_ja_fallback         events= 53 ticks=353 distinct_lines=17 identical_lines=True identical_full_trace=True
demo_en_30s_ideal      events= 60 ticks=360 distinct_lines=13 identical_lines=True identical_full_trace=True
```

The corrected figures reproduce exactly: events `69 / 52 / 60 / 53 / 60`,
distinct caption lines `15 / 13 / 18 / 17 / 13` (tick counts
`369 / 352 / 360 / 353 / 360` match the older report too, now labelled
correctly). `PYTHONPATH=. python scripts/replay_canonical_overlay.py` twice →
both `rc=0`, `diff` clean, `md5 a7ed5390c6a2c27a03c8331926f823ce`, 44 trace
lines.

Falsifiability (re-run): `now = self._clock()` → `now = time.monotonic()` in
`tick()` reddens 3 replay tests (`test_reword_retraction_held`,
`test_canonical_stream_every_final_sentence_reaches_the_line`,
`test_canonical_stream_never_scrolls_a_draft_into_history`). The earlier
validator's F-3 nit is fixed and I confirm the fixed numbers.

### AC-2 — PASS

Named tests: the 12 tests AC-2 cites (23 cases with their parametrisation) exist
and pass together — `23 passed, 43 deselected`. The four rules, probed directly
through the public API (`/tmp/val3-5m/ac2_ac3.py`, not by reading the tests):

- partition: `translation("First sentence. Second sentence. Third sentence.")` →
  `['First sentence.', 'Second sentence.', 'Third sentence.']`;
- held and shown: at `hold=1.0` the three lines appear at `0.05 / 1.05 / 2.05`,
  gaps exactly `1.0 / 1.0`;
- promote in place: `[('Hello there.','provisional')]` →
  `[('Hello there.','same')]` in one tick, no empty frame, `prev` untouched;
- no shrink/reword: a shorter ASR partial leaves `tick() is None` with the long
  partial intact; a reworded final amends the line (`[('Dentists use lasers to
  remove tumor tissue','same')]`) without blanking or retraction.

Golden-wide "every sentence of every `translation_final` displays verbatim",
extended past what the shipped test covers — **5 goldens × holds 1.2/3.5/5.0 × 6
view cadences = 90 cells** (`/tmp/val3-5m/ac2_golden.py`; cadences: the repo
convention, emit-then-advance, 30 fps, 10 fps, 0.1 s/event, 0.6 s/event):

```
cells checked: 90
cells with a missing final sentence: 0
sentences never shown as an EXACT line: 0
```

Per golden at the shipped hold and a short one (instrument cadence):

```
hold=3.5  zh_long_canonical 12/12 · time_frontier 8/8 · ideal 6/6 · zh_ja_fallback 12/12 · demo_en_30s 6/6
hold=1.2  zh_long_canonical 12/12 · time_frontier 8/8 · ideal 6/6 · zh_ja_fallback 12/12 · demo_en_30s 6/6
```

The queue half of AC-2 (no unshown committed caption leaves the queue) is green
for all 5 goldens × holds 3.5/1.2 and reddens under the restored bounds (M1–M4
below), so the criterion's "held and shown" clause is falsifiable in both
directions at the shipped hold.

### AC-3 — PASS

`test_no_display_state_without_a_consumer` passes, and I rebuilt the wiring over
a real `AudioProcessor` (bare `TranscriptionEngine`, pcm/vac off):

```
no consumer:    caption_display is None: True | event_tap._sink is None: True
no consumer:    tap accepted an event with no sink (no exception)
event-log only: caption_display is None: True | sink type: EventLog
display only:   same object: True | sink is the model: True | model received the event: 'Hello there.'
both:           sink type: _FanOutSink | fan-out sinks: ['CaptionDisplay', 'EventLog']
```

(Note for future readers: `--event-log` reaches the processor through
`engine.args.event_log`, not a constructor kwarg; passing `event_log=` as a
kwarg is silently ignored and made the sink look absent in my first probe.)

### AC-4 — PASS

The documented command
(`pytest -q tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_asr_coalescing_pipeline.py`)
run in two trees, with the imported package verified on each side:

```
origin/main ada82d4   → 8 failed, 335 passed, 13 skipped in 49.22s
branch   d6def32      → 8 failed, 420 passed, 13 skipped in 50.71s
```

Same eight failure IDs on both sides (canary backend ×2, deepgram SDK ×1, qwen3
shims ×5 — environment-dependent, present upstream); no branch-only failure.
The branch figure now matches the AC text (`d6def32` / `420`), so the stale
`c8dce70` / `395` note from the previous round is resolved. The origin/main
export contains no `caption_display` reference at all (checked:
`grep -rln "caption_display\|caption_events" tests/ whisperlivekit/` in the
export → empty), so the comparison is not contaminated by the branch's files.

### F-1 re-verified — FIXED (queue bound)

1. **No completed-item bound remains.** `grep -n "_queue\[-\|_queue\[:\|len(self._queue)"`
   returns only `cut = len(self._queue)` at `:456` (the insert point). The
   invariant is stated where the queue is declared (`:211-217` "NOT capped —
   every completed caption in it must display … The only superseded content is
   a DRAFT"), at `_enqueue_sentence` (`:445-449`), at the `translation()`
   rebuild and at `_enqueue_item` (`:727` "uncapped — see __init__: never
   evicted").
2. **Behavioural proof at the shipped hold** (`/tmp/val3-5m/dense_probe.py`,
   public API only, 12 committed captions, arrival 0.3 / 0.9 / 1.2 / 1.6 s and
   holds 3.5 / 1.2 → 8 scenarios): `missing=[]` in every cell, peak queue depth
   up to 10 — i.e. captions arriving up to 5.8× faster than the 1.75 s release
   interval all display, in order.
3. **Red before / green after, each site separately** (see the mutation table):
   restoring the bound at `_enqueue_item` loses up to 7 of 12 committed captions
   in my dense probe (`['Bravo is here.', 'Charlie is here.', 'Echo is here.', …]`)
   and reddens 4 repo tests; restoring it at the `translation()` rebuild loses
   4/12 and 3/30 and reddens the backlog test; restoring it at
   `_enqueue_sentence` reddens `test_no_committed_caption_leaves_the_queue_unshown[zh_long_time_frontier-hold3.5]`;
   all three at once (the pre-fix `c8dce70` shape) reddens 6 repo tests. Each
   restore returns `caption_display.py` to md5
   `0d4c76b293adca5fe31edf596adc80d1` and green.

### F-2 re-verified — RESOLVED

`zh_ja_fallback` displays every final sentence at both holds (12/12 at 3.5 and
at 1.2, the table above), including the sentence the second validator cited,
`出血や汗、痛みを減らす。` (`True` at both holds, exact-line match). Its mechanism
was a cap eviction at `_enqueue_item`: restoring that one bound reddens
`[zh_ja_fallback-hold3.5]` and `[…-hold1.2]`, which is the pre-fix damage
reproduced.

### R-1 re-verified — FIXED (stale utterance-local index)

1. **Reproducer from scratch** (`/tmp/val3-5m/r1_repro.py`, model level, public
   API): the previous utterance's line ends on sentence index 1, then a longer
   final arrives:

   ```
   hold=1.2: beta shown=['Beta one.', 'Beta two.', 'Beta three.'] OK
   hold=2.0: beta shown=['Beta one.', 'Beta two.', 'Beta three.'] OK
   hold=3.5: beta shown=['Beta one.', 'Beta two.', 'Beta three.'] OK
   hold=5.0: beta shown=['Beta one.', 'Beta two.', 'Beta three.'] OK
   deep(prev idx 2) hold=1.2 / 3.5 / 5.0: ['Beta one.'…'Beta four.'] OK
   golden time_frontier hold=1.2 / 3.5 / 5.0: 'In ophthalmic surgery, lasers are used to correct vision.' displayed=True
   R-1 ALL PASS
   ```

   and every final sentence of all five goldens is an exact displayed line at
   holds 1.2 / 3.5 / 5.0 (no misses reported).
2. **Red before the fix**: dropping `_en_current_sent = -1` **and**
   `_en_line_prov = False` from `_end_utterance_routing()` (in a throwaway tree)
   → `3 failed`: `test_final_after_a_held_caption_displays_every_sentence[3.5]`,
   `[5.0]` and `test_golden_every_final_sentence_displays_verbatim[zh_long_time_frontier-hold3.5]`,
   with `never displayed: 'In ophthalmic surgery, lasers are used to correct
   vision.'`. Dropping the whole five-field reset gives the same 3 failures.
   Restored → md5 back, `13 passed` on the same selection (baseline).
3. **Is the rule justified from signals the stream actually has?** Yes, and I
   re-derived the rejection of the alternatives from the goldens
   (`/tmp/val3-5m/r1_signals.py`) rather than from the report:
   `transcription_final` fires 1–6 times *inside* one MT span
   (canonical `[2,2,2,1,1,1,2,1,2,1,2,1]`, time_frontier `[6,3,6,2]`);
   `translation_provisional.committed` is empty mid-span (canonical 14 of 23)
   and also empty on the first draft of later spans; `fresh` is False mid-span
   (canonical 17, demo 14) and False on the first draft of later spans. No final
   duplicates its predecessor (0 of 34 finals start with the previous final's
   text), so text after a final is always new text — which is what makes
   "a final ends the routing" safe.
4. **Is the code stating it at the read site?** Yes: the docstring of
   `_end_utterance_routing()` (`:632-651`) states the rule and the rejected
   signals, and the comment immediately above the read
   (`cur_i = …`, `:585-589`) says the previous utterance's index is what would
   step `start` past this final's leading sentences. Both reset call sites exist
   (`:565` legacy exit, `:627` routing exit).
5. **One accuracy nit (documentation, non-blocking, F-5).** The stated *reason*
   — "the producer finalizes and resets the MT buffer at a segment boundary
   (`validate_buffer_and_reset` on Silence/ChangeSpeaker/sentinel)" — is exactly
   true for the simul backend, which is the only backend that produces drafts
   (`translation_mlx_llm_mt_simul.process` returns `(None, buffer)`; finals come
   only from `validate_buffer_and_reset`). It is *not* the whole story for the
   base segment backend: `translation_mlx_llm_mt.insert_tokens` queues a segment
   final at every **punctuation** (`_pending_finals`, `_buffer_tokens` cleared)
   and `process()` drains them, so a `translation_final` can fire mid-utterance
   without a buffer reset. The rule still holds there — the buffer is cleared at
   that punctuation, finals are non-cumulative (0/34), and that backend sets no
   `provides_drafts`, so the routing state it would reset is never populated —
   but the docstring should say "every event after a final describes new text"
   rather than assert a boundary flush, so a future backend that both drafts and
   emits mid-utterance finals is not silently assumed safe.

### Per-utterance-field audit (the class of bug this history is about)

State initialised once in `__init__` and mutated during routing, with where it
is reset:

| field | declared | reset site | does a `translation_final` reset it? |
|---|---|---|---|
| `_en_sent_texts` | `:224` | `_end_utterance_routing` `:653` | yes |
| `_en_current_sent` | `:225` | `:656` | yes (this is R-1's field) |
| `_en_line_prov` | `:226` | `:657` | yes (R-1's second field) |
| `_en_prev_sent_idx` | `:233` | `:654` | yes |
| `_en_line_sent` | `:234` | `:655` | yes |
| `_en_draft_full` | `:223` | **no reset**; overwritten with the *finished* final's text at `:562` (legacy) / `:628` | no — but it is a "last text seen" cache: `preview`'s early return and the append-effect delta are correct for any value that is a prefix of the new text, and no failure is constructible (see F-4 note) |
| `_en_frag` | `:227` | **no reset**; set to the final's trailing fragment at `:563` (legacy: `""`) / `:629` | no — residual fragment is only consumed by `_update_fragment`'s append/rewrite branches, which additionally require the new draft to start with the stale full text; no loss constructible |
| `_queued_draft` | `:228` | cleared only on the legacy exit (`:564`) and when `tick()` releases it (`:799`) — **not** on the sentence-routing path | **no — F-4 below** |
| `_queue` | `:218` | untouched by a final by design (the reader's backlog) | intentionally not reset; pinned by `test_new_multi_sentence_final_never_evicts_the_pending_backlog` |
| `_en_plain`, `_en_spans`, `_en_is_final`, `_en_shown_at`, `_en_prev_plain/_spans/_at`, `_partial`, `_partial_shown_at`, `_last_partial`, `_last_state`, `_dirty` | `:203-209`, `:237-241` | n/a | display-lifetime state: persists across utterances by design (the line, its history and the source row are not utterance-scoped) |

**F-4 (new, non-blocking — same stale-lifetime shape, no loss):**
`_queued_draft` (`:228`) holds the in-progress fragment parked behind a bright
sentence and is **not** invalidated when its utterance ends, unlike the five
fields R-1 fixed. Reproducer (public API, hold 1.2):

```
preview("S1 sentence. S2 sentence."); tick          → line 'S1 sentence.' (_en_current_sent 0)
preview("S1 sentence. S2 sentence. fragment of S3") → _queued_draft = 'fragment of S3'
translation("S1 sentence. S2 sentence. Fragment of S3.")  → _queued_draft STILL 'fragment of S3'
displayed: ['S1 sentence.', 'S2 sentence.', 'Fragment of S3.', 'fragment of S3', 'Zeta one.', 'Zeta two.']
```

The superseded draft fragment pops back onto the line *after* the utterance's
committed sentences and after the final replaced it. Nothing is lost (every
committed sentence of both utterances displays); what the reader gets is stale
dim text from a finished utterance. It is not reachable from the recorded
streams: across all 5 goldens × holds 3.5/1.2 × {instrument, 10 fps} (20 cells) a
`translation_final` never leaves a `_queued_draft` behind and no pre-final
queued draft is ever released later (0 / 0 in every cell). Missing reset: add
`self._queued_draft = None` to `_end_utterance_routing()`, but only after
confirming with the author that the fragment is genuinely superseded by every
final (the final's own trailing fragment is re-created from `sents` the same
tick, so it is). Not a gate blocker by the stated bar (no reproducible loss).

### F-2b — judged explicitly (as the gate requires)

*What it is.* `preview("Alpha one. Beta two. Gamma thre")` then
`translation("Alpha one. Beta two. Gamma three.")` **with no view tick in
between** takes the `line_j` branch: it puts `sents[line_j]` on the line and
enqueues only `i > line_j`, so the leading draft-routed queue items are dropped
and never re-supplied. Reproduced exactly as disclosed
(`/tmp/val3-5m/f2b.py`): displayed lines = `['Gamma thre', 'Gamma three.']` at
holds **1.2, 3.5 and 5.0** — `'Alpha one.'` and `'Beta two.'`, both sentences of
the committed final, never display. One `tick()` between the two calls fixes it
(`['Alpha one.', 'Beta two.', 'Gamma three.']`).

*Is it content loss under AC-2?* **Yes, in mechanism.** Those two strings are
sentences of a `translation_final`, and AC-2 says a finished sentence is held
and shown; a sentence never enqueued is lost content of exactly the R-1 kind
(same branch, same "start index steps over sentences this utterance has not
displayed" logic — R-1's fix reset the index across utterances and did not
cover this same-utterance-before-any-tick case). It is not a wording/retraction
case: neither the final's nor a draft's wording reaches the line.

*Is it reachable from any shipped path?* **No.**
- No view ships in this task (overlay/TUI are explicitly out of scope; the diff
  contains no view code), and the only shipped consumers are `--event-log`
  (records, does not render) and the replay instrument, which ticks once per
  event — there is always a tick between two events, so the branch cannot be
  taken there. Empirically: 90/90 audit cells and all five goldens are clean.
- For a future view, the condition is "a frame boundary does not fall between
  the draft that routes the sentence and the following final". Measured on the
  recorded streams, the tightest draft→final gap where the draft had already
  routed a sentence is **0.653 s** (time_frontier, wall clock) and **0.677 s**
  (canonical, wall clock); the two synthetic goldens carry no wall clock at all
  (`t == 0.0` on every event) and show a 0.25 s `audio_t` gap. So any consumer
  ticking faster than ~1.5 fps (real captures) / ~4 fps (synthetic) cannot hit
  it; a consumer that batches several events per frame, or ticks at ≤1 fps,
  can.

*Does it block?* **No.** Both blocking bars the gate sets are mechanical — a
sentence of a golden failing to display at the shipped hold (none: 90/90 cells,
10/10 golden×hold cells), and another stale-lifetime field with a reproducible
loss (`_queued_draft` produces stale text but no loss). F-2b is a latent
content-loss defect that this task's shipped artifacts do not expose, so it does
not fail this gate; it must be fixed before (or with) the view that Task C ships,
and the minimal reproducer belongs in `tests/test_caption_display.py` now rather
than later. Concrete fix: in `translation()`, before taking the `line_j` branch,
enqueue the sentences before it that were routed from this utterance's draft and
have not displayed (`sents[0:min(line_j, cur_i)]`, or start the enqueue at the
first undisplayed index); the R-1 test and this reproducer then both go green.

### Mutations run (each in the throwaway tree, restored byte-for-byte)

| # | mutation (exact-string, single occurrence) | result before restore | restore |
|---|---|---|---|
| M0 | none (baseline tree) | `66 passed` (display + replay suites) | — |
| M1 | completed-item bound back at `_enqueue_sentence` (`del self._queue[:-3]`) | **red**: `1 failed, 12 passed` — `…leaves_the_queue_unshown[zh_long_time_frontier-hold3.5]` | md5 `0d4c76b2…` ✔ |
| M2 | bound back at the `translation()` rebuild (`(kept + new_items)[-3:]`) | **red**: `1 failed` — `test_new_multi_sentence_final_never_evicts_the_pending_backlog`; dense probe loses 4/12 and 3/30 | md5 ✔ |
| M3 | bound back at `_enqueue_item` | **red**: `4 failed` — dense stream, `zh_ja_fallback` (3.5 and 1.2), `zh_long_canonical` (3.5); my dense probe loses 7/12 at 0.3 s arrival, 3/12 at 0.9 s | md5 ✔ |
| M4 | all three bounds (the pre-fix `c8dce70` shape) | **red**: `6 failed, 7 passed` | md5 ✔ |
| M5 | drop `_en_current_sent = -1` + `_en_line_prov = False` from `_end_utterance_routing()` | **red**: `3 failed` — two-utterance `[3.5]`, `[5.0]`, `time_frontier-hold3.5` verbatim (`never displayed: 'In ophthalmic surgery, …'`) | md5 ✔ |
| M6 | drop the whole five-field reset (`pass`) | **red**: the same `3 failed` (no additional test distinguishes the other three fields — they are defence-in-depth, not independently pinned) | md5 ✔ |

Every mutate/restore pair was verified with md5 and, per run, with a check that
the imported module is the tree's (`/tmp/val3-5m/mutate.py` prints
`…/tree/whisperlivekit/caption_display.py` and probes `_enqueue_item`'s source
for the injected bound). After all mutations the tree is byte-identical to the
worktree file.

### Scope / hygiene

`git diff --name-only db143d3 HEAD` = `scripts/replay_canonical_overlay.py`, the
five `tests/golden/*.jsonl`, `tests/test_caption_display.py`,
`tests/test_overlay_replay.py`, `whisperlivekit/{caption_display.py,
audio_processor.py, test_harness.py}` — no view/overlay/TUI code, no
consumer-task file. `ruff check whisperlivekit/ tests/ scripts/` → `All checks
passed!`. Worktree clean, nothing staged, nothing pushed (`d6def32` is local
only; `git branch -r --contains d6def32` is empty).

### Residual risks / recommendations for the next cycle

1. **F-2b** — fix in `translation()`'s `line_j` branch and pin with the minimal
   reproducer before Task C ships a view (the one non-blocking correctness gap
   left in this class).
2. **F-4 `_queued_draft`** — add the reset in `_end_utterance_routing()`; it only
   mis-displays stale text today.
3. **F-5 docstring accuracy** — state the rule as "text after a final is new
   text" instead of naming the segment-boundary flush as its mechanism, so the
   punctuation-final path in `translation_mlx_llm_mt` is covered by the
   justification rather than by luck.
4. **Test-strength note (F-6, informational):** the three routing fields other
   than `_en_current_sent`/`_en_line_prov` are not independently falsifiable
   (M5 and M6 give the identical failure set); if the author wants them pinned,
   a test needs to construct a case where only `_en_sent_texts`,
   `_en_prev_sent_idx` or `_en_line_sent` is stale. Similarly
   `test_drained_replay_displays_every_completed_sentence` never goes red under
   any restored bound (it spot-checks three sentences), which is why the
   golden-wide verbatim test is the load-bearing one.
5. **Validation-environment trap** (both bullets at the top) — `PYTHONPATH=.`
   and "verify which package pytest imported" should be in the next dispatch;
   without them a mutation can appear green (I hit exactly that).

### Summary

Third fresh validation passes the entity: AC-1's determinism and its corrected
figures re-derive (5 goldens × 2 replays identical, `69/52/60/53/60` events,
`15/13/18/17/13` lines, instrument byte-identical `a7ed5390…`), AC-2's four
rules hold directly and across 90 golden × hold × cadence cells with zero
missing final sentences, AC-3 shows no display object or sink without a
consumer, and AC-4 gives the same eight failure IDs on `origin/main ada82d4`
(8/335/13) and the branch `d6def32` (8/420/13). The three prior corrections are
fixed, each proven by restoring the pre-fix shape in a throwaway tree: the
completed-caption bound goes red at all three enqueue sites (4–7 of 12 committed
captions lost in my dense probe, 1–6 repo tests red) and green on restore at md5
`0d4c76b2…`; `zh_ja_fallback` displays 12/12 sentences at holds 3.5 and 1.2
including the cited Japanese sentence; and the stale utterance-local index is
gone at holds 1.2/2.0/3.5/5.0 and for all five goldens, going red exactly on
`[3.5]`, `[5.0]` and `time_frontier-hold3.5` when the reset is removed.
The field audit found two further fields with the same stale-lifetime shape that
no final resets — `_en_draft_full`/`_en_frag` (harmless caches) and
`_queued_draft`, which can re-display a superseded draft fragment after its
utterance ended (reproducer given, no loss, absent from all 20 recorded-stream
cells). The disclosed F-2b is judged content loss in mechanism but unreachable
from every shipped path (the instrument ticks per event; the tightest recorded
draft→final gap is 0.65 s wall / 0.25 s audio, so only a ≤1–2 fps consumer can
hit it), so it does not block this gate — it must be fixed with Task C's view,
with the minimal reproducer added as a test now.
