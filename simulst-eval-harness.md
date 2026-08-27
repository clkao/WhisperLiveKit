---
title: SimulST eval harness — MLX IWSLT anchor + flagship compare
status: implementation
worktree: ""
id: 8zdhkj86eqshqypzzme2v6ss
gates:
    version: 1
    records:
        - id: gate:8zdhkj86eqshqypzzme2v6ss:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-backlog-1
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:backlog:attempt-1:revision-1
                digest: sha256:f27ce53e5ca2e7f8638a80912e575eb26bf38dc7f3d735b6bc9bc6b0187e8315
                request-digest: sha256:41f947b510293c408f37c049ec6753d2a0cc6737305baae64c1f5b59d828f61e
                room-ref: ./simulst-eval-harness/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:backlog:1
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-27T19:46:33.81354Z"
                decision: approve
                reason: 'Captain direction: file and dispatch. Emitter is simple (timestamp per emitted word). Baseline anchor + flagship compare is the eval purpose.'
              application:
                target-stage: ideation
                state: consumed
        - id: gate:8zdhkj86eqshqypzzme2v6ss:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-ideation-1
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:ideation:attempt-1:revision-1
                digest: sha256:0769ce1c1e72ba17c7ae35b0f99a6cc9dc8f77a8fc74de4e670aba3d2804ad69
                request-digest: sha256:ba74cbfb12684f889d00029cc598ad1fed7a090873f3cf4263f72b5742220da1
                room-ref: ./simulst-eval-harness/review/ideation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:ideation:1
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:ideation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-27T21:30:00.799924Z"
                decision: approve
                reason: Captain approval. Concrete plan (3 scripts, no lib changes), two-stage TimestampSource abstraction is the broadly-useful artifact, 4 sharpened ACs, en->zh heads resolved. Advance to implementation.
              application:
                target-stage: implementation
                state: consumed
started: 2026-08-27T19:46:38Z
---

A SimulST evaluation harness that runs our MLX ASR+MT cascade over the
AlignAtt4LLM IWSLT 2026 devset and scores it with XCOMET-XL + LongYAAL via the
existing `alignatt-eval` scorer. Two purposes:

1. **Baseline anchor** — one reproducible entry on the IWSLT devset (en→zh) so
   our results connect to what others benchmark. Not a full reproduction of the
   paper's numbers; a comparable entry on the same devset + same scorer.
2. **Flagship compare** — once the anchor exists, run our flagship setup
   (nemotron-mlx transducer + Hy-MT2-1.8B simul-MT with en→zh heads) on the same
   devset and compare against the anchor + the paper's reference anchors.

## Why this is small (the pieces already exist)

The existing `alignatt-batch` harness is its own CUDA cascade (forced-align
ASR + vLLM MT) and does NOT drive our WLK/MLX stack. But its pieces are already
ported or available in MLX:

- **MT (AlignAtt simul)** — PR2 (`translation_mlx_llm_mt_simul.py` +
  `simul_mt_capture.py`) is the MLX port of the AlignAtt commit policy +
  bit-identical Q/K capture. Done.
- **ASR (forced-align, time frontier)** — `mlx-community/Qwen3-ForcedAligner-0.6B-4bit`
  + `mlx_audio.stt.models.qwen3_asr.qwen3_forced_aligner` is a native MLX port
  of the exact forced-aligner the paper uses. Loadable now. (The nemotron-mlx
  transducer — separate entity, in implementation — gives a time-based frontier
  too, via `AlignedToken.start`; complementary, not required for the anchor.)
- **Scoring** — `alignatt-eval` (AlignAtt4LLM) wraps `omnisteval.evaluate_instances`
  + `resegment` + `write_evaluation_outputs`, defaulting to `Unabel/XCOMET-XL`.
  Scores `hypothesis.jsonl` → XCOMET-XL (quality) + LongYAAL (latency). No port
  needed; MLX-agnostic.
- **IWSLT devset refs** — `AlignAtt4LLM/data/devset/ref/{en,zh,it,de}.txt`
  (919 lines each, aligned) + `audio-segments.yaml` are tracked. Audio files
  (`*.wav`) are NOT tracked (gitignored); must be sourced from the IWSLT 2026
  shared task.

## The one real gap — hypothesis emitter (simple)

`alignatt-eval` scores a `hypothesis.jsonl` (one record per audio). The record
shape (from `alignatt4llm/artifacts.py:build_asr_hypothesis_record`):

```json
{
  "source": ["OiqEWDVtWk.wav"],
  "source_length": 12345.0,
  "prediction": "the full transcription or translation text",
  "delays": [ms per word at which the system emitted it],
  "elapsed": [normalized wallclock ms per word],
  "elapsed_semantics": "ca_compatible_incremental"
}
```

The emitter hooks our cascade's per-word emission: for each committed word,
record (a) the audio-processed-time at emission (`delays`, in ms) and (b) the
wallclock at emission (`elapsed`, in ms). The cascade already emits words; we
just timestamp them. The normalizer
(`normalize_computation_aware_timestamps`) + the builder both live in
`alignatt4llm.artifacts` — importable, no rewrite.

So the emitter is: run our MLX ASR+MT over each devset audio, timestamp each
emitted word, call `build_asr_hypothesis_record` (or write the dict directly),
emit one `hypothesis.jsonl` per run + a `manifest.json`. Then `alignatt-eval`.

## Acceptance criteria

- AC-1: A `hypothesis.jsonl` emitter exists and round-trips through
  `alignatt-eval` producing non-null XCOMET-XL + LongYAAL on one devset audio.
  Verified by: a single-audio smoke run producing a scored `evaluation.json`.
- AC-2: The anchor run (en→zh, forced-aligner ASR + Hy-MT2-1.8B simul-MT) scores
  on the full 919-line devset. Verified by: `alignatt-eval` over all devset
  audios producing a devset-level score.
- AC-3: The emitter works for both ASR-only (transcribe) and ASR+MT (translate)
  modes. Verified by: two `hypothesis.jsonl` files, one per mode, both scored.
- AC-4: The flagship run (nemotron-mlx + Hy-MT2-1.8B simul-MT, en→zh heads)
  drops into the same harness. Verified by: swapping the ASR frontend in the
  runner and producing a scored devset run.

## Open dependencies

- **IWSLT devset audio** — refs + segmentation tracked in `AlignAtt4LLM/data/devset/`;
  audio wavs gitignored, must be sourced (IWSLT 2026 shared task download).
- **en→zh heads for Hy-MT2-1.8B** — backgrounded (separate slow task); the
  anchor can run with zh→en heads' mirror or fall back to serial MT if en→zh
  heads aren't calibrated yet. Flagship compare needs them.
- **nemotron-mlx** — in implementation (separate entity); flagship compare
  needs it. Anchor uses the forced-aligner, not blocked.

## Stage Report: ideation

- DONE: Produce the ideation (implementation plan + ACs + test plan) for the SimulST eval harness
  Concrete plan, sharpened AC-1..AC-4, and a staged test plan below; risk evidence gathered from the actual AlignAtt4LLM scorer, PR2 simul-MT, forced-aligner, and the eval venv.

### Selected approach

The harness is three pieces, all small, all reusing existing code:

1. **Emitter** (`WhisperLiveKit/scripts/simulst_emit.py`, ~250-350 lines) — the one real build. Runs our MLX cascade over one devset audio file, hooks the per-word emission, timestamps each emitted word, and writes a `hypothesis.jsonl` (one record per audio) + `manifest.json` into a run output dir. It does NOT re-implement the scorer or the cascade; it drives the cascade and records emission events.
2. **Runner** (`WhisperLiveKit/scripts/simulst_run.py`, ~120-200 lines) — drives the emitter over the 21 devset audios (or a single-audio smoke), then invokes `alignatt-eval` over the collected `hypothesis.jsonl`. Mode flag selects ASR-only (transcribe, prediction = source-language text) vs ASR+MT (translate, prediction = target-language text). ASR-backend flag selects the anchor (mlx-qwen3-asr + forced-aligner) vs the flagship (nemotron-mlx).
3. **Eval** — the existing `alignatt-eval` CLI (AlignAtt4LLM `alignatt4llm.cli.evaluate`), invoked by the runner with `--output-dir <run> --speech-segmentation <devset/audio-segments.yaml> --target-reference <devset/ref/zh.txt> --source-reference <devset/ref/en.txt> --target-lang-code zh`. No port, no new scoring code.

The emitter mirrors `alignatt4llm.cli.batch.run_single_audio`'s shape (the CUDA cascade's emitter), but drives the WLK/MLX cascade instead. The key reuse: `alignatt4llm.emission.register_translation_words` / `register_translation_timestamps` (LCP word-diff registration, language-aware — char-level for zh) and `alignatt4llm.artifacts.normalize_computation_aware_timestamps` (the CA-compatible normalizer) are imported directly. The hypothesis record is written via the same dict shape as `build_asr_hypothesis_record` / `InferenceArtifacts.hypothesis_record`.

### Semantic changes (what the emitter records, precisely)

For each committed/emitted word of the **prediction** (transcription in ASR-only mode; translation in ASR+MT mode):
- `delays[i]` = audio-processed time (ms) at which the system *emitted* word i = the chunk-boundary audio time of the chunk that flushed that word. This is the SimulEval/LongYAAL emission-latency semantic. It is **NOT** the acoustic position of the word (the forced-aligner's `start_time`/`end_time`) — `build_asr_hypothesis_record`'s docstring warns explicitly that using `end_time_s` collapses LongYAAL below the chunk length, which is physically impossible. The forced-aligner's acoustic timestamps feed the AlignAtt commit-policy frontier (which source words are committed), NOT the hypothesis `delays`.
- `elapsed[i]` = wallclock (ms) at which that chunk finished processing, then normalized to CA-compatible incremental form via `normalize_computation_aware_timestamps(delays, elapsed)`.
- `prediction` = the full final prediction text; for zh target, `prediction_text_from_target_surface` applies char-level surface (each non-whitespace char is a unit).
- `source` = `[wav_name]`; `source_length` = `audio_duration_ms`; `elapsed_semantics` = `"ca_compatible_incremental"`.

The manifest records `schema_version: cascade_v1`, `target_language_code`, `runtime_config.hypothesis_elapsed_semantics`, so `alignatt-eval`'s `resolve_fix_emission_ca` sees CA-compatible semantics and skips the legacy fix.

### Two-stage ASR frontier (the timestamp-source abstraction)

The emitter has a single seam — a `TimestampSource` that, given a chunk's audio and its emitted text, returns per-word source-accessibility times (the frontier the MT commit policy reads against). Two implementations:
- **Anchor** (`ForcedAlignTimestampSource`): after each chunk closes, run `mlx-community/Qwen3-ForcedAligner-0.6B-4bit` (via `mlx_audio.stt.models.qwen3_asr.qwen3_forced_aligner`) over the chunk audio + chunk text to get per-word acoustic timestamps; words whose timestamp < chunk end are accessible. Post-hoc within the chunk. The `delays` are still the chunk-boundary audio time (not the aligner's acoustic position).
- **Flagship** (`NativeTokenTimestampSource`): nemotron-mlx's mid-decode `AlignedToken.start` (from `livecaption/asr.py:_decode_chunk`'s `self._hypothesis`) gives real-time per-word source timestamps as they're decoded; no post-hoc aligner call. The MT commit policy reads these directly.

Both produce the same hypothesis record shape; only the commit-policy frontier granularity differs. The abstraction is one small class with two subclasses — the broadly-useful artifact regardless of the comparison outcome (it also unblocks the livecaption no-timestamp-adapter next step).

### Expected files and lines (with tolerance)

| File | LoC (est.) | Role |
|---|---|---|
| `WhisperLiveKit/scripts/simulst_emit.py` | 250-350 | Emitter: load cascade, drive one audio, timestamp emissions, write hypothesis.jsonl + manifest.json |
| `WhisperLiveKit/scripts/simulst_run.py` | 120-200 | Runner: iterate devset audios (or smoke single), invoke emitter per audio, then `alignatt-eval` |
| `WhisperLiveKit/scripts/simulst_timestamp.py` | 80-140 | `TimestampSource` + `ForcedAlignTimestampSource` + `NativeTokenTimestampSource` (the frontier abstraction) |
| `WhisperLiveKit/scripts/simulst_devset.py` | 40-80 | devset loader: parse `audio-segments.yaml`, map wav→segments, resolve audio paths |
| `WhisperLiveKit/scripts/README_simulst_eval.md` | 60-100 | runbook: env setup (eval venv + editable alignatt4llm), the two audio-source dependencies, the one-liner smoke + full commands |

Total: ~550-870 lines, all scripts (no library changes). The cascade, the MT simul backend, the forced aligner, and the scorer are all imported as-is. Tolerance: ±30% per file; the emitter is the only piece with real logic.

### Risk evidence (probed, not asserted)

1. **Scorer confirmed importable**: `_eval_venv/bin/python -c "import sys; sys.path.insert(0,'AlignAtt4LLM/src'); from alignatt4llm.cli.evaluate import main"` → OK. `alignatt4llm` is NOT pip-installed in the eval venv; the implementation step must `uv pip install -e AlignAtt4LLM` (or run `python -m alignatt4llm.cli.evaluate`) to get the `alignatt-eval` entrypoint. OmniSTEval 0.1.10 + unabel-comet 2.2.7 + simulstream 0.3.0 are installed in `_eval_venv` (per `_work/eval_env_runbook.md`).
2. **Forced aligner confirmed loadable**: `mlx_audio.stt.models.qwen3_asr.qwen3_forced_aligner` imports; `ForcedAlignerModel` + `ForceAlignProcessor` + `ForcedAlignResult`/`ForcedAlignItem` (text, start_time, end_time) are the surface. `mlx_audio.stt.generate` has a `--text` flag for forced alignment. Model `mlx-community/Qwen3-ForcedAligner-0.6B-4bit` is the MLX port of the paper's aligner.
3. **MT simul backend confirmed (PR2)**: `MlxLlmTranslationSimul` (translation_mlx_llm_mt_simul.py) drives the AlignAtt commit policy with calibrated heads; the WLK `insert_tokens`/`process`/`validate_buffer_and_reset` contract is the emission seam. The `process()` return `(Translation|None, TimedText)` is where provisional/final target words surface.
4. **en→zh heads resolved**: `data/alignatt_heads/translation_heads_tencent_Hy-MT2-1_8B_en-zh.json` exists (19 heads, top L9/H5 TS=0.86) AND is wired into `simul_mt_capture.CALIBRATION_REGISTRY` under `("hy-mt2-1.8b","en","zh")` (disabled_quants={"4bit"} → 8bit only). The entity body's "en→zh heads backgrounded" open dependency is now resolved; the anchor runs with real en→zh 8bit heads, not a mirror or serial fallback. 4bit remains disabled (48.9% argmax match — attention patterns differ too much).
5. **Hypothesis-record shape confirmed**: `build_asr_hypothesis_record` (artifacts.py:154) and `InferenceArtifacts.hypothesis_record` both produce `{source, source_length, prediction, delays[], elapsed[], elapsed_wallclock_ms[], elapsed_semantics}`. `normalize_computation_aware_timestamps` is the CA normalizer. `register_translation_words` (emission.py:51) does LCP word-diff with `split_target_emission_units` (char-level for zh/ja).
6. **Hard dependency — devset audio**: `AlignAtt4LLM/data/devset/audio/` is empty (gitignored); 21 unique wavs referenced in `audio-segments.yaml` (919 segments). These must be sourced from the IWSLT 2026 shared task. This blocks AC-2/AC-4 (full devset) but NOT AC-1 (single-audio smoke, if one wav is provided) or AC-3 (two modes on one audio). The runner must fail clearly with a "source the devset audio" message when wavs are missing.
7. **XCOMET-XL gated**: `Unabel/XCOMET-XL` needs CL's HF access (confirmed in runbook). WMT22-COMET-DA is the ungated fallback (`--comet-model Unabel/wmt22-comet-da`); the runner defaults to XCOMET-XL but the smoke can run `--skip-comet` (local BLEU/CHRF + LongYAAL only) to verify the latency path without the gated download.
8. **MLX runtime**: the WLK worktree venv has mlx_lm/mlx_audio (the import error observed is a `huggingface_hub.is_offline_mode` symbol drift in that venv's huggingface_hub version — a venv-pin issue to resolve at implementation, not a design blocker; the livecaption venv loads both cleanly). The emitter runs from the WLK worktree venv; the scorer runs from `_eval_venv`. Two-venv split is inherent (the scorer needs torch/omnisteval; the cascade needs mlx).

### Acceptance criteria (sharpened, with `Verified by:`)

- **AC-1 (smoke round-trip)**: The emitter produces a `hypothesis.jsonl` from one devset audio that `alignatt-eval` scores with non-null BLEU/CHRF + LongYAAL (CA + CU). Verified by: `simulst_run.py --audio <one.wav> --mode asr-only --skip-comet` writes `outputs/smoke/<run>/{hypothesis.jsonl,manifest.json}`, then `alignatt-eval --output-dir outputs/smoke/<run> --skip-comet` writes `evaluation.json` with non-null `LongYAAL CA` and `LongYAAL CU` (and non-null `BLEU`/`CHRF`). Falsified if: any score is null/NaN, or `delays` length ≠ word count of `prediction`, or `elapsed_semantics != "ca_compatible_incremental"`.
- **AC-2 (full devset anchor)**: The anchor run (en→zh, forced-aligner ASR + Hy-MT2-1.8B-8bit simul-MT, en→zh heads) scores on all 919 segments across 21 audios. Verified by: `simulst_run.py --devset full --mode asr-mt --asr-backend forced-align --target zh` produces a 919-record `hypothesis.jsonl`, and `alignatt-eval --output-dir <run> --target-lang-code zh` writes `evaluation.json` with a devset-level `XCOMET-XL` (non-null when CL's HF access is available; else `--skip-comet` and non-null `BLEU`/`CHRF`/`LongYAAL`). Falsified if: record count < 919, or any segment's `source` wav is unmatched by the segmentation filter, or `XCOMET-XL` is null without a `metric_blockers` entry.
- **AC-3 (both modes)**: The emitter works for ASR-only (prediction = source transcription) and ASR+MT (prediction = target translation) on the same audio(s). Verified by: two `hypothesis.jsonl` files in two run dirs (`--mode asr-only` and `--mode asr-mt`), both round-tripping through `alignatt-eval` to non-null latency scores; the ASR-only `prediction` matches the source ref language, the ASR+MT `prediction` matches the target ref language (zh char-level). Falsified if: either mode's `prediction` is empty, or `--mode asr-only` produces target-language text (or vice versa).
- **AC-4 (flagship swap)**: The flagship run (nemotron-mlx + Hy-MT2-1.8B-8bit simul-MT, en→zh heads) drops into the same harness by swapping only the `--asr-backend` flag. Verified by: `simulst_run.py --devset full --mode asr-mt --asr-backend nemotron-mlx --target zh` produces a 919-record `hypothesis.jsonl` scored by the same `alignatt-eval` invocation as AC-2; the `TimestampSource` is `NativeTokenTimestampSource` (nemotron `AlignedToken.start`), not the forced aligner. Falsified if: the flagship path requires emitter code changes beyond the `--asr-backend` flag, or `delays` semantics differ from the anchor (they must both be chunk-boundary audio time). Blocked by: nemotron-mlx completion (separate entity).

### Test plan (staged, falsifiable)

1. **Unit: hypothesis-record shape** (AC-1 precondition, no audio needed). A pytest in `WhisperLiveKit/tests/test_simulst_emit.py`: feed the emitter a synthetic emission log (fake chunks with known audio-processed-time + wallclock + emitted words), assert the written `hypothesis.jsonl` record has `len(delays)==len(prediction.split())` (or char count for zh), `elapsed_semantics=="ca_compatible_incremental"`, `delays` monotonic, and `normalize_computation_aware_timestamps` round-trips. Falsified if the emitter writes acoustic positions as `delays`.
2. **Unit: timestamp-source abstraction**. Test `ForcedAlignTimestampSource` on a short synthetic chunk (audio + known text) returns per-word timestamps matching the forced aligner's `ForcedAlignResult.items`; test `NativeTokenTimestampSource` on a fake `AlignedToken` list returns `token.start`. Both must satisfy the `TimestampSource` protocol.
3. **Smoke (AC-1)**: one devset audio (requires one wav sourced). `simulst_run.py --audio <wav> --mode asr-only --skip-comet` → `alignatt-eval --skip-comet`. Assert `evaluation.json` `contract_scores` has non-null `LongYAAL CA`, `LongYAAL CU`, `BLEU`, `CHRF`. This is the gate that proves the emitter's `delays`/`elapsed` are scored correctly by the existing scorer — the load-bearing assertion.
4. **Both modes (AC-3)**: same audio, `--mode asr-only` and `--mode asr-mt`. Assert two scored runs; ASR-only prediction is source-language, ASR+MT prediction is zh (char-level unit count).
5. **Full devset (AC-2)**: all 21 audios (requires full audio set sourced). `--devset full --mode asr-mt --asr-backend forced-align`. Assert 919 records, scored. This is the baseline anchor.
6. **Flagship (AC-4)**: `--devset full --mode asr-mt --asr-backend nemotron-mlx`. Assert 919 records scored by the same scorer. Blocked by nemotron-mlx; the harness (emitter + runner + scorer invocation) must be ready before nemotron lands so the swap is flag-only.

### Open dependencies (carry-forward)

- **IWSLT devset audio** (21 wavs) — blocks AC-2/AC-4 (full devset); AC-1/AC-3 need one wav. Sourced from the IWSLT 2026 shared task; not downloadable by the harness. The runner checks for the wavs and fails with a clear message.
- **alignatt4llm editable install into `_eval_venv`** — `uv pip install -e AlignAtt4LLM` (or `python -m alignatt4llm.cli.evaluate`) to get the scorer. Implementation step.
- **WLK worktree venv `huggingface_hub` pin** — the `is_offline_mode` import drift blocks `import mlx_audio` in that venv; resolve at implementation (pin or patch). The livecaption venv loads both cleanly.
- **nemotron-mlx** (AC-4) — separate entity; harness must be flag-ready before it lands.
- **XCOMET-XL HF access** (AC-2/AC-4 quality score) — CL's gated access; `--skip-comet` or WMT22-COMET-DA fallback for latency-only verification.

### Summary

The harness is an emitter + runner + the existing `alignatt-eval` scorer, all in `WhisperLiveKit/scripts/` (~550-870 lines, no library changes). The emitter drives the WLK/MLX cascade (PR2 simul-MT + mlx-qwen3-asr/nemotron-mlx), records per-word emission times (audio-processed-time as `delays`, normalized wallclock as `elapsed` — the exact SimulEval semantics, NOT acoustic positions), and writes the `hypothesis.jsonl` shape that `alignatt-eval` already scores. A `TimestampSource` abstraction (forced-aligner for anchor, nemotron native for flagship) handles the two ASR-frontier timestamp sources behind one seam. en→zh heads are calibrated and wired (resolving the entity's open dependency). The hard blockers are the devset audio (sourcing) and XCOMET-XL access (CL's HF); both are external to the harness. Risk evidence was probed against the actual scorer, PR2 backend, forced aligner, and eval venv — not asserted.
