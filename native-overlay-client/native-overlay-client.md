---
id: gzagg3hhtajwdg6wbwq1mgtx
title: native macOS overlay client (always-on-top NSWindow)
status: backlog
source: WhisperLiveKit Apple-Silicon backend work
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

# Native macOS overlay client

## Goal

Add a native macOS caption window to WhisperLiveKit. The window floats over fullscreen apps. The window shows the live ASR partial, the finalized source text, and the translation. A min-hold queue stops fast utterances from flashing.

## What ships

- `whisperlivekit/overlay.py`. The `OverlayRenderer` class makes a borderless NSWindow. The window level is above Keynote Play. The window is draggable, transparent, and ignores mouse events. The window has three text fields: the finalized source text, the translation, and the live partial. The min-hold queue holds a finalized translation for a set time before it replaces the current one.
- `scripts/lc_terminal.py`. The driver runs the WhisperLiveKit `TestHarness` loop in a worker thread. The driver runs the NSWindow run loop on the main thread. The `on_update` callback sends the stream state to the overlay fields. The driver has a terminal mode that prints to stdout when the overlay is off.
- The `pyobjc` dependencies are isolated in an `[overlay]` extra.

## Acceptance criteria

- Run `python scripts/lc_terminal.py --source mic --overlay`. The command shows a borderless always-on-top caption window over fullscreen apps.
- The live source partial streams to the partial line. The clean source text and the translation appear at each utterance boundary.
- The `--overlay-hold` flag sets the minimum time a finalized translation stays before replacement. Fast utterances do not flash.
- The overlay runs on the main thread. The WhisperLiveKit pipeline runs in a worker thread. Ctrl-C stops the process cleanly.

## Notes

The overlay is a client of the WhisperLiveKit stream. The overlay consumes the same `on_update` callback as the terminal sink. The overlay does not touch the ASR or MT pipeline. The `--source mic` flag needs a real terminal with mic TCC. Use Terminal.app, not the sandbox.
