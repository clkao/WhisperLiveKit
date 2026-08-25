---
id: bp5akt44cfke2akcttkkaag9
title: hunyuan-mlx translation backend (in-process Tencent Hy-MT2 via mlx-lm)
status: backlog
source: WhisperLiveKit Apple-Silicon backend work
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

# hunyuan-mlx translation backend

## Goal

Add an in-process translation backend to WhisperLiveKit. The backend runs the Tencent Hy-MT2 model via mlx-lm on Apple Silicon.

The backend fills a gap. The qwen3 ASR backends cannot use the in-process NLLB translator. The only built-in translation path for qwen3 is the AlignAtt sidecar. The AlignAtt sidecar needs vLLM and CUDA. This backend needs no vLLM and no CUDA.

## What ships

- `whisperlivekit/translation_hunyuan_mlx.py`. The `HunyuanMlxTranslation` class implements the translation contract. The four methods are `insert_tokens`, `process`, `validate_buffer_and_reset`, and `insert_silence`.
- The `wants_hypothesis_tail` flag is `False`. The backend translates a segment only when the segment closes.
- The prompt uses the `HUNYUAN_MT_PROMPT` string. The backend applies the chat template via `tokenizer.apply_chat_template`. Hunyuan-MT is a chat model. A prompt without the chat template makes the model run past the end-of-sequence token.
- The sampling parameters are temp=0.7, top_p=0.6, top_k=20, and repetition_penalty=1.05. The model card gives these values.
- The backend warms up at init. The warmup runs one short decode so the Metal kernel compile does not stall the first real sentence.
- The `core.py` dispatch adds a `hunyuan-mlx` branch next to the `alignatt` and `nllb` branches.
- The `config.py` file adds the `hunyuan_mlx_model` knob.
- The `parse_args.py` file adds the `--translation-backend hunyuan-mlx` flag and the `--hunyuan-mlx-model` flag.
- The `pyproject.toml` file adds the `mlx-lm` extra.
- The stale `qwen3+NLLB guard` block in `core.py` is removed. The proper backend makes the guard unnecessary.

## Acceptance criteria

- Run `wlk serve --backend mlx-qwen3-asr --translation-backend hunyuan-mlx --target-language en`. The command produces a correct zh-to-en translation in-process.
- The backend applies the chat template. The model does not run past the end-of-sequence token.
- The `validate_buffer_and_reset` method returns empty when there is nothing to flush. The output text does not double.
- The warmup runs at init. The first real translation does not stall.

## Out of scope

The simultaneous-MT variant is a separate task. The variant captures Q/K attention, uses the calibrated zh-to-en alignment heads, applies a commit policy, and sets `wants_hypothesis_tail` to `True`. The variant overlaps the MT decode with the ASR tail and saves about 1.4 s on long utterances. This task ships the plain baseline only.

## Notes

The working dependency set is transformers 5.11.0, huggingface_hub 1.18.0, and mlx-lm 0.31.1. The set coexists with mlx-qwen3-asr. OpenCC s2twp stays out of the MT backend. The production MT input is raw Simplified Chinese. OpenCC is a display-path concern.
