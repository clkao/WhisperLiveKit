---
title: "caption event stream for PR #449 (PR-A: typed caption events + --event-log)"
status: implementation
score: 0.85
id: 6yfnt6r6tx4mqj9p4dkrgaq8
worktree: .worktrees/wlk-display-unification
pr: "#449"
---

# Caption event stream for PR #449 (PR-A) — typed caption events and --event-log

## Context

PR #449 goes upstream as the caption event stream: the typed `CaptionEvent`
payload (`t`, `audio_t`, `type`, `text`, plus `committed`/`source`/`fresh` on
translation provisionals), the stateless `EventTap` the generation loop emits
into (`audio_processor.py` for the ASR side — committed segment, rolling tail,
terminal flush — and `translation_processor.py` for the MT side), an `EventLog`
JSONL sink that exists only when `--event-log PATH` is set, and the backend
draft contract (`TranslationProgress`, `provides_drafts`, `progress()`, read
through a `_ProgressReader` so backends predating it stay on the no-draft
path). The stream is the seam a display, a test or an evaluation harness
consumes independently of how anything renders; the web UI's `FrontData` wire
protocol is untouched. Upstream main carries none of it — this whole file set
is new surface.

This entity was split during the PR #449 review of 2026-11-08: the display half
(caption display model, overlay/TUI views, the goldens and the replay
instrument) left for PR-B, now entity `wlk-caption-display` (`5m`), parked on
branch `wlk/caption-display` @ `513b6fa`.

## End value

Display behavior and the event stream stop being entangled with the MT layer, and a
downstream consumer can be built on a recorded stream.

## Work

1. `whisperlivekit/caption_events.py`: the typed payload `CaptionEvent` (`t`,
   `audio_t`, `type` one of transcription_provisional / transcription_final /
   translation_provisional / translation_final, `text`, plus `committed`,
   `source`, `fresh` on translation provisionals), the `EventSink` protocol, a
   stateless `EventTap` whose `sink=None` is a no-op, and `EventLog` — a JSONL
   sink that opens the path in append mode and writes + flushes one line per
   `emit()`.
2. Emission points: `audio_processor.py` builds the tap (and an `EventLog` only
   when `--event-log` is set), emits transcription provisionals/finals at the
   ASR commit points, the streaming refresh and the finish flush, and closes the
   log in `cleanup()`; `translation_processor.py` emits `translation_final`
   (single or list results) and `translation_provisional` (committed summary,
   full source the MT saw, fresh flag) from the translation loop.
3. Backend contract: `TranslationProgress` in `timed_objects.py`, plus
   `provides_drafts` and `progress()` on the translation backends
   (`MlxLlmTranslation` false/honest-empty, `MlxLlmTranslationSimul` true), read
   in `translation_processor.py` through a `_ProgressReader` that leaves
   backends predating the contract on the no-draft path and disables drafts for
   the rest of a session (one warning) if `progress()` raises.
4. `--event-log PATH` on the server CLI (`parse_args.py` →
   `WhisperLiveKitConfig.event_log`), off by default, documented in
   `docs/configuration.md`.

Not in this PR: the caption display model that consumes the stream — that is
PR-B, entity `wlk-caption-display`.

## Acceptance

**AC-1 — Typed caption events are emitted at the documented points
(transcription provisionals/finals, translation provisionals/finals), each
carrying its text and the source it was produced against.**
Verified by:
`tests/test_caption_events.py::TestEventTap::test_one_utterance_emits_the_typed_sequence_in_order`
drives one utterance's events through the tap into a recording sink and asserts
the observed sequence in full — the four types in emission order, each event's
`text`, `audio_t` and its emit-time `t`, and both translation provisionals'
`committed`/`source`/`fresh` — so it fails if a tap emit method drops or
reorders a call, stops forwarding text or audio position, or mis-threads the
`committed`/`source`/`fresh` columns (confirmed red by stripping `source` from
`translation_provisional`, which trips the payload assertion);
`tests/test_asr_emission.py::test_one_utterance_emits_the_transcription_sequence`
drives one utterance through the real `AudioProcessor.transcription_processor`
loop with a tap on a recording sink and asserts the exact
`(type, text, audio_t)` sequence the four ASR-side call sites in
`audio_processor.py` produce — the committed segment, the rolling tail, the
periodic buffer refresh on the loop's queue timeout, and the terminal flush at
end of stream — so it fails if any of those call sites stops emitting or
reorders them (confirmed red twice: deleting the terminal-flush emit, and
swapping the chunk-path final/provisional pair, each trips the sequence
assertion);
`tests/test_translation_emission.py::test_translation_final_emitted_for_single_and_list`
and `::test_provisional_carries_committed_source_fresh` drive the real
`run_translation` loop against a mock backend and fail if finals stop emitting
for single-or-list results or a provisional loses its `committed`/`source`.

**AC-2 — `--event-log` appends one JSONL line per event as it is emitted, with
no in-memory accumulation and no write-on-cleanup.**
Verified by: `tests/test_caption_events.py::TestEventLog::test_two_events_are_two_lines_before_close`,
which emits twice and reads the file while the sink is still open; it fails if
the sink buffers and writes on close.

**AC-3 — No per-session display state is allocated when nothing consumes the
stream (no accumulator object when `--event-log` is unset).**
Verified by: a processor built from args with `event_log=None` has
`event_tap._sink is None` and no line/display-state attribute, and
`git grep -n 'EventLog(' whisperlivekit/audio_processor.py` shows the log built
only on the truthy path; it fails if a session allocates display state
unconditionally.

**AC-4 — Translation backends declare `provides_drafts` and `progress()`; a
backend without drafts needs no change and never enters the draft path.**
Verified by: `tests/test_translation_emission.py::test_provisional_requires_provides_drafts`
and `::test_base_backend_contract_defaults_are_honest`; they fail if a backend
that declares no drafts emits a provisional or is forced to implement the
contract.

**AC-5 — No new suite failures versus `origin/main` at the same commit.**
Verified by: full-suite counts on the branch compared against a detached
`origin/main` worktree at the merge-base with the same interpreter, diffing the
failure + error sets; any failure id absent from the baseline fails the AC.

## Notes

- Parked material for PR-B: branch `wlk/caption-display` @ `513b6fa`, the
  pre-trim state of this branch. It carries `whisperlivekit/caption_display.py`,
  `tests/test_caption_display.py`, `tests/test_overlay_replay.py`,
  `scripts/replay_canonical_overlay.py` and the five `tests/golden/*.jsonl`
  goldens (including `zh_long_time_frontier.jsonl`), all cut from this PR in
  commit `7394a9b`. The display model's owner is entity `wlk-caption-display`
  (`5m`).
- `wlk-tui-package` (`42`) consumes this stream contract and targets the
  integration branch until PR #449 clears upstream.
- Historical: this entity was rescoped from the unified display task on
  2026-11-08 and now describes the event-stream half only.

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

## Stage Report: display-unification (cycle 2 — emission wiring)

- DONE: All four event types emitted from main's restructured pipeline
  audio_processor __init__ attaches EventTap+DisplayAdapter (+EventLog when
  args.event_log set); transcription_final/provisional emitted at the ASR
  commit block, the streaming timeout-refresh, and the terminal finish()
  flush; translation_final/provisional emitted from run_translation
  (translation_processor.py) — finals for single-or-list results,
  provisionals with committed/source snapshots + fresh flag.
- DONE: Dedupe + _simul_active guard semantics preserved (tests)
  tests/test_translation_emission.py (6 tests, no live model): finals emit
  single+list; provisionals REQUIRE _simul_active (base-path buffer =
  untranslated source must not flash); identical consecutive provisionals
  deduped; fresh=True only when _mt_call_count advances; final suppresses
  the provisional in the same batch; state contract unchanged.
- DONE: Event log from a live run round-trips; golden replay still passes
  lc_terminal --event-log over demo_en_30s.wav captured 37 events
  (15 prov/12 final ASR + 10 translation finals) through the full pipeline.
  DisplayAdapter over the golden zh_long_time_frontier.jsonl renders all 4
  final pairs. Golden replays (overlay model + TUI unified) green.
- DONE: Suite green vs baseline; ASR-side emission points verified
  Full suite -p no:randomly: 376 passed / 3 failed / 43 errors. Failure set
  is a strict SUBSET of clean origin/main (identical canary x2 +
  deepgram x1; all 43 errors pre-existing). My change FIXED the 9
  object.__new__-fixture failures the tap exposed (fixture completeness:
  event_tap/_last_asr_prov/_last_mt_prov/processing_error/sep now set,
  mirroring production __init__). NOTE: 6 of those 9 were ALSO failing on
  the integration branch tip (same AttributeError there — carried, never
  fixed upstream-side); 3 (silent-backend watchdog) fail on the integration
  branch due to the local-only heard_speech commit (bf789a7) reading
  self.transcription the upstream fixture fake lacks — pre-existing, NOT
  emission-related, left as-is (upstream code path unaffected).
  Machine note: the qwen3-asr-causal submodule had to be initialized in the
  worktree (git submodule update --init) — fresh worktrees need this.
- FAILED: none

### Summary

Cycle 2 closes the emission gap: main's restructured pipeline now emits the
full caption event stream, live-verified end-to-end (37 events from a real
run), with the dedupe/_simul_active guard contracts under fixture-level
tests. Suite: 376 passed, failure set a strict subset of the origin/main
baseline. Commit 0143f1e on wlk/display-unification. NOT pushed, NOT PR'd —
awaits FO review.

## Stage Report: display-unification (cycle 3 — progress contract)

- DONE: Zero getattr probes / zero private-attribute reads on translation objects in translation_processor.py
  Grep-verified: `grep 'translation\._'` → no hits; the only remaining getattrs are main's pre-existing PUBLIC optional-method lookups (`close` line 20, `finish` line 81 — main's own idiom, untouched) plus `_ProgressReader`'s two public-contract accessors with documented third-party defaults.
- DONE: Zero silent except blocks in the emission path
  The one `except Exception` (translation_processor.py:54) is the sanctioned progress()-raise path: logs once per session naming the backend class and disables provisional drafts (returns None → emission skipped) — verified by test_progress_raise_disables_drafts_with_one_warning (asserts exactly 1 warning, no provisional, loop continues, `_Broken` named).
- DONE: Capability via class attribute (base False, simul True)
  `MlxLlmTranslation.provides_drafts = False`; `MlxLlmTranslationSimul.provides_drafts = True` — matches upstream's class-based routing idiom. The simul `progress()` override is a pure re-expose of existing private state (zero renames); the base default is honest-empty, proven against the REAL base class constructed with warmup=False (test_base_backend_contract_defaults_are_honest).
- DONE: Event semantics identical to cycle 2; goldens byte-identical
  All 6 cycle-2 emission tests pass with unchanged assertions (mock updated to the contract, not the semantics); display suite 65 passed incl. golden replays over zh_long_time_frontier.jsonl (overlay + TUI drained-replay).
- DONE: Suite green vs baseline
  Full suite: 379 passed / 3 failed / 43 errors — failures are exactly the pre-existing canary(2)+deepgram(1) environment set. Cycle-3 initially regressed 3 tests (SimpleNamespace fakes in test_translation_mlx ×2 / test_translation_alignatt lacked event_tap — masked by cycle 2's defensive getattr); fixed with no-op EventTap() mirrors of production init, re-run green.
- DONE: Any deviation and why
  Two documented deviations from the dispatch letter: (1) plain `translation.provides_drafts` attribute reads would crash third-party backends (nllw OnlineTranslation, alignatt sidecar) that flow through run_translation but predate the contract — reads go through `_ProgressReader`, which getattr's the PUBLIC contract names with documented no-draft defaults (no private probes; third-party backends report honestly-empty). (2) The dispatch's "dedupe keyed on d.source_text" would have CHANGED cycle-2 semantics (cycle 2 deduped on draft text alone); the binding "semantics identical" constraint won — dedupe key stays the draft text. Also: `scripts/simul_fixture.py` does not exist on this branch (integration-branch tooling, task-F disposition), so the generation-side gate here is upstream's simul tests (test_translation_mlx.py simul tests: construct MlxLlmTranslationSimul with a test calibration, exercise draft release + failure paths — green) plus the provably-additive engine diff (class attr + one method, process() untouched).

### Summary

Replaced cycle-2's private-attribute reach-through with an explicit display contract: `TranslationProgress` dataclass + `provides_drafts` class attribute + `progress()` method (base default honest-empty; simul pure re-expose), read via a `_ProgressReader` that handles third-party backends and turns progress() failures into one visible warning + session-scoped draft-display disable. Fixed 3 latent test fakes the removed getattr had masked. 65 display tests + 9 emission tests + 30 translation tests green; full suite 379/3/43 with the failure set exactly the pre-existing canary+deepgram baseline. Commit 9bc03f5 on wlk/display-unification; NOT pushed, NOT PR'd — awaits FO review.

## Stage Report: display-unification (cycle 4 — scope change: TUI moves out)

- DONE: tui.py, tests/test_tui_unified.py, and scripts/lc_terminal.py removed from the PR branch
  Captain decision: the terminal client becomes the standalone wlk-tui package
  (entity wlk-tui-package.md). The TUI work is preserved in this branch's
  history (f8110c9's tui.py is the seed); nothing is lost. Note: lc_terminal
  could not stay without tui.py (its whole display path is TuiRenderer/
  MultiRenderer), so both moved out together — this also resolves the open
  "drop lc_terminal from the PR?" question in favor of dropping it.
- DONE: Dangling references cleaned
  overlay.py (2 comments), display_adapter.py (2 doc refs), audio_processor.py
  (1 comment) reworded; test_overlay_model.py's three TuiRenderer tests
  removed; test_overlay_replay.py's zh_ja_fallback test lost its vestigial
  lc_terminal import (the module was exec'd but never used) — assertions
  unchanged and still pass.
- DONE: --event-log moved to the server CLI (parse_args + WhisperLiveKitConfig)
  Without lc_terminal the JSONL log was unreachable in production. The flag
  flows: parse_args -> config.from_namespace -> AudioProcessor tap (which
  already read args.event_log). Verified: parse_args(['--event-log', ...])
  sets it; default None.
- DONE: Ruff clean — the branch adds zero violations
  origin/main passes ruff clean (verified in a detached worktree), so the
  branch must too: 49 violations fixed (auto-fixes + manual: doubled
  docstring, E402 imports, E701/E702 statement splits, F841 unused locals in
  overlay.py/overlay_model.py where the assignment was pure documentation).
  `ruff check .` now passes clean on the branch.
- DONE: Suite vs baseline
  Branch: 3 failed / 373 passed / 13 skipped / 4 errors. Main (same
  interpreter, detached worktree at 363e4f6): 8 failed / 308 passed / 4
  errors. The branch's failure set is a STRICT SUBSET of main's — the 5
  test_qwen3_backend_shims failures on main pass on the branch; the
  canary(2)/deepgram(1) failures and asr_coalescing_pipeline errors(4) are
  identical. Zero new failures. Display/emission/model suites all green.
- FAILED: none

### Summary

Scope change executed: the PR now ships the caption event stream, the display
model, emission wiring, the backend contract, and the overlay view — one
view, view-agnostic model. The terminal renderer's next home is the wlk-tui
package (its seed lives in this branch's history at f8110c9). The --event-log
CLI flag keeps the JSONL log reachable without the dev driver. Ruff-clean,
failure set a strict subset of main's. NOT pushed, NOT PR'd — awaits FO
review. Commit e63c3d4 on wlk/display-unification.

## Stage Report: display-unification (cycle 5 — history rebuild + stacked TUI branch)

- DONE: PR branch history rebuilt without the TUI
  wlk/display-unification = 4 commits on origin/main (9199cc5 model+events,
  980ef9a emission, 1a14f8f progress contract, 0c83284 --event-log flag +
  lint hygiene). Tree verified byte-identical to the pre-rebuild verified
  tree (git diff vs e63c3d4: empty). Old history preserved at
  wlk/display-unification-old (e63c3d4). No TUI appears anywhere in PR
  branch history.
- DONE: TUI on its own stacked branch
  wlk/tui-view = wlk/display-unification + 1 commit (aae6299): tui.py +
  test_tui_unified.py restored from f8110c9, one unused-variable ruff fix.
  Both TUI tests pass (2); full suite 375 passed / 3 failed / 4 errors —
  failure+error set identical to origin/main (canary x2, deepgram,
  ffmpeg coalescing); ruff clean on both branches.
- SKIPPED: none
- FAILED: the dispatched worker run died on a connection error after
  completing the rebuild + branch move; FO completed the remaining steps
  (tui-view branch, suite/ruff verification) directly.

### Summary

The PR branch now carries only what it ships: event stream, display model,
emission wiring, progress contract, --event-log server flag, overlay view.
The terminal view lives on wlk/tui-view, stacked, as the seed for the
wlk-tui package (entity wlk-tui-package.md updated below). Ready for FO
review and push on captain approval.

## Stage Report: display-unification (cycle 6 — view code moves out)

- DONE: PR branch trimmed to the model layer
  Removed from wlk/display-unification (commit 1896443): whisperlivekit/
  overlay.py (AppKit view, no entry point on main), src_buffer.py (view-side
  src-row state machine), overlay_events.py (imported by nothing — dead),
  event_diff.py (stream-diff helper; its three assertions inlined into
  tests/test_caption_events.py as transparent counting logic, one threshold
  fix: fragmentation fires at >= 2x golden finals). tests/test_overlay_model.py
  and tests/test_overlay_replay.py keep only model-level tests; the view/
  src-buffer tests moved to the stacked branch. scripts/replay_canonical_overlay.py
  rewritten as a model-only instrument: drives OverlayDisplayModel directly,
  traces the committed caption line through the hold-drain (verified: the
  golden's full bright chain — 'It reduces bleeding...', 'Dermatologists...
  spots and tattoos.', 'In summary...' — all display, no retype).
- DONE: Stacked branch retains the views
  wlk/tui-view forked at 0c83284, BEFORE the trim, so it already carries
  overlay.py, src_buffer.py, the view-level replay script and the src-buffer
  tests; an accidental duplicate test section was reverted (the interim
  commit dropped). tui.py + test_tui_unified.py from aae6299 unchanged.
- DONE: Verification
  PR branch: 364 passed / 3 failed / 4 errors — failure+error set identical
  to origin/main (canary x2, deepgram, ffmpeg coalescing); ruff clean; zero
  references to overlay/src_buffer/event_diff/overlay_events/AppKit/tui.
  Stacked branch: 375 passed, same failure set, ruff clean.

### Summary

The display PR now ships exactly the semantics layer: caption event stream,
display model, emission wiring, progress contract, --event-log server flag,
model-level replay instrument and tests (+4,163 -7 over 30 files before this
cycle; smaller after the trim). The overlay and terminal views live on
wlk/tui-view (stacked), seeding the wlk-tui package. Ready for FO review
and push on captain approval.

## Stage Report: display-unification (cycle 7 — first-principles rename)

- DONE: overlay_model.py -> caption_display.py; OverlayDisplayModel -> CaptionDisplay
  Rationale recorded in the module docstring: "model" collides with the
  repo's ML-model meaning (model_mapping.py, model_paths.py); "overlay"
  named a view on a view-agnostic component. Commit 513b6fa.
- DONE: display_adapter.py absorbed into caption_display.py; duplicate
  DisplayState name resolved
  The adapter's simple reducer moves in as CaptionLineAccumulator with
  state CaptionLineState (the styled-spans DisplayState keeps its name).
  audio_processor now holds self.caption_lines; test_harness reads it via
  the renamed attribute. Module count reduced by one.
- DONE: Threading contract documented in caption_display.py's module docstring
  Events are forwarded synchronously on the event loop thread; both
  classes are single-threaded from that thread; native views marshal
  state across to their own threads.
- DONE: Full reference sweep clean; docstrings de-scoped
  git grep for OverlayDisplayModel/overlay_model/display_adapter/
  DisplayAdapter: 0 hits. Remaining "overlay" mentions in the diff are in
  pre-existing origin/main docstrings (translation_mlx_llm_mt.py), left
  untouched to keep the diff scoped.
- DONE: Suites + lint + replay verified after rename
  Full suite 364 passed / 3 failed / 4 errors — failure+error set
  identical to origin/main (canary x2, deepgram, ffmpeg coalescing).
  ruff clean. Replay of tests/golden/zh_long_time_frontier.jsonl through
  CaptionDisplay shows the full bright chain (It reduces bleeding... ->
  Dermatologists... spots and tattoos) with no retype. Note: run the
  replay with PYTHONPATH pointing at the worktree; the editable venv
  install resolves whisperlivekit to the main checkout, which predates
  the rename.
- DONE: tui-view note
  wlk/tui-view is now one rename behind (forked at 0c83284); it will be
  rebased onto the renamed PR branch when the wlk-tui package work starts.

### Summary

Final component list (source of truth for the PR description):
whisperlivekit/caption_events.py (CaptionEvent, EventTap, EventLog,
FanOutSink), whisperlivekit/caption_display.py (CaptionDisplay policy
state machine + DisplayState styled spans + CaptionLineAccumulator
stream-level line state), timed_objects.py (TranslationProgress),
emission points in audio_processor.py + translation_processor.py,
provides_drafts/progress() backend contract, --event-log server flag
(parse_args + config). Zero behavior change: all suites return the same
sets as before the rename. NOT pushed; awaiting FO review.

### Feedback Cycles

- Cycle 1 (2026-10-31 maintainer review on PR #449, our head 513b6fa): REJECTED pending fixes.
  (a) `--event-log PATH` never writes anything: `EventLog` collects events in memory and
  nothing calls `save()`, so the flag only grows a list for the whole session.
  (b) `CaptionLineAccumulator` is created for every session even without translation or an
  event log; without translation `committed_transcription` only resets on
  `translation_final`, so it grows until the session ends — the maintainer just bounded
  per-session state with `--retention-seconds` and will not take a second unbounded copy of
  the transcript. (c) Nothing in the server reads `caption_lines` yet (test harness only),
  so ~950 lines plus hot-path work have no consumer. Requested disposition: create the tap
  only when `--event-log` is set or something consumes it, write the JSONL on cleanup, bound
  the accumulator, and either bring the UI wiring into the PR or hold `caption_display.py`
  for the follow-up that uses it. The 2026-11-07 follow-up ping offers the split explicitly:
  the event tap + `--event-log` (created only when enabled, written on cleanup) first, then
  `caption_display.py` together with the UI wiring that consumes it.
  Status: awaiting distinct FO authorization (fix / decline / hold / route for decision)
  before any candidate edit, commit, or reviewer rerun.

## Stage Report: display-unification (cycle 8 — PR-A scope trim, authorized fix)

Authorization: `fix — maintainer findings on PR #449 cycle 1. No scope change. Captain
approved the split.` Disposition performed: reduce the branch to the caption event stream;
`caption_display.py` leaves for PR-B with the UI wiring that consumes it.

- DONE: PR branch trimmed to the event stream
  Removed: `whisperlivekit/caption_display.py` (958 lines), `tests/test_caption_display.py`,
  `tests/test_overlay_replay.py`, `tests/golden/*` (5 files),
  `scripts/replay_canonical_overlay.py`. PR-B's seed is preserved two ways: stacked branch
  `wlk/caption-display` (forked at 513b6fa, the last commit before the trim) and this
  branch's own history.
- DONE: the tap and its sink exist only when `--event-log` asks for them
  `audio_processor.__init__`: `self._event_log = EventLog(path) if args.event_log else None`,
  `self.event_tap = EventTap(sink=self._event_log)` — with the flag unset that is
  `EventTap(sink=None)` and nothing else is allocated. `CaptionLineAccumulator` and
  `audio_processor.caption_lines` are gone; `FanOutSink` went with them (once the
  accumulator left it had no second sink).
- DONE: `--event-log` appends one JSONL line per event, flushed per line
  `EventLog` is a file sink now: opens `PATH` in append mode, writes `json.dumps(...) + "\n"`
  and flushes inside `emit()`. No in-memory list, no `save()`, no `load()` (the goldens that
  used `load()` moved to PR-B and nothing else needed it). A write error disables the log
  with one warning instead of ending a live session; the handle is closed in `cleanup()`
  after the producer tasks have stopped.
- DONE: `test_harness.py`'s `TestState.display` hunk dropped
  The `dataclasses` import, the `display` field and the accumulator snapshot in
  `_collect_results` are gone; the file is now byte-identical to origin/main.
- DONE: `--event-log` documented
  `parse_args` help (append, written as each event is emitted, sessions sharing one PATH
  interleave lines) plus a `## Caption event log` section in `docs/configuration.md`
  (line shape, append mode, the interleaving caveat, off-by-default, write-failure
  behaviour) and a row in the Common settings table.
- DONE: `test_caption_events.py` / `test_translation_emission.py` kept, adapted
  The accumulator and stream-comparison tests left with the display module and goldens;
  what remains covers the event payload, tap no-op/forwarding/blank-text filtering, and the
  `EventLog` sink (per-event append, append across restarts, emit-after-close,
  write-error degradation). `test_translation_emission.py` used the old in-memory
  `EventLog()` as a recording sink; that is now a local `_Recorder` test double — its
  assertions are unchanged.

### Proof (exactly as run; no overclaim)

- Targeted selection PASSED:
  `pytest -q tests/test_caption_events.py tests/test_translation_emission.py tests/test_backends.py -p no:randomly`
  → **51 passed in 3.45s**.
- `ruff check .` → **clean** (rc=0, "All checks passed!").
- Append-per-event proven **hermetically**:
  `tests/test_caption_events.py::TestEventLog::test_two_events_are_two_lines_before_close`
  constructs the sink on a `tmp_path`, emits two events, and reads the file **while the sink
  is still open**, asserting two newline-terminated JSONL lines. That is the maintainer's
  property — written as emitted, not save-on-cleanup — proven without any live session.
- Live `--event-log` session run: **NOT performed.** This agent sandbox has no microphone,
  so a live run is impossible here. Do not read this report as claiming one. If a live check
  is wanted, the FO must run it on a machine with mic access
  (`wlk serve --event-log /tmp/ev.jsonl ...` and watch the file grow).
- Full suite: **cannot serve as evidence here.** 4 tests in
  `tests/test_asr_coalescing_pipeline.py` error during setup with
  `RuntimeError: Failed to download any test samples` (`whisperlivekit/test_data.py:311`);
  this sandbox cannot fetch the samples, so those tests sit in network timeouts. These
  errors are environmental and pre-existing, not PR-A regressions.
- Supplementary context (recorded earlier in this cycle against 7394a9b, i.e. before the
  test-only commit 80a040b; NOT re-run against the final tree): branch
  `3 failed / 331 passed / 12 skipped / 4 errors` vs a detached worktree at the merge-base
  363e4f6 with the same interpreter `3 failed / 314 passed / 12 skipped / 4 errors`. The
  failure+error set is identical (canary x2, deepgram, the 4 sample-download errors) and the
  17-test delta is exactly `tests/test_caption_events.py` + `tests/test_translation_emission.py`.
  Treat the targeted selection above as the binding evidence; this line is context only.

### Branch state

- `wlk/display-unification` tip **80a040b** (7394a9b = the trim, 80a040b = the hermetic
  append-per-event test). Worktree clean. NOT pushed; PR #449 not touched — FO publishes.
- PR-B seed branch `wlk/caption-display` created at 513b6fa (pre-trim), not pushed.

- FAILED: none

### Summary

Cycle 8 executes the authorized fix. The branch now ships one thing: the caption event
stream — `caption_events.py` (event payload, no-op-able `EventTap`, append-and-flush JSONL
`EventLog`), the emission points in `audio_processor.py` / `translation_processor.py`, the
`provides_drafts` + `progress()` backend contract, and the documented `--event-log` flag.
Nothing allocates per-session display state any more, and `--event-log` writes every event
to disk as it happens instead of growing a list that nothing saved. The display model and
its goldens/replay tests are parked on `wlk/caption-display` for PR-B with the UI wiring
that consumes them. Proof is the targeted test selection (51 passed), ruff clean, and the
hermetic unclosed-sink test; no live run was performed because the sandbox has no mic.

## Stage Report: implementation (cycle 1 — entity rescope to PR #449)

Authorization: `rescope — captain approved narrowing entity 6y to PR #449 only (the caption
event stream). This is an ENTITY BODY edit, no code work.`

- DONE: `## Work` rewritten to the PR #449 scope
  Four items grounded in the branch at 80a040b: `caption_events.py` (typed payload, no-op
  `EventTap`, append-and-flush JSONL `EventLog`); emission points `audio_processor.py`:615,
  662, 797, 804 and `translation_processor.py`:120, 140; `TranslationProgress` +
  `provides_drafts`/`progress()` read via `_ProgressReader`; `--event-log` through
  `parse_args.py` -> `WhisperLiveKitConfig.event_log` and `docs/configuration.md`.
- DONE: `## Acceptance` replaced with AC-1..AC-5 in the bold-line + "Verified by:" shape
  Each names a check reproducible outside the body that can fail; the six test ids cited in
  AC-1/AC-2/AC-4 collect and pass (17 passed, `pytest -q tests/test_caption_events.py
  tests/test_translation_emission.py`), and AC-1/AC-3's `git grep` claims were run.
- DONE: `## End value` added (one line)
  Display behavior and the event stream stop being entangled with the MT layer, and a
  downstream consumer can be built on a recorded stream.
- DONE: display-model scope kept out; history untouched
  `git diff` touches only the span between `## Context` and `## Notes`; frontmatter, every
  `## Stage Report` and `### Feedback Cycles` are byte-identical. No code file, no code
  branch push, PR #449 untouched.
- FAILED: none

### Summary

Entity 6y now describes what PR #449 actually ships — the caption event stream and the
backend draft contract — instead of the display-work unification it was filed for. The
display half is no longer described here (entity `wlk-caption-display` / 5m owns it).
Residual: the H1 ("Task B (A2) — unify WLK display semantics...") and the `## Context` and
`## Notes` sections still narrate the pre-split display scope; they were outside the
authorized edit list, so they were left byte-identical rather than silently rewritten.

## Stage Report: implementation (cycle 2 — H1/Context/Notes rescope + AC-1 behavioural proof)

Authorization: `complete the rescope of entity 6y to PR #449 only (captain approved).
State-only edit, three enumerated items; nothing outside them.` One code test was
added under item 3's "If no such test exists, add it ... and name it".

- DONE: H1 rewritten to the event-stream scope
  Now `# Caption event stream for PR #449 (PR-A) — typed caption events and --event-log`
  (was `# Task B (A2) — unify WLK display semantics behind one caption display model`).
  The pre-split display task is no longer named as this entity's subject.
- DONE: "## Context" and "## Notes" rewritten to the event-stream work only
  Context now describes what #449 ships (typed payload, `EventTap` emission points in
  `audio_processor.py` / `translation_processor.py`, `--event-log` JSONL sink,
  `TranslationProgress` + `provides_drafts`/`progress()` via `_ProgressReader`, `FrontData`
  untouched) and carries the split history in one sentence. Notes now names the parked
  PR-B material — branch `wlk/caption-display` @ `513b6fa`, the files cut in `7394a9b` —
  and its owner entity `wlk-caption-display` (`5m`); the pre-split "B first, then D+G"
  review sequence and the overlay/TUI-as-views narration are gone.
- DONE: AC-1's presence grep replaced with a behavioural clause
  Was `git grep -n 'event_tap.transcription_' whisperlivekit/audio_processor.py`. Now names
  `tests/test_caption_events.py::TestEventTap::test_one_utterance_emits_the_typed_sequence_in_order`
  (one utterance through the tap; asserts the four types in emission order, each event's
  text/`audio_t`/emit-time `t`, and both provisionals' `committed`/`source`/`fresh`) plus
  the two `tests/test_translation_emission.py` loop tests, with one clause per test naming
  the change that makes it fail. A scope note records what is NOT behaviourally pinned:
  the four ASR-side call sites are exercised by the pipeline suites (a tap is attached,
  emission must not disturb the loop) but no test asserts the sequence they emit.
- DONE: the test added and run
  `tests/test_caption_events.py::TestEventTap::test_one_utterance_emits_the_typed_sequence_in_order`
  — 6 events, assertion is the exact `(type, text, audio_t)` list plus the provisional
  `(committed, source, fresh)` list plus `t`. Falsified by construction: re-running the
  test body against an `EventTap.translation_provisional` that drops `source` raises
  `AssertionError` at the payload assertion (script `/tmp/falsify_check.py`, run, exit 0
  printing "RED as expected"). A tap that reorders calls or stops forwarding text fails
  the first assertion the same way.
- FAILED: none

### Proof (exactly as run)

- `pytest -q tests/test_caption_events.py -p no:randomly` → **9 passed** (8 before; +1 new).
- `pytest -q tests/test_caption_events.py tests/test_translation_emission.py tests/test_backends.py
  -p no:randomly` → **52 passed in 34.44s** (51 before; +1 new).
- `ruff check tests/test_caption_events.py whisperlivekit/` → **All checks passed!**
- Full suite: not run this cycle — unchanged from cycle 8's reason (the 4
  `test_asr_coalescing_pipeline` setup errors are this sandbox's inability to download test
  samples, pre-existing and environmental). Treat the targeted selection as binding.

### Branch state

- Code: commit **32c38ac** on `wlk/display-unification` (one test file, `tests/test_caption_events.py`).
  Not pushed; PR #449 untouched, as instructed.
- State: this file only. Nothing outside H1 / Context / AC-1 / Notes changed — `git diff`
  hunk headers are `@@ -9`, `@@ -13`, `@@ -64`, `@@ -101`; frontmatter, Work, AC-2..AC-5,
  End value and every prior Stage Report are byte-identical.

### Summary

Entity 6y now reads as the PR #449 event-stream entity throughout: the title, the context
and the notes no longer describe the display unification that moved to `wlk-caption-display`
(`5m`, parked at `wlk/caption-display` @ `513b6fa`), and AC-1's unfalsifiable presence grep
is replaced by a test that drives one utterance through the tap and asserts the emitted
sequence. The only code change is that one test; it passes, ruff is clean, and its
falsifiability was demonstrated by breaking the tap's payload and watching it go red.
Residual: no behavioural test asserts that the four ASR-side call sites in
`audio_processor.py` emit at their documented points — the AC records that gap rather
than hiding it behind a grep.

## Stage Report: implementation (cycle 3 — AC-1 ASR-side emission proof)

Authorization: `close the AC-1 evidence gap — the pipeline emission points are not
covered by any test. Do not change AC-1's wording; the acceptance criteria stay as they
are.` Only the AC-1 "Verified by:" clause was edited; the bold AC statement is byte-identical.

- DONE: close the AC-1 evidence gap — the pipeline emission points are not covered by any test
  `tests/test_asr_emission.py` (new) pins all four ASR-side call sites; the AC-1 clause
  that recorded the gap ("do not assert the emitted sequence") was replaced by that test id,
  so the entity no longer claims an open gap.
- DONE: add the test that drives the real ASR-side pipeline path with a tap on a recording sink
  `tests/test_asr_emission.py::test_one_utterance_emits_the_transcription_sequence` runs
  `AudioProcessor.transcription_processor` end to end (scripted streaming backend shaped like
  LocalAgreement's tail buffer, `processor.event_tap = EventTap(sink=_Recorder())`; no model, no
  network) and asserts the exact `(type, text, audio_t)` list:
  `final "今天我們"@0.25`, `provisional "討論"@0.25`, `provisional "討論皮膚科"@0.4`,
  `final "皮膚科。"@0.75` — i.e. chunk-path committed segment + rolling tail
  (`audio_processor.py`:797/804), the periodic buffer refresh on the loop's 0.5 s queue timeout
  (:662, driven by `decode_between_chunks()`), and the terminal flush (:615, driven by SENTINEL).
  Harness shape follows `tests/test_pause_segmentation.py::_boundary_processor` /
  `tests/test_asr_coalescing_boundaries.py::_processor_for` (local `_processor_for`, tap injected).
- DONE: prove the test can fail — two mutations run, both red, file restored byte-for-byte
  A (removal): replaced the terminal-flush `self.event_tap.transcription_final(...)` block at
  `audio_processor.py`:614-618 with `pass` → FAILED, "Right contains one more item:
  ('transcription_final', '皮膚科。', 0.75)".
  B (reorder): swapped the chunk-path final/provisional blocks at :795-807 → FAILED, "At index 0
  diff: ('transcription_provisional', '討論', 0.25) != ('transcription_final', '今天我們', 0.25)".
  After each: `git checkout -- whisperlivekit/audio_processor.py`,
  `shasum -a 256 -c` → `whisperlivekit/audio_processor.py: OK`, `git status --porcelain` shows only
  the new test file; re-run green (1 passed). Tree left unmodified.
- DONE: update AC-1's "Verified by:" clause to name the new test id (AC wording unchanged)
  Added the clause naming `tests/test_asr_emission.py::test_one_utterance_emits_the_transcription_sequence`
  with the change that makes it fail (a call site stops emitting or reorders) and the two
  observed red mutations; the scope note that said no test asserts the sequence is gone.
  `git diff` touches only that span (hunk `@@ -76,14 +76,20 @@`); AC-1's bold statement,
  AC-2..AC-5, frontmatter and every prior Stage Report are byte-identical.
- DONE: keep the existing tests green, ruff clean
  87 passed, 1 skipped on `tests/test_asr_emission.py tests/test_caption_events.py
  tests/test_translation_emission.py tests/test_pause_segmentation.py
  tests/test_asr_coalescing_boundaries.py tests/test_asr_coalescing.py tests/test_backends.py`;
  `ruff check tests/test_asr_emission.py whisperlivekit/` → All checks passed.
- DONE: append the stage report, commit path-scoped, push the state branch
  This section; state commit path-scoped to this entity, then pushed to `dev-state`.
- FAILED: none

### Proof (exactly as run)

Invocation note (no hidden dependency): the worktree `.venv` has no pytest, so runs use
`/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/pytest` from the worktree root; verified it
imports the worktree package (`"wlk-display-unification" in whisperlivekit.__file__`), and
`uv run` was reverted because it rewrote `uv.lock` (left clean).

- New test green: `pytest -q tests/test_asr_emission.py -p no:randomly` → **1 passed** (3.27s);
  5 consecutive runs without `-p no:randomly` → 1 passed each (1.68-2.19s), so the 0.5 s
  timeout refresh is not flaky.
- Mutation A / B red, restore, green: results quoted per item above; baseline
  `shasum -a 256 whisperlivekit/audio_processor.py` recorded before mutating and re-verified
  with `-c` after each restore.
- Targeted selection: **87 passed, 1 skipped in 3.69s** (was 86 passed, 1 skipped before this
  cycle's test).
- Full suite: not re-run — the 4 `test_asr_coalescing_pipeline` setup errors are this sandbox's
  inability to download test samples (pre-existing, environmental, cycle 8's reason). Treat the
  targeted selection as binding.

### Branch state

- Code: commit **633e35c** on `wlk/display-unification` (one new test file). Not pushed;
  PR #449 untouched.
- State: this file only — AC-1's "Verified by:" clause plus this report.

### Summary

The AC-1 gap is closed behaviourally: one test drives the real ASR-side processor loop with a
recording sink and asserts the exact transcription event sequence from all four documented call
sites, including the periodic refresh that only fires on the loop's queue timeout. Falsifiability
is demonstrated by two run mutations (a removal and a reorder) that both turn the test red, with
the source restored byte-for-byte and re-verified by hash. Residual: the test covers the
transcription call sites only; the translation side keeps its own loop tests.

- Cycle 9 (2026-11-08): PR-A published. Branch `wlk/display-unification` force-pushed to the
  fork branch `spacedock-ensign/caption-display` (513b6fa -> db143d3, 10 commits, rebased on
  ada82d4), PR #449 body replaced with the event-stream scope, and the split reply posted
  (issuecomment-6731795843). Push needed SSH plus an explicit lease: the https credential
  lacks `workflow` scope because the rebase carries main's .github/workflows/ci.yml change,
  and the first force-with-lease was refused on a stale remote-tracking ref. Live run evidence
  in the PR: the log grew during the session (285 -> 3069 bytes before finish, 4097 after, 34
  lines, transcription_final only because the backend commits without drafts and translation
  was off).
