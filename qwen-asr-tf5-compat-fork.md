---
title: "qwen-asr transformers 5.x compatibility fork"
status: implementation
source: dep cleanup — unblocks qwen3-asr-causal on our Apple-Silicon prototype
score: 0.9
id: zyarn2ybkarvajyz0dd46m1r
gates:
    version: 1
    records:
        - id: gate:zyarn2ybkarvajyz0dd46m1r:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:zyarn2ybkarvajyz0dd46m1r-backlog-1
              briefing:
                id: briefing:zyarn2ybkarvajyz0dd46m1r:backlog:attempt-1:revision-1
                digest: sha256:d71b77f9a57e84c1ff3386da4dc169e200e43b17078fce5d6af6bd31c63c7f4c
                request-digest: sha256:69ee3b3fc12324e03b0e916f804f3d0c140c9a905e7ab49945ef028128a4ebce
                room-ref: ./qwen-asr-tf5-compat-fork/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:zyarn2ybkarvajyz0dd46m1r:backlog:1
                briefing: briefing:zyarn2ybkarvajyz0dd46m1r:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T16:55:48.567447Z"
                decision: approve
              application:
                target-stage: ideation
                state: consumed
        - id: gate:zyarn2ybkarvajyz0dd46m1r:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:zyarn2ybkarvajyz0dd46m1r-ideation-1
              briefing:
                id: briefing:zyarn2ybkarvajyz0dd46m1r:ideation:attempt-1:revision-1
                digest: sha256:1a60f871591c407965cdcda8e4c2dadb95f7684d1feac88fa043c6360c76ec2f
                request-digest: sha256:d678d56522856f9cda829c448d660b8b5967c97bd268ab2ff02da3ba65c202c7
                room-ref: ./qwen-asr-tf5-compat-fork/review/ideation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:zyarn2ybkarvajyz0dd46m1r:ideation:1
                briefing: briefing:zyarn2ybkarvajyz0dd46m1r:ideation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T16:55:51.593875Z"
                decision: approve
              application:
                target-stage: implementation
                state: consumed
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
