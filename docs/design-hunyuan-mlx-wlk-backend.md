# Design: in-process Hunyuan-MT-on-MLX translation backend for WLK

## Goal

Add an in-process Hunyuan-MT translation backend for WhisperLiveKit, running `tencent/Hy-MT2-1.8B` (and optionally 7B) via `mlx-lm` on Apple Silicon. This fills the gap WLK leaves: the qwen3 ASR backends are blocked from in-process NLLB (`core.py:321`) and told to use the AlignAtt sidecar (vLLM/CUDA only). An in-process MLX Hunyuan backend is the Apple-Silicon answer.

## Two tiers

**Tier A — plain in-process Hunyuan-MLX (the baseline, design first).**
`mlx-lm.stream_generate` with the `HUNYUAN_MT_PROMPT`. No attention capture. `wants_hypothesis_tail = False`. This is a correct, simple MT: accumulate committed source, translate on segment boundary, return `Translation`. This alone replaces the NLLB guard-removal hack with a proper backend.

**Tier B — simultaneous MT (the opt-in latency upgrade).**
`CapturedAttention` + the calibrated zh→en alignment heads + the commit policy + forced-prefill-delta-decode. `wants_hypothesis_tail = True`. Overlaps MT with ASR for ~1.4s latency win on long utterances (measured; see `_work/simul_mt_calibration_verdict.md`). Tier A is the floor; B is the opt-in.

## Contract impl (both tiers)

The duck-typed contract (`translation_alignatt.py:120-170`): `insert_tokens(items)`, `process() -> (Translation|None, TimedText buffer)`, `validate_buffer_and_reset()`, `insert_silence(duration)`, and the `wants_hypothesis_tail` flag.

**Tier A:**
- `insert_tokens(items)` — append committed `ASRToken`s to the current segment. Punctuation closes the segment (mirrors `translation_alignatt.py:145`).
- `process()` — if a closed segment exists, run `mlx-lm.stream_generate(HUNYUAN_MT_PROMPT + source)`, return `(Translation(text), buffer)`. Else return `(None, buffer)`.
- `validate_buffer_and_reset()` — flush the open segment at silence/speaker-change, translate, return `(Translation, buffer)`.
- `insert_silence(duration)` — no-op (or segment boundary).
- `wants_hypothesis_tail = False`.

**Tier B (adds the simultaneous path):**
- `wants_hypothesis_tail = True` — opts into the unstable tail via `_queue_hypothesis_tail_for_translation` (`audio_processor.py:312`).
- `insert_tokens` also accepts `HypothesisTail` (the unstable ASR tail). The MT drafts over the tail but commits only against committed source — the AlignAtt mechanism.
- `process()` runs the commit policy (`committed_target_tokens` from `simul_mt.py`): for each generated target token, check the top alignment head's attention argmax over the source span; commit if it lands on committed source, hold if on the tail. Held tokens release when ASR commits the tail, **without a new MT call** (the latency win).
- The calibrated heads (`ALIGNMENT_HEADS` in `simul_mt.py`, 23 zh→en heads for `hunyuan_v1_dense` 32×16) are the portable seam — just `(layer, head)` tuples.

## Registration

1. **translation_backend dispatch** (`core.py:305-330`): a new branch `elif config.translation_backend == "hunyuan-mlx"` that builds the backend. This sits alongside the existing `alignatt` and `nllb` branches.
2. **Extra** (`pyproject.toml`): `hunyuan-mlx = ["mlx-lm>=0.31.1"]`. mlx-lm is the only dep.
3. **Config knobs** (`config.py`): `hunyuan_mlx_model` (default `tencent/Hy-MT2-1.8B-8bit`; also `hunyuan-mt-7b-4bit`), `hunyuan_mlx_simul` (bool, tier A vs B), `hunyuan_mlx_commit_mode` (`mass` default; the measured best).
4. **parse_args** (`parse_args.py`): `--translation-backend hunyuan-mlx`, `--hunyuan-mlx-model`, `--hunyuan-mlx-simul`.

## Incremental generation for Tier B

The forced-prefill-delta-decode mechanism (livecaption `translate.py:_translate_simul_continue`): at finalization, prefill the committed tokens as **forced tokens** against the final prompt, then generate only the delta. This reuses the partial KV cache instead of re-decoding the whole utterance.

**Load-bearing: the EOS check.** `generate_step` does not auto-stop on EOS; the loop needs `if int(t) == eos: break`. A missing one masqueraded as a fundamental limitation (the "cache reuse is dead" finding that was actually a bug — see `_work/simul_incremental_design.md`). The design names this requirement explicitly; it's the single most likely implementation error.

This fits `process()` as: on finalization, call `_translate_simul_continue(prompt, committed_prefix)` → returns the delta text → emit as the finalized `Translation`.

## OpenCC placement — stays OUT of the MT backend

Production MT input is **raw Simplified Chinese** ASR output. `--opencc-mt` is off by default in livecaption; `--opencc s2twp` converts for **display only**. The MT backend gets Simplified (the LLM reads both forms identically). So OpenCC is a display-path concern, not the MT backend's job. Folding it into the backend would couple the backend to a display decision and break the clean backend contract. Resolve: **OpenCC stays in the display/render layer**, exactly as livecaption has it.

## Gaps and risks

1. **Sync translator vs async AudioProcessor.** `AudioProcessor.translation_processor` is `async def` (`audio_processor.py`), but it calls `self.translation.insert_tokens(item)` and `self.translation.process()` **synchronously** from the async loop (`audio_processor.py:910`). The contract is sync; the async wrapper just awaits nothing on the translator. So a sync Hunyuan backend fits cleanly — no threading wrinkle. mlx-lm's `stream_generate` is a blocking sync generator, called from the async loop; this is fine (it's the same shape as nllw's blocking `load_model`/translate). For long MT, the only concern is blocking the event loop — but nllw has the same property, and WLK accepts it.
2. **The simultaneous path's EOS requirement** (named above) — the single most likely implementation error; the design calls it out.
3. **Memory.** 1.8B-8bit (~2GB) is the production default and fits comfortably on Apple Silicon unified memory. The 7B-4bit (~4GB) is wired but the 7B's context-off behavior (livecaption `config.py` notes it ships no context template) means the simultaneous path (which needs context) may be 1.8B-only. The design states: Tier B is 1.8B-only until a 7B context template exists.
4. **transformers pin.** mlx-lm wants transformers 5.x; qwen3-asr-causal needs 4.57.6. They coexist on 4.57.6 (mlx-lm imports and runs fine on it). The Hunyuan-MLX backend works on 4.57.6 — verified this session. Not a blocker, but the pin dance is a fragility to document.

## Honest scope

This design covers the translation backend (both tiers). It does NOT cover: the ASR backend (separate, the nemotron/qwen3 designs), the overlay (client concern), the LCP comparison backend (`lcp_mt.py` is a benchmark artifact, not production), or the paper eval. The simultaneous path's MLX Q/K capture (`CapturedAttention`) is the heart of Tier B and is MLX-specific; a CUDA equivalent would be AlignAtt4LLM's `vllm_qk/observer.py` — out of scope for this Apple-Silicon design.
