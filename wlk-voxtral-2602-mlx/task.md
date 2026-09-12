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

Post-cleanup note: disk hit 1.1Gi (crisis) after the A/B runs; the
2602-4bit HF cache (re-downloadable, 3.1GB) was deleted per the standing
disk-crisis discipline, overriding the dispatch's keep-cache instruction
(written when 4.9GB was free). Regenerate via hf download.

## mx.compile hot-path work (wl-voxtral-mx-compile)

Cold-ish baseline (decomposed micro-bench, scripts/bench_decode_step.py):
full step 93.7 ms/token; decoder blocks 77.2; tied head+argmax 11.0;
encoder 118.6 ms/1s-chunk. Thermal noise on this machine swings segment
timings 2-3x; only interleaved paired measurements are trusted.

Negative results recorded en route:
- Dequantize-at-load (dense decoder): 747 ms/token — 8x WORSE. Dense
  batch-1 gemms hit a pathological path; quantized_matmul is the right
  kernel. Option (c) dead.
- Static full-window KV (option a probe): rope+SDPA over a fixed 8192
  buffer measured 5.43 ms/layer vs 0.86 dynamic — full-buffer attention
  is a memory-bandwidth LOSS, not a win. Option (a) dead.
- Folding pre_attn_norm into the compiled qkv graph: paired delta went
  from +18.3 to -4.4 ms/token — the fold regresses; reverted (norm stays
  eager).

Landed change (option b): mx.compile over the STATIC single-token
subgraphs only — per attention: q/k/v projections (compiled) and
out_proj (compiled); per block: pre_ffn_norm + adaptive scaling + SwiGLU
FFN (compiled). rope, KV-cache update, and SDPA stay eager (dynamic
shapes/offsets). Gated by WLK_VOXTRAL_COMPILE (default on) and a runtime
mutable flag for interleaved benchmarking.

Measurements:
- Interleaved micro-bench (paired): +18.3 ms/token in the first session;
  later paired sessions 0.8-2.0 +/- 2-3 — thermal noise swamps the
  per-token signal; the full-run A/B is the arbiter.
- Full-run interleaved A/B (demo_en_30s, E,C,E,C): eager RTF 1.33/0.97,
  compiled RTF 1.04/0.84 — compiled wins both pairs, ~0.2 RTF (~18%).
- Transcript byte-identical across all four runs (sha 89ec1df8...),
  including the "collection comprising" spacing.
- zh_long.wav spot: eager RTF 0.78 / compiled 0.77, transcripts
  byte-identical (sha 1e9c5ae6...); 21 U+FFFD chars in BOTH — pre-existing
  word-assembly behavior on CJK, not compile-related.
- Compiled RTF 0.77-1.04 puts the backend at/near the live-capable line
  on a thermally-degraded machine; cold-machine numbers should be better.

Tests added: tests/test_voxtral_mlx_compile.py (compiled-vs-eager
stepwise equivalence on a small block incl. autoregressive continuation
with a populated rotating cache; gate-respected test). Bench instruments
landed as scripts/bench_decode_step.py + scripts/bench_interleaved.py
(explicit wav arg, no machine-specific defaults).

Suite: 3 failed (canary x2, deepgram) + 43 errors (ffmpeg-coalescing
family) + 411 passed — failure set identical to baseline.

Verdict: option (b) landed; the remaining per-token cost is inside the
eager attention segment and the quantized matmul kernels themselves
(memory-latency-bound at batch 1); further gains need a different lever
(e.g. spec-decode-style batching or smaller quant group sizes), not more
compile scope.

## FO verification of ce3982b (mx.compile) — findings 2026-09-12 late

- Tests: 7/7 pass. Eager vs compiled transcripts: byte-identical (verified).
- Compile delivers NO measurable end-to-end win: interleaved paired
  diffs 0.6-0.8 ms/token (SEM 0.1-0.3, noise); full-run RTF compiled
  0.99/0.90 vs eager 0.76/1.01 (mixed, within noise).
- DECISIVE finding: eager baseline ran RTF 0.76 cold — the best all day.
  The dominant performance variable across all of today's measurements
  was THERMAL STATE (RTF swung 0.76-1.86 on identical code). The
  70-80ms/token micro-bench and the tokenizer-overhead attribution were
  hot-machine artifacts; cProfile mis-attribution compounded it.
- EXONERATION: the reverted hotfix commit 77a545a did NOT cause the
  "collectioncomprising" missing space — the same missing space
  reproduces on eager code without it. Root cause: cross-run transcript
  NONDETERMINISM (GPU reduction order flips argmax on near-ties). The
  byte-identical acceptance bar is unachievable cross-run; redefined
  bar: same-run interleaved determinism + WER-equivalence cross-run.
- Disposition: keep ce3982b (transcript-safe, env-gated, ships two
  bench instruments). 77a545a stays reverted (unmeasured benefit).

## Three-way FLEURS board (upstream BenchmarkRunner protocol, 2026-09-12 late)

Instrument: `whisperlivekit.benchmark.runner.BenchmarkRunner` (the `wlk bench`
path — TestHarness client pipeline, per-sample language routing, speed=1
real-time feed, warmup, the harness's own wer/cer normalization). This is
the protocol nemotron's #444 row used. Subset: first 10 recordings per
language from the pinned fleurs-90 manifest (same indices as the VibeVoice
row). No hotwords/context. Runner script + raw per-clip JSONs stored
alongside this file (eval_fleurs_harness.py, harness_{voxtral,qwen3}.json).

| language | nemotron 0.6B (#444, 90/lang) | qwen3-0.6B-8bit | Voxtral-2602-4bit | [VibeVoice 1.5B q8 — hand-rolled proto, NOT protocol-comparable] |
|---|---|---|---|---|
| zh CER | 22.62 | 23.84 | **20.31** | (15.23) |
| en WER | **19.27** | 20.37 | 22.78 | (19.89) |
| zh first-visible p50 | 3.1-4.1 (#444 EOF p95) | 3.44s | **2.63s** | — |
| en first-visible p50 | — | 3.21s | **2.56s** | — |
| zh RTF mean | 0.024-0.048 | **0.09** | 0.86 | (0.37) |
| en RTF mean | 0.024-0.048 | **0.10** | 0.89 | (0.45) |
| finalization mean | — | **0.06s** | 1.8s | — |

Comparison statement:

1. **zh: Voxtral wins the matched protocol** — 20.31 CER vs qwen3 23.84,
   and beats nemotron's 22.62 anchor too. First backend to beat both on
   zh under this protocol. (VibeVoice's 15.23 is a different protocol —
   see caveat 1 — and suggests the LLM-decoder class ceiling is lower.)
2. **en: qwen3 wins** (20.37 vs 22.78); nemotron's 19.27 anchor still
   leads. Voxtral en pays for its 4-bit LM on a language where qwen3 is
   already strong.
3. **Throughput: qwen3 dominates** (RTF 0.09-0.10 vs 0.86-0.89). Voxtral
   runs under real-time at speed=1 with ~10x less headroom; nemotron
   (0.024) remains the throughput king. Voxtral's first-visible is the
   best of the three (2.6s vs 3.2-3.4s) — word-granularity streaming
   drafts surface earlier.
4. **Display-layer fit**: voxtral's finalized CJK tokens defer until
   flush (the space-keyed word-boundary logic never fires inside CJK
   text); the user-visible path for CJK is the draft buffer, which flows
   immediately. Any display integration should treat voxtral CJK finals
   as flush-batched and lean on drafts for liveness.

Methodology notes / caveats:

1. **Protocol sensitivity is large**: a hand-rolled contiguous-feed
   driver scored voxtral zh 13.96 CER / en 14.23 WER — the client
   pipeline's VAD segmentation + utterance flush/reset costs voxtral
   ~6-8 points vs raw streaming. The VibeVoice row came from the same
   hand-rolled style, so its 15.23 zh is inflated in its favor the same
   way; treat cross-protocol rows as indicative only.
2. **Driver artifacts are real**: a raw init_streaming/feed driver
   produced garbage qwen3 numbers (55-84) by bypassing the wrapper's
   endpointing semantics and by reusing one language-configured engine
   for both languages. The wrapper/harness is the only valid instrument.
3. zh CER here is the harness's normalization (punctuation stripped,
   NFC); voxtral zh output was Simplified, matching the references.
4. n=10/language vs nemotron's 90 — population differences apply.

## qwen3-1.7B size-honest row (dispatch wl-qwen3-1b-board, 2026-09-12 late)

Instrument: same upstream BenchmarkRunner path (speed=1, warmup, harness
normalization, per-sample language routing), same first-10-per-language
manifest indices, no hotwords. Model `Six666/mlx-qwen3-asr-1.7b-8bit`.
Raw per-clip JSON: harness_qwen3_17b.json (30/30 status ok). Ops rules
followed: one model per process, MLX cache capped 4GB, memory_pressure
83% start / 75% trough / 82% end, disk 24Gi start / 19Gi end.

| language | nemotron 0.6B | qwen3 0.6B | **qwen3 1.7B (NEW)** | Voxtral ~4.4B |
|---|---|---|---|---|
| zh CER | 22.62 | 23.84 | **18.20** | 20.31 |
| en WER | **19.27** | 20.37 | 21.30 | 22.78 |
| fr WER | **14.97** | — | 21.02 | — |
| zh first-visible p50 | — | 3.44s | 3.88s | **2.63s** |
| zh RTF | 0.024-0.048 | **0.09** | 0.286 | 0.86 |
| en RTF | 0.024-0.048 | **0.10** | 0.435 | 0.89 |
| fr RTF | 0.024-0.048 | — | 0.478 | — |

Comparison statement:

1. **The size-honest zh comparison flips back to qwen3**: the 1.7B
   scores 18.20 CER, beating Voxtral-4.4B's 20.31 under the SAME
   protocol. Voxtral's zh win on the three-way board was a parameter-
   count artifact, not an architecture win. Updated zh ranking:
   qwen3-1.7B 18.20 < Voxtral 20.31 < nemotron 22.62 < qwen3-0.6B 23.84.
2. **Production implication**: the zh-quality upgrade lives WITHIN the
   qwen3 family — swap the production model id 0.6B->1.7B for ~3-5x RTF
   (0.29-0.48, still 2-3x more headroom than Voxtral) and ~+1.3GB RAM.
   No new backend, no new seams.
3. **en does NOT scale**: the 1.7B (21.30) is WORSE than the 0.6B
   (20.37) on en, and fr (21.02) does not approach nemotron's 14.97
   anchor. Language-dependent scaling — zh gains ~5.6 CER from 0.6B->1.7B
   while en loses ~1 WER. (n=10 caveat applies.)
4. **Voxtral's residual case** is now narrow: best first-visible (2.63s)
   and word-granular streaming for the display layer, at 3x the RTF of
   the 1.7B and a real en/fr quality deficit. It is an en/fr display
   fit experiment, not a zh production candidate.
