---
id: sd-terminal-cli-stats
title: "terminal CLI with live stats and latency readout"
status: backlog
source: prototype — pure terminal output before the overlay
started:
completed:
verdict:
score: 0.8
worktree:
issue:
pr:
---

# Terminal CLI with live stats and latency readout

## Problem

The prototype runs in two output modes: a native macOS overlay (always-on-top
NSWindow) and a terminal printout. The terminal printout today is plain text
with no instrumentation. For calibration and A/B measurement (with and without
simultaneous MT), the operator needs live stats in the terminal: ASR latency,
MT latency, MLX memory, and commit/emit counts. The overlay has no status line
of its own, so the terminal is the only place to show these during a live run.

## Proposed approach

Improve `scripts/lc_terminal.py` to print a live status line to stderr on a 1s
timer. The status line shows:

- ASR EWMA latency (seconds): the time from audio in to committed text.
- MT EWMA latency (seconds): the time from committed text to translated text.
- MLX active/cache/peak memory (GB).
- Commit count and emit count (tokens committed / translations emitted).

The status line uses carriage-return overwrite (no scroll) so it stays at the
bottom of the terminal. The caption text scrolls above it. A `--stats` flag
enables the status line; it is off by default to keep the output clean.

The simplest alternative — log stats to a file only — is rejected: the
operator needs live visibility during a live presentation to catch regressions.

## Risk evidence

The latency EWMA and MLX memory readout already work in livecaption's `render.py`
and `--mem` flag. The work is porting that readout to the WLK terminal driver.
No new mechanism; the risk is format only.

## Expected surface and tolerance

Estimate: +80 net LOC across 1 file (`scripts/lc_terminal.py`), tolerance ±20.
Semantics this may change: the terminal output format (new `--stats` flag, new
stderr status line). No change to the WS protocol or the overlay.

## Acceptance criteria

**AC-1 — The terminal CLI prints a live status line when `--stats` is set.**
Verified by: run `python scripts/lc_terminal.py --stats --backend mlx-qwen3-asr
--language zh`; the stderr shows a line that updates every second with ASR
latency, MT latency, and MLX memory.

**AC-2 — The status line does not scroll the caption text.**
Verified by: the caption text appears above the status line; the status line
overwrites in place (carriage return, no newline).

**AC-3 — Without `--stats`, the terminal output is unchanged.**
Verified by: run without `--stats`; the output matches the current behavior
(plain scrolling text, no status line).

## Test plan

- Manual test: run the CLI with and without `--stats` against a Mandarin WAV;
  confirm the status line appears, updates, and does not scroll captions.
- Format check: the status line fits in 120 columns (the default terminal
  width).

## Out of scope

- The overlay (this task is terminal-only).
- A TUI framework (curses, textual). The status line is a plain stderr
  overwrite.
- Logfile output (the `--stats` flag is for live visibility, not logging).
