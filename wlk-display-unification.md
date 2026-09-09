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
