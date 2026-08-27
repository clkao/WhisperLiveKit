# Issue 2 — Push translation events to display sinks instead of polling `TestState`

> Paste this body into a GitHub issue on QuentinFuxa/WhisperLiveKit.
> ASD-STE100. No internal vocabulary. This issue depends on Issue 1 (the tagged return).

## Summary

The display sinks poll a shared state object on each update. Each sink must know every field on that object. When a new field is added, every sink must learn to read it. This session, a new field was added but no sink read it. The data was lost.

This issue proposes a push contract. The processor emits typed events. The sinks subscribe. A new field reaches every sink by default.

## The problem

The audio processor writes to a shared `TestState` object. The display sinks (the web client, the terminal, the overlay) read that object on each update. Each sink diffs the fields it knows about.

This model has a failure mode. When the processor adds a new field, each sink must add code to read it. If a sink does not, the field is lost. The sink did not fail. It did not know the field existed.

This session, the processor wrote a provisional translation to `state.buffer_translation`. The terminal sink and the overlay sink did not read that field. The provisional translation never reached the display. The user saw no text during speech.

The root cause is the contract, not the sinks. A pull contract makes each sink responsible for every field. A push contract makes the processor responsible for delivery.

## The proposed change

The processor emits typed events. The sinks subscribe to the events they want. The processor does not write to a shared state for the display path.

The events:

- `Partial(text)` — the live source text changed.
- `Final(segments)` — a source utterance was committed.
- `Translation(segments)` — the translation for a committed utterance arrived.
- `Preview(text)` — a provisional translation is available during speech.

A new display field becomes a new event. Every sink that subscribes to the event receives it. No sink must learn a new field name. The loss this session becomes impossible.

## Why this depends on Issue 1

The `Preview` event carries a provisional draft. The processor can not emit a `Preview` event until it can tell a provisional draft from "no work". Issue 1 tags the return value so the processor can tell the two apart. Land Issue 1 first.

## Why an issue, not a PR

This change touches the display path for every sink. The web client, the terminal, and the overlay all change. We open this issue to agree on the event set before we send code.

## The trade-off

A push contract is more work for the processor. It must emit events instead of writing to a state object. The state object can stay for the cases that need a snapshot (the test harness, the metrics). The display path moves to events.

The win is that a new field reaches every sink by default. The cost is one event per field. The session showed that the pull contract loses fields. The push contract does not.
