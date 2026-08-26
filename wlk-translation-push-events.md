---
title: "WLK translation: push events to display sinks instead of pulling TestState"
status: backlog
source: architecture — session finding from the Apple-Silicon port (the provisional-loss bug)
score: 0.5
id: 1c05jaab4vbzknwkv4y2qarp
---

The display sinks (the web client, the terminal, the overlay) read `TestState` fields
and diff them on each update. Each sink must know every field; adding a field means
updating every sink. This session, `buffer_translation` existed but neither the
terminal nor the overlay sink read it, so the provisional was lost a second time
(after the producer guard dropped it).

A push-event contract is the alternative: the processor emits `partial`, `final`,
`translation`, `preview` events; sinks subscribe. The provisional-loss becomes
impossible — the processor emits a `preview` event and every sink receives it. No
sink needs to know `buffer_translation` exists.

This is the model the livecaption prototype uses (the `Renderer` contract:
`partial/final/translation/preview`). It was ported into the WLK terminal/overlay
renderers, but the WLK `audio_processor` -> `TestState` -> sink path is pull, so the
push-contract renderers were adapted to a pull source and the adaptation dropped a
field.

## Acceptance criteria

- AC-1: The processor emits typed events (Partial, Final, Translation, Preview) that
  sinks subscribe to, instead of writing to a shared `TestState` that sinks poll.
- AC-2: A new display field (e.g. a provisional translation) reaches every sink by
  default; no sink-specific wiring is needed.
- AC-3: The existing web client still works (it subscribes to the events; the
  WebSocket serializes them).

## Out of scope

- The tagged-return task (separate task: wlk-translation-contract-tag-return). That
  task is the producer side; this task is the delivery side. Land the tag first.

## Dependencies

- Upstream-incompatible. Land as a WLK issue first, not a direct PR. The issue draft
  is at /Users/clkao/git/asr/_work/wlk_issue_push_events.md.
- Depends on wlk-translation-contract-tag-return (the tag makes the events
  unambiguous).
