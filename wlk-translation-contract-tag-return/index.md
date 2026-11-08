---
title: "WLK translation contract: tag the process() return instead of overloading None"
status: backlog
source: architecture — session finding from the Apple-Silicon port (the provisional-loss bug)
score: 0.6
id: h730gcxpw0qce6c849fypwrx
---

The translation backend `process()` method returns `(Optional[Translation], TimedText)`.
`None` for the first element means two different things:
  1. Nothing happened (no closed segment, no running partial).
  2. A provisional draft was produced; read the buffer (simul MT).

The `audio_processor.py` guard `if new_translation is not None:` treats both cases the
same and drops the buffer in case 2. This lost the simultaneous-MT provisional this
session (AC-2 failed live, unit tests passed).

Tag the return so the two cases are explicit:
  - `Final(translation, buffer)` — a closed segment was translated.
  - `Provisional(buffer)` — an in-progress draft; show it, do not commit it.
  - `Idle` — nothing to emit.

The processor matches on the tag, not on "is the translation None". The guard bug
becomes impossible.

## Acceptance criteria

- AC-1: `process()` returns a tagged result (Final/Provisional/Idle), not a tuple
  where None is overloaded.
- AC-2: `audio_processor.py` matches on the tag and forwards the buffer for
  Provisional (the current guard drops it).
- AC-3: The existing backends (nllb, mlx-llm-mt) return the same shape under the new
  contract (Final for closed segments, Provisional for the running partial, Idle
  otherwise).
- AC-4: The simultaneous-MT provisional reaches the display (the
  `provisional-before-final` benchmark metric is True).

## Out of scope

- The push-events refactor (separate task: wlk-translation-push-events).
- The display sinks (they consume the state; this task is the producer contract).

## Dependencies

- This is an upstream-incompatible contract change. Land as a WLK issue first, not a
  direct PR. The issue draft is at /Users/clkao/git/asr/_work/wlk_issue_tag_return.md.
