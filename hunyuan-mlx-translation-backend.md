---
id: bp5akt44cfke2akcttkkaag9
title: "mlx-llm-mt: generic decoder-LLM translation backend (Hunyuan-MT as first config)"
status: implementation
source: WhisperLiveKit Apple-Silicon backend work
started: 2026-08-25T17:18:01Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-hunyuan-mlx-translation-backend
issue:
pr:
gates:
    version: 1
    records:
        - id: gate:bp5akt44cfke2akcttkkaag9:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:bp5akt44cfke2akcttkkaag9-backlog-1
              briefing:
                id: briefing:bp5akt44cfke2akcttkkaag9:backlog:attempt-1:revision-1
                digest: sha256:5848b254fddb5b11c4aeefda4920fdb34634e9bf3dab0d072db3c3f3aaa9314d
                request-digest: sha256:f20cc3f4ef2df47c4918388f83521324d950e12800242022c529bbec8f679945
                room-ref: ./hunyuan-mlx-translation-backend/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:bp5akt44cfke2akcttkkaag9:backlog:1
                briefing: briefing:bp5akt44cfke2akcttkkaag9:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T17:17:47.088206Z"
                decision: approve
              application:
                target-stage: ideation
                state: consumed
        - id: gate:bp5akt44cfke2akcttkkaag9:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:bp5akt44cfke2akcttkkaag9-ideation-1
              briefing:
                id: briefing:bp5akt44cfke2akcttkkaag9:ideation:attempt-1:revision-1
                digest: sha256:7d646e239409088b99b430c63eab100c2ae8dc16ad1f6ffc64647ca6d5655988
                request-digest: sha256:2414bb531f45e98a4ea6e334510fc2c629ba0e36530978e4a7e52eb12cc06042
                room-ref: ./hunyuan-mlx-translation-backend/review/ideation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:bp5akt44cfke2akcttkkaag9:ideation:1
                briefing: briefing:bp5akt44cfke2akcttkkaag9:ideation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T17:17:50.252027Z"
                decision: approve
              application:
                target-stage: implementation
                state: consumed
---

# mlx-llm-mt: generic decoder-LLM translation backend

## Goal

Add an in-process translation backend to WhisperLiveKit that runs a
decoder-LLM MT model via mlx-lm on Apple Silicon. The backend is generic;
Hunyuan-MT is the first config, not the identity of the backend.

The backend fills a gap. The qwen3 ASR backends cannot use the in-process NLLB
translator (NLLB is an encoder-decoder; the contract differs). The only
built-in translation path for qwen3 is the AlignAtt sidecar. The AlignAtt
sidecar needs vLLM and CUDA. This backend needs no vLLM and no CUDA.

## Why generic, not HY-specific

The existing `translation_hunyuan_mlx.py` works end-to-end, but its model
identity is baked into the code: the prompt, the EOS token string, and the
model registry are hardcoded for Hunyuan. The pipeline underneath is generic:
`mlx_lm.load` accepts any HF repo with MLX weights; `apply_chat_template` is
any chat model; `stream_generate` is mlx-lm; the 5-method WLK contract is
shared with NLLB and AlignAtt.

A decoder-LLM MT model (Hunyuan, TranslateGemma, Aya, Qwen-MT) differs only
in three config values: the prompt template, the EOS token, and the model
registry. The decode loop and the contract are shared. The refactor extracts
the shared base and externalizes the three config values. This keeps the
forthcoming Tier B simultaneous-MT port (the `CapturedAttention` + commit
policy + calibrated heads) model-agnostic — it works on any decoder LLM with
alignment heads, not just Hunyuan.

## What ships

- `whisperlivekit/translation_mlx_llm_mt.py`. The `MlxLlmTranslation` generic
  base class. Implements the 5-method WLK contract (`insert_tokens`,
  `process`, `validate_buffer_and_reset`, `insert_silence`,
  `wants_hypothesis_tail`). Takes a `prompt_template`, an `eos_token` (or
  reads it from the tokenizer), and a model registry. Does the mlx-lm load,
  chat-template prompt, stream-generate, warmup, the duck-typed return types
  (`whisperlivekit.timed_objects.Translation`/`TimedText`).
- A model-config registry. Each entry declares: short name → HF repo, prompt
  template, EOS token, sampling params. Hunyuan-MT is one entry
  (`hy-mt2-1.8b-8bit`, `hy-mt2-1.8b-4bit`, `hy-mt2-7b-4bit`,
  `hunyuan-mt-7b-4bit`, `hunyuan-mt-7b-8bit`). The config is data, not code.
- The `core.py` dispatch: rename the `hunyuan-mlx` branch to `mlx-llm-mt`,
  select the model config by the `--mlx-llm-mt-model` flag.
- `config.py`: `mlx_llm_mt_model` knob (replaces `hunyuan_mlx_model`).
- `parse_args.py`: `--translation-backend mlx-llm-mt` and
  `--mlx-llm-mt-model`.
- `pyproject.toml`: the `mlx-lm` extra.
- Remove the stale `qwen3+NLLB guard` in `core.py` (the backend makes it
  unnecessary).
- Backward-compat alias: `--translation-backend hunyuan-mlx` still works
  (maps to `mlx-llm-mt` with the default Hunyuan config) so the existing
  verified invocation does not break.

## Acceptance criteria

**AC-1 — The backend translates zh→en in-process via mlx-lm.**
Verified by: `wlk serve --backend mlx-qwen3-asr --translation-backend
mlx-llm-mt --target-language en` produces a correct zh-to-en translation.

**AC-2 — The chat template is applied; no runaway past EOS.**
Verified by: the output text does not ramble or repeat; the decode stops at
EOS. (The bare-prompt bug the chat template fixed must not regress.)

**AC-3 — `validate_buffer_and_reset` does not double the output.**
Verified by: at a silence boundary, the method returns the translation once;
the output text does not appear twice.

**AC-4 — Hunyuan is one config, not the backend identity.**
Verified by: a second config entry (e.g., a placeholder for TranslateGemma)
loads with a different repo + prompt without new code — only the config dict
changes. (A dry import/construct check suffices; no need to download a
second model.)

**AC-5 — The backward-compat alias works.**
Verified by: `--translation-backend hunyuan-mlx` still produces the same
output as before (maps to mlx-llm-mt + Hunyuan default).

**AC-6 — Warmup at init; first real decode does not stall.**
Verified by: the first real translation returns within normal latency
range (no one-time Metal-compile stall).

## Out of scope

- **Tier B simultaneous MT** (the `CapturedAttention` MLX Q/K observer +
  calibrated zh→en heads + commit policy + `wants_hypothesis_tail=True`).
  This is the ~1.4s latency win. It subclasses the generic base and adds the
  attention capture. Separate task. Needs this refactor first so it is
  model-agnostic from the start.
- **New model configs beyond Hunyuan.** The architecture supports them; this
  task ships Hunyuan only. A second real config is AC-4's dry check, not a
  shipped model.
- **OpenCC** (s2twp display-path conversion stays out of the MT backend;
  production MT input is raw Simplified Chinese).

## Notes

Working dependency set: transformers 5.11.0, huggingface_hub 1.18.0,
mlx-lm >= 0.31.1 (install with `--no-deps`; metadata wants transformers 5.x
but runs on 5.11.0). Coexists with mlx-qwen3-asr.

The existing `translation_hunyuan_mlx.py` is the starting point — refactor
it, don't rewrite from scratch. The two-pass re-decode, the sampling params,
and the warmup are all correct and stay.
