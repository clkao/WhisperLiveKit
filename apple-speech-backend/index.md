---
title: "apple-speech ASR backend (Apple SpeechAnalyzer via the apple-asr package)"
status: implementation
worktree: .worktrees/wlk-apple-speech-adapter
source: _work/apple-asr-package/ — SPEC.md, MEASUREMENTS.md, ORDER*/CLOCKFIX/WHEEL/TINY/CIFIX/WLKFINISH/SELFCONTAINED reports, ORDER3-DESIGN.md, PR-apple-speech.md
id: rz6edm6r175hfqy7z9h7r032
---

## End value

A WhisperLiveKit `apple-speech` backend giving zh/en on-device SpeechAnalyzer quality
above every MLX backend, with volatile partials and per-word timings at zero GPU cost —
carried as a thin adapter over a released package so upstream takes no Swift/toolchain
burden and there is one implementation to maintain, not two.

## State (as filed)

Implemented and verified on branch `wlk/apple-speech-adapter` (worktree above; 7 commits
over `wlk/integration-2` @ 9d366f9; net +557/−753). Adapter tests 9 passed / 0 skipped;
golden cadence 12 committed segments vs the golden's 12; measured zh CER 13.19 streaming /
11.23 accurate and en WER 13.94 / 9.51 vs the board's 18.20 / 19.27. Dependency published:
github.com/clkao/apple-asr @ v0.1.2 (CI green, toolchain-free platform wheel).

Open: the upstream PR is drafted but NOT opened (captain's go), and the live mic ja/zh
sign-off is outstanding.

Process note: this work was dispatched without worktree isolation and landed on a branch in
the main checkout; corrected by creating the worktree above. It was also not filed as a task
until now.
