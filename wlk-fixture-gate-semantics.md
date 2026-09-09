---
title: "Fixture gate semantics: per-final vs pooled draft coverage"
status: backlog
score: 0.7
id: f2o6p7q8r9s0t1u2v3w4x5y6
worktree: .
---

# Task G — fixture gate semantics decision

## Context

The deterministic fixture (`scripts/simul_fixture.py` replay over
`tests/golden/simul_zh_long_calls.jsonl`) reports draft coverage 0.57 — under
the 0.6 gate — on every faithful replay of the current code, while live runs
pass (0.69/0.63 text; 0.82/0.83/0.87 time). The ensign proved the number is
not a port artifact (byte-identical engine files at the source commit). The
known cause: the final short segment's tail sentence is not ASR-committed
when the segment closes, so its final's quality pass is by construction its
first release (structurally ~0.30-0.40). The pooled gate mixes that
structurally-capped final with healthy ones.

The gate failure now blocks task D's PR acceptance line, so the semantics
must be decided before D's description is finalized.

## Options (captain decides)

1. **Pooled gate stays 0.6** — accept the structural FAIL on this fixture,
   report the number + explanation in the PR (honest, but the gate then
   signals nothing for this fixture).
2. **Per-final reporting, pooled informational** — each final's coverage
   reported; gate applies per-final above a length threshold (e.g. finals
   with < N source tokens are excluded as structurally capped). The litmus
   stays honest; short-final capping becomes visible rather than averaged.
3. **Informative-only gate** — coverage reported, no pass/fail; regression
   detection via fixture DIFF (coverage must not drop below a recorded
   baseline per final), not an absolute threshold.

## Work

1. Captain picks the semantics.
2. Implement in `check_simul_heads.py` + the fixture replay output (local
   tooling; PR disposition is task F).
3. Task D's PR cites the decision + the fixture numbers under it.

## Acceptance

- [ ] Decision recorded here with rationale.
- [ ] Gate/report implemented; the fixture output reflects it.
- [ ] Task D's acceptance references the decided semantics.
