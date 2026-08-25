---
title: "terminal CLI with live stats and latency readout"
status: backlog
source: prototype — pure terminal output before the overlay
score: 0.8
id: 4903005btdrgc54j17s5bcax
---

The prototype runs in two output modes: a native macOS overlay and a terminal printout. The terminal printout today is plain text with no instrumentation. For calibration and A/B measurement, the operator needs live stats: ASR latency, MT latency, MLX memory, and commit/emit counts.

## Proposed approach

Improve scripts/lc_terminal.py to print a live status line to stderr on a 1s timer. Show: ASR EWMA latency, MT EWMA latency, MLX active/cache/peak memory, commit count, emit count. Use carriage-return overwrite (no scroll). A --stats flag enables it; off by default.

## Acceptance criteria

- AC-1: terminal CLI prints a live status line when --stats is set. Verified by: run with --stats; stderr shows a line that updates every second.
- AC-2: status line does not scroll the caption text. Verified by: captions appear above; status line overwrites in place.
- AC-3: without --stats, output is unchanged. Verified by: run without --stats; output matches current behavior.

## Out of scope

- The overlay. A TUI framework. Logfile output.
