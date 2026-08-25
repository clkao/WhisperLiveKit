---
title: mlx-qwen3-asr ASR backend (pure MLX, Apple Silicon)
status: backlog
source: livecaption port + this session's work
id: p0f67wa79kd56yh3bs0cca2e
---
# mlx-qwen3-asr ASR backend for WhisperLiveKit

## Goal

Add `mlx-qwen3-asr` (moona3k's pure-MLX Qwen3-ASR reimplementation) as a new
ASR backend for WLK. This is the Apple-Silicon qwen3 path that avoids the
torch/transformers pin conflict: `mlx-qwen3-asr` is pure MLX (no torch, no
transformers), so it coexists cleanly with `mlx-lm` and the `hunyuan-mlx`
translation backend on transformers 5.x.

## What ships

- `whisperlivekit/asr_mlx_qwen3.py` — `MlxQwen3AsrOnlineProcessor` wrapping
  mlx-qwen3-asr's `init_streaming`/`feed_audio`/`finish_streaming` behind WLK's
  `insert_audio_chunk`/`process_iter`/`start_silence`/`end_silence`/`finish`/
  `get_buffer` contract. Two-pass re-decode at `start_silence`/`finish`
  (re-decodes the accumulated utterance audio offline for clean text, no
  rolling-decode repetition). Warmup at init (absorbs Metal kernel compile).
- Registration: `_do_init` + `online_factory` in `core.py`; `mlx_qwen3_asr_*`
  config knobs; `--mlx-qwen3-asr-*` flags; `backend_support` available-check;
  BACKENDS entry (streaming: native, platform: darwin-arm64).
- The `mlx-qwen3-asr` extra in `pyproject.toml`.

## Acceptance criteria

- `wlk serve --backend mlx-qwen3-asr --language zh` transcribes Mandarin
  in-process, no torch/transformers dep, no WebSocket sidecar.
- The dep combo coexists with `mlx-lm` and `hunyuan-mlx` on transformers 5.x
  (document the working combo).
- Two-pass re-decode produces clean per-utterance text (no rolling-decode
  repetition) on utterances longer than the chunk size.
- Warmup at init; first real decode is not a cold-start stall.

## Notes

Working dep combo (measured this session): transformers==5.11.0,
huggingface_hub==1.18.0, mlx-lm>=0.31.1, mlx-qwen3-asr>=0.3.5,<0.4. The
transformers==4.57.6 pin from qwen3-asr-causal is the thing this avoids.
