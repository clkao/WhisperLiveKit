---
title: native macOS overlay client (always-on-top NSWindow, ported from livecaption)
status: backlog
source: livecaption port + this session's work
id: gzagg3hhtajwdg6wbwq1mgtx
---
# Native macOS overlay client for WhisperLiveKit

## Goal

Port the livecaption native macOS caption overlay (borderless always-on-top
NSWindow, ported from `livecaption/overlay.py`) into WLK as a client of the
in-process stream. This is the presentation-overlay product layer: a caption
window that floats over Keynote/fullscreen apps, with a min-hold queue so fast
utterances don't flash.

## What ships

- `whisperlivekit/overlay.py` — the `OverlayRenderer` (ported from livecaption,
  self-contained: pyobjc + stdlib, no livecaption imports). Borderless
  NSWindow, level above Keynote Play, draggable, transparent, ignores mouse.
  Three fields: finalized zh (top), EN translation (middle, large), live
  partial (bottom, dimmer). Min-hold caption queue (finalized EN captions
  enqueue; a daemon releases the newest after MIN_HOLD_SEC). Sentence
  splitting for long multi-sentence translations.
- `scripts/lc_terminal.py` — the in-process driver: WLK `TestHarness` asyncio
  loop in a worker thread; the overlay NSWindow run loop on the main thread
  (pyobjc requires this); the `on_update` callback marshals WLK stream state
  to the overlay fields. Terminal mode (`--overlay` off) prints to stdout.

## Acceptance criteria

- `python scripts/lc_terminal.py --source mic --overlay` shows a borderless
  always-on-top caption window over fullscreen apps.
- Live zh partials stream (rolling ASR buffer -> partial line); clean zh +
  en translation appear at each utterance boundary (two-pass ASR + MT).
- `--overlay-hold <sec>` controls the min time a finalized EN caption stays
  before replacement (no flash on fast utterances).
- The overlay runs on the main thread; the WLK pipeline runs in a worker
  thread; Ctrl-C stops cleanly.
- The `pyobjc` deps are isolated (an `[overlay]` extra, like livecaption).

## Notes

The overlay is a CLIENT of the WLK stream, not a backend — it consumes the
same `on_update(TestState)` callback the terminal sink does. It does not touch
the ASR/MT pipeline. The `lc_terminal.py` driver is the demo; a future task
could ship it as a `wlk overlay` subcommand.

The pyobjc deps: pyobjc-framework-Cocoa, pyobjc-framework-Quartz (the Vision/
NaturalLanguage ones are only for the screen-OCR hotword loop, which is a
separate task). The overlay needs a real terminal with mic TCC for
`--source mic` (Terminal.app, not the sandbox).
