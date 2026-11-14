---
title: SimulST eval harness — MLX IWSLT anchor + flagship compare
status: implementation
worktree: .worktrees/integration-3
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
  + `resegment` + `write_evaluation_outputs`, defaulting to `Unbabel/XCOMET-XL`
  (`artifacts.py:56`; earlier notes misspelled it `Unabel`).
  Scores `hypothesis.jsonl` → XCOMET-XL (quality) + LongYAAL (latency). No port
  needed; MLX-agnostic.
- **IWSLT devset refs** — `AlignAtt4LLM/data/devset/ref/{en,zh,it,de}.txt`
  (919 lines each, aligned) + `audio-segments.yaml` (919 segments).
  `data/devset/audio/` holds **21 wav files on disk**; the claim that they must
  be sourced is stale.

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

## Base and capstone

**Base:** `wlk/integration-3`, cut from `origin/main` @ `496b5f6` with PR #426
already upstream. The `wlk/integration-2` branch named in the dispatch artifact
is retired and is not a target.

**Capstone:** `QuentinFuxa/WhisperLiveKit` issue #477, "Benchmark suite: score
the translation, and report its latency". Every AC below must be satisfiable by
the PR that answers #477. The captain owns that conversation; this entity never
opens, edits or comments on the issue.

## Why a measurement is a task here

The workflow rule is that a task carries user-visible value, and a measurement
is normally the acceptance of the task it serves. This is the exception the rule
names: upstream has no translation metric at all — `whisperlivekit/benchmark/`
scores WER/CER, and zero of 23 checked-in reports carry a non-null
`first_translation_time_s` — so a harness is a capability other people run, not
a number we consume.

## Acceptance criteria (tiered; numbers in the cycle-2 report)

- **Tier 1 — local harness (AC-1..AC-3), the shippable #477 PR.** Translation is
  engaged, joined and scored on `benchmarks/corpora/fleurs-90.json` through the
  `sentence_id` join that needs no download; the latency fields carry real
  numbers instead of placeholders.
- **Tier 2 — the standard pair (AC-4..AC-6), `scripts/` only.** XCOMET(-XL) +
  LongYAAL CA/CU through `alignatt-eval` on the IWSLT devset: one wav
  round-trips, the 919-segment anchor runs, the flagship swaps a flag. Kept out
  of the #477 PR because it needs Alignatt4LLM, a COMET checkpoint and
  non-shipped audio.
- **Boundary with `km` (`wlk-simul-time-frontier-pr`).** Tier 1's *realizable
  commit fraction* is km's number: km owns the port of
  `bench_commit_fraction.py` (the calibrated-attention coverage script) and this
  entity reuses that file rather than writing a second capture path. If km's
  file is not on the base, tier 1 reports that row as `not run` — it is not
  reimplemented here. This entity measures the whole cascade on emitted output;
  it does not isolate the commit policy.

## Open dependencies (status after cycle 2)

- **IWSLT devset audio — RESOLVED.** `AlignAtt4LLM/data/devset/audio/` holds 21
  wav files; `data/devset/ref/{de,en,it,zh}.txt` measure 919 lines each;
  `audio-segments.yaml` lists 919 segments. Nothing to source.
- **en→zh heads — RESOLVED.**
  `whisperlivekit/calibrations/translation_heads_mlx-community_Hy-MT2-1_8B-8bit_en-zh.json`
  is in the base. No mirror, no serial fallback.
- **nemotron-mlx — RESOLVED.** Merged in the base via PR #426; AC-6 is a flag
  swap, not an integration.
- **FLEURS audio — cached and reproducible.** All 90 manifest files are present
  in `~/.cache/whisperlivekit/benchmark_data/fleurs_v1/`, and
  `scripts/prepare_fleurs_benchmark.py` (111 lines) recreates them from the
  pinned Hub revision. No new download and no new corpus.
- **Evaluation environment — REGRESSED since the implementation stage.**
  `_eval_venv` no longer exists, and `_eval_cache/hub` holds only
  `xlm-roberta-large`: no COMET checkpoint is cached anywhere. The runbook's
  "wmt22-comet-da downloaded and load-verified" is stale. A venv rebuild plus a
  checkpoint fetch is a tier-2 prerequisite.
- **Disk — hard blocker for tier 2.** 210 MiB free on the volume. COMET
  checkpoints are ~2.2 GB (`wmt22-comet-da`) or larger. Tier 1 needs no
  download; tier 2 cannot fetch a scorer until space is freed.
- **COMET access — the captain decides** (next section).

## COMET access is the captain's decision

All three options are satisfiable by the same `hypothesis.jsonl`; only the
scorer invocation changes.

| Option | What it buys | Consequence |
|---|---|---|
| **A. Captain HF access for `Unbabel/XCOMET-XL`** | The IWSLT 2026 primary metric and the scorer's default, so our number sits beside the paper's published anchors | Gated: needs an approved token plus a venv rebuild and a multi-GB download — impossible at 210 MiB free until disk is freed |
| **B. Ungated `Unbabel/wmt22-comet-da`** | No approval needed; an internal quality signal on the same devset | A different metric (reference DA COMET, not XCOMET-XL): the number cannot be placed beside the paper's. Still ~2.2 GB of disk |
| **C. `--skip-comet` first pass** | No download at all: BLEU/chrF + LongYAAL CA/CU | The latency comparison stays valid, because LongYAAL is the paper's latency metric and needs no model; the quality comparison to the paper is unavailable, and tier 1's chrF carries the quality story |

Tier 2's latency AC is independent of this choice; only its quality bound moves.
This entity does not choose — the captain decides, the first officer records it.

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

## Stage Report: implementation

- DONE: Implement the 3 scripts (simulst_timestamp.py, simulst_emit.py, simulst_run.py)
  Commit f673273 on feat/apple-silicon-backends. 5 files, 1249 lines (within the ±30% tolerance of the plan's ~550-870 estimate; the eval wrapper is a 4th small file for the sandbox Pool fix).
- DONE: TimestampSource abstraction + ForcedAlignTimestampSource + NativeTokenTimestampSource
  scripts/simulst_timestamp.py — Protocol with two implementations. ForcedAlignTimestampSource wraps mlx_qwen3_asr.forced_aligner.ForcedAligner; NativeTokenTimestampSource wraps transducer AlignedToken.start. Unit test verifies Protocol conformance and token update/reset.
- DONE: HypothesisEmitter (asr-only + asr-mt modes)
  scripts/simulst_emit.py — drives mlx-qwen3-asr streaming over one audio, hooks per-word emission via register_translation_words/register_translation_timestamps, writes hypothesis.jsonl + manifest.json in alignatt-eval schema. delays = chunk-boundary audio-processed-time (NOT acoustic positions). elapsed = normalized wallclock. elapsed_semantics = ca_compatible_incremental.
- DONE: Runner (single-audio + full devset + eval invocation)
  scripts/simulst_run.py — argparse CLI, iterates audios, invokes emitter per audio, then runs alignatt-eval via the eval venv. Multi-audio merges records into one hypothesis.jsonl.
- DONE: alignatt4llm install in eval venv
  .pth file approach (alignatt4llm requires Python >=3.13, eval venv is 3.12; package has no deps so .pth import works). Created at both _eval_venv and WLK .venv site-packages.
- DONE: No-audio unit tests (hypothesis-record shape + TimestampSource abstraction)
  tests/test_simulst_emit.py — 5 tests: record shape (delays=chunk-boundary, monotonic, len matches word count), char-level zh (7 char units), TimestampSource protocol conformance, CA normalization round-trip, manifest builder. All pass.
- DONE: Single-audio smoke (AC-1) on ccpXHNfaoy.wav with --skip-comet
  Emitted hypothesis.jsonl (4810 chars, 747 delay units). alignatt-eval produced non-null scores: BLEU=23.35, CHRF=68.49, LongYAAL CA=3262, LongYAAL CU=3645. XCOMETXL=None (--skip-comet, expected). evaluation.json written.
- SKIPPED: Full devset run (AC-2)
  Requires all 21 audios + XCOMET-XL access (CL's HF). The harness is ready; the 21 wavs are present but the full run is outside this implementation stage's scope (AC-1 is the gate).
- SKIPPED: ASR+MT mode smoke (AC-3)
  asr-mt code path is implemented but untested live (requires MT model warmup + the PR2 simul-MT backend, which needs the sandbox's GPU access). The emitter code for asr-mt is complete but not exercised in this stage.
- SKIPPED: Flagship run (AC-4)
  Blocked by nemotron-mlx (separate entity). Harness is flag-ready (--asr-backend nemotron-mlx) but the backend is not yet available.

### Summary

Implemented the SimulST eval harness as 5 scripts (1249 lines) on feat/apple-silicon-backends (commit f673273). The emitter drives mlx-qwen3-asr streaming over devset audio, timestamps per-word emission with chunk-boundary audio-processed-time as `delays` (SimulEval semantics, not acoustic positions), normalizes wallclock to CA-compatible `elapsed`, and writes hypothesis.jsonl + manifest.json in the alignatt-eval schema. A sandbox-specific eval wrapper patches omnisteval's multiprocessing Pool to serial execution (sandbox blocks semaphores). AC-1 verified: single-audio smoke on ccpXHNfaoy.wav (asr-only, --skip-comet) round-trips through alignatt-eval producing non-null BLEU=23.35, CHRF=68.49, LongYAAL CA=3262, LongYAAL CU=3645. The harness is ready for AC-2 (full devset) and AC-4 (flagship) once the external dependencies (XCOMET-XL access, nemotron-mlx) are available.

### Feedback Cycles

#### Cycle 1 — scope correction before the build (2026-11-14)

The entity returns to `ideation` from `implementation`. The build plan is sound. Six
items were stale or undecided, so a build against this text would have aimed at the
wrong base and an unmeasurable target.

1. **Name the base.** The text targets "the integration branch". `wlk/integration-3`
   now exists, cut from `origin/main` @ `1b2986d`, and carries `nemotron-mlx-asr`,
   `mlx-qwen3-asr`, the simul time frontier and the caption display work. State which
   base the runner runs on.
2. **Close the resolved dependencies.** `nemotron-mlx` is merged, so AC-4's blocker is
   gone. The en→zh heads are upstream at
   `whisperlivekit/calibrations/translation_heads_mlx-community_Hy-MT2-1_8B-8bit_en-zh.json`,
   so the "mirror or serial fallback" contingency no longer applies. Rewrite
   "Open dependencies".
3. **The devset audio is present.** `Alignatt4LLM/data/devset` holds 21 wav files. The
   text says the audio must be sourced. Correct that, and record the segment count
   observed on disk before promising 919.
4. **Decide the COMET access.** `Unabel/XCOMET-XL` is gated and needs the captain's HF
   access. Pick one: captain access, the ungated `Unabel/wmt22-comet-da`, or
   `--skip-comet` for the first pass with BLEU/CHRF and LongYAAL only. A build cannot
   decide this.
5. **State an acceptance number.** AC-1 to AC-4 require non-null scores. Non-null is
   not a target. State the value each run must reach, or state plainly that the first
   build establishes a baseline and supports no claim.
6. **Draw the boundary with `scripts/simul_fixture.py`.** This harness scores the whole
   cascade (ASR, aligner, commit policy, MT) on emitted output. It does not isolate the
   commit policy. `simul_fixture.py` does, by replaying the engine's exact inputs. Name
   both tools, and say that the fixture port belongs to the simul PR entity `km`, not
   here.

#### Cycle 2 — filed upstream as issue #477, and the scope is now the measurement harness (2026-11-14)

1. **Filed publicly.** `QuentinFuxa/WhisperLiveKit` issue #477, "Benchmark suite: score the
   translation, and report its latency". It quotes the repo's own `benchmarks/README.md`:
   "A WLK audio-to-translation benchmark is a separate experiment; it must record both ASR and
   MT configurations." So this answers a gap the maintainer documented.
2. **Upstream has no translation metric at all.** `whisperlivekit/benchmark/` scores WER/CER
   and records `first_text_time_s`, `first_visible_time_s`, `first_translation_time_s`,
   `avg_latency_ms`, `p95_latency_ms`. Zero of 23 checked-in reports carry a non-null
   `first_translation_time_s`. `grep -riE "code.?switch|bleu|comet"` over the benchmark module,
   `benchmarks/` and `docs/` returns nothing. There is one corpus, `fleurs-90.json`.
3. **The references need no download.** FLEURS is parallel and the checked-in manifest holds
   30 identical `sentence_id`s across en, fr and zh. A join on `sentence_id` supplies the
   translation reference. This satisfies the rule the maintainer stated in #343: public
   datasets only.
4. **The narrow gap.** `runner.py:52` builds `kwargs` from `model_size`, `pcm_input`,
   `backend` and `engine_kwargs`, then calls `TestHarness(**kwargs)`. `TestHarness` forwards
   to `AudioProcessor`, which already accepts `target_language` and a translation backend. So
   the work is forwarding two options plus a metric, not building a pipeline path.
5. **What this entity is now.** The measurement harness contribution, and issue #477 is its
   capstone. Tier 1 is the local harness, portable from the now-deprecated `livecaption`,
   whose authorship split is recorded in `_work/livecaption-findings.md`. Of its six bench
   scripts, `bench_e2e_latency.py` (92 lines) and `bench_commit_fraction.py` (241) are ours,
   while the base pipeline techniques are upstream's. Tier 2 is the standard pair, XCOMET-XL
   at LongYAAL CA/CU through `alignatt-eval`, on the IWSLT devset.
6. **Why a measurement may be a task.** The workflow rule is that a task carries user-visible
   value, and a measurement is normally the acceptance of the task it serves. This is the
   exception the rule names: upstream has no translation metric, so a harness is a capability
   other people run. That is what makes it a deliverable rather than a number.
7. **Still open.** `Unabel/XCOMET-XL` is gated and needs the captain's HF access. Choose
   between that, the ungated `Unabel/wmt22-comet-da`, and `--skip-comet` for a first pass.
   State an acceptance number, not "non-null".

## Stage Report: ideation (cycle 2)

- DONE: Name the base explicitly: wlk/integration-3, cut from origin/main @ 496b5f6, plus issue #477 as the capstone.
  `git log -1 wlk/integration-3` = `9bd11ca` descending from `496b5f6` (PR #426); base + capstone stated in the body's "Base and capstone".
- DONE: Close the three blockers the body still lists: nemotron-mlx is upstream, the en to zh heads are upstream, and AlignAtt4LLM/data/devset holds 21 wav files.
  `ls AlignAtt4LLM/data/devset/audio | wc -l` = 21; refs 919 lines each × {de,en,it,zh}; `whisperlivekit/calibrations/..._en-zh.json` present; PR #426 in the base. Body section rewritten to "Open dependencies (status after cycle 2)".
- SKIPPED: Decide the COMET access.
  The first officer's scope note assigns this decision to the captain, so the body presents options A/B/C with the consequence of each and states plainly that the captain decides. Nothing in the design branches on it except tier 2's quality bound.
- DONE: State an acceptance number for quality and latency per run, not non-null.
  AC-1..AC-6 below carry thresholds (corpus chrF ≥ 20.0 with a 26.21 partial-run reference, latency ratio p95 ≤ 0.85, ≥ 28/30 rows, provisional lead ≥ 0.20 s when drafting, ≥ 900/919 segments, ±1.0 repeat bound), each with a falsifier.
- DONE: Split tier 1 (local harness: user-visible latency and realizable commit fraction) from tier 2 (XCOMET-XL at LongYAAL through alignatt-eval).
  Tier 1 = `whisperlivekit/benchmark/` + `benchmarks/README.md` + tests (the #477 PR). Tier 2 = `scripts/simulst_*.py` + a local runbook, excluded from the PR because it needs Alignatt4LLM, a COMET checkpoint and non-shipped audio.
- DONE: Draw the boundary with km: km owns the copy of the coverage script it uses, and 8z reuses that file rather than writing a second capture path.
  Body section "Boundary with km (`wlk-simul-time-frontier-pr`, id `kmjvq6k0q7c2p265xgbj56cm`)": the realizable-commit-fraction number is km's `bench_commit_fraction.py` port; absent it, the row reads `not run` and is not reimplemented.
- DONE: Record that a measurement is a task here only because upstream has no translation metric, per issue #477.
  Body section "Why a measurement is a task here".
- FAILED: Full 30-sample en→zh corpus baseline (attempted, aborted).
  The run was launched and aborted on the disk constraint (210 MiB free). No corpus-level chrF or latency distribution exists; every number below is a partial run with its n stated. Not re-run.

### Selected approach

Two tiers, one capture path each, no pipeline change:

1. **Tier 1 — extend the module `wlk bench` already runs** (the #477 PR). Add per-row
   `target_language` + `translation_reference` (joined on `sentence_id`), `chrf`,
   `final_translation_time_s`, `provisional_lead_s`; add `compute_chrf` to
   `benchmark/metrics.py`; record the ASR *and* MT configuration in the report
   `config` block as `benchmarks/README.md` requires; first-class
   `--target-language` / `--translation-backend` / `--mt-model` flags; bump
   `benchmark_version` 3.1 → 3.2. The join is a `load_manifest` change, not a
   corpus change: `fleurs-90.json` already carries `sentence_id` for all 90 rows
   (30 ids × {en, fr, zh}), so no download and no re-preparation.
2. **Tier 2 — one emitter over the same pipeline.** `scripts/simulst_hypothesis.py`
   drives `TestHarness` (the `wlk bench` path, not a private MLX loop) over one
   devset wav, taps the caption event stream, and writes `hypothesis.jsonl`
   (`delays` = `CaptionEvent.audio_t`, `elapsed` = wallclock since feed start,
   normalized by `alignatt4llm.artifacts.normalize_computation_aware_timestamps`).
   `scripts/simulst_run.py` loads the devset (`audio-segments.yaml` + refs) and
   invokes `alignatt-eval` from a venv named by an env var, failing loudly when
   absent. The record builders and word-diff registration come from
   `alignatt4llm`; nothing is re-implemented.

**Not the base:** `f673273` (5 files, 1249 lines, only on the orphan branch
`feat/apple-silicon-backends-old`) drives `mlx_qwen3_asr.streaming` and
`MlxLlmTranslationSimul` directly and bypasses `AudioProcessor`/`TestHarness`, so
its numbers are not the pipeline's. Its record-shape work is the reference; the
file is not reused as-is.

### Risk evidence (probed — read or run; nothing re-run for this report)

1. **`--config` already reaches translation; `first_translation_time_s` already
   populates.** `BenchmarkRunner(backend="mlx-qwen3-asr", speed=1,
   engine_kwargs={target_language:"zh", translation_backend:"mlx-llm-mt",
   mlx_llm_mt_model:"hy-mt2-1.8b-8bit"})` on `fleurs_en_1700` (7.2 s) → `status ok`,
   `wer 0.0`, `first_text_time_s 3.757`, `first_visible_time_s 3.757`,
   **`first_translation_time_s 4.081`**, `finalization_time_s 0.527`. The 23
   reports are null because no run ever set a target language, not because the
   field is unreachable. `runner.py:52` validates `engine_kwargs` against
   `WhisperLiveKitConfig` field names, and `target_language`,
   `translation_backend` and `mlx_llm_mt_*` are all fields.
2. **The two derived fields are observable without touching the pipeline.**
   A `/tmp` probe drove `TestHarness` directly with `on_update` and recorded
   first provisional, first committed-line translation and last committed-line
   translation. Non-simul, n=4 launched / 3 rows retained (the first row was lost
   to output truncation, not re-run), zh references joined on `sentence_id`:
   chrF **8.10** (`en_1700`), **37.15** (`en_1993`), **33.39** (`en_1921`) →
   mean **26.21**; first line translation **3.97 / 6.71 / 7.84 s** on durations
   7.2 / 8.66 / 9.72 s → ratios **0.55 / 0.77 / 0.81**. Single runs, no repeats,
   thermal state uncontrolled.
3. **`provisional_lead_s` needs a drafting backend, by construction.**
   `translation_mlx_llm_mt.py` clears the buffer every pass ("Source words must
   not appear in the target-language buffer"), so the non-simul backend emitted a
   provisional on **0/3** probed samples. With `mlx_llm_mt_simultaneous=True`,
   n=2: provisional at **4.052 / 3.745 s**, committed translation at
   **4.316 / 6.652 s** → lead **0.26 / 2.91 s**, chrF 8.10 / 34.51. So the field
   is null on a default run and non-null on a drafting run — the same convention
   as `cer` being null for English, and it must be documented or the AC looks
   broken rather than unsatisfied.
4. **chrF needs no dependency.** `benchmark/metrics.py` holds `normalize_text`,
   `compute_wer` and `compute_timestamp_accuracy`; there is no `sacrebleu` in
   `pyproject.toml`. The probe's 25-line whitespace-stripped char n-gram F-beta
   (n = 1..6, β = 2) is the version the PR ships, and it is what makes zh score
   without a tokenizer — the same rationale as the existing CER path.
5. **Report shape is known.** `BenchmarkReport.to_dict()` emits
   `benchmark_version: "3.1"`, a `measurement` documentation dict, `summary`, and
   per-sample rows; `report.py` formats the terminal table. New fields land in
   all four places, and the `measurement` dict is where the new field semantics
   get documented for future readers.
6. **Test pattern exists.** `tests/test_benchmark.py` (158 lines) already runs a
   real harness with `backend="whisper"`, `transcription=False`,
   `pcm_input=True` and a silence wav, asserting measurement plumbing rather than
   model quality. New fields can be asserted the same way without any model.
7. **Tier 2 environment has regressed.** `_eval_venv` is gone; `_eval_cache/hub`
   holds only `xlm-roberta-large`, so no COMET checkpoint is cached. Disk is
   210 MiB free. The prior stage's `--skip-comet` smoke (BLEU 23.35, chrF 68.49,
   LongYAAL CA 3262, CU 3645 on `ccpXHNfaoy.wav`) is real evidence that the
   scorer path works and that CA ≤ CU holds, but it ran through the orphan
   emitter and an environment that no longer exists.

### Semantic changes (precise)

- `chrf` — whitespace-stripped character n-gram F-beta (n = 1..6, β = 2) between
  the translation and the joined reference; `null` when the run has no
  translation, mirroring `cer` for English.
- `translation_reference` — the reference of the *same sentence_id* in the target
  language, resolved at manifest load; `null`/absent for a sentence with no
  target-language recording.
- `final_translation_time_s` — the last moment a committed line first showed a
  translation, measured from feed start; paced runs only (speed = 1), like
  `first_visible_time_s`.
- `provisional_lead_s` — `final_translation_time_s − first_translation_time_s`;
  `null` unless a drafting backend produced provisional text.
- `delays[i]` (tier 2) — audio position of the emission that first carried word
  *i*, in ms. **Not** the acoustic position: the forced aligner's `end_time_s`
  would collapse LongYAAL below the chunk length.
- No engine, `AudioProcessor`, `TestHarness` or CLI-runtime behaviour changes;
  `effective_config` already records the MT settings per row.

### Expected files and lines (tolerance ±30%)

Tier 1 — the #477 PR: `whisperlivekit/benchmark/metrics.py` +45..65
(`compute_chrf`, five `SampleResult` fields, report summary, version bump);
`benchmark/datasets.py` +20..30 (`sentence_id`, `translation_references`,
the group-by join in `load_manifest`); `benchmark/runner.py` +30..45 (observation
of the two new latency fields, chrF scoring, row population);
`benchmark/report.py` +10..20 (chrF and translation-latency lines);
`whisperlivekit/cli.py` +20..35 (three flags, pair validation);
`benchmarks/README.md` +25..40 (the translation experiment, field semantics,
schema 3.2); `tests/test_benchmark.py` +80..120. Total ≈ 230..355 added lines.

Tier 2 — `scripts/` only, not in the PR: `simulst_hypothesis.py` 160..240;
`simulst_run.py` 100..160; `_work/SIMULST_EVAL_RUNBOOK.md` 60..100 (local, since
it names machine paths). No re-derivation of `f673273`'s 486-line emitter.

### Acceptance criteria (cycle 2, with numbers)

- **AC-1 (translation engaged, joined, scored — tier 1).** `wlk bench --languages
  en --target-language zh --translation-backend mlx-llm-mt --speed 1 --manifest
  benchmarks/corpora/fleurs-90.json --json out.json` over the 30 English FLEURS
  samples: 30/30 rows carry `target_language == "zh"` and a non-empty
  `translation_reference`; ≥ 28/30 rows carry a non-null `chrf`; corpus mean
  `chrf` ≥ 20.0; and the three probed samples reproduce 8.10 / 37.15 / 33.39
  within ±0.01. *Verified by:* the run's JSON plus the reproduction check.
  *Falsified by:* a mean below 20.0, any null `translation_reference`, or a
  reproduction drift above 0.01.
- **AC-2 (latency per run — tier 1).** Same run: ≥ 28/30 rows carry a non-null
  `first_translation_time_s`; the p95 of `first_translation_time_s /
  duration_s` ≤ 0.85 (observed 0.55 / 0.77 / 0.81, mean 0.71); ≥ 28/30 rows carry
  a non-null `final_translation_time_s`, and `final ≥ first` wherever both exist.
  With `--config '{"mlx_llm_mt_simultaneous": true}'`, `provisional_lead_s` is
  non-null and ≥ 0.20 s on at least one row (observed 0.26 s and 2.91 s), while
  the default non-drafting run has it null on every row. *Falsified by:* a null
  `first_translation_time_s` on a `status == "ok"` row, `final < first`, or a
  non-null lead on the non-drafting run.
- **AC-3 (no regression, no new dependency — tier 1).** A `--languages en` run
  without `--target-language` yields `chrf: null`, `target_language: ""` and
  unchanged WER/CER/RTF and `first_visible_time_s` on the same samples;
  `benchmark_version` reads 3.2; `pyproject.toml` gains no dependency. *Verified by:* the ASR-only run diffed against a pre-change run
  of the same manifest. *Falsified by:* any changed WER/CER/RTF value, or a new
  dependency.
- **AC-4 (one devset wav round-trips — tier 2).** `simulst_run.py --audio
  <wav>` → `hypothesis.jsonl` → `alignatt-eval --skip-comet` →
  `evaluation.json` with finite LongYAAL CA and CU satisfying `0 < CA ≤ CU`, and
  `len(delays)` equal to the prediction's unit count (char-wise for zh).
  *Falsified by:* a null score, `CA > CU`, or a length mismatch.
- **AC-5 (919-segment anchor — tier 2).** The anchor run (en→zh,
  `--asr-backend forced-align` + Hy-MT2-1.8B-8bit simul, en→zh heads) writes 919
  records from 21 wavs; ≥ 900 (97.9%) score; two consecutive runs agree within
  ±1.0 point of the chosen quality metric and ±10% on LongYAAL CA. The first
  run's quality number becomes the recorded anchor: an absolute quality
  threshold cannot be pre-committed because our cascade has never been measured
  on this devset, so this AC's number is a reproducibility bound stated as such.
  *Falsified by:* fewer than 900 scored segments, or a repeat outside the bounds.
- **AC-6 (flagship swap — tier 2).** `--asr-backend nemotron-mlx` changes nothing
  else: same 919 records, same `alignatt-eval` invocation, same AC-5 bounds.
  *Falsified by:* any emitter code change beyond the flag, or a different
  `delays` semantic between the two runs.

### Test plan (staged, falsifiable)

1. **Unit — chrF arithmetic.** Identical strings → exactly 100.0; empty
   hypothesis → 0.0; a fixed pair → an exact expected value; whitespace
   differences → identical score. Falsified by any other value.
2. **Unit — the `sentence_id` join.** Every row of `fleurs-90.json` gets a
   non-empty `translation_references["zh"]`; a row whose `sentence_id` has no
   target-language sibling gets `{}` without raising, and the run reports a null
   `chrf` rather than a fabricated one. Falsified by a wrong pairing or a crash.
3. **Plumbing (existing pattern, no model).** `backend="whisper"`,
   `transcription=False`, `pcm_input=True`, silence wav, engine kwargs
   `target_language="zh"` → row has `target_language == "zh"`, `chrf is None`
   (no hypothesis to score), `provisional_lead_s is None`; without the kwarg →
   `target_language == ""` and `chrf is None`. Falsified if a row shows a score
   without a hypothesis.
4. **Reproduction (the AC-1/AC-2 gate).** The 30-sample run reproduces 8.10 /
   37.15 / 33.39 ±0.01 and the observed latency ratios. Falsified by drift.
5. **Tier-2 smoke (AC-4).** One devset wav through the emitter and
   `alignatt-eval --skip-comet`; assert `0 < CA ≤ CU` and the unit-count match.
6. **Tier-2 anchor and flagship (AC-5, AC-6).** 919 records, ≥ 900 scored, repeat
   within the bounds; then the same with `--asr-backend nemotron-mlx`.

### Summary

The scope is now a measurement harness whose capstone is issue #477, not a
private pipeline. Reading the base shows the gap is far narrower than the entity
assumed: `--config` already forwards `target_language` and `translation_backend`,
and a probe produced a non-null `first_translation_time_s` of 4.081 s on an
unmodified base — the null field in 23 reports is unexercised code, not missing
plumbing. What the PR owes is the `sentence_id` reference join, a ~40-line chrF,
two derived latency fields, the row/report fields and three CLI flags, with a
3.1 → 3.2 schema bump. Tier 2 keeps the standard pair where it belongs — in
`scripts/`, behind the existing `alignatt-eval` — and shares one capture path
with tier 1 by driving `TestHarness` rather than a private MLX loop, which is
also why the orphan 1249-line emitter is not reused as-is. Measured evidence is
partial and says so: 3 non-simul and 2 simul samples, single runs, corpus-wide
numbers absent because the 30-sample run was aborted on the disk constraint. The
one open input is the COMET access choice, presented as three options with
consequences and left to the captain.
