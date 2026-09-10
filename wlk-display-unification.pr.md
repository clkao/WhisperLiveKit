feat: caption display semantics and a standardized caption event stream

## Summary

This PR adds a caption event stream and a caption display policy. It changes
nothing about what the web UI shows today. It creates the layer that makes
correct, testable caption display possible for every consumer, on every
backend.

### Before: how captions work without this PR

WhisperLiveKit produces caption state, and every consumer renders it
directly:

- The web UI renders `FrontData` fields as they arrive. `buffer_translation`
  is a single string with no metadata. For translation backends that do not
  produce provisional translations, that string holds the untranslated source
  queue, so raw source appears under the translation label until the real
  translation replaces it.
- Every state update replaces the translation buffer wholesale. If one
  translation covers several sentences, the whole text is replaced when the
  next update lands. There is no notion of a finished sentence, so nothing
  paces what the reader sees.
- When a translation is corrected mid-sentence, the corrected text replaces
  the old text directly in the UI. Words the reader already saw can vanish
  and reappear.
- There is no way to test any of this. Display behavior cannot be captured,
  replayed, or compared; every fix is verified by watching a live session.

The root cause is the same for all four: caption state has no semantics. A
string in a buffer cannot say whether it is a draft or a final, which
sentence it belongs to, or what changed since the last update.

### After: what this PR enables, through what

Through what, in one line: the pipeline emits a typed caption event stream; a
display policy turns events into a display state; consumers render the state.

- `caption_events.py` defines four events (transcription and translation,
  each provisional or final), with the text, the committed and full source it
  was produced against, and whether a translation model call produced it. A
  tap in `AudioProcessor` fans out to sinks. `--event-log` records the stream
  as JSONL, so display behavior becomes capturable and replayable.
- `caption_display.py` defines `CaptionDisplay`, the policy state machine.
  It turns events into `DisplayState` under five rules: captions split at
  sentence ends (`.` `!` `?` and the CJK marks `。！？`); a finished sentence
  is always shown and held for a minimum time, even when sentences finish in
  quick succession; a sentence the viewer is watching flips to final style in
  place, never cleared and retyped; final text never visibly shrinks or
  rewords; and per-sentence events mean multi-sentence translations are shown
  sentence by sentence instead of being replaced wholesale.
- A small backend contract: translation backends declare `provides_drafts`
  and a `progress()` method reporting how far translation has progressed in
  the source. Backends without provisional translation (NLLB, the AlignAtt
  sidecar) need no changes; their buffers can no longer appear as
  translation drafts because the draft path is unreachable for them, not
  because a view guards against it.
- Emission rules live where events are created, so every consumer inherits
  them: the same provisional text is never emitted twice in a row, and a
  `progress()` failure is logged once and disables draft display rather than
  showing a wrong value.

What this enables that was impossible before:

1. A recorded caption stream can be replayed through any consumer to check
   exactly what a viewer would have seen. Five recorded streams ship with
   the PR as test fixtures.
2. Display rules have regression tests. Each rule has a test that fails when
   the rule is broken.
3. Any backend gets correct display semantics by conforming to a two-method
   contract, with honest defaults.
4. New caption consumers (a terminal view, a native overlay, the web UI in a
   later step) can be built on the same policy instead of reimplementing it.

Threading: events arrive on the event-loop thread through the tap;
`CaptionDisplay` is single-threaded, and views that render elsewhere receive
state snapshots.

## User impact

- The web UI, FrontData, and `results_formatter` are unchanged. The event
  stream runs beside them; the JSONL log is written only when `--event-log`
  is passed.
- The simultaneous MLX engine exposes state it already tracks. `process()`
  semantics are unchanged. The base MLX engine gains the default contract
  only.
- Per-event cost is one dataclass append plus, when enabled, a JSONL line.
  The in-memory consumer is always present; the log sink exists only when
  flagged.

## Validation

- New tests: `test_caption_display.py` (the five display rules),
  `test_caption_events.py` (stream contract and stream comparison),
  `test_translation_emission.py` (emission rules, no live model). Each rule
  has a test that fails when the rule is broken.
- Replay evidence: a recorded zh→en simultaneous session
  (`tests/golden/zh_long_time_frontier.jsonl`) replayed through
  `CaptionDisplay` shows every finished sentence, in order, each shown once.
  The same stream shows the before-state failures: a multi-sentence final
  whose tail sentences were dropped, and a retype on promotion.
- `uv run pytest -q tests/ --ignore=tests/test_pipeline.py`: same result as
  `main` apart from the new tests. The pre-existing canary, deepgram, and
  ffmpeg-dependent failures are unchanged, verified by comparison.
- Pipeline test on Apple Silicon with the MLX backend
  (`mlx-community/Hy-MT2-1.8B-8bit`, Qwen3 ASR): a live session emitted the
  full event stream, and the recorded log replays through the display
  policy.
- `ruff check .`: passes on this branch; `main` also passes.

## Checklist

- [x] I searched for an existing issue or discussion and linked it when
      relevant. (The issue opened before this PR will be linked.)
- [x] I added or updated tests for behavior changes.
- [ ] I updated documentation for user-facing changes. (A section for
      `--event-log` will be added.)
- [x] I ran `ruff check .`.
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or
      private data.
