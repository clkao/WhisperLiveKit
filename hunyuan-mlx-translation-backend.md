---
title: hunyuan-mlx translation backend (in-process Tencent Hy-MT2 via mlx-lm)
status: backlog
source: livecaption port + this session's work
id: bp5akt44cfke2akcttkkaag9
---
# hunyuan-mlx translation backend for WhisperLiveKit

## Goal

Add an in-process Hunyuan-MT translation backend running `tencent/Hy-MT2`
(1.8B-8bit default, 7B optional) via `mlx-lm` on Apple Silicon. This fills the
gap WLK leaves: the qwen3 ASR backends are blocked from in-process NLLB
(`core.py` guard) and told to use the AlignAtt sidecar (vLLM/CUDA only). An
in-process MLX Hunyuan backend is the Apple-Silicon answer.

## What ships (Tier A — plain mlx-lm, the baseline)

- `whisperlivekit/translation_hunyuan_mlx.py` — `HunyuanMlxTranslation`
  implementing the duck-typed contract: `insert_tokens`/`process`/
  `validate_buffer_and_reset`/`insert_silence`. `wants_hypothesis_tail=False`
  (Tier A; the simultaneous Tier B is a separate follow-up).
- The `HUNYUAN_MT_PROMPT` applied via `tokenizer.apply_chat_template` (Hunyuan
  is a chat model — a bare prompt hallucinates past EOS). Sampling params
  ported from the model card: temp=0.7, top_p=0.6, top_k=20,
  repetition_penalty=1.05. Warmup at init.
- Registration: `translation_backend == "hunyuan-mlx"` dispatch in `core.py`
  (alongside `alignatt` and `nllb`); `hunyuan_mlx_model` config knob;
  `--translation-backend hunyuan-mlx` + `--hunyuan-mlx-model` flags; the
  `mlx-lm` extra.
- Removes the stale `qwen3+NLLB guard` block in `core.py` (the proper backend
  makes the guard unnecessary, rather than the guard-removal hack).

## Acceptance criteria

- `wlk serve --backend mlx-qwen3-asr --translation-backend hunyuan-mlx
  --target-language en` produces correct zh->en translation in-process.
- The chat template is applied (no EOS runaway / hallucination).
- `validate_buffer_and_reset` returns empty when nothing to flush (no
  sentence doubling).
- Warmup at init; first real translation is not a cold-start stall.

## Out of scope (Tier B follow-up)

The simultaneous-MT variant (`CapturedAttention` + calibrated zh->en alignment
heads + commit policy + forced-prefill-delta-decode, `wants_hypothesis_tail=
True`) is a separate task. Tier A is the correct baseline; Tier B is the
opt-in latency upgrade (~1.4s win, overlaps MT with the ASR tail). The EOS
check requirement (a missing one masqueraded as a fundamental limit) is named
in the Tier B design doc.

## Notes

Working dep combo: transformers==5.11.0, huggingface_hub==1.18.0,
mlx-lm>=0.31.1. Coexists with mlx-qwen3-asr on the same combo. OpenCC s2twp
stays OUT of the MT backend (production MT input is raw Simplified; OpenCC is
display-path only).
