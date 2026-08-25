---
title: "qwen-asr deep transformers 5.x port (model load + transcribe)"
status: backlog
source: follow-up to qwen-asr-tf5-compat-fork (AC-1 only; model load blocked)
score: 0.85
id: epw1ee1k2gma0yv5yb8ynynk
---

The qwen-asr-tf5-compat-fork task fixed the import (AC-1) but discovered qwen_asr 0.0.6 has multiple transformers 5.x incompatibilities. Three are fixed in the fork; model load still fails at Qwen3ASRThinkerConfig.pad_token_id (a 4th), with more likely to follow. This task completes the deep port so the model loads and transcribes on transformers 5.11.0.

## The blockers (discovered, not exhaustive)

1. check_model_inputs decorator — FIXED (AC-1)
2. Qwen3ASRConfig.__init__ ordering (thinker_config before super) — FIXED
3. RoPE init fallback — FIXED
4. Qwen3ASRThinkerConfig.pad_token_id — NOT FIXED (model load fails here)
5. likely more in the modeling layer (cache_position docstring warnings, generate path)

## Proposed approach

Continue the fork at third_party/qwen-asr. Work through each modeling/config 5.x incompatibility until model load + transcribe succeed. The fork is already vendored and pinned via [tool.uv.sources]. Test iteratively: import → config instantiate → model load → transcribe a short clip.

## Acceptance criteria

- AC-1: Qwen3ASRModel loads on transformers 5.11.0. Verified by: python -c "from qwen_asr import Qwen3ASRModel; m = Qwen3ASRModel.from_pretrained('Qwen/Qwen3-ASR-0.6B')" exits 0.
- AC-2: qwen3-streaming backend transcribes Mandarin. Verified by: wlk serve --backend qwen3-streaming --language zh produces text from a Mandarin WAV.
- AC-3: stable_commit flush path is active. Verified by: backend log shows [qwen3-streaming] start_silence: flushed N words.

## Out of scope

- Upstreaming the fork. The vllm-metal loader swap. Any change to the check_model_inputs decorator itself.
