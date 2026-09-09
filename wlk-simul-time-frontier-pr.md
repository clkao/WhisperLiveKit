---
title: "Simul PR: time-based frontier stack (frontier, drain clamp, default flip)"
status: backlog
score: 0.85
id: e1n5p6q7r8s9t0u1v2w3x4y5
worktree: .
---

# Task D — simul PR: the time-frontier stack onto upstream main

## Context

Local-only, measured improvements to the simul commit policy that upstream
main lacks:

1. **Time-based accessible frontier** (`bcb0467`): `frontier_mode`
   (text|time|auto), `hold_back_s` knob, audio-position cursor, accessible
   prefix from token end times + fractional release of the unstable tail
   (word-level access without word timestamps).
2. **Drain clamp + fragment guard** (`7f13e08`): end-of-feed clamp
   (`source_complete` + DRAIN_RELEASE poke) — no frozen fragment at EOF;
   `_MIN_RELEASED_TOKENS=6` released-prefix gate — no 1-3 word stubs at
   sentence opens (FO-endorsed deviation from the 15-token letter; measured
   0.87→0.56 coverage if 15 used; 6 preserves 0.82-0.87 with zero fragments).
3. **Auto→time default flip** (`e9fbadf`): `auto` resolves to the time
   frontier for every simul backend; text remains explicit opt-out.

Measured A/B (same audio, same ASR text, zh_long + demo_en_30s):
- zh→en: text 0.63 → time 0.82-0.87; en→zh: 0.55 → 0.70; churn unchanged or
  better; drain fixed (full tail draft before its ASR final; 4 finals).
- Deviation from the paper (committed-only frontier) is deliberate; tail
  revisions protected by dim/bright grammar + full-re-translation finals.

## Work

1. Port `bcb0467` + `7f13e08` + `e9fbadf` onto a branch cut from origin/main.
2. **Re-verify against the maintainer's adapted simul code first** —
   `translation_mlx_llm_mt_simul.py` differs by 748 lines between our tip and
   the PR heads (his #440-445 merges). Confirm the frontier seam still fits
   (his `translation_processor.py` split may own the audio-position cursor).
3. Regression tests (drain clamp, fragment guard, auto resolution), fixture
   replay byte-identical in text mode.
4. PR with the A/B numbers; state the paper deviation + protections plainly.
5. Decide gate semantics (task G) before finalizing the PR description.

## Acceptance

- [ ] Upstream-main branch: time frontier + clamp + guard + default flip.
- [ ] All simul tests green vs upstream baseline; text mode byte-identical.
- [ ] Real-clip A/B re-run on the ported code (acceptance ≥ 0.75 coverage,
      0 fragments, 4 finals, drain unfrozen).
- [ ] PR opened with measured numbers + deviation statement.

## Notes

- Review sequence: after B, parallel with G (fold G's decision in).
- Prerequisite check: task A's calibration files (zh→en simul on main needs
  them to even construct the engine).
