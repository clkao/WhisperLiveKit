---
title: "mlx-llm-mt: generic decoder-LLM MT backend (clean PR off origin/main)"
status: implementation
source: fast-tracked from hunyuan-mlx-translation-backend (completion-guard wedged on the prior entity; captain authorized re-filing with the existing clean worktree)
score: 0.8
worktree: .worktrees/spacedock-ensign-hunyuan-mlx-translation-backend
id: 5c87da2jhj60dtxmybb72v6p
started: 2026-08-26T06:46:29Z
---

Generic decoder-LLM translation backend via mlx-lm, with Hunyuan-MT as the
first config. In-process zh→en (and en→X) MT on Apple Silicon, no CUDA sidecar.
Replaces the AlignAtt CUDA sidecar for the Apple-Silicon prototype.

## Fast-track authorization (captain)

The captain authorized filing this as a fresh task at `implementation` with the
existing clean worktree, because the prior entity (`hunyuan-mlx-translation-backend`,
slug `bp`) is wedged at its completion guard — its stage report is written,
formatted, committed, and pushed, but `status --set ... status=validation` still
refuses. The clean PR branch already exists
(`spacedock-ensign/hunyuan-mlx-translation-backend` at `802fdfc`, 7 files,
+610/-8, only mlx-llm-mt). This task carries that work forward without the
prior entity's guard issue.

## What ships (already built — the clean commit `802fdfc`)

- `whisperlivekit/translation_mlx_llm_mt.py` (300 lines — generic
  `MlxLlmTranslation` base + `MlxLlmMtModelConfig` registry, 6 Hunyuan + 1
  TranslateGemma placeholder; accepts `HypothesisTail` in `insert_tokens` for
  the AlignAtt simultaneous-MT seam)
- `whisperlivekit/translation_hunyuan_mlx.py` (20 lines — backward-compat shim
  re-exporting `HunyuanMlxTranslation = MlxLlmTranslation`)
- `tests/test_mlx_llm_mt.py` (226 lines — 16 tests including the 4
  `HypothesisTail` contract tests)
- `whisperlivekit/config.py` — `mlx_llm_mt_model` field + `hunyuan_mlx` alias +
  reconciliation (only the mlx-llm-mt hunks, no ASR)
- `whisperlivekit/core.py` — the `("mlx-llm-mt", "hunyuan-mlx")` dispatch branch
  (only, no ASR branches)
- `whisperlivekit/parse_args.py` — `--translation-backend` choices +
  `--mlx-llm-mt-model` (only, no ASR args)
- `pyproject.toml` — the `mlx-llm-mt` extra (`mlx-lm>=0.31.1`)

The diff vs `origin/main` is exactly 7 files, +610/-8. No ASR, overlay, CLI,
vendored fork, or local docs.

## Acceptance criteria

- AC-1: `wlk serve --backend mlx-qwen3-asr --translation-backend mlx-llm-mt
  --target-language en --language zh` produces correct zh→en translation.
  Verified by: live run on CL's Mac (sandbox lacks mic TCC + live Metal).
- AC-2: `validate_buffer_and_reset` does not double the output. Verified by:
  `tests/test_mlx_llm_mt.py` AC-3 test (16/16 pass).
- AC-3: Hunyuan is one config, not the backend identity — a second config loads
  with a different repo+prompt without new code. Verified by:
  `tests/test_mlx_llm_mt.py` AC-4 test.
- AC-4: backward-compat alias `--translation-backend hunyuan-mlx` works.
  Verified by: `tests/test_mlx_llm_mt.py` AC-5 test.
- AC-5: The branch diff vs `origin/main` is exactly 7 files (no ASR/overlay/
  CLI/vendored/docs leakage). Verified by: `git diff --stat origin/main..HEAD`
  on the worktree branch.
- AC-6: `insert_tokens` accepts `HypothesisTail` (the AlignAtt simultaneous-MT
  seam). Verified by: `tests/test_mlx_llm_mt.py` (4 HypothesisTail tests pass).

## Test plan

`tests/test_mlx_llm_mt.py` (16 tests, mock `_translate_text` — no model load):
contract logic, buffer/commit, HypothesisTail handling. Full non-async suite
(209 passed, 12 skipped, 1 pre-existing unrelated error on origin/main).

## Out of scope

- The simultaneous-MT (Tier B) port — separate task
  (`mlx-llm-mt-tier-b-simultaneous`).
- The ASR backend, overlay, terminal CLI — separate tasks.
- The `pr-merge` mod handles the PR; this task does not push or open a PR.

## Notes

The worktree branch `spacedock-ensign/hunyuan-mlx-translation-backend` at
`802fdfc` is the PR source. The prior entity's stage report (on
`origin/dev-state`) documents the reconstruction; this task re-uses that
worktree + commit.

## Stage Report: implementation

- DONE: test

### Summary

test
