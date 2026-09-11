# Task: wlk-voxtral-2602-mlx

Support the 2602-generation MLX Voxtral checkpoint
(`mlx-community/Voxtral-Mini-4B-Realtime-2602-4bit`) in the `voxtral-mlx`
backend without regressing the 6bit sibling.

## Dispatch

`/tmp/spacedock-dispatch/wl-voxtral-2602-mlx.md` (ensign run, branch
`wlk/voxtral-2602-mlx`, unpushed).

## Findings

1. **Architecture is identical across generations** — encoder 32x1280,
   decoder 26x3072 GQA-8 (n_kv_heads=8), hidden 9216, head_dim 128,
   sliding windows 750/8192, tied embeddings. The existing model code
   already handles all of it (GQA in `_DecoderAttention`, tied output head
   via `as_linear`). No architectural work was needed.
2. **Config schema is NOT** — the 2602 conversion flattens the config
   (`decoder.*` + top-level `encoder_args` with inline `downsample_factor`)
   where the 6bit sibling nests (`multimodal.whisper_model_args.*`). Fixed
   with `_normalize_config` (pure re-keying; nested configs pass through
   unchanged; unknown schemas raise).
3. **Weight naming is a third family** — Mistral-style prefixed names
   (`decoder.layers.N.attention.wq`, flattened `feed_forward_wN`,
   `ada_rms_norm_t_cond.ada_down/ada_up` instead of sequential indices).
   Added `_V2602_RULES` + `_remap_v2602_name`, selected by key prefix.
   The `.bias`-key pattern (q/v/out have biases, k doesn't; FFN down has
   bias) matches the model's wiring exactly.
4. **Quantization inventory differs per checkpoint** (the load-blocking
   discovery): the 2602 checkpoint leaves the token embedding AND the
   adaptive-scale projections in bf16, while the old loader quantized by a
   shape heuristic. A strict load failed with 58 missing params. Fix: the
   quantized-module set is now derived from the checkpoint's own `.scales`
   keys. On top of that, the tied output head (embedding) and `proj_in`
   are force-quantized at load from their own bf16 weights with the
   checkpoint's bits/group-size — leaving the tied head unquantized turns
   every decode step into a full bf16 [131072, 3072] matmul (measured
   ~1.8x slower, ~1.5 GiB larger). `proj_out` cannot be quantized (32-dim
   input < group size 64).
5. **Converted-path load is now strict**: unrecognized weight keys raise
   instead of being silently skipped (the silent-skip was the bug class
   the VibeVoice q8 work flagged).

## Verification

- 2602-4bit loads strictly in ~2s (406 checkpoint-quantized modules +
  27 force-quantized stragglers); 6bit sibling loads strictly (435
  quantized — its embedding IS quantized in-checkpoint; per-checkpoint
  derivation handles both).
- Smoke: demo_en_30s.wav through `VoxtralMLXOnlineProcessor` — coherent
  English with word timestamps, same known error family as prior runs
  (PaLM → "PRAM"/"Pronting").
- A/B (same clip, warmup, peak-memory via `mx.metal.get_peak_memory`):
  - 2602-4bit: RTF 1.284/1.309, peak 3.76 GiB (two runs)
  - 6bit:      RTF 1.141/1.423, peak 4.10-4.11 GiB (two runs)
  - Verdict: **speed tied within machine noise**; **memory ~8% lower**
    for the 4bit. The 2602 generation is NOT faster in practice — its
    value is the memory reduction.
- New unit tests: `tests/test_voxtral_mlx_config.py` (5 tests: flattened
  normalisation, nested pass-through, idempotence, unknown-schema raise,
  real-model construction incl. GQA/tied-embedding wiring). All pass.
- Full suite: failure set IDENTICAL to integration-2 baseline
  (3 failed canary×2/deepgram + 43 ffmpeg-coalescing errors; 409 passed).
  Environment note: the worktree needed `git submodule update --init
  third_party/qwen3-asr-causal` (the qwen3 shim tests read the vendored
  checkout; a fresh worktree lacks it).
- ruff clean on changed files.

## Residual risks

- The force-quantized 4-bit output head slightly changes tail-token
  logits vs the checkpoint author's bf16 intent; smoke text identical,
  full quality eval is follow-up.
- The A/B harness is the naive 1s-chunk streaming loop — absolute RTF
  values carry harness overhead; only the relative comparison is claimed.
- Checkpoint cache (~3.1GB in ~/.cache/huggingface) deleted after
  measurement per disk discipline; re-downloadable.
