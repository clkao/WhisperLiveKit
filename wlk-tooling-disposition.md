---
title: "Tooling disposition: simul_fixture / check_simul_heads / explore_heads / lc_terminal"
status: backlog
score: 0.7
id: b4r8s9t0u1v2w3x4y5z6a7b8
worktree: .
---

# Task F — tooling disposition

## Context

Local dev tooling with no upstream equivalent (upstream took only
`calibrate_ts_mlx.py`):

- `scripts/simul_fixture.py` — deterministic record/replay fixture (the
  regression gate for the simul engine; record mode captures the ASR
  interface; replay is cross-process identical with greedy sampling).
- `scripts/check_simul_heads.py` — draft-coverage litmus over event logs.
- `scripts/explore_heads_mlx.py` — all-head attention survey + per-call
  frontier dump.
- `scripts/lc_terminal.py` — the captain's terminal driver: --event-log,
  --simul-commit/--simul-frontier/--simul-heads flags, --overlay/--mem,
  the shutdown fix. Upstream has no equivalent CLI.

Upstream now has its own eval surface (`wlk bench`, FLEURS, scatter runner,
schema 3.1) that overlaps the measurement half of our tooling.

## Work (disposition per tool — captain decides per item)

1. **simul_fixture.py** — PR as test tooling (it gates tasks D; upstream CI
   benefits) OR fold its record/replay idea into upstream's benchmark
   schema. Default recommendation: PR it; it's self-contained.
2. **check_simul_heads.py** — likely superseded by upstream's WER/CER
   latency fields for corpus evals, but remains the only word-level
   draft-coverage litmus for policy work. Keep local unless D's PR wants it.
3. **explore_heads_mlx.py** — exploration tool; archive (its findings are
   recorded; the calibration registry supersedes its purpose).
4. **lc_terminal.py** — decide: propose as upstream CLI, keep as local dev
   driver, or let task C (wlk-tui) absorb its terminal responsibilities.
   Note: upstream #445 may absorb the shutdown fix; verify first.

## Acceptance

- [ ] Each tool has a recorded disposition (PR / fold / archive / keep-local).
- [ ] Dispositions that end in PRs reference the tasks that depend on them
      (D needs the fixture; C may absorb lc_terminal).
