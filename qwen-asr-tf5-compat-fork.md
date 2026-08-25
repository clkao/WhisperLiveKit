---
title: "qwen-asr transformers 5.x compatibility fork"
status: backlog
source: dep cleanup — unblocks qwen3-asr-causal on our Apple-Silicon prototype
score: 0.9
id: zyarn2ybkarvajyz0dd46m1r
---

The qwen3-asr-causal backend uses a stronger commit policy (LocalAgreement via stable_commit) than mlx-qwen3-asr. It gives more accurate ASR text for our zh-tw prototype. But qwen3-asr-causal depends on the qwen_asr package, which fails to import on transformers 5.x.

## The blocker

One import-time error, verified in our venv (transformers 5.11.0, huggingface_hub 1.18.0):

qwen_asr/core/transformers_backend/modeling_qwen3_asr.py:986
@check_model_inputs()
TypeError: check_model_inputs() missing 1 required positional argument: 'func'

The check_model_inputs decorator signature changed in transformers 5.x. Note: is_offline_mode is NOT a blocker (present in huggingface_hub 1.18.0).

## Proposed approach

Fork qwen-asr. Patch the check_model_inputs call at modeling_qwen3_asr.py:986 to match the transformers 5.x signature. Pin the fork in our prototype install. Do not upstream — this is a local prototype dep.

## Acceptance criteria

- AC-1: qwen_asr imports on transformers 5.11.0. Verified by: python -c "import qwen_asr" exits 0.
- AC-2: qwen3-streaming backend loads and transcribes. Verified by: wlk serve --backend qwen3-streaming --language zh starts without import error.
- AC-3: stable_commit is active. Verified by: backend log shows the stable_commit flush path.

## Out of scope

- Upstreaming the fork. The vllm-metal loader swap. Any change to the decorator itself.
