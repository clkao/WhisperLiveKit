---
title: "terminal CLI with live stats and latency readout"
status: implementation
source: prototype — pure terminal output before the overlay
score: 0.8
id: 4903005btdrgc54j17s5bcax
gates:
    version: 1
    records:
        - id: gate:4903005btdrgc54j17s5bcax:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:4903005btdrgc54j17s5bcax-backlog-1
              briefing:
                id: briefing:4903005btdrgc54j17s5bcax:backlog:attempt-1:revision-1
                digest: sha256:f80754ffe2446de7cdc7900d1047c1f666f881488c1ab791d54dfe7e773822ee
                request-digest: sha256:77b6a271c089875c2626b020527fe7bf7666157db7577bbe3419ad96bd623ade
                room-ref: ./terminal-cli-stats/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:4903005btdrgc54j17s5bcax:backlog:1
                briefing: briefing:4903005btdrgc54j17s5bcax:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T16:55:54.498568Z"
                decision: approve
              application:
                target-stage: ideation
                state: consumed
        - id: gate:4903005btdrgc54j17s5bcax:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:4903005btdrgc54j17s5bcax-ideation-1
              briefing:
                id: briefing:4903005btdrgc54j17s5bcax:ideation:attempt-1:revision-1
                digest: sha256:5bbb17f776da5b9322828d0db92b05ddf042aa188c033e713818bc3353ea7d1d
                request-digest: sha256:decbbea9e41332e7f6c7904db4d40ba9b54951cf93e631486168ac820c45c835
                room-ref: ./terminal-cli-stats/review/ideation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:4903005btdrgc54j17s5bcax:ideation:1
                briefing: briefing:4903005btdrgc54j17s5bcax:ideation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T16:55:57.878895Z"
                decision: approve
              application:
                target-stage: implementation
                state: consumed
started: 2026-08-25T16:56:15Z
worktree: .worktrees/spacedock-ensign-terminal-cli-stats
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

## Summary

Implemented `--stats` flag in `scripts/lc_terminal.py`. Added a `StatsTracker` class that runs a daemon thread printing a status line to stderr every 1s using `\r` (carriage-return overwrite, no newlines between updates). The line shows: MLX active/cache/peak memory (if mlx.core available), ASR EWMA latency, MT EWMA latency, commit count, emit count. `TerminalSink` records latency samples (partial→commit = ASR, commit→emit = MT) and increments counters on each state update. `--stats` is off by default; when off, no thread is started and no hooks are called (behavior identical to before). Committed on `spacedock-ensign/terminal-cli-stats` as fc57c7d.

## Stage Report: implementation

- DONE: terminal CLI prints a live status line when --stats is set.
  StatsTracker class (1s timer thread, \r overwrite to stderr) added to scripts/lc_terminal.py. ASR/MT latency EWMA, MLX memory, commit/emit counts.
- DONE: status line does not scroll the caption text.
  Carriage-return overwrite (no \n between updates); stop() prints one trailing \n.
- DONE: without --stats, output is unchanged.
  TerminalSink(stats=None) produces identical output (no hooks, no thread).
- DEFERRED to CL's Mac: runtime rendering of the status line (sandbox can't run the terminal driver).

### Summary
Added StatsTracker to scripts/lc_terminal.py. --stats flag gates a 1s-timer stderr status line (ASR/MT latency EWMA, MLX memory, commit/emit counts) with carriage-return overwrite. Without --stats, output is identical to original. 1 commit (fc57c7d) on spacedock-ensign/terminal-cli-stats.
