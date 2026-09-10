---
title: "Upstream follow-through: #444 M5 evaluation, nemotron rewrite review, harness adoption"
status: backlog
score: 0.75
id: a3q7r8s9t0u1v2w3x4y5z6a7
worktree: .
---

# Task E — #444 follow-through + harness adoption

## Context

The maintainer opened #444 (draft): the M5 screening of OUR backends on his
new FLEURS-90 harness. Measured so far (7/16 reports, power-contaminated
latency): nemotron 0.6B beats whisper-small-LA on zh CER (22.6 vs 25.3) and
fr WER; loses en WER (19.3 vs 11.7); finalization p95 0.05-0.11s vs 0.70-1.00s
(6-20x). Whisper's 10-min zh stream hit a repetition loop. Pending: all 8
qwen3 runs + nemotron zh-continuous. He also committed to our PR branches:
a nemotron streaming-cache rewrite ("Use upstream Nemotron streaming caches
and the compatible MLX checkpoint") and a single-MLX-thread fix
(`nemotron-thread-regression-before.json.gz` documents the regression).

## Work

1. **Review his nemotron rewrite** on the #426 branch head — our local
   adapter knowledge is partially obsolete. Verify the single-MLX-thread fix
   against the thread-regression artifact; check our endpointing/token
   contracts survived.
2. **Watch the pending qwen-vs-nemotron zh runs** — they decide the
   production zh backend and answer the question our deprioritized
   comparison was built for. Adopt the result; do not duplicate it.
3. **Adopt the FLEURS-90 + scatter harness** for any evals we owe (the
   time-frontier A/B rerun in task D should use it where practical —
   FLEURS-zh Mandarin + `wlk bench`). Stop extending ad-hoc zh_long loops.
4. Check upstream #445 (translation cancellation) against our lc_terminal
   executor/shutdown fix — if redundant, note it; if complementary, port
   with task D.
5. Watch the M5 gate rule (≥20% finalization/memory per pass, ≤1pp quality
   regression) — it will decide #426's integration; keep our numbers aligned
   with his methodology.

## Acceptance

- [ ] His nemotron rewrite reviewed; findings recorded (adapter contracts).
- [ ] The qwen-vs-nemotron zh decision recorded when #444 completes.
- [ ] At least one of our evals migrated to the FLEURS harness.
- [ ] #445-vs-our-shutdown-fix relationship documented.
