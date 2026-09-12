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

## Decode hotfix (dispatch 2, commit 77a545a on wlk/voxtral-2602-mlx)

**Diagnosis correction (load-bearing).** The dispatch's premise —
`tokenizer.decode([id])` costing ~58ms/token (~21s of wall) — was a
**profiling artifact**. cProfile attributes GPU sync stalls (the per-token
`.item()`) to the executing frame and inflates C-extension timing;
isolated timing shows `tok.decode([id])` costs ~0.5ms/token
(739 calls: 0.00s total). The prior profile's 21s `tottime` in
`_decode_positions` was mostly sync stalls, not decode calls.

**What landed anyway (verified equivalent, kept):** `_piece_text` —
per-id memo of the O(1) rule (`'' if is_special` /
`byte_piece.decode(errors='replace') if is_byte` / `id_to_piece`),
replacing both per-token decode call sites. Equivalence verified three
ways: (1) 0 mismatches on all 165 unique ids the en+zh runs emit vs
`decode([id], IGNORE)`; (2) controlled same-process slow-vs-fast run on
zh_long: transcripts byte-identical; (3) interleaved A/B en+zh x2 rounds:
byte-identical 4/4. Unit tests: tests/test_voxtral_piece_text.py (4
tests — rule equivalence, special caching, lone-byte replacement char,
boundary-bookkeeping equivalence on a fixture stream). ruff clean.

**Measured truth (interleaved A/B, same process, alternating):**
en demo_en_30s: slow 35.8s / fast 35.0s (round0); zh_long: slow 57.1s /
fast 53.0s (round0). Round1 degraded across the board (58.1s en slow)
— **thermally contaminated machine; absolute RTF numbers unreliable
under sustained load**. Steady-state RTF is ~1.0-1.2 (en) — NOT the
<0.9 target. The RTF 1.38-1.44 baselines themselves carry the same
thermal caveat.

**The real bottleneck (measured, corrected):** per-token eager-mode
decoding — 361 sequential single-token forwards through 26 quantized
layers ≈ 500 small kernel launches + one `.item()` GPU sync per token.
Model math is ~11ms/token; launch/sync overhead is the rest. The fix is
`mx.compile` of the decode step, **blocked by SlidingKVCache's dynamic
slicing** (per-step varying slice bounds prevent static-shape
compilation). Needs a static ring-buffer cache in model.py — a model
change, outside this dispatch's scope; queued as the follow-up decision.

**New upstream bug discovered (not fixed — changes transcript contract):**
the zh transcript contains U+FFFD replacement chars (e.g.
"我们今天来\ufffd\ufffd论") because multi-byte CJK chars arrive as
consecutive byte pieces and per-token decoding of a lone continuation
byte cannot produce the real character. Present in the ORIGINAL code
(per-token decode behavior). Proper fix: buffer bytes across tokens and
decode complete UTF-8 sequences — improves zh text but is NOT
byte-identical to current output, so it needs its own decision.
