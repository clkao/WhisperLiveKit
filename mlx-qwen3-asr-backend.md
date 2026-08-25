---
id: p0f67wa79kd56yh3bs0cca2e
title: mlx-qwen3-asr ASR backend (pure MLX, Apple Silicon)
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

# mlx-qwen3-asr ASR backend

## Goal

Add a new ASR backend to WhisperLiveKit. The backend runs the Qwen3-ASR model via the `mlx-qwen3-asr` package on Apple Silicon.

The `mlx-qwen3-asr` package is a pure-MLX reimplementation. The package needs no torch and no transformers. The backend coexists with mlx-lm and the hunyuan-mlx translation backend on transformers 5.x. The built-in `qwen3-streaming` backend pins transformers to 4.57.6. This backend avoids that pin.

## What ships

- `whisperlivekit/asr_mlx_qwen3.py`. The `MlxQwen3AsrOnlineProcessor` class wraps the `mlx-qwen3-asr` streaming API. The class exposes `insert_audio_chunk`, `process_iter`, `start_silence`, `end_silence`, `finish`, and `get_buffer`.
- The backend warms up at init. The warmup runs one short decode on silence so the Metal kernel compile does not stall the first real sentence.
- The `start_silence` and `finish` methods do a two-pass re-decode. The method re-decodes the accumulated utterance audio offline. The offline decode gives clean text with no rolling-decode repetition.
- The `core.py` file adds the `_do_init` branch and the `online_factory` branch.
- The `config.py` file adds the `mlx_qwen3_asr_*` knobs.
- The `parse_args.py` file adds the `--mlx-qwen3-asr-*` flags.
- The `backend_support.py` file adds the `mlx_qwen3_asr_backend_available` check.
- The `cli.py` file adds the BACKENDS entry. The entry sets `streaming` to `native` and `platform` to `darwin-arm64`.
- The `pyproject.toml` file adds the `mlx-qwen3-asr` extra.

## Acceptance criteria

- Run `wlk serve --backend mlx-qwen3-asr --language zh`. The command transcribes Mandarin audio in-process. The backend needs no torch, no transformers, and no WebSocket sidecar.
- The dependency set coexists with mlx-lm and the hunyuan-mlx backend on transformers 5.x. Document the working set in the install hint.
- The two-pass re-decode gives clean per-utterance text. The text has no rolling-decode repetition on utterances longer than the chunk size.
- The warmup runs at init. The first real decode does not stall.

## Notes

The working dependency set is transformers 5.11.0, huggingface_hub 1.18.0, mlx-lm 0.31.1, and mlx-qwen3-asr 0.3.5. The `qwen3-asr-causal` package pins transformers to 4.57.6. This backend does not use that package.
