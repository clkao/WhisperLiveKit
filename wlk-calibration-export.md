---
title: "Export zh→en and ja→zh translation-head calibrations to upstream; resolve missing-calibration behavior"
status: backlog
score: 0.85
id: b8k2m3n4p5q6r7s8t9u0v1w2
worktree: .
---

# Task A — zh→en/ja→zh calibration export + deactivate policy question

## Context

Upstream merged #422/#423 and converted the hardcoded alignment-head constants
into a file-based calibration registry (`whisperlivekit/simul_mt_calibration.py`
+ `whisperlivekit/calibrations/`). Main carries only **en→zh** for
mlx-community/Hy-MT2-1.8B-8bit. Our local stack holds validated calibration
data for **zh→en** (production direction, 8 heads, top (9,5) TS=0.79 on mlx,
0.794 on PyTorch bf16, quantization-innocent) and a seed for **ja→zh**
(en→zh + ja→zh seed commit `31c224b` locally).

On upstream main, `MlxLlmTranslationSimul.__init__` calls `load_calibration`
unconditionally, which **raises** when the file is missing → `--simultaneous`
with zh→en crashes at startup. The validated design (captain's gate decision,
validation cycle 2) was **SILENT DEACTIVATE**: missing tuple →
`wants_hypothesis_tail=False`, log a warning naming the tuple, behave as base
translate-on-close. That fallback was lost in the maintainer's integration.

## Work

1. Export the zh→en and ja→zh head sets into the upstream calibration file
   format (fields: model, direction, num_layers, num_heads, heads,
   ts_matrix, stability_checks, promotion_gate, runtime provenance). Source
   data: local `whisperlivekit/simul_mt_capture.py` (deleted upstream — read
   from the integration branch) + `/tmp/ts_mlx.json` if still present.
2. Validate the export round-trips through upstream `load_calibration`
   (prompt must match the model profile exactly).
3. PR the calibration files to QuentinFuxa/WhisperLiveKit.
4. In the PR description (or an issue), raise the missing-calibration
   question: hard-fail (current main) vs silent deactivate (validated design,
   cites the AlignAtt4LLM hard-fail RuntimeError as the pattern we chose
   against). Do NOT implement the policy change in this PR — one decision per
   PR; the calibration files stand alone.

## Acceptance

- [ ] zh→en and ja→zh calibration JSONs load via upstream
      `load_calibration` with exact prompt match.
- [ ] Simul smoke on upstream main + the PR files: zh→en releases drafts
      (coverage ≥ 0.6 on the local fixture or equivalent).
- [ ] The deactivate-policy question is raised with the maintainer with both
      designs' tradeoffs stated.

## Notes

- Files live on the integration branch; cut the PR branch from origin/main.
- The maintainer's #444 may touch calibrations — rebase-check before opening.
