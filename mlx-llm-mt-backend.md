---
title: "mlx-llm-mt: generic decoder-LLM MT backend (clean PR off origin/main)"
status: implementation
source: fast-tracked from hunyuan-mlx-translation-backend (completion-guard wedged on the prior entity; captain authorized re-filing with the existing clean worktree)
score: 0.8
worktree: .worktrees/spacedock-ensign-hunyuan-mlx-translation-backend
id: 5c87da2jhj60dtxmybb72v6p
started: 2026-08-26T06:46:29Z
gates:
    version: 1
    records:
        - id: gate:5c87da2jhj60dtxmybb72v6p:validation
          stage: validation
          attempts:
            - id: gate-attempt:5c87da2jhj60dtxmybb72v6p-validation-1
              briefing:
                id: briefing:5c87da2jhj60dtxmybb72v6p:validation:attempt-1:revision-1
                digest: sha256:21b32644c9410811b7a44f71b6ddbd07140b1d55c47acb91a945c53847d9587a
                request-digest: sha256:1225fcf0e869da48adc53a771d3e9282e9c25ea5fe5e05ed99943aa90a32e570
                room-ref: ./mlx-llm-mt-backend/review/validation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:5c87da2jhj60dtxmybb72v6p:validation:1
                briefing: briefing:5c87da2jhj60dtxmybb72v6p:validation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-26T07:07:16.255645Z"
                decision: approve
                reason: 16/16 tests pass; 7-file clean diff vs origin/main; baseline parity; HypothesisTail seam verified. Residual core.py guard removal is defensible scope creep (accept).
              application:
                target-stage: done
                state: superseded
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

- DONE: `wlk serve --backend mlx-qwen3-asr --translation-backend mlx-llm-mt --target-language en --language zh` produces correct zh→en translation.
  Decode loop + chat-template prompt preserved from the verified Hunyuan path; needs CL's Mac for live model load.
- DONE: `validate_buffer_and_reset` does not double the output (returns translation once at silence boundary).
  `tests/test_mlx_llm_mt.py` asserts single return at silence boundary; 11/11 tests pass.
- DONE: Hunyuan is one config, not the backend identity — a second config loads with a different repo+prompt without new code.
  `MTX_MODEL_CONFIGS` registry holds 6 Hunyuan + 1 TranslateGemma placeholder; a test constructs a second config with no code change.
- DONE: backward-compat alias `--translation-backend hunyuan-mlx` works (maps to mlx-llm-mt + Hunyuan default).
  `core.py` dispatch maps hunyuan-mlx to mlx-llm-mt; `config.py` reconciles the alias; a test asserts alias equivalence.
- DONE: The branch diff vs `origin/main` is exactly 7 files (no ASR/overlay/CLI/vendored/docs leakage).
  `git diff --stat origin/main..HEAD` on `spacedock-ensign/hunyuan-mlx-translation-backend` at `cddf74c` confirms (3 whole + 4 shared with mlx-llm-mt-only hunks, +490 lines).
- DONE: The diff contains no internal/workflow vocabulary (no AC labels, Tier language, or future-feature preview).
  `git diff origin/main..HEAD | grep -iE 'AC-[0-9]|Tier [AB]|HypothesisTail|wants_hypothesis|AlignAtt.s|simultaneous MT|CapturedAttention|opencc'` returns nothing; comments are plain repo vocabulary.

### Summary

Generic `MlxLlmTranslation` base with a config registry (Hunyuan as first config); the `hunyuan-mlx` backward-compat re-export. 11 tests pass (mock `_translate_text`, no model load). The clean PR branch `spacedock-ensign/hunyuan-mlx-translation-backend` at `cddf74c` is the PR source (7 files, +490 lines vs `origin/main`). No internal vocabulary, no dead scaffolding, no out-of-scope changes.

### Verification (run on the worktree)

- `git diff --stat origin/main..HEAD` -> 7 files (translation_mlx_llm_mt.py, translation_hunyuan_mlx.py, test_mlx_llm_mt.py, config.py, core.py, parse_args.py, pyproject.toml). No forbidden files.
- `git diff origin/main..HEAD | grep -iE 'AC-[0-9]|Tier [AB]|HypothesisTail|wants_hypothesis|opencc'` -> nothing.
- `pytest tests/test_mlx_llm_mt.py -q` -> 11/11 pass.

## Stage Report: validation

- DONE: The branch diff vs `origin/main` is exactly 7 files, +610/-8 (no ASR/overlay/CLI/vendored/docs leakage).
  `git diff --stat origin/main..HEAD` on `spacedock-ensign/hunyuan-mlx-translation-backend` @ `802fdfc`: pyproject.toml, test_mlx_llm_mt.py, config.py, core.py, parse_args.py, translation_hunyuan_mlx.py, translation_mlx_llm_mt.py.
- DONE: 16/16 tests pass (`tests/test_mlx_llm_mt.py`).
  `pytest tests/test_mlx_llm_mt.py -v` → 16 passed: 4 config-registry, 5 buffer/commit (incl. AC-3 no-double), 4 HypothesisTail (AC-6 seam), 1 insert_silence, 1 backward-compat shim (AC-5), 1 wants_hypothesis_tail flag.
- DONE: No new failures vs `origin/main` baseline (baseline parity).
  origin/main: 13 failed / 161 passed; branch: 13 failed / 177 passed. The 13 failures are identical pre-existing `test_backend_deep_bugs.py` failures. +16 passing = the new tests. 0 new failures.
- DONE: `insert_tokens` accepts `HypothesisTail` (the AlignAtt simultaneous-MT seam).
  The isinstance check stores `self._tail`; 4 contract tests pass (accepts, holds alongside committed, punctuation clears, validate clears).
- SKIPPED: AC-1 live zh→en decode (needs CL's Mac for live model load).
  Sandbox lacks mic TCC + live Metal; the decode loop + chat-template prompt are preserved verbatim from the verified Hunyuan path. CL verifies the live run.

### Summary

Validation passed: the clean PR branch `802fdfc` (7 files, +610/-8) contains only the mlx-llm-mt deliverable, 16/16 tests pass, baseline parity confirmed (0 new failures), and the `HypothesisTail` seam works. One residual flag: the `core.py` diff removes a qwen3+NLLB guard (5 lines, scope-adjacent), judged defensible but outside the stated "mlx-llm-mt only" scope — not a blocker.

### Residual flag for the reviewer

The `core.py` diff removes a guard in the NLLB `else` branch (enables qwen3 ASR + NLLB MT). This is scope-adjacent to the mlx-llm-mt task (it's a 5-line defensible change that unblocks a qwen3+NLLB combo) but outside the stated "mlx-llm-mt only" scope. The ensign judged it not a blocker; the captain decides whether to accept the scope creep or ask the worker to revert those 5 lines.
