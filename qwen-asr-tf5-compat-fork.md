---
id: zcj7d9suqr3aruk8lv35d199
title: "qwen-asr transformers 5.x compatibility fork"
status: backlog
source: dep cleanup — unblocks qwen3-asr-causal on our Apple-Silicon prototype
started:
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
---

# qwen-asr transformers 5.x compatibility fork

## Problem

The `qwen3-asr-causal` backend uses a stronger commit policy (LocalAgreement
via `stable_commit`) than `mlx-qwen3-asr`. It gives more accurate ASR text for
our zh-tw prototype. But `qwen3-asr-causal` depends on the `qwen_asr` package,
which fails to import on transformers 5.x. The prototype must use the
`qwen3-asr-causal` emission for accuracy, so this import failure blocks the
prototype.

## The blocker

One import-time error, verified in our venv (transformers 5.11.0,
huggingface_hub 1.18.0):

```
qwen_asr/core/transformers_backend/modeling_qwen3_asr.py:986
@check_model_inputs()
TypeError: check_model_inputs() missing 1 required positional argument: 'func'
```

The `check_model_inputs` decorator signature changed in transformers 5.x. The
`qwen_asr` package calls it without a positional argument, which transformers
5.x rejects.

Note: `is_offline_mode` is NOT a blocker. It is present in huggingface_hub
1.18.0 (our combo has it). The only blocker is the decorator signature.

## Proposed approach

Fork `qwen-asr` (or `qwen3-asr-causal` if it vendors the file). Patch the
`check_model_inputs` call at `modeling_qwen3_asr.py:986` to match the
transformers 5.x signature. Pin the fork in our prototype install. Do not
upstream the fork to the original repo — this is our local prototype dep, not
a WLK contribution.

The simplest alternative — pin transformers to 4.57.6 — is rejected: it
breaks our mlx-lm + mlx-qwen3-asr combo, which needs transformers 5.x.

## Risk evidence

The decorator signature change is documented in the transformers 5.x
changelog. The fix is one line: pass the decorated function as the positional
argument, or adjust the call to the new signature. No model behavior changes.

## Expected surface and tolerance

Estimate: +5 net LOC across 1 file, tolerance ±3.
Semantics this may change: none. The patch makes an import work; it does not
change model output.

## Acceptance criteria

**AC-1 — The qwen_asr package imports on transformers 5.11.0.**
Verified by: `.venv/bin/python -c "import qwen_asr"` exits 0 with no traceback.

**AC-2 — The qwen3-streaming backend loads and transcribes.**
Verified by: `wlk serve --backend qwen3-streaming --language zh` starts without
an import error and transcribes a Mandarin sample.

**AC-3 — The qwen3-asr-causal commit policy (stable_commit) is active.**
Verified by: the backend log shows `[qwen3-streaming] start_silence: flushed N
words` (the stable_commit flush path), not a raw decode dump.

## Test plan

- Import test: `.venv/bin/python -c "import qwen_asr; print('ok')"`
- Backend test: run `wlk serve --backend qwen3-streaming --language zh` against
  a Mandarin WAV; confirm transcription output.
- Regression: the existing `mlx-qwen3-asr` backend still works (no dep change
  to its path).

## Out of scope

- Upstreaming the fork to the original `qwen-asr` repo. This is a local
  prototype dep.
- The vllm-metal loader swap for `qwen3-vllm-metal` (separate dep cleanup).
- Any change to the `check_model_inputs` decorator itself (we patch the call
  site, not the decorator).
