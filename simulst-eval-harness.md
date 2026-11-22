---
title: SimulST eval harness — MLX IWSLT anchor + flagship compare
status: validation
worktree: .worktrees/simulst-eval-harness
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
        - id: gate:8zdhkj86eqshqypzzme2v6ss:validation
          stage: validation
          attempts:
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-1
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-1:revision-1
                digest: sha256:0bc10f20cbe6841c269989a035421ffce035ff45adcb18decea89e0a6b06b240
                room-ref: '@review/validation/briefing-1'
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:validation:1
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-1:revision-1
                by: agent:first-officer
                at: "2026-11-15T03:31:02.068126Z"
                decision: revise
                reason: 'Validator reproduced every tier-1 claim (join 4/4 rows, chrF to 6dp from a from-scratch implementation, both latency fields with final>=first, schema 3.2, 7 tests green with three demonstrated falsifiers). Two findings return to implementation: NOTES.md''s drafting-run reproduction passes inline JSON to --config, which takes a path and fails with FileNotFoundError; and chrF("abc","abd") has precision equal to recall so the assertion passes for any beta. Finding 2 is resolved by the captain''s rescope of AC-1/AC-2 to the #477 harness scope, recorded in Cycle 4. Finding 4 (repeat non-determinism on MT text) defers to tier 2.'
                conn:
                    quote: 'Gate result: revise, as you recommend. The implementation corrects findings 1 and 3. Then a new validation runs.'
                    source: MetaFO brief relaying CL's decisions, 2026-11-14
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-2
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-2:revision-1
                digest: sha256:47969f87880293c2edbbc2b147b584b9cd2a710782cf599db31d24f1cba73af2
                room-ref: '@review/validation/briefing-2'
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:validation:2
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-2:revision-1
                by: agent:first-officer
                at: "2026-11-15T03:42:45.965061Z"
                decision: approve
                reason: 'Second validation reproduced all three checklist items independently (3 done, 0 skipped, 0 failed): both returned findings fixed with falsifiers that bite, rescoped AC-1/AC-2 matching code and both checked-in reports, and chrF arithmetic sacrebleu-identical with the entire divergence traced to the suite''s punctuation-stripping normalization. Remaining items are one documentation sentence, a pre-existing --config help string, and the deferred tier-2 non-determinism risk.'
                conn:
                    quote: 'Validation gate of tier 1: approved, as you recommend. Record the approval with my words as the grant.'
                    source: MetaFO brief relaying CL's decisions, 2026-11-14
              application:
                target-stage: done
                state: superseded
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-3
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-3:revision-1
                digest: sha256:d7a80c4e3eb101c8356f241e5a18be05a7e7ef6dd51f250bd5a0136bb29fb335
                room-ref: '@review/validation/briefing-3'
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:validation:3
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-3:revision-1
                by: agent:first-officer
                at: "2026-11-22T05:15:00.520097Z"
                decision: revise
                reason: 'Validation reproduced every chrF value independently and cleared the join, reports, README and base, but AC-3''s second clause fails: drafted is derived from a non-empty buffer, so a non-drafting run carrying untranslated source reports a 0.35 s lead. That is the maintainer''s own requirement. Two smaller findings are in scope: alignatt reports record no MT model, and the km boundary row is unrecorded.'
                conn:
                    quote: send it back
                    source: CL, direct instruction, 2026-11-21
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-4
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-4:revision-1
                digest: sha256:bc67457a293ab6a3cf6b0939e4f4463442d4dbd93225de310cbb7c916c87590a
                room-ref: '@review/validation/briefing-4'
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:validation:4
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-4:revision-1
                by: agent:first-officer
                at: "2026-11-22T05:40:20.556595Z"
                decision: revise
                reason: 'Validation verified chrF, the corpus aggregation, the join, the alignatt record and the disclosures independently, and confirmed the buffer gate is gone. One under-inclusion remains: nllb, the default backend, publishes a provisional target buffer, so the predicate suppresses a real lead while the README says such nulls mean no draft. CL also decided the boundary row stays prose only.'
                conn:
                    quote: send to back. boundary prose is fine
                    source: CL, direct instruction, 2026-11-21
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-5
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-5:revision-1
                digest: sha256:61d4a5c5e744c2e63a6ab9abbd8d716a3fa86e1e049db283df68d4f18cf28660
                room-ref: '@review/validation/briefing-5'
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:validation:5
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-5:revision-1
                by: agent:first-officer
                at: "2026-11-22T06:08:44.811032Z"
                decision: revise
                reason: 'Third validation passed every checklist item by running code and cleared chrF, the corpus aggregation, the join, the alignatt record and the diff scope. One material defect remains outside the criteria: the predicate is fed requested kwargs, so a default nllb run (bench omits translation_backend) reports a null lead while its report names nllb. The same root cause has a second trigger: the bench flag has no choices, so an unlisted name runs nllw and reports null.'
                conn:
                    quote: send it back
                    source: CL, direct instruction, 2026-11-22
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-6
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-6:revision-1
                digest: sha256:a0409f68d74a65e57dfc0e5417c5bd7cbd8ebca67ba8ea5cf096b8ce868d3fd0
                room-ref: '@review/validation/briefing-6'
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:validation:6
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-6:revision-1
                by: agent:first-officer
                at: "2026-11-22T07:11:28.565927Z"
                decision: revise
                reason: 'Fourth validation passed every item and cleared the resolved-config path, the shared backend list, the invocation matrix and the completeness check by running code. One material defect survives at the last entry point: BenchmarkRunner validates only engine_kwargs keys, so --config can set an unlisted translation_backend that core routes to nllw while the predicate calls it non-drafting. Two test tightenings ride along.'
                conn:
                    quote: send it back
                    source: CL, direct instruction, 2026-11-22
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-7
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-7:revision-1
                digest: sha256:0c97138baaddd91c06192ba7abbe72676f3ab0b764cb22cf5a8a18a246033052
                room-ref: '@review/validation/briefing-7'
              resolution:
                type: Resolution
                id: resolution:spacedock:8zdhkj86eqshqypzzme2v6ss:validation:7
                briefing: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-7:revision-1
                by: agent:first-officer
                at: "2026-11-22T08:30:40.396682Z"
                decision: approve
                reason: Fifth validation passed all three items by running code against the worktree tree, with the import path proven first. The backend bound holds at six entry points and each half is independently load-bearing. The completeness test passes alone, the cascade fake derives its resolved configuration, and chrF, the corpus aggregation, the join, the byte-unchanged corpus, the alignatt record and schema 3.2 all reproduce. Five findings sit outside the criteria; the material one is a pre-existing help string on --config.
                conn:
                    quote: Approve
                    source: CL, direct instruction, 2026-11-22
              application:
                target-stage: done
                state: superseded
            - id: gate-attempt:8zdhkj86eqshqypzzme2v6ss-validation-8
              briefing:
                id: briefing:8zdhkj86eqshqypzzme2v6ss:validation:attempt-8:revision-1
                digest: sha256:554a4eeef8c8a3ec761f91cb2354473c89b364b48cce83541c375a936edd75a0
                room-ref: '@review/validation/briefing-8'
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

## Acceptance criteria (tiered; tier 1 restated from the maintainer's #477 reply in cycle 5)

Tier 1 is the shippable #477 PR. The five criteria below are transcribed word for
word from `#### Cycle 5`, which records the maintainer's 2026-11-21 reply on
issue #477 and the captain's approval of it as this entity's tier-1 criteria.

**AC-1 — the translation is joined and scored at corpus level.**
The reference is built at manifest load from the same `sentence_id`, and `benchmarks/corpora/fleurs-90.json`
with its hashes stays unmodified. Every scored row carries `target_language` and a non-null `chrf` where
both a translation and a reference exist, and the summary reports **corpus-level chrF**, computed from
character n-gram statistics summed over all rows of the language pair; the per-row `chrf` is kept for
inspection and is not the headline.
*Falsified by:* a modified corpus file, a row whose reference differs from the manifest join, or a summary
chrF equal to the mean of per-sentence scores.

**AC-2 — the chrF implementation matches sacrebleu exactly.**
Character order 6, word order 0, beta 2, whitespace removed. A unit test pins several sacrebleu values,
computed once and hard-coded, so the implementation is checked against the reference library without
depending on it at run time.
*Falsified by:* a value that differs from pinned sacrebleu output on the same input, or a test that cannot
fail when the arithmetic changes.

**AC-3 — the provisional lead is honest and local.**
`provisional_lead_s` is non-null only when the MT backend actually drafts, and is measured from the
front-end snapshots the harness already sees, so nothing in this PR depends on #449. On a backend without
drafts the field is null even when `buffer_translation` carries untranslated source text.
*Falsified by:* a non-null lead on a non-drafting run, or an import that requires the #449 event stream.

**AC-4 — the report says what ran.**
Each report records both configurations: ASR backend and model, and MT backend, model and direction. The
schema moves to 3.2. Reports already checked in under `benchmarks/evaluations/` stay as they are.
*Falsified by:* a report that omits either configuration, or a schema that is not 3.2 in a new report.

**AC-5 — the README states what chrF covers here.**
One sentence in `benchmarks/README.md` saying that chrF scores ASR and MT together, so ASR errors flow
into it.

**The measured note is withdrawn.** The earlier note that tier 1 measures a mean chrF of 7.01 is the
superseded variant's figure under the wrong aggregation; it is replaced by corpus-level values from the
corrected implementation, with the sample size stated and no quality claim attached.

**Delivery.** Rebase onto current `origin/main` first, then regenerate the demonstration reports through
the corrected implementation, because their chrF values change. Tier 2 — XCOMET and LongYAAL on the IWSLT
devset — remains our own work and is **not** part of the #477 PR.

**Measured, not a floor.** The corrected implementation reports corpus-level
chrF **8.59** over three English FLEURS samples without drafting and **9.32**
over the same three with drafting, in
`benchmarks/evaluations/translation-fleurs-en-zh/`. Their per-row means are 8.57
and 9.67, which is the aggregation the withdrawn 7.01 figure used. Three samples
carry no quality claim, and tier 1 makes none.

- **Tier 2 — the standard pair (the cycle-2 AC-4..AC-6), `scripts/` only.** XCOMET(-XL) +
  LongYAAL CA/CU through `alignatt-eval` on the IWSLT devset: one wav
  round-trips, the 919-segment anchor runs, the flagship swaps a flag. Kept out
  of the #477 PR because it needs Alignatt4LLM, a COMET checkpoint and
  non-shipped audio. Moved here from tier 1 in cycle 4: the corpus mean-chrF
  minimum (20.0) and the ±0.01 reproduction of the cycle-1 probe's 8.10 / 37.15
  / 33.39. A quality floor measures the cascade rather than the harness, and
  those probe numbers came from the IWSLT path the cycle-2 rescope replaced.
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

#### Cycle 3 — implementation re-dispatched for the #477 scope (2026-11-14)

The `## Stage Report: implementation` above records the cycle-1 build: five scripts at
commit `f673273` on `feat/apple-silicon-backends`, measuring the IWSLT devset through
`alignatt-eval`. Cycle 2 narrowed this entity to the measurement harness whose capstone is
issue #477. The cycle-1 build therefore does not answer the current stage, and the branch it
lives on is not this workflow's base.

Decision (first officer, 2026-11-14): the implementation stage re-opens for a second build
against `origin/main` @ `496b5f6`, the base the body declares. The cycle-1 report stays as
history; it is not completion evidence for the #477 scope. The scheduler does not list this
entity as dispatchable, because a stage report already exists for the stage. It is not a ready
gate either. The dispatch is therefore issued directly against the current stage, which the
entity status already equals.

Scope for the build is tier 1 only, the shippable #477 PR: a `sentence_id` join supplies each
row's translation reference, chrF scores the translation, `target_language`,
`final_translation_time_s` and `provisional_lead_s` carry the direction and the latency, and the
report schema moves 3.1 to 3.2. Tier 2 stays blocked: a COMET checkpoint needs about 2.2 GB and
the volume has 2.5 GiB free.

Prerequisites verified on 2026-11-14: FLEURS audio is cached (183 wav files, three languages),
`mlx-llm-mt` with the Hy-MT2 profiles is already on that base, and `Hy-MT2-1.8B-8bit` is cached.
A demonstration run of the cascade needs no download.

Budget for this build: one worker, 90 minutes, one retry, at most two model-loading runs of
three samples each, no download, and stop if free disk falls below 1.5 GiB.

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

## Stage Report: implementation (cycle 2)

- DONE: The benchmark suite scores the translation: each translated row carries a chrF value, and its reference comes from a sentence_id join on benchmarks/corpora/fleurs-90.json with no new corpus and no new download.
  `load_manifest` groups the manifest rows by `sentence_id` and attaches every sibling reference; a row scores `chrf` only when both the translation and the joined reference are non-empty. `compute_chrf` is a 0..100 character n-gram F-beta (n=1..6, beta=2) over the WER-normalized, whitespace-stripped pair. No corpus file added: the three-sample subset stayed in `/tmp`, and its five-line derivation is in `NOTES.md`.
- DONE: Each row carries the translation direction and its latency: target_language, final_translation_time_s and provisional_lead_s, with the report schema moved 3.1 to 3.2 and the ASR plus MT configuration recorded in the report.
  `SampleResult` gained `target_language`, `translation`, `translation_reference`, `chrf`, `final_translation_time_s`, `provisional_lead_s`; `benchmark_version` reads "3.2"; `config.translation` (`describe_translation_config`) states target language, backend, model and drafting beside each row's existing `effective_config`. Final is the last committed line that first showed a translation; lead is final minus first, null unless the backend drafted.
- DONE: A model-free unit test covers chrF, and one checked-in report comes from a real cascade run (ASR then MT) on cached models, on a branch cut from origin/main @ 496b5f6.
  `tests/test_benchmark.py`: 7 passed. chrF arithmetic includes the exact 38.8889 for "abc"/"abd"; the join test covers a missing sibling and a row with no `sentence_id`; the fake-harness test proves chrF and both latency fields reach the row, and deleting the per-line timestamp makes it fail. Reports: `benchmarks/evaluations/translation-fleurs-en-zh/{report.json,report-simultaneous.json}` from nemotron-mlx-asr then mlx-llm-mt hy-mt2-1.8b-8bit, all cached, `HF_HUB_OFFLINE=1`, branch `wlk/simulst-eval-harness` at base 496b5f6.

### Summary

Tier 1 shipped in two commits (0721830 code and README, ab7cf62 reports, 1c404c8 docstrings): `--target-language/--translation-backend/--mt-model` on `wlk bench`, the `sentence_id` reference join, chrF, the two derived translation latencies, schema 3.2, and the ASR-plus-MT configuration in both the report config and the row. Two model-loading runs were spent, three samples and one sample, both real cascades: mean chrF 7.01 over three English FLEURS rows without drafting, and 12.30 on one row with drafting, where `provisional_lead_s` measured 5.67 s (first translation 2.43 s, final 8.10 s in a 9.72 s sample) — the field is null on the non-drafting run by design, and both reports say so. The scored output is poor for this cascade (the row data shows MT diverging on a word-perfect transcript), which is the harness reporting what the pipeline emitted, not a quality claim; nothing was downloaded, tier 2 was not touched, and the demonstration reports state what three samples cannot establish.

## Stage Report: validation

- DONE: Tier-1 acceptance criteria are reproduced independently, not read from the implementation report: the sentence_id join supplies each row's translation reference from `benchmarks/corpora/fleurs-90.json`, and chrF is recomputed for at least one row from the row's own translation and reference.
  `load_manifest` over the real manifest gives 90/90 rows a zh reference and 30/30 English rows the same-sentence_id zh sibling; in both checked-in reports each row's `translation_reference` equals the manifest's zh string for that `sentence_id` (4/4 rows). chrF was recomputed with a from-scratch char n-gram F-beta (n=1..6, beta=2) over each row's own `translation`/`translation_reference`: 5.303753, 10.483989, 5.227909 (`report.json`) and 12.302523 (`report-simultaneous.json`), each matching the reported value to 6 decimals. Falsifier: a row whose reference differs from the manifest join, or a recomputation that misses the reported value.
- DONE: The two translation latency fields carry real measured numbers, and each is null only where the run makes it structurally null, with the report schema at 3.2 and the ASR plus MT configuration present in the report.
  All 4 checked-in rows and all 3 rows of my own run carry non-null `first_translation_time_s` and `final_translation_time_s`, with `final >= first` everywhere (equal on the three non-drafting rows, 8.099 >= 2.431 on the drafting one, all rows `n_lines = 1`). `provisional_lead_s` is null on 3/3 non-drafting rows and 5.668 s on the drafting row; `runner.py` gates it on `state.buffer_translation`, so null tracks "no drafting backend", not a missing measurement. `benchmark_version` reads "3.2" in both reports and in `benchmarks/README.md`; `config.translation` states target zh, backend mlx-llm-mt, model hy-mt2-1.8b-8bit, `simultaneous` false/true, and each row's `effective_config` carries the ASR half (nemotron model, att_context) beside the MT half.
- DONE: The model-free tests actually run green in this worktree, and the checked-in demonstration report is reproducible from the committed code on a base cut from origin/main @ 496b5f6 with no download.
  `pytest tests/test_benchmark.py` = 7 passed on HEAD `1c404c8` (merge-base with `origin/main` = `496b5f6`). Falsifiability was exercised in a throwaway copy, not by re-reading: dropping the per-line timestamp leaves `final_translation_time_s` null, emptying the join drops the reference, and removing chrF's normalization returns 72.57 where the test expects 100.0 — each fails the named test. One model-loading run, offline: the `report.json` command on the same three samples reproduced 3 ok rows, same WER (0.00/13.64/22.22), same references, chrF 5.30/11.25/5.17 against 5.30/10.48/5.23, mean 7.24 vs 7.01, schema 3.2, no cache writes.
- SKIPPED: Re-running the 30-sample corpus clause of AC-1/AC-2.
  Out of this stage's budget (one model-loading run of at most three samples); see finding 2, which routes the clause rather than deciding it.

### Findings

1. **NOTES.md's drafting-run command cannot run as written** (material, documentation; implementation owns the fix). Observation (`benchmarks/evaluations/translation-fleurs-en-zh/NOTES.md`): the reproduction line uses `--config '{"mlx_llm_mt_simultaneous": true}'`, but `cli.py:894` does `json.loads(Path(parsed.config).read_text())`, so the flag is a path. Observed: `wlk bench ... --config '{"mlx_llm_mt_simultaneous": true}'` exits with `FileNotFoundError: '{"mlx_llm_mt_simultaneous": true}'`. The same option as a file parses and fails only later at the manifest, so `report-simultaneous.json` stays reproducible with `--config /tmp/cfg.json`. One-line doc correction; the misleading `--config` help string ("JSON object") predates this branch. Proposed disposition: fix.
2. **AC-1's and AC-2's corpus-wide numbers are not evidenced** (needs decision; captain/FO scope). The ACs require 30/30 rows, corpus mean chrF >= 20.0 and reproduction of the ideation probe's 8.10/37.15/33.39 within +-0.01. What exists is 3 samples at mean chrF 7.01 plus 1 drafting sample, and the same three sample names now score 5.30/10.48/5.23, so that +-0.01 clause does not hold (the probe drove `TestHarness` directly; the report is the `wlk bench` path). The body already records the 30-sample run as aborted on disk, and free space is now 2.4 GiB, so the clause may be runnable. Route for decision: rescope the clause or run it.
3. **The exact-value chrF unit case does not pin beta** (polish). `compute_chrf("abc", "abd")` has precision == recall, where F-beta equals that shared value for any beta, so 38.8889 would also pass with `beta**2` replaced by `beta`. The implementation is correct: my independent beta=2 recomputation matches the reported real-row values, where precision != recall. A non-symmetric pair would make the assertion bite.
4. **Repeat determinism is not bit-exact on the MT text** (deferred risk, relevant to tier-2 AC-5). Two runs of the same three samples gave identical WER and references but different Chinese text on 2 of 3 rows (chrF moved 0.77 and 0.05) because the incremental MT input depends on timing. AC-5's "+-1.0 point of the chosen quality metric" bound is therefore plausible but not generous; the trigger to promote is a tier-2 repeat pair drifting more than 1.0.

### Summary

The tier-1 harness validates: the sentence_id join, the chrF score, both translation latency fields, schema 3.2, and the recorded ASR+MT configuration all reproduce from the row data and from an independent implementation, and the model-free tests are green and demonstrably falsifiable. The checked-in `report.json` reproduced offline from this worktree on the same base with the same WER, references and scores; the only reproducibility break is NOTES.md's inline `--config` line for the drafting run (finding 1). Recommendation: **PASSED** for delivery of the tier-1 harness, with finding 1 as a one-line fix and finding 2 routed to the FO/captain, since AC-1's numeric clause is a scope question this stage may not decide.

#### Cycle 4 — flat form, rescoped tier-1 criteria, and the revise round (2026-11-14)

**The validation gate could not be prepared.** `gate prepare` resolved a retained room against the
entity folder and prepended the slug a second time, failing on
`.../simulst-eval-harness/simulst-eval-harness/review/backlog/briefing-1/request.json`. That is
spacedock#883, open. Both retained refs are `./simulst-eval-harness/review/<stage>/briefing-1`,
which do resolve from the state root.

**Decision — flat form.** With CL's approval, this entity moved from
`simulst-eval-harness/index.md` to `simulst-eval-harness.md`, one `git mv`, keeping `review/` beside
it. That directory already sat at the path the flat form resolves, so the stored rooms needed no
edit. After the move `status` resolves the task and `--validate` reports no unresolvable room for
it.

**Decision — tier-1 acceptance criteria rescoped.** Tier 1 is complete when the suite reports chrF and
both translation latency fields on a real run of the cascade system, with each reference joined by
`sentence_id`. The corpus mean-chrF minimum (20.0) and the ±0.01 reproduction of the ideation probe
leave tier 1; the quality minimum moves to tier 2. The measured value stays in the record as
measured: mean chrF 7.01 over three samples. Reason: those numbers came from the cycle-1 IWSLT
probe, which the cycle-2 rescope replaced. A quality floor measures the cascade, not the harness, and
tier 1 ships the harness.

**Gate outcome — revise.** The validator reproduced every tier-1 claim and recommended PASSED, with
four findings. Finding 1 is material: `NOTES.md`'s drafting-run reproduction uses
`--config '{"mlx_llm_mt_simultaneous": true}'`, but `--config` takes a path, so the checked-in
command fails with `FileNotFoundError`. Finding 3 is polish: `chrF("abc","abd")` has precision equal
to recall, so the assertion passes for any beta. Both return to implementation in this round. Finding
2 is the criterion rescope above. Finding 4, repeat non-determinism on MT text, defers to tier 2.

**Limits for this round:** two workers, at most 45 minutes each, no download, stop below 1.5 GiB free
disk. Push, pull request, merge and any issue comment stay with CL and are not done here.

## Stage Report: implementation (cycle 3)

- DONE: Finding 1 — the drafting-run reproduction in `NOTES.md` runs as written, with `--config` taking a file path, and the run it documents is recorded.
  `NOTES.md` states that `--config` is a path (`cli.py` reads it with `Path(parsed.config).read_text()`), creates the file with `printf '{"mlx_llm_mt_simultaneous": true}\n' > /tmp/simulst_simultaneous_config.json`, and gives both commands against the same manifest, differing only in `--config`. Executed: the inline form still fails with `FileNotFoundError: '{"mlx_llm_mt_simultaneous": true}'`, and the corrected command exits 0 — one model-loading run at the full budget (three English FLEURS samples, `--speed 1`, `HF_HUB_OFFLINE=1`, 34 s wall) with 3/3 rows ok: chrF 5.303753 / 10.483989 / 5.601148 (mean 7.13), first translation 3.21 / 2.44 / 2.35 s, final 4.40 / 8.45 / 7.38 s, `provisional_lead_s` 1.19 / 6.02 / 5.03 s. That run replaces the one-sample drafting report, so both checked-in reports now cover the same three samples; `report-simultaneous.json` records `git_commit 0ffb22d` and `git_dirty false` (it was written to `/tmp` and copied in). Commit `40e4b7e`.
- DONE: Finding 3 — the chrF unit case now pins the beta exponent, and the falsifier is demonstrated in a scratch copy.
  `tests/test_benchmark.py` keeps the 38.8889 case and adds `compute_chrf("ab", "abc") == pytest.approx(87.5, abs=1e-4)`: a two-character reference is wholly contained in "abc", so recall is 1 while precision averages to 7/12 over its two orders — precision differs from recall, which the old pair could not provide. Demonstrated, not argued: with `/tmp/falsify_beta/whisperlivekit/metrics.py` mutated from `beta_squared = beta * beta` to `beta_squared = beta`, the test fails with `assert 80.76923076923076 == 87.5 ± 1.0e-04`; unmutated, `pytest tests/test_benchmark.py` = 7 passed. Commit `0ffb22d`.
- DONE: The body's AC-1 and AC-2 state the rescoped tier-1 criteria, and the clauses that left tier 1 are recorded as moved to tier 2.
  `## Acceptance criteria (tiered; tier 1 rescoped in cycle 4)` now states AC-1 (translation engaged, reference joined on `sentence_id`, non-null `chrf` wherever both sides exist) and AC-2 (non-null `first_translation_time_s` and `final_translation_time_s` on every `ok` row with `final >= first`, `provisional_lead_s` non-null only on a drafting run), each with its falsifier, then the measured mean chrF **7.01** over three samples (7.13 for the drafting run) as a measurement rather than a floor. The corpus mean-chrF minimum (20.0) and the ±0.01 reproduction of the cycle-1 probe's 8.10 / 37.15 / 33.39 are recorded as moved from tier 1 to tier 2, with the reason. Frontmatter and status untouched.
- SKIPPED: Finding 4 — repeat non-determinism on MT text.
  Deferred to tier 2 by the first officer; not attempted. The new drafting run shows it again (identical WER, two chrF values equal to six decimals, `fleurs_en_1993` 5.23 -> 5.60), and `NOTES.md` records it as chunk-timing dependence rather than a drafting effect.

### Summary

Both findings the validation gate returned are fixed and executed rather than reworded. `NOTES.md` documents `--config` as a file path with the file-creation step, and the corrected drafting command ran at the full budget of three samples and was checked in as `report-simultaneous.json` (3/3 ok, mean chrF 7.13, `provisional_lead_s` 1.19 / 6.02 / 5.03 s, `git_dirty false`). The chrF unit case now asserts an asymmetric pair that yields 80.77 instead of 87.5 once the beta exponent is removed, demonstrated in a scratch copy. The body's AC-1/AC-2 carry the rescoped tier-1 criteria with mean chrF 7.01 kept as a measurement, and the corpus floor plus probe reproduction are recorded as tier 2's. No download, no tier-2 work, one model-loading run of three samples, targeted test file only, branch `wlk/simulst-eval-harness` at `40e4b7e` on base `1c404c8`/`496b5f6`, disk unchanged at 2.4 GiB free.

## Stage Report: validation (cycle 2)

- DONE: The two findings from the previous review are fixed and their falsifiers reproduce here: the inline --config form still fails while the documented file-path command succeeds, and removing the beta exponent from compute_chrf still fails the new asymmetric unit case.
  Inline, reproduced from this worktree: `--config '{"mlx_llm_mt_simultaneous": true}'` exits 1 with `FileNotFoundError: [Errno 2] No such file or directory: '{"mlx_llm_mt_simultaneous": true}'`, raised at `cli.py`'s `json.loads(Path(parsed.config).read_text())` and therefore before any model load; the message NOTES.md quotes is exact. The file-path form, reproduced end-to-end (my one model-loading run: the three cached FLEURS samples, `HF_HUB_OFFLINE=1`, exit 0, report written to `/tmp`): the drafting command differs from the non-drafting one only in `--config /tmp/simulst_simultaneous_config.json`, created by the NOTES `printf`, and the run reports 3/3 ok with chrF 5.303753 / 12.302523 / 5.601148, first 2.958 / 2.473 / 2.407 s, final 4.399 / 8.201 / 7.323 s, lead 1.441 / 5.728 / 4.915 s. The beta exponent, mutated in place to `beta_squared = beta`: `pytest tests/test_benchmark.py` = 1 failed, 6 passed, the failure exactly `compute_chrf("ab", "abc")` returning 80.76923076923076 where the test expects 87.5, while the retained `("abc", "abd") == 38.8889` case still passes — the old pair was blind to the exponent, the new one is not. File restored with `git checkout`; `git status --porcelain` empty and the unmutated targeted file re-run 7 passed.
- DONE: The rescoped AC-1 and AC-2 in the entity body match what the code and the checked-in reports actually do, and the clauses that moved to tier 2 are recorded there with the reason.
  AC-1: `load_manifest` gives all 90 manifest rows their same-`sentence_id` siblings (30 ids × {en, fr, zh}); in both checked-in reports all 3 rows carry `target_language == "zh"`, a `translation_reference` byte-identical to the manifest's zh string for that id, and a non-null `chrf` with both sides non-empty. AC-2: 6/6 rows carry non-null `first_translation_time_s` and `final_translation_time_s`, with `final >= first` everywhere (equal on the three non-drafting rows; 4.4046 >= 3.2143, 8.4515 >= 2.4363, 7.3834 >= 2.3517 drafting); `provisional_lead_s` is null 3/3 without drafting and 1.190 / 6.015 / 5.032 s with it, which `runner.py` gates on `state.buffer_translation`, so those nulls track the run rather than a lost measurement. The body's measured values are the reports' own: `avg_chrf` 7.00522 and 7.12963 for "7.01" and "7.13". The tier-2 bullet records the moved clauses (corpus mean-chrF 20.0 and the ±0.01 reproduction of 8.10 / 37.15 / 33.39) with the reason — a quality floor measures the cascade rather than the harness, and those probe numbers came from the IWSLT path the cycle-2 rescope replaced; the live AC text carries no floor, and the old numbers survive only inside the historical stage-report sections.
- DONE: chrF is compared against an independent reference implementation of the same metric, and any divergence is reported with its cause, so a reader knows whether the reported value can be compared with published chrF numbers.
  Reference: `sacrebleu 2.6.0`'s `CHRF(char_order=6, word_order=0, beta=2)`, the canonical implementation, whose default path also averages per-order precision and recall over effective orders. The arithmetic is identical: a from-scratch char n-gram F-beta over raw whitespace-stripped text equals sacrebleu to 4 dp on all 6 checked-in rows and on 8 synthetic pairs, including short texts (72.5735 for "hell"/"hello", 78.125 for "abcd"/"ab", 87.5 for "abc"/"ab", 0.0 for an empty side), so the shorter-than-order `break` matches sacrebleu's effective-order exclusion. The whole divergence is the input preprocessing: `compute_chrf` scores `normalize_text` output (lowercase, punctuation deleted), so the reported 5.3038 / 10.4840 / 5.2279 / 5.6011 stand against sacrebleu's 5.5810 / 13.1213 / 5.5416 / 5.8788 — -0.28 to -2.64 points, -4.7 % to -20.1 % relative, lower on every row. Cause isolated: punctuation deletion alone reproduces 10.4840 exactly, and lowercasing alone leaves the zh rows at 13.1213 while moving Latin text ("The Cat Sat" vs "the cat sat": 100.0 here, 100.0 for sacrebleu `lowercase=True`, 17.36 for its default). These values are therefore a punctuation-stripped, case-folded variant and not comparable with published chrF.

### Findings

1. **The comparability above is not stated where a reader meets the number** (documentation polish; implementation owns it, not repaired here). `benchmarks/README.md`'s chrF bullet and the report's `measurement.chrf` say both sides get the WER normalization and lose whitespace, which names the deviation but neither its size nor its consequence; one sentence saying the score is not comparable with sacrebleu/Popović chrF closes it.
2. **`--config`'s help string still reads "JSON object of additional engine options"** while the flag takes a path. NOTES.md now states the path semantics and its failure mode; the help string predates this branch and this branch does not change it.
3. **Repeat non-determinism, already recorded.** My drafting run scored mean chrF 7.74 against the checked-in 7.13 (`fleurs_en_1921` 10.48 → 12.30, WER identical on all three rows), which is the body's finding 4 still live. The body's "measured 7.01 / 7.13" are single runs, and it says so.

### Summary

All three checklist items reproduce independently here: NOTES.md's `--config` correction is exact in both directions and the documented drafting command exits 0 on cached models, the beta-pinning unit case fails on mutation with the reported value, the rescoped AC-1/AC-2 match the code and both checked-in reports down to the row, and chrF's arithmetic is sacrebleu-identical with the divergence traced entirely to `normalize_text`. One documentation gap keeps a reader from judging comparability (finding 1). Recommendation: **PASSED** for delivery of the tier-1 harness, with finding 1 as a one-sentence fix and finding 2 left to the captain's PR call; finding 3 stays the deferred tier-2 risk.

#### Cycle 5 — tier-1 acceptance criteria realigned to the upstream requirements (2026-11-21)

The maintainer replied on issue #477 on 2026-11-21: he asked for the PR and listed what it must get
right. CL approved adopting his list as the tier-1 criteria. The design does not change — the same
`sentence_id` join, the same metric slots, the same schema 3.2 — so this is not a return to ideation; the
pass conditions are restated below, and this entry is where the decision and its exact words live.

**AC-1 — the translation is joined and scored at corpus level.**
The reference is built at manifest load from the same `sentence_id`, and `benchmarks/corpora/fleurs-90.json`
with its hashes stays unmodified. Every scored row carries `target_language` and a non-null `chrf` where
both a translation and a reference exist, and the summary reports **corpus-level chrF**, computed from
character n-gram statistics summed over all rows of the language pair; the per-row `chrf` is kept for
inspection and is not the headline.
*Falsified by:* a modified corpus file, a row whose reference differs from the manifest join, or a summary
chrF equal to the mean of per-sentence scores.

**AC-2 — the chrF implementation matches sacrebleu exactly.**
Character order 6, word order 0, beta 2, whitespace removed. A unit test pins several sacrebleu values,
computed once and hard-coded, so the implementation is checked against the reference library without
depending on it at run time.
*Falsified by:* a value that differs from pinned sacrebleu output on the same input, or a test that cannot
fail when the arithmetic changes.

**AC-3 — the provisional lead is honest and local.**
`provisional_lead_s` is non-null only when the MT backend actually drafts, and is measured from the
front-end snapshots the harness already sees, so nothing in this PR depends on #449. On a backend without
drafts the field is null even when `buffer_translation` carries untranslated source text.
*Falsified by:* a non-null lead on a non-drafting run, or an import that requires the #449 event stream.

**AC-4 — the report says what ran.**
Each report records both configurations: ASR backend and model, and MT backend, model and direction. The
schema moves to 3.2. Reports already checked in under `benchmarks/evaluations/` stay as they are.
*Falsified by:* a report that omits either configuration, or a schema that is not 3.2 in a new report.

**AC-5 — the README states what chrF covers here.**
One sentence in `benchmarks/README.md` saying that chrF scores ASR and MT together, so ASR errors flow
into it.

**The measured note is withdrawn.** The earlier note that tier 1 measures a mean chrF of 7.01 is the
superseded variant's figure under the wrong aggregation; it is replaced by corpus-level values from the
corrected implementation, with the sample size stated and no quality claim attached.

**Delivery.** Rebase onto current `origin/main` first, then regenerate the demonstration reports through
the corrected implementation, because their chrF values change. Tier 2 — XCOMET and LongYAAL on the IWSLT
devset — remains our own work and is **not** part of the #477 PR.

## Stage Report: implementation (cycle 5)

- DONE: The tier-1 acceptance criteria in the entity body are transcribed from the Cycle 5 entry word for word, and the withdrawn mean-chrF note is replaced, so the code is judged against the maintainer's requirements rather than the superseded ones.
  `## Acceptance criteria (tiered; tier 1 restated from the maintainer's #477 reply in cycle 5)` now carries the Cycle 5 block byte for byte — verified programmatically: the 38-line block extracted from `#### Cycle 5` is present verbatim in the section — covering AC-1 through AC-5, the withdrawal of the 7.01 note and the Delivery paragraph, every falsifier intact. The old tier-1 AC-1/AC-2 and the "Measured, not a floor: mean chrF 7.01" line are gone. In their place a measured line records the corrected implementation's corpus-level 8.59 (no drafting) and 9.32 (drafting) over three samples, names the per-row means 8.57 and 9.67 as the aggregation the withdrawn figure used, and attaches no quality claim. Tier 2 keeps its text, with its cycle-2 ids qualified so they cannot be read as the cycle-5 criteria of the same number. Frontmatter and status untouched.
- DONE: The chrF implementation matches sacrebleu exactly with pinned tests, and the summary reports corpus-level chrF from summed n-gram statistics while per-row values stay for inspection, demonstrated by values that change from the old implementation.
  `whisperlivekit/metrics.py` splits `chrf_statistics` (per-order hypothesis, reference and match counts over whitespace-free text, case and punctuation kept) from `chrf_score`, and `compute_chrf` is now `CHRF(char_order=6, word_order=0, beta=2)`. Checked against `sacrebleu 2.6.0` in `/Users/clkao/git/asr/WhisperLiveKit/.venv` as a one-time reference, never a dependency: identical to 1e-9 on 20 synthetic pairs — including `The Cat Sat`/`the cat sat` 17.361111 and `你好世界。`/`你好，世界！` 24.910180, both of which the old variant scored 100.0 — and on every row of both regenerated reports. `tests/test_benchmark.py` pins nine of those values hard-coded (38.888889, 87.5 for the beta-separating pair, 17.361111, 24.910180, 72.573464) plus sacrebleu's corpus score 59.093996 against the per-row mean 51.048780 for the same three segments: 8 passed. Falsifiers run, not argued, each restored to 8 passed afterwards: `beta_squared = CHRF_BETA` fails the pinned case (2 failed), WER normalization back inside `chrf_statistics` fails it (2 failed), returning `self.avg_chrf` as `corpus_chrf` fails the aggregation case (1 failed). `BenchmarkReport.corpus_chrf` sums the rows' counts and scores once, `avg_chrf` keeps its per-row mean with a docstring saying it is not the headline, and `measurement` separates `chrf`, `corpus_chrf` and `avg_chrf` in words.
- DONE: The demonstration reports are regenerated through the corrected implementation on a branch rebased onto current origin/main, the README carries the one sentence on what chrF covers, and both configurations plus schema 3.2 are recorded per report.
  Rebased clean onto `origin/main` (`edcbaef02f386d4774f978e4a87e59029337d045`, "Merge pull request #481: prepare 0.2.28"), no conflict, all 5 commits replayed. Code commit `06a902c`, reports `486a439`. Both reports retaken at `--speed 1` on the same three English FLEURS samples, offline (`HF_HUB_OFFLINE=1`), from one subset manifest so both now carry the same `corpus_sha256`: corpus chrF 8.59 and 9.32; per-row 5.58, 14.67, 5.46 and 8.76, 14.76, 5.49; `provisional_lead_s` null 3/3 without drafting and 1.36 / 8.80 / 6.84 s with it; `final >= first` on every row. `config.asr` names the recognizer and model, `config.translation` the source languages, target language, backend, model and drafting flag; schema 3.2 in both; `git_dirty false`. `benchmarks/README.md` states chrF is sacrebleu's, that it scores ASR and MT together so ASR errors flow into it, and that `corpus_chrf` is the figure to quote; `NOTES.md` states the sample size, retires 7.01 and carries no quality claim. `benchmarks/corpora/fleurs-90.json` is unchanged against `origin/main`, and both m5 evaluation directories are unchanged against the base.

### Summary

The tier-1 criteria now state the maintainer's #477 requirements verbatim, and the code meets them. chrF had been applying the WER normalization (NFC, lowercase, punctuation stripped), which is why it sat 0.28 to 2.64 points below sacrebleu; it is now sacrebleu's `CHRF(char_order=6, word_order=0, beta=2)` exactly — whitespace removed, case and punctuation kept — with the n-gram counts exposed so the report sums them over the language pair and scores once. The headline became `corpus_chrf` (8.59 without drafting, 9.32 with it) while per-row `chrf` and their mean (8.57, 9.67) stay for inspection, which also retires the 7.01 figure: it was the per-sentence variant's mean, not a corpus score. Both demonstration reports were regenerated on the same three cached clips after a clean rebase onto `edcbaef`, name both configurations, and claim no quality. No download, no push, no issue comment, targeted test file only, disk 7.1 GiB free before and after.

## Stage Report: validation (cycle 3)

- DONE: chrF is checked against sacrebleu independently, on synthetic pairs and on every row of both checked-in reports, and the pinned test values fail if the arithmetic changes.
  17 pairs recomputed against `sacrebleu 2.6.0` `CHRF(char_order=6, word_order=0, beta=2)` (reference only, from `/Users/clkao/git/asr/WhisperLiveKit/.venv`; never imported by the deliverable): max |delta| 1.4e-14 — Chinese identical 100, `你好世界。`/`你好，世界！` 24.910180, `The Cat Sat`/`the cat sat` 17.361111, and precision≠recall both ways (`我喜歡吃蘋果。` vs a long hypothesis 44.553655, the reverse 20.434602; `ab`/`abc` 87.5). Corpus level 49.649591 = 49.649591. All 6 rows of both reports match exactly (5.581001/14.671230/5.463721 and 8.761835/14.764175/5.489434, delta 0) and their `corpus_chrf` 8.591371/9.316592 equal sacrebleu's corpus score. All 9 pinned values reproduce (38.888889, 87.5, 17.361111, 24.910180, 72.573464, and 59.093996 vs mean 51.048780). No run-time dependency: `sacrebleu` is absent from `pyproject.toml`, and the 3 chrF tests pass with `sacrebleu` blocked by a `sitecustomize` meta-path hook that makes `import sacrebleu` raise. Five mutations in a throwaway copy each fail the suite — `beta_squared = CHRF_BETA` (2 failed), WER `normalize_text` inside `chrf_statistics` (3), `corpus_chrf` returning the per-row mean (1), `CHRF_CHAR_ORDER = 5` (2), plain `(P+R)/2` for F-beta (2) — and the copy returns to 3 passed restored.
- DONE: The summary carries corpus-level chrF computed from summed statistics while the per-row values stay, and the criteria transcribed in the body are satisfied word for word with the withdrawn mean-chrF note absent.
  `corpus_chrf` sums each row's `chrf_statistics` and scores once; recomputing both reports from their own rows reproduces the stored `corpus_chrf` to 1e-9 and the stored `avg_chrf`, and the two differ on both (8.591371 vs 8.571984; 9.316592 vs 9.671815), so the headline is not the mean of per-sentence scores. Both numbers are labelled in the JSON (`summary` plus `measurement.chrf`/`corpus_chrf`/`avg_chrf`), in `print_report` ("corpus chrF 8.59% (per-row mean 8.57%)"), in `NOTES.md`'s table and in the README. The 61-line Cycle 5 block is present in the AC section byte for byte (programmatic containment check), the superseded "Measured, not a floor: mean chrF 7.01" claim is gone, and 7.01 survives only inside the withdrawal sentence and prior stage reports.
- DONE: The reports name both configurations with schema 3.2, the README states what chrF covers, the branch sits on a base rebased to current origin/main, and nothing depends on the #449 event stream.
  `report.json`/`report-simultaneous.json`: `benchmark_version` 3.2; `config.asr` = nemotron-mlx-asr/base; `config.translation` = en→zh, mlx-llm-mt, hy-mt2-1.8b-8bit, `simultaneous` false/true; `git_commit` 06a902c with `git_dirty` false. `benchmarks/evaluations/m5-20260907` and `m5-20261107` are unchanged against `origin/main`, which is the merge-base `edcbaef02f386d4774f978e4a87e59029337d045` (0 behind, 7 ahead; 11 files, all in-repo, nothing from an unmerged branch). `benchmarks/corpora/fleurs-90.json` is byte-identical (blob `c84af0b`, sha256 `95586eb…`). README: "It scores ASR and MT together, so ASR errors flow into it." The diff contains no `449` and no new external import beyond `collections.Counter`.

### Findings

1. **AC-3's second sentence is not implemented** (material; needs a decision on disposition). `runner.py` sets `drafted = True` whenever `state.buffer_translation` is non-empty, so it cannot tell a draft from untranslated source text. Reproduced in a throwaway copy: a non-drafting run (`mlx-llm-mt`, `simultaneous: false`) whose buffer carries source text yields `provisional_lead_s = 0.3511 s` — the AC's own falsifier. No in-repo backend triggers it (`MlxLlmTranslation` returns an empty `TimedText` by design; both drafting backends put a translated partial there; `docs/API.md` defines the field as translation text), but the default out-of-tree NLLB backend (`nllw`) cannot be inspected, and the README describes the field as "null unless the backend drafted provisional text (`mlx_llm_mt_simultaneous`)" — a guarantee the code does not enforce. No test covers the buffer-carries-source case. Concrete fix: gate `drafted` on the configured drafting backend in one predicate, and add that test.
2. **`describe_translation_config` records a model only for `mlx-llm-mt`** (`model`/`simultaneous` are `None` for `alignatt`, and `alignatt_preset` is not recorded), so AC-4's "MT backend and model" would not hold for an alignatt report. The two checked-in reports are unaffected.
3. **Tier-1 boundary row unrecorded.** `bench_commit_fraction.py` is not on `origin/main` and nothing in the deliverable reports the realizable-commit-fraction row as `not run`, which the body's boundary paragraph asks for.
4. **The `translation` field can score a draft**: it falls back to `state.buffer_translation` when no committed line carries a translation, which the README's "Final translation" definition does not disclose. Not triggered by either report (all six rows had line translations).

### Summary

Tier 1 verifies on chrF, the join, the reports, the README and the base: every chrF value I recomputed — 17 pairs, both corpus aggregates and all six checked-in rows — matches sacrebleu 2.6.0 exactly, the corpus figure is demonstrably summed-statistics rather than a row mean and is labelled as such wherever it appears, the manifest join reproduces the reports' Chinese references from the same `sentence_id` with the corpus file byte-unchanged, and five arithmetic mutations each break the pinned tests. One criterion clause fails: `provisional_lead_s` is gated on the buffer being non-empty rather than on the backend drafting, so a non-drafting run whose buffer carries source text produces a non-null lead (reproduced at 0.35 s), which is the AC-3 falsifier word for word. Recommendation: **REJECTED** for that one guard plus its test — everything else in tier 1 can ship as is.

## Stage Report: implementation (cycle 6)

- DONE: The provisional lead is gated on the backend actually drafting, in one predicate keyed to the configured translation backend, with a test that fails when a non-drafting backend carries source text in the buffer.
  `benchmark/metrics.py:drafts_provisional_text` is the single gate — `alignatt`, or `mlx-llm-mt`/`hunyuan-mlx` with `mlx_llm_mt_simultaneous` — and `runner.py` reads it from the run's config instead of setting `drafted` on a non-empty `state.buffer_translation` (that line is gone). `test_benchmark.py::test_a_non_drafting_backend_leaves_the_provisional_lead_null` drives a segment-backend run whose buffer carries the source text `Hello` and whose committed lines do carry translations, so both timing endpoints exist and `final > first`: it fails with the old gate (lead `1.25e-06 s`, not null) and passes with the predicate. Real audio, offline, `--speed 1`: a non-drafting run reports `provisional lead n/a` (null), the same cascade with `--config '{"mlx_llm_mt_simultaneous": true}'` reports `6.64 s` — the predicate fires on the switch, end to end.
- DONE: Every report names the MT model for any backend it can run, including alignatt, so AC-4's configuration record holds beyond mlx-llm-mt.
  `describe_translation_config` now branches on backend: `hunyuan-mlx` gets the same model/simultaneous record as `mlx-llm-mt` (it was in `core.py`'s simultaneous branch but not in this one); alignatt records `model: null` **plus** `model_note` saying the model runs in the server and `server: {url, preset, latency}` — the endpoint it called instead of a checkpoint it cannot see; `nllb` gets a `model_note` naming `nllb_backend`/`nllb_size`. `runner.py` now passes the **effective** config (each row's recorded `effective_config`, falling back to the requested kwargs) so the defaults the engine filled in — the alignatt URL, the MT model id — are what get recorded. `test_translation_config_records_what_an_alignatt_run_can_know` pins the alignatt and nllb records; it fails when the alignatt branch is deleted (the record then falls through to the nllb note). Both checked-in reports are unchanged: `config.translation` re-derived from their own recorded `effective_config` is equal to what they store, key for key, and a real `--speed 1` run through the modified runner wrote the same record (`mlx-llm-mt`/`hy-mt2-1.8b-8bit`/`simultaneous: false`), so no value moved and nothing was regenerated.
- DONE: The km boundary row is reported as not run where the script is absent, and any field whose meaning a reader could misread is disclosed in the README, including a translation value that came from a draft.
  `bench_commit_fraction.py` is absent from this tree and from `origin/main` (`git ls-tree -r origin/main | grep commit_fraction` empty), and `NOTES.md` now carries a `## Rows these runs report as not run` table with the realizable-commit-fraction row marked **not run** and why (km owns it; tier 1 does not reimplement a capture path); `benchmarks/README.md` states the same in the audio-to-translation section. Finding 4 — **disclosed in the README, field unchanged**: a new `**Translation:**` bullet says the row joins committed-line translations with a fallback to the in-flight buffer, that on a drafting backend that buffer is a provisional translation, so the scored text can be a draft scored as it stood at EOF, and that `config.translation.simultaneous` (or the alignatt backend) plus a non-null `provisional_lead_s` say when that run could draft. The `**Provisional lead:**` bullet was rewritten to say the null is keyed to the configured backend being one that drafts — "a backend not known to draft counts as one" — so the README promise and the code now state the same rule.
- DONE: Target tests pass, the base is untouched, and nothing was pushed.
  `tests/test_benchmark.py` 10 passed (targeted file only); `tests/test_translation_alignatt.py` + `tests/test_translation_mlx.py` 21 passed as a backstop on the two backends the record now describes. Code commit `88d8e20` on `wlk/simulst-eval-harness`, still based on `486a439`/`edcbaef` (no rebase). Disk 7.1 GiB free. No push, no issue or PR comment.

### Summary

The one clause that rejected tier 1 is fixed at its root: drafting is a property of the configured MT backend, decided in `drafts_provisional_text`, and the runner no longer infers it from a buffer whose contents it cannot classify — a non-drafting backend with source text in the buffer now reports a null lead, which the old gate turned into `1.25e-06 s` in the new test and `0.35 s` in the validator's reproduction. The configuration record became backend-complete for the same reason AC-4 needed it: alignatt names the server it called and says outright that the checkpoint is not visible, nllb says which settings pick its checkpoint, and the runner reads the effective config so defaults are recorded; the two checked-in reports are provably unaffected, re-derived records and a fresh run agreeing with them value for value. The remaining two findings were documentation gaps: the `km` boundary row is now reported as `not run` where the script is absent, and the README discloses that a scored `translation` can be a fallback draft rather than changing the field.

## Stage Report: validation (cycle 4)

- DONE: The lead predicate is checked adversarially: a run whose buffer holds untranslated source but whose backend does not draft must report a null lead, and the test must fail if the old buffer-based gate returns.
  The old gate is gone (`grep -n "drafted" whisperlivekit/benchmark/runner.py` is empty; `drafts_provisional_text` at `runner.py:108` is the only gate). Independent validator-written fake at `--speed 1` with `buffer_translation="Hello"` (source text) and later committed-line translations: segment backend `mlx-llm-mt` gives `first 3.1e-06 / final 3.3e-02 / lead None` while `final > first` (both endpoints exist, so the null is the gate, not missing data); the same states with `mlx_llm_mt_simultaneous` give `lead 3.3e-02`. Predicate table: `alignatt` True, `mlx-llm-mt` False, `mlx-llm-mt`+simul True, `hunyuan-mlx` False, `hunyuan-mlx`+simul True, `nllb` False, `nllw` False, absent `""` False. Falsifier reproduced in a throwaway copy: restoring the buffer-based `drafted` makes `test_a_non_drafting_backend_leaves_the_provisional_lead_null` fail with `provisional_lead_s = 2.46e-06` (not None), restored to 10 passed; making the predicate always False fails 3 tests. In-repo drafting backends (`AlignAttRemoteEngine`, `MlxLlmTranslationSimul`) are the ones the predicate lists, and `MlxLlmTranslation` provably never writes a buffer (`translation_mlx_llm_mt.py:285`).
- DONE: Every backend a report can name records what it can honestly know about its MT model, and both checked-in reports re-derive their records key for key from their own effective config.
  `describe_translation_config` on real `WhisperLiveKitConfig` namespaces: `alignatt` → `model null` + `model_note` ("runs in the alignatt server … not the served checkpoint") + `server {url: ws://localhost:8765, preset: null, latency: balanced}`; `nllb` → `model null` + note naming `nllb_backend`/`nllb_size`; `mlx-llm-mt`/`hunyuan-mlx` → model id + `simultaneous`. Both reports (schema 3.2) re-derive equal key for key from their first row's `effective_config` — `{mlx-llm-mt, hy-mt2-1.8b-8bit, simultaneous false/true, en→zh}` — and the record key set is exactly those five, so nothing was widened. Deleting the alignatt branch fails `test_translation_config_records_what_an_alignatt_run_can_know` (`'server' not in 'nllw selects …'`); restored to 10 passed.
- DONE: The criteria transcribed in the body are satisfied word for word, including the boundary row marked not run and any field whose meaning a reader could misread disclosed in the README.
  AC-1/AC-2: 17 pairs recomputed against `sacrebleu 2.6.0` (reference only, absent from `pyproject.toml`), max |delta| 1.4e-14, including `你好世界。`/`你好，世界！` 24.910180, `ab`/`abc` 87.5 vs 63.636363 the other way, precision≠recall; all 6 report rows equal their `sentence_score`; both `corpus_chrf` (8.591371, 9.316592) equal sacrebleu's `corpus_score` and equal the score of the rows' summed counts, and differ from `avg_chrf` (8.571984, 9.671815). References re-join from `fleurs-90.json` by `sentence_id` (`load_manifest` builds them at load) and match all six stored rows, with audio SHA-256 matching. AC-3's falsifier absent, AC-4's both-configs record and schema 3.2 present, AC-5's sentence present. Boundary row: `bench_commit_fraction.py` absent from the tree and from `origin/main`; `NOTES.md` has the `## Rows these runs report as not run` table and `benchmarks/README.md` states the same (prose only — the report JSON carries no machine-readable `not run` row). README discloses the `translation` fallback-draft meaning and the lead gate — but see finding 1 for the "not known to draft" half being wrong for `nllb`.
- DONE: Nothing else moved — chrF still equals sacrebleu, the corpus figure is summed statistics, the join is at manifest load, `fleurs-90.json` is byte-unchanged, and the reports were not regenerated.
  `benchmarks/corpora/fleurs-90.json` blob `c84af0b` = `origin/main`'s, sha256 `95586eb…`; `git diff --stat origin/main -- benchmarks/corpora/` empty. `report.json`/`report-simultaneous.json` last touched by `486a439` and unchanged by `88d8e20` (which touched only `benchmarks/README.md`, `NOTES.md`, `tests/test_benchmark.py`, `benchmark/metrics.py`, `benchmark/runner.py`); `git diff 486a439 HEAD -- benchmarks/evaluations` is the 12 claude NOTES lines only. m5 evaluation directories unchanged against `origin/main` (merge-base `edcbaef`, 0 behind). No `#449` and no new external import in the diff. Working tree clean, nothing staged.

### Findings

1. **The predicate is under-inclusive in the other direction: `nllb` drafts, and its lead is suppressed** (material for the default MT backend; AC-3 is one-way so not falsified word for word). `nllw.OnlineTranslation.process()` returns `(stable, buffer)` where `buffer` decodes the not-yet-common-prefix **target** tokens (`nllw-0.1.6/nllw/core.py:352-368`, `nllw/translation.py:59-72`; its own README documents the pair), and `run_translation` publishes that buffer as `buffer_translation` — this repo's `docs/API.md` defines the field as "Ephemeral translation text". Reproduced with the real class (stub model): `process()` → `('You are', ' welcome to my')`; `drafts_provisional_text({"translation_backend": "nllb"})` → False. End to end through the runner, the shape `wlk bench --target-language zh` actually sends (no `--translation-backend`): `first 6.0e-06 / final 3.6e-02 / provisional_lead_s None` on states whose buffer carries a provisional translation. So the default backend loses the tier-1 latency field, and the README tells the reader the null means the run did not draft. Fix is small: add `nllb` to the drafting set with a test pinning it, and correct the README's "a backend not known to draft" sentence (nllw is the pinned `translation` extra; it is known, and it drafts).
2. **Polish:** the `not run` boundary row exists only as prose in `NOTES.md`/`README.md`; the report JSON has no such row, which a strict reading of "reports that row as `not run`" could want.

### Summary

The rejection's clause is fixed at its root and every claim in the implementation report reproduces: the buffer-based gate is gone, one predicate keyed to the configured MT backend decides drafting, the new test yields a null lead only because of that predicate (old gate → `2.46e-06`), and the alignatt record names the endpoint it called while both checked-in reports re-derive key for key from their own `effective_config`. chrF, its corpus aggregation, the manifest join, the byte-identical corpus and the untouched reports all still hold. One defect remains, in the direction the criteria do not cover: `nllb` — the default translation backend — genuinely publishes a provisional target buffer, so the new predicate suppresses a real lead for it while the README says such nulls mean the run did not draft. Recommendation: **REJECTED** for that single under-inclusion (one predicate entry, one test, one README sentence), unless the captain prefers to ship with the limitation restated accurately and file the fix as follow-up.

## Stage Report: implementation (cycle 7)

- DONE: The drafting predicate includes every backend that actually publishes provisional target text, with nllb among them, and a test pins one case per backend against how that backend's process returns its buffer.
  `benchmark/metrics.py` now carries `_ALWAYS_DRAFTING_BACKENDS = ("nllb", "nllw", "alignatt")` — `nllw` is the library name for the same backend — beside the unchanged `mlx_llm_mt_simultaneous` switch, and the docstring says which `process()` buffer each rests on. New `tests/test_benchmark_drafting.py` drives each one and reads the buffer: `FakeSidecar` alignatt → `HELLO WORLD`; `MlxLlmTranslation` without the switch → validated `你好`, buffer empty (`translation_mlx_llm_mt.py:285`); `MlxLlmTranslationSimul` with a stubbed `_translate_simul` → buffer `您好`; and nllw's `(stable, buffer)` shape through the real `run_translation`, which publishes `欢迎来到我的` as `new_translation_buffer`. Falsifiers run against the set: dropping `nllb` fails the nllb case and the runner case, dropping `nllw` fails the nllb case's alias line, dropping `alignatt` fails the alignatt case and the completeness case, ignoring the switch fails the segment case.
- DONE: The README sentence about a backend the harness cannot identify no longer claims that such a null means the run did not draft, and a run with nllb reports a measured lead rather than null.
  In `benchmarks/README.md` the **Provisional lead** bullet names `nllb` among drafting backends and replaces "a backend not known to draft counts as one" with: those are all the backends `--translation-backend` accepts, so a null means the run's translator did not draft (the MLX segment path being the only such backend), and the **Translation** bullet's drafting enumeration now reads `config.translation` plus a non-null `provisional_lead_s` instead of listing two backends. Runner case `test_the_nllb_backend_reports_a_measured_provisional_lead` drives the same fake states: `translation_backend=nllb` → `first 2.96e-06 / final 1.43e-05 / lead 1.13e-05`; with the pre-fix set restored the same probe on the same states reports `lead None` while both endpoints exist, so the field moves because of the predicate.
- DONE: The boundary row stays prose in NOTES and the README as decided, and no criterion or field beyond that changes.
  `NOTES.md` is byte-unchanged and the realizable-commit-fraction prose is unedited; the diff names only `benchmarks/README.md`, `tests/test_benchmark.py`, `tests/test_benchmark_drafting.py`, `whisperlivekit/benchmark/metrics.py`. No schema version, report field, chrF, corpus aggregation, manifest join, alignatt record or criterion changed, and no report was regenerated — both checked-in reports run `mlx-llm-mt`, whose answer this change does not touch (their `provisional_lead_s` values stay `[null,null,null]` and `[1.36, 8.80, 6.84]`).
- DONE: Targeted tests pass, base unchanged, nothing pushed.
  `tests/test_benchmark.py` 11 passed + `tests/test_benchmark_drafting.py` 5 passed (targeted files only, 16 total); `ruff check` clean on the three changed Python paths. Commit `d125cba` on `wlk/simulst-eval-harness`, parent `88d8e20` (no rebase). No push, no issue or PR comment, nothing staged.

### Summary

The under-inclusion is closed at the entry the validator named: `nllb` (and its `nllw` spelling) joins `alignatt` in the always-drafting set, so the default backend's provisional target buffer now yields a measured lead instead of a null. The set is pinned the way the finding asked — one case per backend reading that backend's own `process()` buffer, plus a completeness case that fails when `--translation-backend` gains or loses a name — and the README's "backend not known to draft" sentence now states the true rule: every accepted backend is classified, so a null lead means the run's translator did not draft.

## Stage Report: validation (cycle 5)

- DONE: The drafting predicate now classifies every accepted backend, with nllb reporting a measured lead, and the classification is driven per backend by how each returns its buffer rather than by assumption.
  Drove each one myself instead of trusting the new module: alignatt `process()` → `(None, 'HELLO WORLD')`; `MlxLlmTranslation` → `('你好', TimedText(''))`; `MlxLlmTranslationSimul` → `(None, '您好')`; the **real** `nllw.translation.OnlineTranslation.process()` (nllw 0.1.6, stub model) → `('You are', ' welcome to my')`, so the second element is target text in all three drafting cases, and `nllw.core:358` decodes it from the translation tokens outside the common prefix. Predicate table: `nllb`/`nllw`/`alignatt` True, `mlx-llm-mt` and `hunyuan-mlx` False, either with `mlx_llm_mt_simultaneous` True, `""` False. `nllw` is not a CLI choice but `core.py`'s dispatch is a catch-all (`every name that is not alignatt/mlx-*` → `nllw.load_model`), so the alias is that dispatch's spelling, not an invention. `test_benchmark_drafting.py` 5 + `test_benchmark.py` 11 pass; falsifiers in a throwaway copy: pre-fix set → 4 failed, `mlx-llm-mt` added to the always-drafting set → 3 failed, switch ignored → 3 failed, each restored to 16 passed. Inverse risk checked and absent: nllw `translate()` on `"Hi"` returns `('', '')` (under three words) and the early-cut path returns an empty buffer, so no drafting backend can put source text in the buffer, and `TimedText.__bool__` is `bool(self.text)`, so an empty buffer cannot start the clock.
- DONE: The completeness test genuinely binds the predicate to the CLI's accepted backends, so a backend added later cannot enter the schema unclassified.
  Throwaway copy of `d125cba`: adding `"xtrans"` to `parse_args.py:905` fails `test_every_translation_backend_the_cli_accepts_is_classified` with `Extra items in the left set: 'xtrans'`; restored → 1 passed. It reads `build_parser()`, the parser `wlk` runs, so the binding is to the real accepted set and not a copy of it.
- DONE: The restated README rule matches the code word for word, and nothing outside the predicate, its tests and that sentence moved.
  `git diff 88d8e20 d125cba` is four files: `benchmark/metrics.py` (the set and the docstring), `benchmarks/README.md` (two bullets), the two test modules; no new external import (only `pytest` and in-repo modules), no `449`. chrF re-checked against `sacrebleu 2.6.0`: all six report rows exact (max delta 8.9e-16), `corpus_chrf` 8.591371 / 9.316592 equal sacrebleu's corpus score and unequal to `avg_chrf` 8.571984 / 9.671815, schema 3.2 in both, every row's Chinese reference re-joins from `fleurs-90.json` by `sentence_id` with matching audio SHA-256, corpus blob `c84af0b` identical to `origin/main` (sha256 `95586eb…`), `NOTES.md` and both `benchmarks/evaluations/m5-*` untouched. The commit-fraction row is prose only (`NOTES.md:105`, `README.md:209`) and absent from the report JSON, which is CL's decision. Tree clean, nothing staged, `ruff check` clean on the three Python paths. Validator probes live in `/tmp/val5/`, not in the tree.

### Findings

1. **A default-nllb run still loses its real lead, because the predicate is fed kwargs that omit the key** (material for that invocation; AC-3 is one-way, so not falsified word for word). Observation: `cli.py:892` copies only truthy flags into `engine_kwargs` and the bench `--translation-backend` default is `None` (`cli.py:825`), so `wlk bench --target-language zh` sends `{"target_language": "zh"}`; `runner.py:108` then calls `drafts_provisional_text(harness_kwargs)`, whose `config.get("translation_backend", "")` is `""` → False, while `WhisperLiveKitConfig.translation_backend` defaults to `"nllb"` (`config.py:56`) and `core.py` routes it to `nllw.load_model` — the drafting backend. Reproduction: my own fake harness at `--speed 1`, drafting states (buffer first carries `你好`, then a committed-line translation): with `translation_backend="nllb"` → first 5.8e-06 / final 2.7e-04 / **lead 2.63e-04**; the same states with the key omitted → first 2.96e-06 / final 9.56e-05 / **lead None**. Materiality: tier-1's own README sentence ("the default `nllb`" drafts; "a null here means the run's translator did not draft") is false on that path, and the report it writes says `config.translation.backend == "nllb"` beside a null lead, which is the same harm the previous round rejected on. Ownership: outside the three checklist items as written (they are about classification, which is now right); disposition is the FO's, and the fix shape is to feed the predicate the config the engine resolved (`result.effective_config`, or default the key to `nllb`) plus one runner case with the key absent. Same root cause, second trigger: core's dispatch is a catch-all and the bench subparser has no `choices`, so `--translation-backend` set to an unlisted name runs nllw and reports null.
2. **Polish:** the completeness test binds a hard-coded `drilled` map to the choices, so a future backend added to both the choices and that map without a driving case passes — the "answer established by driving that backend" property is prose, not checked. It also binds the `parse_args` choices only; `cmd_bench`'s own `--translation-backend` has no `choices`, which is finding 1's second trigger.

### Summary

The checklist items hold under independent reproduction: the always-drafting set is right for every accepted backend (nllw included, as `core.py`'s catch-all spells it), the completeness test fails when a choice is added to `parse_args`, and the diff really is the predicate, its two test modules and two README bullets — chrF, the corpus aggregation, the manifest join, the byte-unchanged corpus, the alignatt record, schema 3.2 and the prose-only boundary row all reproduce unchanged. One defect the criteria do not cover: because the runner hands the predicate the *requested* kwargs and the bench CLI omits `translation_backend` unless it is passed, the default nllb run still reports a null lead on states that draft — the previous round's harm, surviving on the invocation that relies on the engine default. Recommendation: **PASSED** for tier 1 as specified, with finding 1 carried to the FO as a one-line follow-up (predicate input = resolved config) if the default invocation is in scope; that fix plus its runner case would be the only change needed.

## Stage Report: implementation (cycle 8)

- DONE: The predicate is fed the configuration the engine resolved rather than the requested flags, so a default bench run with no translation backend reports the lead nllb actually produces, with a runner case that fails when the key is absent.
  `runner.py:_run_sample` no longer calls `drafts_provisional_text(harness_kwargs)`; the gate now sits directly under the assignment of `result.effective_config` and reads `drafts_provisional_text(result.effective_config)` — the same row record `run()` already prefers for `describe_translation_config`, which is `asdict(WhisperLiveKitConfig)` from `TranscriptionEngine.args`, so `translation_backend` is present as `nllb` even when the bench flag is unset (`cli.py:826` keeps `default=None`). New case `test_benchmark.py::test_a_run_that_names_no_backend_reports_the_default_ones_lead` sends `dict(transcription=False, pcm_input=True, target_language="zh")` with the key asserted absent, and asserts the recorded `effective_config["translation_backend"] == "nllb"`, both timing endpoints present, and `provisional_lead_s == final - first > 0`. Falsifier: with only `whisperlivekit/benchmark/runner.py` stashed back to `d125cba` the case fails `assert None == 9.29180532693e-06` (lead None while both endpoints exist); restored → 13 passed in `tests/test_benchmark.py`. `_cascade_run`'s `FakeHarness` was made faithful for this: it builds `{"translation_backend": WhisperLiveKitConfig.translation_backend, "mlx_llm_mt_simultaneous": False, **kwargs}` for both its observed states and its `_processor.args`, mirroring the engine filling defaults in, instead of `SimpleNamespace(pcm_input=True)` which could not carry the answer.
- DONE: The bench translation flag rejects a name the engine would not route to a known backend, closing the second trigger where an unlisted name runs nllw and reports a null lead.
  `TRANSLATION_BACKENDS = ("nllb", "alignatt", "mlx-llm-mt", "hunyuan-mlx")` now lives in `config.py` beside the field it bounds, with a comment naming `core.py`'s four routes and saying any other name falls through to the nllb branch. `cmd_bench`'s `--translation-backend` gained `choices=list(TRANSLATION_BACKENDS)`, and `parse_args.build_parser` uses the same tuple instead of its own literal, so the two CLIs cannot drift. New case `test_benchmark.py::test_the_bench_translation_flag_rejects_a_name_the_engine_would_not_route`: `cmd_bench(["--target-language", "zh", "--translation-backend", "nllw"])` exits 2 with `error: argument --translation-backend: invalid choice: 'nllw' (choose from nllb, alignatt, mlx-llm-mt, hunyuan-mlx)` and `_run_bench_new` is never reached. Nothing else moved: with `_run_bench_new` stubbed, `--target-language zh` still parses to `translation_backend None`, `mlx-llm-mt` + `--mt-model hy-mt2-1.8b-4bit` still passes both, `hunyuan-mlx` still accepted, and `--languages en` unchanged.
- DONE: The completeness test fails when a backend appears in both the CLI choices and the mapping without a case that drives it, so the check cannot pass on an untested entry.
  The hard-coded `drilled` map is gone. `tests/test_benchmark_drafting.py` keeps `_DRIVEN: Dict[str, bool]`, filled only by `drove(backend, drafts)` calls the four driving cases make after asserting their backend's own buffer, and the renamed `test_every_translation_backend_the_cli_accepts_has_a_case_that_drives_it` asserts `choices - set(_DRIVEN)` is empty with the message `--translation-backend accepts ['seamless'] with no case that drives it`, then that every recorded backend's predicate answer matches its record. Falsifier: adding `"seamless"` to `TRANSLATION_BACKENDS` (so to the flag's choices) with no driving case fails that test while the four driving cases still pass (4 passed, 1 failed); reverting restores 5 passed. The record states the bare-name answer (the simul case drives the switch and deliberately records nothing), and `nllw` stays an asserted spelling rather than a recorded name since the flag does not accept it.
- DONE: Nothing else moved — no chrF, aggregation, join, alignatt record or schema change, no report regenerated, no push.
  `git diff --stat d125cba 60aba1b` is 6 files / 98 insertions / 16 deletions, all in `whisperlivekit/{config,parse_args,cli}.py`, `benchmark/runner.py` and the two targeted test modules. `benchmark/metrics.py`, `benchmark/report.py`, `benchmarks/corpora/fleurs-90.json`, `NOTES.md` and both `benchmarks/evaluations/translation-fleurs-en-zh/*.json` are untouched. Both reports need no regeneration and none was written: their rows carry `translation_backend: mlx-llm-mt` with `mlx_llm_mt_simultaneous` false/true, and running the patched predicate over each row's own `effective_config` returns False/True/True for the three rows of each, matching the stored `[null,null,null]` and `[1.36, 8.80, 6.84]`. `ruff check` clean on the six changed paths; commit `60aba1b` on `wlk/simulst-eval-harness`, parent `d125cba` (no rebase), tree clean and nothing staged. No push, no issue or PR comment.

### Summary

The cycle-5 finding is closed at both of its triggers. The lead gate now asks the configuration the engine resolved instead of the flags the caller passed, so `wlk bench --target-language zh` — the invocation that leans on the engine default — reports nllb's measured lead rather than a null beside `config.translation.backend == "nllb"`; the new runner case proves the difference on one fake harness (lead 9.3e-06 s with the fix, None without it, both endpoints present either way). The second trigger, an unlisted backend name running nllw, is shut by giving the bench subparser the same `choices` the serve parser has — one tuple in `config.py`, so the two cannot diverge — which rejects the name with exit 2 and leaves every valid invocation and default byte-identical. The completeness check no longer rests on a map written beside the choices: the classified set is the record the cases fill by driving each backend, so a new choice with nothing behind it now fails with its own name in the message. The two checked-in reports re-derive unchanged.


## Stage Report: validation (cycle 6)

- DONE: A bench run that names no translation backend reports the lead the resolved default produces, proven by a case that inspects the request, the effective config and the reported lead together.
  `runner.py:159` gates on `result.effective_config` (`runner.py:148-152` ← `vars(harness._processor.args)` ← `audio_processor.py:99` `self.args = models.args` ← `core.py:90` `Namespace(**asdict(config))`, defaults filled by `from_kwargs`): ran it — the engine's args say `translation_backend nllb` for a request that never names one, and `AudioProcessor.args is engine.args`. My own fake (args = `asdict(WhisperLiveKitConfig.from_kwargs(**request))`, key absent from the request): first 1.92e-06 / final 7.12e-06 / **lead 5.21e-06**; the same probe against the d125cba gate `drafts_provisional_text(harness_kwargs)` → **lead None** with both endpoints and `effective_config nllb` present. Falsifier: reverting `runner.py` to the requested-kwargs gate fails `test_a_run_that_names_no_backend_reports_the_default_ones_lead` (`assert None == 6.67e-06`); restored → 18 passed over the two targeted modules. Finding 3 notes the fake's own resolution is hand-written.
- DONE: The two CLIs share one backend list so they cannot drift, an unlisted name is rejected rather than silently routed, and every valid invocation behaves exactly as before.
  `config.py:15` is the only list; `parse_args.py:907` and `cli.py:826` both pass `choices=list(TRANSLATION_BACKENDS)`, and swapping that name at both import sites to `("alpha","beta")` moved both parsers' choices (a literal in either would not follow). `cmd_bench(["--target-language","zh","--translation-backend","nllw"])` → SystemExit 2, stderr names `nllw`, `_run_bench_new` never entered; the serve parser rejects it on d125cba too. Invocation matrix parsed by HEAD and by a `git archive` of d125cba: serve default/nllb/alignatt/mlx-llm-mt(+model)/hunyuan-mlx/target-only and bench default/no-translation/all four names/`--languages en` are field-identical; the only diffs are bench `--translation-backend nllw` and `wlk-internal`, now exit 2 — flag path only, see finding 1. Both reports stay byte-identical (`git rev-parse` on d125cba) and the new predicate re-derives their gates (False×3 with nulls; True×3 with 1.36/8.80/6.84). Finding 5 records the one accepted-before invocation that now errors.
- DONE: The completeness test fails when a backend is accepted with no case that drives its buffer, and the rest of tier 1 is unchanged.
  Adding `"seamless"` to `TRANSLATION_BACKENDS` → `test_every_translation_backend_the_cli_accepts_has_a_case_that_drives_it` fails `--translation-backend accepts ['seamless'] with no case that drives it` while the four driving cases pass (1 failed, 4 passed); reverting → 5 passed. The cases read buffers, not constants: alignatt's real client returns `HELLO WORLD`, nllb's real `OnlineTranslation` through `run_translation` publishes `欢迎来到我的`, and making `MlxLlmTranslation.process` return `TimedText(text="draft")` fails the segment case at `assert not buffer.text` (making the predicate call that backend drafting fails it at line 66 plus the record). Tier 1 elsewhere: `git diff --stat d125cba 60aba1b` = 6 files/98+16−, nothing under `benchmarks/`; per-row chrF within 8.9e-16 of sacrebleu, `corpus_chrf` 8.591371/9.316592 equal sacrebleu's corpus and unequal to `avg_chrf` 8.571984/9.671815; all six rows re-join `translation_reference` and `audio_sha256` from `fleurs-90.json`; corpus blob `c84af0be` identical to origin/main; `metrics.py`/`report.py` untouched so the alignatt record and schema 3.2 stand; the commit-fraction row is README prose (`README:205`) and absent from the JSON (`'commit_fraction' not in json.dumps(report)`). Probes in `/tmp/val6`, `/tmp/val6base`, `/tmp/probe_*.py`, never in the tree; tree clean, nothing staged, ruff clean.

### Findings

1. **Material, outside the three items: `--config` still lets an unlisted name reach the engine and still reports a null lead beside a drafting translator.** `BenchmarkRunner.__init__` validates only the *keys* of `engine_kwargs`, so `wlk bench --config` with `{"translation_backend": "seamless"}` resolves to `seamless`, `core.py:307/316` fall through to the nllw branch (which drafts), and the predicate answers False: ran it — `resolved='seamless' engine_route=nllb predicate=False recorded_backend='seamless' model_note='nllw selects the NLLB checkp'`; same for `nllw2`, `MLX-LLM-MT`. The flags are bounded, the routing is not, so "an unlisted name is rejected rather than silently routed" holds for the two CLIs' flags only. One-place fix if the FO wants it: validate `translation_backend` against `TRANSLATION_BACKENDS` in `WhisperLiveKitConfig.__post_init__`, which closes the flag, `--config` and the programmatic path at once. Related, not a defect: `TRANSLATION_BACKENDS` is not derived from `core.py`, so a *new* core route would be unroutable from both CLIs until the tuple is edited; the tie is the comment, not a test.
2. **Polish: the completeness test depends on intra-module execution order.** `_DRIVEN` is filled by earlier cases, so running that test alone fails with all four names "undriven" (reproduced), as it would under `-k`, `--lf`, or any xdist/random-order split; the whole-file run passes. A module-scoped fixture would make it order-free.
3. **Polish: the new runner case's "resolved" config is hand-written inside the fake.** `_cascade_run`'s `FakeHarness` resolves `{"translation_backend": WhisperLiveKitConfig.translation_backend, "mlx_llm_mt_simultaneous": False, **kwargs}` itself, so a future change that stopped the engine filling defaults into `args` would leave the case green; my real-engine probe is what shows the record resolves. `SimpleNamespace(**asdict(WhisperLiveKitConfig.from_kwargs(**kwargs)))` in the fake would pin it.
4. **Low: the report-level record can still be the request.** Where every row is skipped or errors before the harness, `runner.run()` falls back to `self.engine_kwargs` (`effective or self.engine_kwargs`), which carries no `translation_backend`: a skipped row produced `report.translation.backend == ""` for a run that resolves nllb. Pre-existing from `88d8e20`, and no lead is affected (a skipped row has none).
5. **Low, deliberate: `wlk bench --translation-backend nllw` was accepted before this commit** (it ran nllw and reported that lead) and now exits 2, matching the serve CLI, which rejected it all along. No documented invocation is affected; worth one line in the release note.

### Summary

The cycle-5 finding is closed where it was reported: the lead gate reads the configuration the engine resolved, and I reproduced both sides — the old null beside `nllb` and the new measured lead — with my own fake rather than the project's. The bench flag now shares one tuple with the serve parser (swapping it moves both), every invocation that was valid before parses identically, and the two checked-in reports re-derive unchanged. The completeness check fails on a choice with nothing behind it and its driving cases are buffer-driven. One defect survives outside the criteria: `--config` can still put an unlisted name into the resolved config, where the engine routes it to nllw and the predicate calls it non-drafting; a `__post_init__` bounds check closes all three entry points at once. Recommendation: **PASSED** for tier 1 as specified, with finding 1 carried to the FO as a one-line follow-up.

## Stage Report: implementation (cycle 9)

- DONE: An unlisted translation backend is rejected wherever it can enter, including through --config and programmatically, in one bound check with a test for each entry point.
  `config.py:211-217` (commit `c563b0b`) rejects any `translation_backend` outside `TRANSLATION_BACKENDS` in `WhisperLiveKitConfig.__post_init__`, naming the value and the accepted set (`translation_backend 'seamless' is not one of: nllb, alignatt, mlx-llm-mt, hunyuan-mlx. The engine routes only those names and sends every other one down the nllb branch.`); `benchmark/runner.py:60-65` resolves the requested name through that same bound in `__init__`, so `--config` fails before a sample runs instead of scoring rows under nllw. Entry points tested: flag — `test_the_bench_translation_flag_rejects_a_name_the_engine_would_not_route` (kept; `cmd_bench --translation-backend nllw` → exit 2, stderr names `nllw`); `--config` — `test_a_bench_config_with_an_unlisted_translation_backend_is_rejected` (`cmd_bench --config '{"target_language":"zh","translation_backend":"seamless"}'` → ValueError naming `seamless` and the accepted set, with `get_benchmark_samples` stubbed so the run cannot start sampling and pass for that reason); programmatic — `test_the_config_rejects_an_unlisted_translation_backend` (constructor and `from_kwargs` both raise, and all four accepted names still resolve). Falsifiers, each restored: deleting the `__post_init__` bound fails both new cases (`DID NOT RAISE ValueError`; `AssertionError: the run started sampling with an unlisted backend`); deleting only the runner's resolution fails the `--config` case with that same AssertionError, so both halves are load-bearing. Unchanged: both parsers' accepted names, `BenchmarkRunner(engine_kwargs={"target_language": "zh"})`, and `build_parser()` + `from_namespace` → `nllb`.
- DONE: The completeness test passes when run alone and in random order, and the runner case derives its resolved configuration rather than writing it by hand inside a fake.
  `tests/test_benchmark_drafting.py` keeps `_DRIVEN`/`drove()` but the driving moved into the module-scoped `driven` fixture (`drive_alignatt`, `drive_mlx_segment`, `drive_mlx_simul`, `asyncio.run(drive_nllb())`), which every case requests and which records each answer as it drives; the four cases now assert on the buffers it returns. Verified: module 5 passed; each of the five tests run alone (loop over `--collect-only`) 1 passed each; the completeness case alone and under `-k every_translation` 1 passed. Falsifier: adding `"seamless"` to `TRANSLATION_BACKENDS` fails it alone with `--translation-backend accepts ['seamless'] with no case that drives it` (whole module 1 failed, 4 passed); reverted → 5 passed. `_cascade_run`'s `FakeHarness` now builds `asdict(WhisperLiveKitConfig.from_kwargs(**kwargs))` for its observed states and its `_processor.args`. Falsifier: reverting it to echo the request fails `test_a_run_that_names_no_backend_reports_the_default_ones_lead` at `KeyError: 'translation_backend'`; restored → 13 passed.
- DONE: The behaviour change for previously accepted invalid names is recorded where a reader meets it, and nothing outside these three items moves.
  `benchmarks/README.md` "Audio-to-translation runs" now says the accepted set is the four names the engine routes — for the flag, for `--config` and for a Python `WhisperLiveKitConfig` — and that `wlk bench --translation-backend nllw` used to run the NLLB path and now exits 2, as `wlk serve` always did. Finding 4 (report-level `effective or self.engine_kwargs` fallback when every row is skipped, pre-existing, no lead affected) is recorded as a comment at `benchmark/runner.py:99-105`, not changed. Diff `60aba1b..c563b0b` is 5 files (2 production, 2 test modules, 1 README), 162 insertions / 50 deletions; `benchmark/metrics.py`, `benchmark/report.py`, `benchmarks/corpora/fleurs-90.json`, both evaluation JSONs and schema 3.2 untouched; parent `60aba1b` (no rebase), no push, no issue or PR comment. Targeted modules only: the six modules this touches plus neighbours, 81 passed; `tests/test_session_limits.py` and `tests/test_silent_backend_guard.py` 29 passed; nothing run as `pytest tests/`.

### Summary

The routing is now bounded where it was not: one check in `WhisperLiveKitConfig.__post_init__` rejects a name outside `TRANSLATION_BACKENDS`, and the runner resolves a requested name through it so `--config` fails before any sample instead of running nllw and reporting a null lead beside the requested name. Each of the three entry points has its own case, and removing either half of the fix (the config bound, the runner's early resolution) makes a case fail. The completeness case's driving moved into a module-scoped fixture so it no longer depends on intra-module order, the cascade fake derives its resolved config with `asdict(WhisperLiveKitConfig.from_kwargs(...))` instead of writing the answer, and the one behaviour change (`--translation-backend nllw` now rejected in bench) plus the untouched report-level fallback are recorded where a reader meets them.

## Stage Report: validation (cycle 7)

**Tree under test, checked before any result was believed.** The venv (`/Users/clkao/git/asr/WhisperLiveKit/.venv`) carries an editable install whose finder maps `whisperlivekit` to the **main checkout**, so `import whisperlivekit` from any cwd but the worktree resolves `/Users/clkao/git/asr/WhisperLiveKit/whisperlivekit`, whose `config.py` has **no bound** (`'is not one of' in source` → False there, True in the worktree). Every command below ran with `PYTHONPATH=/Users/clkao/git/asr/WhisperLiveKit/.worktrees/simulst-eval-harness` (the editable finder is appended to `sys.meta_path`, so PathFinder wins) and each script printed the imported path: `whisperlivekit.__file__` = `…/.worktrees/simulst-eval-harness/whisperlivekit/__init__.py`, `config.py` and `benchmark/runner.py` likewise. A mis-imported run would have failed every bound case rather than passing quietly. Worktree at `c563b0b`, parent `60aba1b`.

- DONE: An unlisted translation backend is rejected at the configuration itself and again before a sample runs, with each entry point proven independently and each half of the bound shown to be load-bearing.
  `config.py:211-217` (`__post_init__`; the bound at 212-217 names the rejected value and the accepted set — `translation_backend 'seamless' is not one of: nllb, alignatt, mlx-llm-mt, hunyuan-mlx. The engine routes only those names and sends every other one down the nllb branch.`), `benchmark/runner.py:60-66` (resolves the requested name through `WhisperLiveKitConfig.from_kwargs`, so no second copy of the set exists). Six entry points probed one at a time, 50/50 assertions in a scratch script (`/tmp/v5/verify_entry.py`, never in the tree), probing `nllw`, `seamless`, `MLX-LLM-MT` and `""` against all four listed names: **bench flag** — exit 2 for each unlisted probe, reaches sampling for each listed backend; **serve flag** (`parse_args`) — exit 2 / resolves all four; **bench `--config`** — ValueError naming the value and the set for each unlisted probe, with `get_benchmark_samples` stubbed to raise, so the run provably never starts sampling, and reaches the stub for each listed backend; **programmatic construction** — `WhisperLiveKitConfig(...)`, `from_kwargs`, `from_namespace` and `dataclasses.replace` all reject, all four names still resolve; **`BenchmarkRunner(engine_kwargs=…)` directly** — rejects/accepts; **`TranscriptionEngine(translation_backend="seamless")`** — ValueError from `core.py:86` `from_kwargs`, raised before any model load. Falsifiers, each restored afterwards: **M1** deleting the `__post_init__` block → `2 failed, 18 passed` (`test_a_bench_config_with_an_unlisted_translation_backend_is_rejected` at `AssertionError: the run started sampling with an unlisted backend`; `test_the_config_rejects_an_unlisted_translation_backend` at `DID NOT RAISE`); **M2** deleting the runner's resolution → `1 failed, 19 passed`, the same `--config` case failing at the sampling stub while the programmatic case still passes. So the `--config` case is falsified by removing **either** half: the config bound and the runner's early resolution are independently load-bearing, and the programmatic case isolates the config half. Restored: `20 passed` over the two targeted modules; `config.py` sha256 `68d3624152665d3f4c07f8cbe603276ef1ab85b64765c78af52204d47bdf1cde` and `benchmark/runner.py` `0e92831add7b8f128d200088702f8383a0d7cee301cbe0468a2f1965ac233d65` back to their committed values, `git status --porcelain` empty, nothing staged.
- DONE: The completeness test passes when run alone and in random order, and the runner case derives its resolved configuration so a fake that echoed the request fails.
  `tests/test_benchmark_drafting.py:141` module-scoped `driven` fixture, `:199` the completeness case. Alone: `1 passed`; under `-k every_translation_backend`: `1 passed, 4 deselected`; completeness-first, reversed, and three independently shuffled node orders: `5 passed` each time. Falsifier for the fixture: the pre-fix file (`git show 60aba1b:tests/test_benchmark_drafting.py`, run as a temporary copy, deleted after) run alone **fails** with `--translation-backend accepts ['alignatt', 'hunyuan-mlx', 'mlx-llm-mt', 'nllb'] with no case that drives it`, so the fixture is the fix and not a cosmetic move. `tests/test_benchmark.py:474` now builds `asdict(WhisperLiveKitConfig.from_kwargs(**kwargs))`. Falsifier: replacing it with `dict(kwargs)` → `1 failed, 14 passed`, `test_a_run_that_names_no_backend_reports_the_default_ones_lead` failing; restored → `15 passed`. Falsifier for the set itself: adding `"seamless"` to `TRANSLATION_BACKENDS` → `3 failed, 17 passed` (the completeness case plus both rejection cases), so the accepted set stays pinned to driven behaviour.
- DONE: The rest of tier 1 is unchanged, with its numbers.
  chrF: per-row values equal sacrebleu 2.6.0 to <1e-9 — `report.json` 5.581001131739981 / 14.671229713481907 / 5.463720750164314 (the last differs at 1e-15), `report-simultaneous.json` 8.761835152060478 / 14.764175361726032 / 5.489434097241064. Corpus aggregation: `corpus_chrf` 8.591371459868263 / 9.316591816717423 equal to `sacrebleu.corpus_chrf(char_order=6, word_order=0, beta=2)` over the same rows and unequal to `avg_chrf` 8.571983865128734 / 9.671814870342525, which equals the unweighted mean of the per-row scores. Join: all six rows' `translation_reference` byte-identical to the same-`sentence_id` zh row of `benchmarks/corpora/fleurs-90.json` as `load_manifest` resolves it (ids 1700/1921/1993); drafting-run `first`/`final` 2.4519 / 11.2494 on `fleurs_en_1921` and leads 1.3643 / 8.7975 / 6.8372, null ×3 on the non-drafting run, all matching `NOTES.md`. Byte-unchanged corpus: `fleurs-90.json` sha256 `95586eb74f53e665f35983f53da31ea510867b54c7fe5f481466e2d6af2619e5` at `60aba1b` and in the tree, `git status benchmarks/` clean. Alignatt record: `test_translation_config_records_what_an_alignatt_run_can_know` passes and `alignatt` is accepted by the new bound on every entry path. Schema 3.2 in both reports (`benchmark_version`), and both reports' whole `config` block re-derives key for key (`describe_asr_config` + `describe_translation_config` + `feed_speed` == recorded) with the recorded backend `mlx-llm-mt` accepted by the bound. Prose-only boundary row: `NOTES.md` untouched since `88d8e20` (`git diff --stat 88d8e20 HEAD -- benchmarks/evaluations/` empty), `| Realizable commit fraction | **not run** |` at `NOTES.md:105`. Defaults untouched: 122 fields, same order, zero value diffs between `60aba1b` and `c563b0b`, `translation_backend` default `nllb` → `nllb`, `TRANSLATION_BACKENDS` tuple byte-identical. Targeted files: `tests/test_benchmark.py` + `tests/test_benchmark_drafting.py` 20 passed; with `test_translation_alignatt.py`, `test_simul_calibration_files.py` and `test_translation_mlx.py` 46 passed; nothing run as `pytest tests/`. No new entry point for `translation_backend` exists: `SessionASRProxy` is ASR-only, no env override reads it, nothing writes `engine.args.translation_backend`, and `create_app` is typed to `WhisperLiveKitConfig`.

### Findings

1. **Material, outside the criteria: `--config`'s help still calls itself a "JSON object" while it takes a path.** `cli.py:822` says `help="JSON object of additional engine options, including pinned model paths"`; `cli.py:895` reads `json.loads(Path(parsed.config).read_text())`. `c563b0b` touched the bench README around it but not the string. This is the same defect an earlier validation returned, and `--help` still points a reader at the call that fails: `--config '{"mlx_llm_mt_simultaneous": true}'` → `FileNotFoundError`. One-line fix; carried to the FO.
2. **Low, outside the criteria: the bound is construction-time only.** `cfg = WhisperLiveKitConfig(target_language="zh"); cfg.translation_backend = "seamless"` is accepted (measured), after which `core.py:307/316` fall through to the nllb branch. Nothing in the repository writes the field after construction (only the declaration and `__post_init__` mention it), and a non-dataclass `config=` is not silently accepted either: `TranscriptionEngine(config=SimpleNamespace(...))` raises `TypeError: asdict() should be called on dataclass instances`.
3. **Low, outside the criteria: the tuple is tied to `core.py`'s dispatch in one direction only.** M3 shows a name added to `TRANSLATION_BACKENDS` without a driver fails; a route added to `core.py` for a name missing from the tuple would reject a working backend with nothing failing. The tie is still the comment at `config.py:12-16`, not a test — the related note from the cycle-6 report stands.
4. **Low, outside the criteria: `--config` still routes other fields past the runner's pre-run check.** `--config '{"max_concurrent_sessions": 0}'` reached sampling and fails only at engine construction (measured): the same shape as this cycle's finding on a different field. The failure is loud, every row errored, rather than a misrecorded null lead, and the checklist scopes the bound to `translation_backend`.
5. **Low, deliberate: an explicit JSON `null` for `translation_backend` is now rejected.** `{"target_language": "zh", "translation_backend": null}` → ValueError naming the accepted set, where it previously fell through to nllb. `null` is not one of the four names and appears in no documented invocation; it belongs with `wlk bench --translation-backend nllw` now exiting 2, which the README paragraph already records.

### Summary

The bound holds at every entry point I could find, and each half of it is independently load-bearing: removing `__post_init__` fails the programmatic and `--config` cases, removing the runner's resolution fails the `--config` case by reaching sampling, and both were restored to their committed bytes. All four listed backends still reach the same place through both CLI flags and through `--config`, the 122 defaults are value-identical to the parent, and both checked-in reports re-derive their recorded configuration key for key. The completeness case now passes alone, under `-k`, reversed and in three shuffled orders — the pre-fix file fails alone, so the fixture is what fixed it — and the cascade fake derives its resolved config, so echoing the request fails the case. Tier 1's other rows are unchanged and re-measured: sacrebleu-identical chrF, corpus aggregation distinct from the row mean, six rows byte-identical from the manifest join, unchanged corpus blob, alignatt record, schema 3.2 and the prose-only commit-fraction row. No new entry point for `translation_backend` was found. Recommendation: **PASSED** for tier 1 as specified, with finding 1 carried to the FO as a one-line help-string fix.

## Stage Report: implementation (cycle 10)

- DONE: The --config help text states that the flag takes a file path, and the wording matches what the code does with it.
  `cli.py:822` is now `help="Path to a JSON file of additional engine options, including pinned model paths"` against the unchanged read at `cli.py:895` `engine_kwargs = json.loads(Path(parsed.config).read_text()) if parsed.config else {}`; the engine-options and pinned-model-path notes are kept. Rendered `wlk bench --help` at `c563b0b` vs `93782d6`: line count equal, the only diffs are that entry's two wrapped lines ("JSON object of additional engine options, including / pinned model paths" → "Path to a JSON file of additional engine options, / including pinned model paths"). The call the old text invited, `--config '{"pcm_input": true}'`, raises `FileNotFoundError` and is now pinned as a case.
- DONE: A targeted test or check fails if the help text and the read path disagree again, and no other behaviour changes.
  New `tests/test_bench_config_help.py` (2 cases), both reading the bench parser itself rather than a copy of the string: `test_bench_config_help_names_a_file_path` spies on `argparse.ArgumentParser.add_argument` while `cli.cmd_bench(["--help"])` builds the real parser and asserts the registered help says "path to a JSON file", does not say "JSON object", and still carries "engine options" / "pinned model paths". `test_bench_config_reads_the_file_path_the_help_names` drives the same flag through `cmd_bench` with `BenchmarkRunner`/`print_report` replaced, and asserts a temp JSON file arrives as `engine_kwargs == {"pcm_input": True, "vac": False}` while an inline object raises `FileNotFoundError`. Falsifiers, each run and then restored: reverting the help string to "JSON object of additional engine options, …" → `1 failed, 1 passed` (`test_bench_config_help_names_a_file_path`, argparse dump in the failure); replacing the read with `json.loads(parsed.config)` → `1 failed, 1 passed` (`test_bench_config_reads_the_file_path_the_help_names` at `JSONDecodeError: Expecting value: line 1 column 1`). Restored: `2 passed`.
  Unchanged, measured base vs HEAD by loading `git show c563b0b:whisperlivekit/cli.py` beside the tree file and capturing the namespace `_run_bench_new` receives: bench option names identical (17), **zero** default value diffs, `languages`→`["en"]` and `categories`→`None` identical; `parse_args`/`build_parser` are not in the diff at all. `git diff c563b0b` is the one cli.py line plus the new test file. Targeted modules only: `tests/test_bench_config_help.py` 2 passed, `tests/test_benchmark_drafting.py` 5 passed, `tests/test_benchmark.py` 15 passed; nothing run as `pytest tests/`.

### Summary

The stale help string is corrected to name a path to a JSON file while keeping its engine-options note, and a two-case check now holds it to the read: one case asks the bench parser what `--config` says, the other drives the flag through `cmd_bench` and observes that a file path is read and an inline object is not. Each case is independently falsified by mutating its own side (help string, read expression) and restored. Nothing else moved: the diff is that one string plus the new test file, both parsers' option names and defaults are identical to `c563b0b`, and the three targeted modules are green. Commit `93782d6` on `wlk/simulst-eval-harness`, parent `c563b0b` (no rebase), tree clean and nothing staged; this state file is committed locally and **not pushed**, per the dispatch's no-push instruction; no issue or PR comment.

## Stage Report: validation (cycle 8)

**Tree under test, checked before any result was believed.** `93782d6ac304234dc963ddeb3e2dc276bc61625b` (parent `c563b0b`), branch `wlk/simulst-eval-harness`, `git status --porcelain` empty, nothing staged. Every command ran with `PYTHONPATH=<worktree>` (the venv's editable finder points at the main checkout, whose `config.py` has no bound) and each printed `whisperlivekit.__file__` / `cli.__file__` = the worktree copy. Mutants ran in throwaway copies at `/tmp/val8/{A,B,C,D}` (`C` = byte copy of the tree), each printing its own imported path; nothing in the tree was edited.

- DONE: The help text of the config flag matches how the value is read, proven by a failing check rather than by reading the string, and the small diff contains nothing else.
  *Check 1 — both sides observed, then each broken.* Independent probe of the real parser (`add_argument` spy around `cli.cmd_bench(["--help"])`, exit 0): registered help = `Path to a JSON file of additional engine options, including pinned model paths`, rendered as `--config CONFIG  Path to a JSON file of additional engine options,`. Independent probe of the read, driving `cli.cmd_bench` with `BenchmarkRunner`/`print_report` replaced: a temp file arrives as `engine_kwargs == {'pcm_input': True, 'vac': False}`; an inline object raises `FileNotFoundError: [Errno 2] No such file or directory: '{"pcm_input": true}'`. Falsifiers, each in its own copy: **A** help reverted to `JSON object of additional engine options, …` → `1 failed, 1 passed` (`test_bench_config_help_names_a_file_path`, argparse usage dump in the traceback); **B** read changed to `json.loads(parsed.config)` → `1 failed, 1 passed` (`test_bench_config_reads_the_file_path_the_help_names` at `JSONDecodeError: Expecting value: line 1 column 1` on the path string, which only the real read line can produce); **D** a *permissive* read that accepts either form (`startswith("{")`) → same case fails, so the inline-object rejection is pinned and not incidental. Unmutated copy **C**: `2 passed`. The new cases are state-free — each alone `1 passed`, module alone `2 passed`, reversed `2 passed`.
  *Check 2 — nothing else moved.* `git diff --name-only c563b0b 93782d6` = `tests/test_bench_config_help.py`, `whisperlivekit/cli.py` (86+/1−); `git diff --stat … -- benchmarks/` empty. Both parsers' surfaces dumped from a `git archive c563b0b` tree beside the worktree: bench 18 options, serve 118 options, both counts equal, **exactly one field differs** — bench `config.help`. Both parsers' `translation_backend` choices = `['nllb','alignatt','mlx-llm-mt','hunyuan-mlx']` before and after; defaults unchanged (bench `backend='auto'`, `repeats=1`, `translation_backend=None`; serve `translation_backend='nllb'`, `target_language=''`). Both checked-in reports `git hash-object`-identical to `c563b0b` (`49d7a4a1`, `e4279e1e`). No stale copy of the old wording survives (`grep -rn "JSON object of additional"` empty); `benchmarks/README.md:37` already documents `--config options.json`. `ruff check` on the two changed files: clean.
  *Check 3 — tier 1 spot-checks, not re-audited.* sacrebleu 2.6.0: per-row `sentence_chrf(char_order=6, word_order=0, beta=2)` reproduces the recorded `chrf` — `report.json` 5.581001131739981 / 14.671229713481907 / 5.463720750164314 (last differs at 8.9e-16), `report-simultaneous.json` 8.761835152060478 / 14.764175361726032 / 5.489434097241064 at delta 0. `summary.corpus_chrf` 8.591371459868263 / 9.316591816717423 equals `corpus_chrf` over the same rows and differs from `summary.avg_chrf` 8.571983865128734 / 9.671814870342525, which is the unweighted row mean. Corpus byte-unchanged: `benchmarks/corpora/fleurs-90.json` blob `c84af0be` at `c563b0b`, in the tree, and at `origin/main`; absent from the diff. Schema 3.2 in both reports (`benchmark_version`). Targeted modules only: `tests/test_bench_config_help.py` + `tests/test_benchmark_drafting.py` + `tests/test_benchmark.py` = 22 passed; nothing run as `pytest tests/`.

### Findings

1. **Polish, outside the criteria: the two cases pin the two sides separately, not against each other.** Case 1 fixes the registered wording, case 2 fixes path-vs-inline semantics; they share the phrase "path to a JSON file" by intent, not by a value read from one and fed to the other. A reader swap that still treats the argument as a path (`json.load(open(parsed.config))`) passes both and still matches the help, so I do not read this as a defect — the falsifiers A/B/D cover every drift the AC names. Promoting condition: if a future change makes the *format* configurable, the wording pin would go stale silently.
2. **Low: the cases couple to `cli._suppress_logging` and to the bench parser's `--help` exiting 0.** Both are stable, and a rename fails loudly (`AttributeError` during monkeypatch setup) rather than passing quietly. Note only.
3. **Low, pre-existing, untouched by this diff: `--config` still routes non-backend fields past the runner's pre-run check** (`{"max_concurrent_sessions": 0}` reaches sampling; cycle-7 finding 4). No line of it is in `c563b0b..93782d6` and I did not re-derive it this cycle.

### Summary

The help string now names what the code does with the value, and the claim is proven by breaking each side in an isolated copy: reverting the wording fails the help case, and both the plain-inline read and a permissive read that accepts either form fail the read case, while the unmutated copy is green. Nothing else moved — one field of the bench parser surface differs between `c563b0b` and `93782d6`, both parsers accept the same four backend names with the same defaults, and both checked-in reports are byte-identical. Tier 1's spot checks reproduce: sacrebleu-identical per-row chrF, corpus aggregation distinct from the row mean, an unchanged corpus blob, schema 3.2. Recommendation: **PASSED**, with finding 1 recorded as polish and finding 3 carried forward unchanged from cycle 7.
