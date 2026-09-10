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

## Stage Report: integration restructure — wlk/integration-2 built

- DONE: New integration branch built as the merge of everything in flight
  Branch wlk/integration-2 (worktree .worktrees/wlk-integration-2, NOT
  pushed), from origin/main 363e4f6. Merge commits, one per source, in
  order: #425 qwen3 (95cc585, clean), #426 nemotron (7409b56, clean),
  #448 calibration (9cb510a, clean), #449 display (0d561ce, ONE conflict:
  parse_args.py — nemotron arg group vs --event-log; unioned), tui-view
  client bundle (992e0ac, clean), simul time-frontier (3d51e0b, TWO
  conflicts: translation_processor imports [unioned TranslationProgress +
  DRAIN_RELEASE], translation_mlx_llm_mt_simul [unioned the progress
  contract block with the _accessible_text/_frontier_text/_accessible_gate_open
  block — disjoint additions after _committed_text]), diarization-mlx
  (2c8a977, clean), ja→zh seed (1423e63), lockfile reconciliation (4f6b014).
- DONE: ja→zh seed adapted
  The constants-era e9956a0 could not cherry-pick (simul_mt_capture.py was
  deleted upstream). Used instead the full-format ja→zh JSON from the
  calibration-export history (6188fd2, 8 heads, top L9/H5, thin-corpus
  caveat in the commit message) — rides on integration until recalibration.
- DONE: lockfile conflict resolved (the real find of this merge)
  The nemotron extra needs mlx-audio>=0.5.1 (transformers>=5.5) while
  qwen3-streaming pins transformers==4.57.6 via qwen-asr==0.0.6. Resolution
  followed the maintainer's own pattern: diarization-mlx-sortformer's pin
  relaxed to >=0.4.4 (backend only uses mlx_audio.vad.load, verified present
  through upstream 0.5.3) and three conflicts entries added
  ({diarization-mlx-sortformer} x {qwen3-streaming,qwen3-vllm,
  qwen3-vllm-metal}), mirroring his nemotron/qwen3 conflict groups.
  `uv lock --check` passes (407 packages). Submodule
  third_party/qwen3-asr-causal init required for lock.
- DONE: Verification
  ruff clean; import smoke OK (package + all 6 new backend/policy modules);
  suite 402 passed / 3 failed / 4 errors — failure set a strict subset of
  the pre-existing baseline (canary x2, deepgram, ffmpeg coalescing; the
  qwen3 shim tests PASS here because the submodule is checked out).
- SKIPPED: live model pipeline run (disk was 500MB free mid-merge; 11GB now
  — recommend a live smoke as the next step before any push decision).
- FAILED: none

### Summary

wlk/integration-2 = origin/main + #425 + #426 + #448 + #449 + simul +
diarization + client bundle + ja→zh seed. The old
feat/apple-silicon-backends is now fully superseded per the audit (49
commits homed across the branches above, 72 superseded-and-documented) and
can be archived once a live smoke passes on integration-2. The mlx-audio
extras conflict is an upstream-level question the diarization PR will face
independently.
