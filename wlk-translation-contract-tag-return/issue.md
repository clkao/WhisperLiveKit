# Issue 1 — The translation buffer is dropped when `process()` returns no finalized translation

> Paste this body into a GitHub issue on QuentinFuxa/WhisperLiveKit.
> ASD-STE100. No internal vocabulary.

## Summary

The audio processor drops the translation buffer when a translation backend returns a buffer with no finalized translation. The backend contract uses `None` for the first element of the return tuple to mean two different things. This overload hides the provisional translation that a backend produces during speech.

## The problem

A translation backend implements `process()`. The method returns a tuple: `(Optional[Translation], TimedText)`. The first element is the finalized translation. The second element is the running buffer.

The first element is `None` in two cases:

1. The backend has no work to do.
2. The backend produced a provisional draft. The draft is in the buffer.

The audio processor does not tell these two cases apart. It keeps the buffer only when the first element is not `None` (`audio_processor.py`, line 920):

```python
if new_translation is not None:
    async with self.lock:
        self.state.new_translation.append(new_translation)
        self.state.new_translation_buffer = new_translation_buffer
```

When the first element is `None`, the processor drops the buffer. A backend that puts a provisional draft in the buffer loses it here.

## Steps to reproduce

1. Run a translation backend that returns a provisional draft in the buffer with `None` for the translation.
2. Feed audio to the pipeline.
3. Read `state.buffer_translation` on each update.

## Expected result

`state.buffer_translation` contains the provisional draft during speech.

## Actual result

`state.buffer_translation` stays empty. The provisional draft is dropped at line 920.

## The root cause

The `None` value is overloaded. The processor can not tell "no work" from "provisional draft in the buffer". The `if new_translation is not None:` guard treats both cases the same.

The base `mlx-llm-mt` backend also returns `None` with a buffer for the running partial (`translation_mlx_llm_mt.py`, line 271). The guard drops that buffer too. No one noticed because the base backend puts the untranslated source text in the buffer, not a provisional translation.

## The proposed change

Tag the return value so the two cases are explicit. Replace the `None` overload with a typed result:

- `Final(translation, buffer)` — a closed segment was translated.
- `Provisional(buffer)` — an in-progress draft. Show it. Do not commit it.
- `Idle` — nothing to emit.

The processor matches on the tag. It does not test `None`. The guard bug becomes impossible.

This change is a contract change. The existing backends must return the new shape. The processor must match on the tag. The display sinks read `state.buffer_translation` for the provisional.

## Why an issue, not a PR

This change touches the translation contract. All backends and the audio processor change together. We open this issue to agree on the contract before we send code.
