---
title: "wlk-tui: standalone terminal caption client package"
status: backlog
score: 0.8
id: d0m4o5p6q7r8s9t0u1v2w3x4
worktree: .
---

# Task C — wlk-tui: standalone terminal caption client package

## Context

The terminal rendering work (rich three-region TUI: scrolling captions / OCR /
status line; `--stats` StatsTracker with MLX memory + ASR/MT latency EWMAs;
MLX sortformer `[S1]/[S2]` markers; dim/bright provisional grammar) is
scattered across the integration branch (`whisperlivekit/tui.py`,
`scripts/lc_terminal.py`, diarization display commits) and is local-only.
Captain decision: make this its own PROJECT — a standalone package whose
result is WLK becoming adaptable to `wlk-tui`. The terminal client is a
consumer of WLK's display output, not a WLK-internal renderer.

## Work

1. Standalone package `wlk-tui`: the three-region TUI, StatsTracker
   (`--stats`), diarization markers, and the sentence-paced caption rendering
   from task B's model.
2. Wire it to task B's unified display contract (event-stream consumer).
   Evaluate upstream surfaces as the transport (`session_asr_proxy.py`,
   `diff_protocol.py`, the web event channel) and pick one; the choice falls
   out of B.
3. Target **our integration branch until prerequisites clear** — i.e. it
   consumes B's contract as implemented locally; migrate to upstream main
   once B lands upstream (captain decision 2026-09-03).
4. Runtime-verify the pending validation item from the terminal-cli-stats
   entity (status line rendering — was blocked on sandbox, verifiable here).
5. Fold in `terminal-cli-stats` (`fc57c7d`, entity status: validation) — the
   StatsTracker becomes part of the package; close that entity when absorbed.

## Acceptance

- [ ] `wlk-tui` runs as a standalone package against the integration branch.
- [ ] Sentence guarantees (partition, no-retype, queue survival) hold in the
      terminal client — verified by replaying the golden streams through it.
- [ ] `--stats` status line renders live (the long-pending runtime check).
- [ ] Migration path to upstream documented (the transport seam).

## Notes

- Prerequisite: B's contract (unified display model) — build against it, but
  the package targets the integration branch until B clears upstream.
- Review sequence position: after B; parallel with D.

## Alignment decisions (captain, 2026-09-03)

- C is standalone; targets our integration branch until prerequisites clear
  (B's contract landing upstream), then migrates.
- The integration branch itself is NOT a tracked task: it freezes as a
  reference (evidence, goldens, the C target) — no rebase planned; all PRs
  (A, B, D) cut fresh from origin/main.

## Note: seed location update (2026-09-10)

The terminal view's current form is branch `wlk/tui-view` — stacked on
`wlk/display-unification` (the display-model PR branch), commit aae6299.
It renders from the shared caption display model (no independent display
logic). When this package work starts per the captain decision, it
consumes the event-stream contract from that branch; the tui.py there is
the starting point, not the integration branch's copy.

## Stage Report: wlk-tui-package (client bundle reconciliation)

- DONE: Client bundle restored onto wlk/tui-view (commit 5328fba)
  From the integration tip: whisperlivekit/{overlay.py,src_buffer.py,
  inline_diff.py,screen_ocr.py} + scripts/{lc_terminal.py,
  test_overlay_fullscreen.py}. overlay.py imports adapted to the renamed
  caption_display (CaptionDisplay). lc_terminal keeps its own --event-log
  (post-hoc tap hook — TestHarness constructs AudioProcessor without user
  args, so the server-side flag path is not reachable from the harness).
- DONE: View-level tests extracted
  tests/test_src_buffer.py (3 tests: full zh sequence, CJK/Latin join,
  promoted-sentence suppression) extracted from the stale untracked
  test_overlay_model.py duplicate (model tests live on the PR branch as
  test_caption_display.py; the untracked duplicate was removed).
- DONE: Live proof
  lc_terminal --event-log over zh_long.wav on the stacked branch: exit 0 in
  53s, 51 events, 4 finals, draft coverage 0.75 PASS. The full client
  bundle works against the renamed display layer.
- DONE: ruff clean; suite 364 passed / same failure set as origin/main.
- SKIPPED: src-row typing-frame trace variant of the replay instrument
  (noted in cycle 6 as living here) — the view-level trace was lost in the
  rebase; restore on demand from wlk/display-unification-old history if
  needed for overlay flicker debugging.
- FAILED: none

### Summary

wlk/tui-view now carries the complete client bundle (terminal driver +
overlay + src buffer + support modules) stacked on the renamed display
branch, live-verified. The package extraction (pyproject/packaging) is the
next step when the captain starts task C in earnest. Note: tui-view was
re-stacked onto 513b6fa (renamed) during the earlier session; the overlay
restore includes the pre-rename→post-rename import adaptation.

## Stage Report: two-pass re-decode port (wl-two-pass-port)

- DONE: Two-pass re-decode implemented in the #425-era native-stream backend
  whisperlivekit/asr_mlx_qwen3.py (commit fc8469d on wlk/tui-view): the
  processor retains utterance audio; finish() re-decodes the whole utterance
  via mlx_qwen3_asr.transcribe (with the per-session hotword context) when
  mlx_qwen3_asr_second_pass is on. A re-decode confirming the committed
  prefix emits only the suffix; one revising it emits the full corrected
  text (documented limitation: stale streaming prefix remains). Failures or
  empty re-decodes fall back to the streaming text with a non-fatal warning.
  Streaming-only finalize keeps the strict prefix contract (native revision
  raises), matching the #425 maintainer contract.
- DONE: The --second-pass/--no-second-pass flag is now functional
  Unit-tested both ways in tests/test_mlx_qwen3.py (4 new tests: correction
  emission, suffix-only confirmation, disabled skip, empty fallback).
- DONE: Verification
  Full suite on wlk/tui-view: 401 passed / 8 failed / 4 errors — the
  failure+error set is exactly the pre-existing baseline (canary x2,
  deepgram, qwen3 shims x5 which also fail on pristine origin/main, ffmpeg
  coalescing). ruff clean. Disk allowed no live lc_terminal smoke (not run).
- FAILED: none

### Summary

The client bundle's --second-pass toggle is functional. Adaptation notes:
the port passes the per-session hotword context to transcribe (the archive
version did not), and the strict-vs-lenient finalize contract is split by
the toggle (strict streaming-only, lenient under two-pass), which the
pre-existing revision test pinned and the port preserves. NOT pushed.
