---
title: "Tier 2: two labelled directions — product zh→en on FLEURS, comparison en→zh on the IWSLT devset, scored by XCOMET-XL"
status: validation
score: 0.8
source: inherits the tier-2 scope of simulst-eval-harness (8z), whose tier 1 is approved for delivery
id: 1mvkhny3ke6wcza27p8x5v8j
gates:
    version: 1
    records:
        - id: gate:1mvkhny3ke6wcza27p8x5v8j:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:1mvkhny3ke6wcza27p8x5v8j-backlog-1
              briefing:
                id: briefing:1mvkhny3ke6wcza27p8x5v8j:backlog:attempt-1:revision-1
                digest: sha256:441a6fdaa2edaef2b055f0792c7fba9ab7b5554d0bd02d8f12c50ba00ffcc600
                room-ref: '@review/backlog/briefing-1'
              resolution:
                type: Resolution
                id: resolution:spacedock:1mvkhny3ke6wcza27p8x5v8j:backlog:1
                briefing: briefing:1mvkhny3ke6wcza27p8x5v8j:backlog:attempt-1:revision-1
                by: agent:first-officer
                at: "2026-11-15T04:52:58.688342Z"
                decision: approve
                reason: 'Seed is specific enough to design against: the two directions are split and labelled, the VM scorer path is named with its pins, and the segment-level emitter is identified as the build the task owns. Three ACs each carry a falsifier.'
                conn:
                    quote: 'Backlog gate of the tier-2 task: approved to ideation, as you recommend. Record the approval with my words as the grant.'
                    source: MetaFO brief relaying CL's decisions, 2026-11-15
              application:
                target-stage: ideation
                state: consumed
        - id: gate:1mvkhny3ke6wcza27p8x5v8j:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:1mvkhny3ke6wcza27p8x5v8j-ideation-1
              briefing:
                id: briefing:1mvkhny3ke6wcza27p8x5v8j:ideation:attempt-1:revision-1
                digest: sha256:fc612d3adf1914252cc3ac6cac47281f4feeddd825d3ba2ab7c5de84e30d8c4c
                room-ref: '@review/ideation/briefing-1'
              resolution:
                type: Resolution
                id: resolution:spacedock:1mvkhny3ke6wcza27p8x5v8j:ideation:1
                briefing: briefing:1mvkhny3ke6wcza27p8x5v8j:ideation:attempt-1:revision-1
                by: agent:first-officer
                at: "2026-11-15T05:03:28.767849Z"
                decision: approve
                reason: 'CL approved the 14-row suite with the first officer''s amendment. The suite names qwen3-ASR and nemotron x Hy-MT2-1.8B-8bit with drafts off and on across both directions, every parameter read from the code, all models cached with no download, run 1 marked first as a one-minute smoke. The amendment adds the run base to each row: wlk/integration-3, which carries the qwen3 MLX adapter that origin/main lacks.'
                conn:
                    quote: 'Ideation gate of the tier-2 task: CL approved the suite of 14 runs, with your amendment. Record the approval of CL.'
                    source: MetaFO brief relaying CL's decisions, 2026-11-15
              application:
                target-stage: implementation
                state: consumed
        - id: gate:1mvkhny3ke6wcza27p8x5v8j:validation
          stage: validation
          attempts:
            - id: gate-attempt:1mvkhny3ke6wcza27p8x5v8j-validation-1
              briefing:
                id: briefing:1mvkhny3ke6wcza27p8x5v8j:validation:attempt-1:revision-1
                digest: sha256:08e3d0c7e8d2e4b102fc7382187af336e13bcbca3bcb7f7f0dc379a1f9f18fe6
                room-ref: '@review/validation/briefing-1'
              resolution:
                type: Resolution
                id: resolution:spacedock:1mvkhny3ke6wcza27p8x5v8j:validation:1
                briefing: briefing:1mvkhny3ke6wcza27p8x5v8j:validation:attempt-1:revision-1
                by: agent:first-officer
                at: "2026-11-15T17:00:26.807123Z"
                decision: revise
                reason: 'Validator reproduced every measured number but rejected two statements in summary.md and NOTES.md: F1 calls two failed segments ''sub-100 ms corpus facts'' when they are 2.010 s and 11.507 s and the short thing is a tail chunk below the decode floor; F2 heads a bullet ''chrF does not fall'' over a 1.17 point fall justified by a noise band the round measured as zero. CL ordered the text corrected to agree with the result files, then a new validation.'
                conn:
                    quote: 'Validation gate of tier 2: the decision of CL is revise. Correct the two material findings, F1 and F2, in the summary and the notes. The corrected sentences must agree with the result files. This is a text change only: start no model run. Then do a new validation, and show the gate again with your recommendation.'
                    source: MetaFO brief relaying CL's decisions, 2026-11-15
            - id: gate-attempt:1mvkhny3ke6wcza27p8x5v8j-validation-2
              briefing:
                id: briefing:1mvkhny3ke6wcza27p8x5v8j:validation:attempt-2:revision-1
                digest: sha256:35472fe03098a18a8f6dd26025597f452cded60f0c018a9624f57fe6fa999515
                room-ref: '@review/validation/briefing-2'
              resolution:
                type: Resolution
                id: resolution:spacedock:1mvkhny3ke6wcza27p8x5v8j:validation:2
                briefing: briefing:1mvkhny3ke6wcza27p8x5v8j:validation:attempt-2:revision-1
                by: agent:first-officer
                at: "2026-11-15T17:23:06.446273Z"
                decision: revise
                reason: 'Second validation: F2 clean and F1''s substance verifies, but the replacement adds F7 (a modulo-8000 tail derivation on a buffer drained at 32000 samples) and F8 (a 0.3.5 finalize path stated beside a 0.4.4-era guard). No measured number changes; two sentences to rewrite.'
                conn:
                    quote: 'Q1: the second revise round of gate 1m is approved, as you recommend. Use one worker for the two sentences, with a maximum of 15 minutes and text only. Then use one worker for the validation, with a maximum of 30 minutes.'
                    source: MetaFO brief relaying CL's decisions, 2026-11-15
started: 2026-11-15T04:53:06Z
worktree: .worktrees/spacedock-ensign-simulst-tier2-two-direction-benchmark
---

Tier 1 shipped the benchmark suite that scores a translation. This task produces the two measured
numbers the project actually needs, and keeps them apart.

## The two directions

**Direction A, the product direction: Mandarin to English.** FLEURS Chinese rows, with the English
reference taken from the same `sentence_id` join tier 1 built. No new corpus and no download. This is
the direction the project exists for: Mandarin speech, English captions.

**Direction B, the comparison direction: English to Chinese.** The IWSLT 2026 devset, 21 wav files
and 919 segments, with `ref/en.txt` and `ref/zh.txt` on disk. This number can be placed beside the
published anchors; direction A cannot.

Never put the two numbers in one table. Each report and each note names its direction.

## Why direction B is the real work

The devset references are per segment, and segment boundaries live in `audio-segments.yaml` as
offset and duration pairs. The tier-1 harness samples one file at a time, so direction B needs a
segment-level emitter: cut each segment, run the cascade on it, and carry the segment's own source
and reference through to the report. That is the build this task owns.

## Scoring

chrF and the latency fields come from the harness locally. XCOMET-XL runs on `asr-xcomet.exe.xyz`,
which holds the 13.94 GB checkpoint in a warm cache; the recipe, its two pins and its 27.9 GB RSS
requirement are in `_work/eval_env_runbook.md` section 2a. Only text crosses the wire.

## Acceptance criteria

- **AC-1.** Direction A produces a checked-in report labelled product, covering at least 10 FLEURS
  Chinese rows, carrying chrF, `first_translation_time_s` and `final_translation_time_s`, plus a
  system XCOMET-XL score from one VM run whose request and response are both recorded. Falsifier: a
  row without a direction label, or an XCOMET score with no recorded request.
- **AC-2.** Direction B's emitter converts `audio-segments.yaml` plus the two reference files into
  per-segment samples and carries at least one whole wav file's segments end to end, with each
  segment's source, reference and hypothesis traceable to its segment index. Falsifier: a segment
  whose reference cannot be traced to its index in `ref/zh.txt`.
- **AC-3.** The run stays inside its limits: no download, cached models only, free disk on this Mac
  never below 1.5 GiB, and the VM paused between runs. Falsifier: a cache write or a disk reading
  below the floor.

## Ideation design: the tier-2 suite

CL's direction: "basically qwen-asr / nemotron x hy first. But we should define the
suite we'd run." So the first sprint is one MT model against two ASR models, in two
labelled directions, and the suite below is the whole of it. Every parameter below was
read out of the code, not recalled: `wlk bench` flags from `whisperlivekit/cli.py`
`cmd_bench`, engine knobs from `whisperlivekit/config.py` `WhisperLiveKitConfig`, the
simultaneous-MT switch from `whisperlivekit/core.py` (`mlx_llm_mt_simultaneous`), and
the latency gate from `whisperlivekit/benchmark/runner.py` (`observe` returns early
unless `self.speed == 1`).

### The one table, and why the results are not one table

CL asked for one suite table with a direction column: that is the planning table
below. The *results* stay split, as the entity body requires: one report table per
direction, each labelled, and no note or report ever places a zh→en chrF or XCOMET
figure beside an en→zh one.

### The suite

The run base is `wlk/integration-3` for every row, because `mlx-qwen3-asr` and the bundled zh-en calibration heads exist on that branch and not on `origin/main`.

One row per run. Ten columns: order, run base, direction, source and samples, ASR model, MT
model, parameters, measures, estimated time, necessary disk. Measure codes are
expanded under the table.

| # | Run base | Dir | Source and samples | ASR model (exact id) | MT model (exact id) | Parameters (exact flag/value) | Measures | Est. time | Necessary disk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `wlk/integration-3` | **A product zh→en** | FLEURS `fleurs-90.json` zh rows, 3 samples (`fleurs_zh_1700/1921/1993`, 27.5 s audio), subset manifest keeping their en siblings | `mlx-community/Qwen3-ASR-0.6B-8bit` via `--backend mlx-qwen3-asr` | `mlx-community/Hy-MT2-1.8B-8bit` via `--mt-model hy-mt2-1.8b-8bit` | `--speed 1 --repeats 1`, drafts **OFF** (`mlx_llm_mt_simultaneous: false`), `--target-language en` | Q L R S | 1 min | 0.1 MB |
| 2 | `wlk/integration-3` | **A product zh→en** | same 3 samples | same | same | `--speed 1 --repeats 1`, drafts **ON** (`mlx_llm_mt_simultaneous: true`, `mlx_llm_mt_simul_commit: "mass"`, `mlx_llm_mt_simul_frontier: "time"`, `mlx_llm_mt_simul_mass_threshold: 0.5`) | Q L R S | 1 min | 0.1 MB |
| 3 | `wlk/integration-3` | **A product zh→en** | FLEURS zh rows, **30 samples** (364.4 s audio), full `benchmarks/corpora/fleurs-90.json`, `--languages zh` | `mlx-community/Qwen3-ASR-0.6B-8bit` | `mlx-community/Hy-MT2-1.8B-8bit` | `--speed 1 --repeats 3`, drafts **OFF** | Q L R S | 19 min | 0.6 MB |
| 4 | `wlk/integration-3` | **A product zh→en** | same 30 | `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit` via `--backend nemotron-mlx-asr` | same | `--speed 1 --repeats 3`, drafts **OFF** | Q L R S | 19 min | 0.6 MB |
| 5 | `wlk/integration-3` | **A product zh→en** | same 30 | `mlx-community/Qwen3-ASR-0.6B-8bit` | same | `--speed 1 --repeats 3`, drafts **ON** (mass / time / 0.5) | Q L R S | 20 min | 0.6 MB |
| 6 | `wlk/integration-3` | **A product zh→en** | same 30 | `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit` | same | `--speed 1 --repeats 3`, drafts **ON** (mass / time / 0.5) | Q L R S | 20 min | 0.6 MB |
| 7 | `wlk/integration-3` | **A product zh→en** | 30 triples from run 3 (`src` = zh reference, `mt` = run 3 `translation`, `ref` = en sibling) | — (text only) | — | VM `asr-xcomet.exe.xyz`, batch_size 1, gpus 0 | X | 4 min VM | 0.3 MB |
| 8 | `wlk/integration-3` | **A product zh→en** | 30 triples from run 5 | — | — | same VM, second invocation | X | 4 min VM | 0.3 MB |
| 9 | `wlk/integration-3` | **B comparison en→zh** | IWSLT devset `OiqEWDVtWk.wav` = segments **0..29** (261.5 s audio, one whole file) | `mlx-community/Qwen3-ASR-0.6B-8bit` | `mlx-community/Hy-MT2-1.8B-8bit` | `--speed 1 --repeats 1`, drafts **OFF**, `--target-language zh`, emitter `scripts/run_iwslt_devset.py --wav OiqEWDVtWk.wav` | Q L R S | 5 min | 0.2 MB + ≤13.6 MB transient cuts |
| 10 | `wlk/integration-3` | **B comparison en→zh** | same 30 segments | same | same | `--speed 1 --repeats 1`, drafts **ON** (mass / time / 0.5) | Q L R S | 5.5 min | 0.2 MB + ≤13.6 MB transient |
| 11 | `wlk/integration-3` | **B comparison en→zh** | IWSLT devset, **all 919 segments** (6283.9 s audio, 21 wavs) | `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit` | `mlx-community/Hy-MT2-1.8B-8bit` | `--speed 0 --repeats 1`, drafts **OFF** | Q R S | 20 min | 5.0 MB (0.7 MB gz) + ≤13.6 MB transient |
| 12 | `wlk/integration-3` | **B comparison en→zh** | same 919 | `mlx-community/Qwen3-ASR-0.6B-8bit` | same | `--speed 0 --repeats 1`, drafts **OFF** | Q R S | 33 min | 5.0 MB (0.7 MB gz) + ≤13.6 MB transient |
| 13 | `wlk/integration-3` | **B comparison en→zh** | same 919 | winner of runs 11–12 | same | `--speed 1 --repeats 1`, drafts **OFF** (paced anchor) | Q L R S | 111 min | 5.0 MB (0.7 MB gz) + ≤13.6 MB transient |
| 14 | `wlk/integration-3` | **B comparison en→zh** | 919 triples from run 11 or 12 (`src` = en reference, `mt` = zh `translation`, `ref` = zh reference) | — | — | VM, third invocation | X | 17 min VM | 1.5 MB |

Measure codes: **Q** = `cer` (run 1–6, zh source) or `wer` (run 9–14, en source) plus
`chrf`, `translation`, `translation_reference`; **L** = `first_translation_time_s`,
`final_translation_time_s`, `provisional_lead_s`, `finalization_time_s`,
`source_end_lag_s`, `asr_call_mean_ms`, `asr_call_p95_ms`; **R** = `rtf`,
`mlx_peak_bytes`, `rss_peak_bytes`, `startup_time_s`, `wall_time_s`; **S** = `status`,
`timing_valid`, `timing_monotonic`, `n` ok/n, `config.translation` (target language,
backend, model, `simultaneous`), and each row's `effective_config`; **X** = the
XCOMET-XL system score with its request and response files recorded.

Directions are labelled at the row level and, again, at the report level. Run 13 is
the only run that produces a per-segment *paced* number for the comparison direction,
and it is the first row to drop if the budget shrinks (see the run order). Row 14 is
the only run whose absence would leave AC-2 satisfied but the comparison un-scored.

**Run 1 comes first.** It is the cheapest end-to-end proof that the product direction
works through the tier-1 harness: 27.5 s of audio, one model load, and it either
produces `chrf` plus both translation-latency fields or it does not. Runs 1–2 precede
the 19-minute rows deliberately: a flag error costs a minute, not an hour.

Estimated time comes from the measured audio duration divided by the feed speed plus
one model load (6.35 s, measured for the first sample in
`benchmarks/evaluations/translation-fleurs-en-zh/report.json`) plus a per-sample tail
drain. The drain is measured in the same report: 0.002–0.49 s without drafting and up
to 1.11 s with it. At `--speed 1` therefore wall ≈ audio + 0.4 s × samples, and for
run 3 that predicts 1136 s, against the retained m5 runs of the same 30 zh samples at
the same repeats (1123.1 s nemotron, 1134.4 s qwen in
`benchmarks/evaluations/m5-20261107/runs.jsonl`). At `--speed 0` wall ≈ `rtf` × audio
+ MT, using the retained per-language `rtf` (nemotron zh 0.114, qwen zh 0.239) plus
~0.5 s of MT per sample.

Mac total ≈ **4 h 15 min** across 11 rows; VM total ≈ **25 min** across three
invocations. That is the honest cost of two ASR models × two drafting states × two
directions, and the reason drafting on the full 919-segment set is deferred.

### Model inventory: cached versus download

Verified today by listing `~/.cache/huggingface/hub/models--*`:

| Model | Role | Cache |
|---|---|---|
| `mlx-community/Qwen3-ASR-0.6B-8bit` (964 MB) | qwen ASR, runs 1,2,3,5,9,10,12 | **cached** |
| `Qwen/Qwen3-ASR-0.6B` | qwen ASR fallback if the 8bit repo will not load | **cached** |
| `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit` (721 MB) | nemotron ASR, runs 4,6,11 | **cached** |
| `mlx-community/nemotron-3.5-asr-streaming-0.6b` | nemotron fallback (unquantized) | **cached** |
| `mlx-community/Hy-MT2-1.8B-8bit` (1.8 GB) | MT for every run | **cached** |
| `whisperlivekit/calibrations/translation_heads_mlx-community_Hy-MT2-1_8B-8bit_zh-en.json` (8 heads) | drafting A | in-repo, not a download |
| `whisperlivekit/calibrations/translation_heads_mlx-community_Hy-MT2-1_8B-8bit_en-zh.json` (48 heads) | drafting B | in-repo, not a download |
| FLEURS audio, 183 wav under `~/.cache/whisperlivekit/benchmark_data/fleurs_v1/` | direction A audio | **cached** |
| IWSLT devset, 21 wav + 919 refs at `Alignatt4LLM/data/devset/` | direction B audio | **on disk** |

No row in the suite needs a download. Models considered and **excluded because they
would need one**: `mlx-community/Hy-MT2-7B-4bit`, `mlx-community/Hy-MT2-7B-8bit`,
`mlx-community/Hunyuan-MT-7B-4bit`, `mlx-community/translategemma-4b-it-4bit`,
`Qwen/Qwen3-ASR-1.7B`, and `Unbabel/XCOMET-XL` (13.94 GB; the local
`models--Unbabel--xcomet-xl` directory is a 36 KB stub, which is why scoring is on the
VM). Two cached models are also excluded for a *code* reason, not disk:
`mlx-community/Hy-MT2-1.8B-4bit` cannot take `--simultaneous` because
`load_calibration` derives the filename from model repo plus direction and only the
8bit calibrations are bundled, so a 4bit drafting row would fail at startup;
`hy-mt2-1.8b-4bit` with drafting OFF stays a cheap follow-on.

### Run order

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (direction A complete, ~1 h 30 m), then the direction-B
emitter is built, then 9 → 10 (AC-2 proof, ~11 m), then 11 → 12 (~53 m), then 14
(scored comparison), then 13 (paced anchor, ~111 m) if the budget still holds.

Paired rows run adjacent and alternating (3 off, 5 on; 4 off, 6 on) so a thermal drift
hits both members of a pair, and the run log records start/end and AC power state the
way `benchmarks/evaluations/m5-20261107/runs.jsonl` does. Comparisons are only made
inside a pair; no cross-pair latency claim is drawn.

Cut-line if the budget shrinks, in order: run 13 (paced 919 anchor), run 8 (drafted
nemotron has no XCOMET number), run 6 (nemotron drafting on FLEURS), run 12 (qwen on
the full 919).

### Direction B's segment-level emitter (the build this task owns)

One new script, `scripts/run_iwslt_devset.py`, using the tier-1 harness's public
surface: it builds `BenchmarkSample` objects and passes them to
`BenchmarkRunner(samples=...)`, then writes the report with
`whisperlivekit.benchmark.report.write_json`. No change to `whisperlivekit/`.

**Cutting.** `audio-segments.yaml` is a flat list of 919 mappings with `wav`, `offset`,
`duration`, `speaker_id`; its order is the global segment index and it is grouped by
wav in file order. Each cut is `wav[offset : offset+duration]` taken from
`Alignatt4LLM/data/devset/audio/<wav>` (16 kHz mono PCM16 — 21/21 files verified, so
`soundfile`'s fast path in `test_harness.load_audio_pcm` applies and the broken
system ffmpeg is never reached). Cuts are written as 16 kHz mono PCM16 wavs into a
transient directory, one wav's segments at a time, and deleted after that wav's
runner finishes, so peak transient disk is the largest file's cut set (425.81 s →
13.6 MB) instead of all 919 (201 MB). Boundaries were checked against the audio:
**0** segments run past their wav's duration; **57** adjacent pairs overlap by
0.008–0.118 s (mean 0.017 s), which does not affect independent cuts but means segment
durations sum ~1 s above the union of speech.

**Reference tracing.** `ref/en.txt` and `ref/zh.txt` each have exactly 919 lines and
line *i* is segment *i*. For direction B the *source* is `en.txt[i]` (the transcript of
this English audio, scored by `wer` because the sample's `language` is `en`) and the
*translation reference* is `zh.txt[i]`, injected as
`BenchmarkSample.translation_references = {"en": en[i], "zh": zh[i]}` with
`target_language="zh"` so `runner` picks `chrf` up through the same field the FLEURS
join uses. `sentence_id` is set to the global segment index, and `name` is
`iwslt_<wavstem>_<index:03d>`, so a report row, a cut file and a reference line are all
keyed by the same integer. Two reference-file facts the emitter must record and not
repair: 17 `en.txt` lines begin with a stray `"` and double their inner quotes (a TSV
export artifact) — `normalize_text` drops it before scoring, so chrF/WER are
unaffected, but the stored `reference` keeps it; and no line is empty.

**What the index join is worth.** Segment duration versus `en.txt` line length
correlates at **0.948** at shift 0 and collapses when shifted (**0.115** at −1, **0.158** at
−2, **0.097** at +1, **0.128** at +2). That is the emitter's self-check: a slipped or
off-by-one join cannot hide behind a plausible score.

**File layout, line estimates and tolerances.**

| Artifact | Lines/items | Estimate | Tolerance |
|---|---|---|---|
| per-wav segment manifest inside the script | 919 rows over 21 wavs (30, 52, 43, 37, 45, 42, 56, 42, 45, 47, 48, 54, 43, 32, 39, 48, 46, 57, 37, 43, 33) | exact by construction | 0 — any deviation is a dropped or duplicated segment |
| `trace-<wav>.csv` | 1 header + N segment rows | 920 for the full set, 31 for run 9 | 0 |
| cut wavs | 1 per segment | 919 total, ≤57 live at once | 0 live-vs-expected per wav |
| report JSON (schema 3.2) | 1 result object per segment | 919 objects, ~5.4 KB each (measured on the tier-1 3-sample reports), ~5.0 MB raw, ~0.7 MB gzipped | ±1 result; ±20% bytes |
| XCOMET request/response | 1 pair per VM invocation | 919 triples ≈ 0.9 MB request | ±0 |

**Acceptance numbers.** Direction A: 30 of 30 zh rows `status == "ok"`, each with a
non-null `chrf`, a non-empty `translation`, a non-null `first_translation_time_s` and
`final_translation_time_s`, `final ≥ first`; `provisional_lead_s` non-null on runs 5–6
and null on runs 3–4; one XCOMET-XL system score per VM invocation with request and
response both on disk. Direction B: 919 of 919 segments present in the trace with
(index, wav, offset, duration, `en` reference, `zh` reference, `hypothesis`,
`translation`, `chrf`), at least 900 with `status == "ok"` and a non-empty
`translation`, 30 of 30 for run 9's wav, the join correlation ≥ 0.90, and one XCOMET-XL
system score over 919 triples. No quality floor is set in either direction: a floor
measures the cascade, not the harness, and the comparison that matters is inside each
direction (qwen vs nemotron; drafting off vs on).

**What would falsify the estimate.** A trace file that is not 920 lines for the full
set; a run-9 trace with fewer than 31 lines; a join correlation below 0.90 or a shift-0
score beaten by a shifted one; a cut whose byte length is not `round(duration×16000)×2`;
a report whose result count differs from the segment count; a disk reading below
1.5 GiB; any HuggingFace cache write (enforced, below); or a measured wall time more
than 25% above a row's estimate, which would falsify the drain-per-sample and `rtf`
assumptions the remaining estimates rest on.

### How the limits are enforced, not promised

- `run_iwslt_devset.py` sets and *requires* `HF_HUB_OFFLINE=1`, and refuses to start
  otherwise, so "no download" fails loudly instead of silently fetching. The tier-1
  demonstration reports used the same mechanism.
- The same script reads free space on `/System/Volumes/Data` before each wav and exits
  non-zero below 1.5 GiB. Today's reading is 2.4 GiB free, i.e. 957 MiB of headroom
  over the floor, against a worst-case per-row footprint of ~20 MB (5 MB report +
  13.6 MB transient cuts). Every row above is therefore **available**, and none is
  marked blocked.
- The VM is paused with `ssh exe.dev pause asr-xcomet` after each of runs 7, 8, 14;
  only `{src, mt, ref}` text crosses the wire.

### Acceptance criteria, with their proof

Refining AC-1..AC-3 into end-state properties; the numbers above are the substance and
these are the checks.

- **AC-1 (direction A report).** Verified by: a checked-in
  `benchmarks/evaluations/simulst-tier2-two-direction/` report labelled product with 30
  FLEURS zh rows carrying `chrf`, `first_translation_time_s`,
  `final_translation_time_s`, plus one XCOMET-XL system score whose request and response
  files sit beside it. Falsified by a row without a direction label, a non-null claim
  with no recorded request, or a row whose `translation_reference` is not its
  `sentence_id`'s en sibling.
- **AC-2 (direction B emitter).** Verified by: run 9's trace of 30 segments from one
  whole wav, plus the 919-segment trace, each row carrying its segment index, wav,
  offset, duration, source, reference, hypothesis and translation; and by the join
  correlation check (0.948 measured, ≥ 0.90 asserted). Falsified by a segment whose
  reference cannot be traced to its index in `ref/zh.txt`, by a trace line count other
  than header+N, or by an off-by-one shift scoring higher than shift 0.
- **AC-3 (limits).** Verified by: `HF_HUB_OFFLINE=1` enforced by the script, no cache
  write in the run logs, every disk reading ≥ 1.5 GiB, and the VM logged paused between
  the three invocations. Falsified by a cache write, a reading below the floor, or a
  resumed VM with no pause record.

### Test plan

| Test | Asserts | Change that would make it fail |
|---|---|---|
| `tests/test_iwslt_emitter.py::test_cut_length_matches_offset_duration` | a sampled cut's byte length equals `round(duration × 16000) × 2` for 10 segments across 3 wavs | slicing with `duration×16000` unrounded, or a half-open/closed off-by-one |
| `::test_reference_index_join` | duration-vs-`en.txt`-line-length correlation ≥ 0.90 at shift 0 and < 0.20 at ±1 over all 919 | sorting segments by offset-within-wav instead of global file order, or joining `zh.txt` to `en.txt` by a shifted index |
| `::test_trace_line_count` | the emitted trace has exactly `1 + N` lines for a 30-segment wav and 920 for the full set | dropping a segment with an empty hypothesis, or emitting the trace before the last sample |
| `::test_refuses_without_offline_flag` | the script exits non-zero with `HF_HUB_OFFLINE` unset | removing the guard, which would let a missing model download silently |
| `::test_refuses_below_disk_floor` | the script exits non-zero when the free-space probe reports < 1.5 GiB | removing the check, or reading the wrong mount |
| run-1 smoke (real, not a unit test) | 3 zh rows with non-null `chrf` and both translation-latency fields | `--speed 1` dropped (latency fields go null), `--target-language en` missing, or the subset manifest losing the en siblings so `translation_reference` is empty |

### Expected files and lines, with tolerance

| File | Change | Lines |
|---|---|---|
| `scripts/run_iwslt_devset.py` | new: parse yaml + refs, cut segments, build samples, run, write report + trace | 200 ± 40 |
| `tests/test_iwslt_emitter.py` | new: the five assertions above | 120 ± 40 |
| `benchmarks/evaluations/simulst-tier2-two-direction/NOTES.md` | new: provenance, both direction sections, commands, limits | 70 ± 25 |
| `benchmarks/evaluations/simulst-tier2-two-direction/report-<run>.json` (11 files, runs 1–6, 9–13) | new: schema 3.2 reports, gzipped where over 1 MB | 0 hand-written lines; 0.1–0.7 MB each |
| `benchmarks/evaluations/simulst-tier2-two-direction/xcomet/<run>-{request,response}.json` (3 pairs) | new: recorded VM text | 0 hand-written lines |
| `benchmarks/evaluations/simulst-tier2-two-direction/summary.md` | new: two separate result tables, one per direction | 60 ± 20 |
| `whisperlivekit/**` | **no change** | 0 |

Semantic changes: none to the library or the CLI. The only new behaviour is outside the
package, in `scripts/`, plus tests.

### Risks, with the evidence behind the estimate

- **qwen 8bit repo may not load in `mlx-qwen3-asr`.** The backend's help text names
  `Qwen/Qwen3-ASR-0.6B` and `Qwen/Qwen3-ASR-1.7B`; the quantized `mlx-community` repo is
  cached but unproven on this backend. Cost if wrong: one 1-minute smoke run, then
  switch to the cached unquantized `Qwen/Qwen3-ASR-0.6B`. No download either way. This
  is one reason run 1 is first.
- **`--speed 0` runs carry no latency fields.** Code-verified (`observe` returns early
  unless `speed == 1`). Runs 11–12 are quality rows only; their reports will have null
  `first_translation_time_s`. That is a property of the run, not a missing measurement,
  and the same convention the README already applies to null CER.
- **Drafting is impossible at `--speed 0`.** The commit policy's frontier tracks the
  audio cursor, so an unpaced feed removes the streaming regime the policy exists for.
  Drafting rows are `--speed 1` only.
- **MT text is not repeat-deterministic** (tier-1 validation finding 4, deferred to tier
  2). `--repeats 3` on the FLEURS rows gives a spread to report rather than a single
  draw; the 919-segment rows rely on aggregation instead, and a repeat there would cost
  another 20–33 minutes.
- **`--config` takes a path, not inline JSON** (tier-1 NOTES). Every drafting row needs
  a small JSON file on disk first; a script writing them is cheaper than remembering.
- **Thermal contamination between back-to-back rows** is why paired rows alternate and
  why comparisons stay inside a pair.
- **The drafting parameters to pin are CL's call, not the code's.** The code default is
  `mlx_llm_mt_simul_commit: "paper"`; the suite pins `"mass"` because that is the best
  measured policy in `_work/SIMUL_MT_CONSOLIDATED.md`. If CL prefers the default, only
  the parameters column and the drafting rows change; nothing else in the suite moves.

## Stage Report: ideation

- DONE: The suite is one table with one row per run and all nine columns: direction, source and sample count, ASR model, MT model, parameters (feed speed, draft translation on or off, repeats), measures, estimated time, necessary disk space.
  `### The suite` — 14 rows (11 Mac + 3 VM), each parameter named as the exact flag and value read from `cli.py:cmd_bench`, `config.py` and `core.py`; measures given as codes Q/L/R/S/X expanded under the table.
- DONE: Each row names the exact cached model id, the table states which models are in the local HuggingFace cache and which would need a download, and the run order is stated with the first run marked.
  `### Model inventory` — qwen 8bit (964 MB), nemotron 8bit (721 MB), Hy-MT2-1.8B-8bit (1.8 GB) plus both bundled calibrations, all verified present in `~/.cache/huggingface/hub` today; five excluded models listed as needing a download, `Hy-MT2-1.8B-4bit` excluded for a code reason instead (no bundled calibration for `--simultaneous`). `### Run order` marks **run 1 first** and gives the cut-line.
- DONE: The design states the segment-level emitter for the IWSLT direction: how segments are cut from audio-segments.yaml, how each reference is traced to its segment index, the file layout with a line estimate and tolerance, the acceptance number each direction must reach, and what would falsify the estimate.
  `### Direction B's segment-level emitter` — soundfile cuts per `offset`/`duration` (0 out-of-bounds of 919, 57 sub-0.118 s overlaps recorded), line *i* of `ref/{en,zh}.txt` is segment *i* with the join witnessed by a duration-vs-reference-length correlation of 0.948 at shift 0 against 0.097–0.158 at ±1, layout table with tolerances (920 trace lines, 919 cuts, 919 results), acceptance numbers per direction, and a falsifier list.
- DONE: Approach, risk evidence, expected files and lines with tolerance, semantic changes and proposed proof for each AC (ideation gate content).
  `### Expected files and lines`, `### Risks, with the evidence`, and `### Acceptance criteria, with their proof` restating AC-1..AC-3 as `Verified by:` end-state properties; `whisperlivekit/**` unchanged.
- DONE: Test plan.
  `### Test plan` — five assertions in `tests/test_iwslt_emitter.py` plus the run-1 smoke, each with the change that would make it fail.
- SKIPPED: Running a model, building the emitter, writing code.
  Ideation stage; CL's scope for this stage is design only. Every time and disk figure is derived from retained reports rather than from a fresh run.

### Summary

Design-only deliverable: a 14-row suite table for qwen-asr × nemotron × Hy-MT2-1.8B-8bit in
both directions, with the parameters read out of the code, an all-cached model inventory, a
stated run order with run 1 first, and the direction-B segment emitter specified down to line
counts and falsifiers. No file in `whisperlivekit/` changes; the emitter is one `scripts/`
file plus one test file. Open point for CL: the drafting rows pin
`mlx_llm_mt_simul_commit: "mass"` while the code default is `"paper"`.

## Stage Report: implementation

- DONE: The suite table names the run base in every row, and the base is wlk/integration-3, so the qwen3 rows name a backend that base actually offers; the amendment is stated once in prose above the table with the reason origin/main cannot run those rows.
  `### The suite` — one sentence above the table names `wlk/integration-3` and why (`mlx-qwen3-asr` and the bundled zh-en calibration heads are on that branch, not on `origin/main`), a `Run base` column was added to the header, and `wlk/integration-3` is in all 14 rows including the three VM rows (source of their triples); state commit `ed7868b`, frontmatter and status untouched.
- DONE: The segment-level emitter builds: it reads audio-segments.yaml and ref/en.txt, ref/zh.txt, cuts each segment, and carries each segment's source, reference and segment index through to the report so a segment is traceable to its line in ref/zh.txt, with a model-free test that fails when a reference is misaligned.
  `scripts/run_iwslt_devset.py` + `scripts/traced_bench.py`, code commit `ebb1ff5`: each cut is `wav[offset : offset+duration]` at `round(duration × 16000)` frames, named `iwslt_<wavstem>_<index:03d>`, one wav's cuts live at a time, and the trace CSV carries index, wav, offset, duration, source, reference_en, reference_zh, hypothesis, translation, status, error and both translation latencies. `tests/test_iwslt_emitter.py` (7 tests) fails when the zh reference is joined one line off and when a cut truncates instead of rounding — both shown by mutating the script and watching the test fail, then reverting.
- DONE: Run 1 of the suite is executed first on the declared base and its report is recorded, and the build reports the exact command, the wall time and the disk it used.
  `benchmarks/evaluations/simulst-tier2-two-direction/`, code commit `7be295e`: 3/3 FLEURS zh rows `status == ok` with `cer` and `first_translation_time_s` in the report and translation text for 3/3 in `trace-run1.csv`; the report records `git_commit c2b506d`, `git_dirty false`. Exact command, wall time 33.16 s against the 1-minute estimate, and disk −1.4 MiB against the 1.5 GiB floor are in `NOTES.md`.
- SKIPPED: Runs 2–14, including the 919-segment direction-B work.
  MetaFO's gate: run 1 is the gate on the rest of the suite. The direction-B emitter is exercised model-free (join self-check over all 919 segments, 30 real cuts from `OiqEWDVtWk.wav`, the trace writer) but has not been run through the harness; row 9 is its first real exercise.

### Summary

The suite now names its base in every row, the direction-B emitter and the direction-A recorder
exist in `scripts/` with no library change, and run 1 passed on `wlk/integration-3`: 3/3 zh rows
ok, translation text in the trace, 33.16 s wall, disk well above the floor, `git_dirty false`.

One base fact shaped the build, with the first officer's approval: tier 1's recorder (the `chrf`,
`translation` and `translation_reference` fields, `compute_chrf`) is on
`wlk/simulst-eval-harness`, not on `wlk/integration-3`, so `SampleResult` here carries no `chrf`
and no report can score itself. Each run therefore writes the canonical report **plus** a trace
CSV, and chrF is applied to the trace at scoring time with sacrebleu's sentence-level chrF (word
order v2, punctuation kept) against its `reference_en` column. That absence is stated in
`notes-<run>.json`, in `NOTES.md` and here, so an empty `chrf` field is not read as a missing
measurement. Run 1's own numbers are therefore `cer` plus `first_translation_time_s`, not chrF.

A second guard came out of the run itself: a script run by path imports the installed package,
which is the main checkout on `wlk/integration-2`, so the first attempt at run 1 measured the
wrong branch's library and said so only in `system_info.git_commit`. The recorder now refuses to
start unless the imported `whisperlivekit` is inside the checkout that holds the script, and
records the resolved package path in each run's notes.

## Stage Report: implementation (cycle 2, the runs round)

- DONE: Runs 2 through 14 execute in the suite's table order on wlk/integration-3, with the long rows 11 to 14 last, and every run's command, report, trace and notes are recorded under benchmarks/evaluations/ with its direction label.
  13 of 14 rows are recorded in `benchmarks/evaluations/simulst-tier2-two-direction/` (runs 2-12, 7, 8, 14) — each with `report-<run>.json`, `trace-<run>.csv`, `notes-<run>.json` carrying the exact command and `"direction"`, plus `run<N>-chrf.json`; runs 11-12 and 14 came last as instructed; code commits `96ea6d7`..`b15eb71` on `simulst-tier2-two-direction-benchmark`.
- SKIPPED: Run 13, the paced 919-segment en->zh anchor at `--speed 1`.
  It is the ideation's declared first cut-line row and needs 111 min against the ~85 min left after run 14; the two measured 919-segment rows overran their estimates by 38% (run 11, 1660.92 s) and 10% (run 12, 2180.26 s), so it would have overrun the round. Nothing else depends on it; direction B keeps its paced numbers from runs 9-10.
- DONE: Every direction-A row's trace carries the translation and its English sibling reference, and chrF is computed from the trace with sacrebleu sentence_chrf, named as that variant wherever the number appears.
  `translation` and `reference_en` are non-empty on 100% of rows in traces 1-6 (3/3, 3/3, 90/90, 90/90, 90/90, 90/90); `scripts/score_trace.py` writes chrF from the trace with the variant string `sentence_chrf (sacrebleu: sentence-level chrF, char_order=6, word_order=2, beta=2, case-sensitive, punctuation kept, whitespace not scored)` into every `run<N>-chrf.json`, and `summary.md` names that variant above both tables; hand-recomputed per-segment chrF on segments 5/100/400 reproduces the scorer's values.
- DONE: The VM scores rows 7, 8 and 14 with the request and response files recorded, the VM is paused after each invocation, and free disk on this Mac never crosses 1.5 GiB.
  `xcomet/{7,8,14}-{request,response}.json` — 30 triples -> 0.6432 (run 3), 30 -> 0.6649 (run 5), 919 -> 0.4378 (run 11), response id counts 30/30/919; resume+pause around each (06:03->06:08, 06:23->06:27, 07:27->08:44, all `exit 0`); the lowest free-space reading before any run was 2 366 108 KiB (2.26 GiB).

### Summary

The suite is executed and recorded except its declared first cut-line row: 12 harness rows and
three VM scorer invocations, all on `wlk/integration-3`, all with `git_dirty: false` and
`HF_HUB_OFFLINE=1`, every report paired with a trace that carries the text the base's report
cannot hold. Direction A (FLEURS zh->en): drafting cuts mean time-to-first-translation on both
backends (qwen 6.519->4.906 s, nemotron 7.554->2.794 s) on byte-identical ASR, with chrF flat to
slightly up (43.128->43.915 qwen) and XCOMET 0.6432->0.6649 on the same 30 triples. Direction B
(IWSLT en->zh): 919/919 segments for nemotron and 917/919 for qwen (two sub-100 ms segments are
too short for qwen's log-mel framing), join self-check 0.9477 at shift 0 against 0.097-0.158
shifted, and XCOMET 0.4378 over nemotron's 919 triples — while nemotron's lower WER (0.2268 vs
0.2938) comes with half the chrF (12.481 vs 26.348), so the two measures disagree in this
direction and both are reported.

Two findings the round produced that the ideation did not expect. `--repeats 3` measures no text
spread on this base at all — 0/30 samples differ in translation or hypothesis between passes on
all four repeated rows, only latency moves (0.043-0.097 s per-sample spread) — so the tier-1
"MT is not repeat-deterministic" concern does not reproduce here, at the cost of two extra passes
per row. And the traced runner had no `--repeats` at all (`BenchmarkRunner` has it, but the
traced recorder drives `TestHarness` directly), so rows 3-6 could not run their declared
parameter until it was added (commit `9eb205a`, with a `repeat` column in the trace and a guard
against replaying the direction-B emitter's one-shot generator). Run 13 remains the one hole, by
the declared cut-line.

## Stage Report: validation

- DONE: Every number in summary.md is reproduced from its run's own artifacts: the chrF from the trace with the named sacrebleu variant, the cer or wer from the report, and the XCOMET system score from the response file, including the row and segment counts claimed beside each.
  Recomputed chrF (sacrebleu 2.6.0 `sentence_chrf`, char_order=6, word_order=2, beta=2, case-sensitive, whitespace not scored, direction's own reference column) from all ten traces: 44.886/47.329/43.128/42.726/43.915/41.556/25.218/24.688/12.481/26.348, max deviation 0.00047 from summary.md; row/ok/with-translation counts 3/3/3, 90/90/90, 30/30/30, 919/919/902, 919/917/916 all match. cer/wer reproduce as the unweighted mean of per-row values (run3 0.2545, run4 0.2352, run11 0.2268, run12 0.2938); `first_translation_time_s` means reproduce to 3 dp (6.519/4.906/7.554/2.794/4.664/3.132) and are null on 919/919 of runs 11-12 as stated. XCOMET `system` equals the mean of the per-segment scores in each response file (0.643247/0.664910/0.437843), 30/30/919 ids all unique and matching the request ids, and every request triple is field-identical to its trace row (`src`=`source`, `mt`=`translation`, `ref`=`reference_en` for A / `reference_zh` for B) with the `chrf` echo equal to `run<N>-chrf.json`. Run 14's 17 empty `mt` equals 919-902.
- DONE: The two directions stay apart: no table quotes the other direction's number, each row names its direction label, and the absence of a direction-B XCOMET score for qwen is stated rather than implied.
  Each table sits under a direction heading naming direction, language pair and corpus; the A numbers (0.6432/0.6649, cer, chrF 42-47) appear only in the A section and the B numbers (0.2268/0.2938, 12.481/26.348, 0.4378) only in B. Direction labels also ride every `notes-<run>.json` (`"A product zh->en"` / `"B comparison en->zh"`) and the report/trace `target_language` (en for 1-6, zh for 9-12) agrees. summary.md:68 states "there is **no** direction-B XCOMET score for qwen, and the 0.4378 belongs to the nemotron row alone".
- FAILED: The runs that did not happen and the rows that did not complete are stated with their counts and their reason, and run 13's cut is consistent with the suite's declared cut-line rather than a silent omission.
  Run 13 is stated (summary table row "not run", NOTES deviation 2, cycle-2 report SKIPPED) and is the ideation's declared first cut-line row, so the cut is consistent. But the stated reason for run 12's two failed rows is contradicted by the artifacts: summary.md:83-85 and NOTES.md:145-148 call indices 213 and 901 "0.010 s / 0.007 s" and "sub-100 ms segments", while `audio-segments.yaml` and `trace-run12.csv` give those segments 2.010 s and 11.507 s of non-silent audio (RMS 0.066/0.039), and 160/112 are those durations mod 1600 samples (0.1 s) — tail chunks below `_MIN_DECODE_SAMPLES = 400` (`whisperlivekit/asr_mlx_qwen3.py`), not segment lengths. Run 12's `total_audio_s` is exactly 13.517 s below run 11's, the sum of those two segments.

### Reviewer findings

- **F1 (material, doc).** summary.md:83-85 and NOTES.md:145-148 assert "the two failed segments ... are corpus facts, not harness failures" and that the devset "contains sub-100 ms segments". Contradicted by the artifacts as above; the short thing is the decode window, not the segment, and the qwen3 path guards that floor in `finish()` but not in `process_iter()`. Numbers unaffected (917/919, AC-2 floor 900); the harm is a false corpus claim plus an unexplained backend condition recorded as out of scope. Fix: restate the mechanism; optionally record the backend condition as an open item.
- **F2 (material, doc).** summary.md:41-42 heads a bullet "**chrF does not fall**" while citing nemotron 42.726 -> 41.556, and justifies it as "inside the noise of a single ASR/MT draw" — but the round's own finding is 0/30 text differences across the three passes, i.e. measured noise is exactly zero, so no noise band exists to place -1.17 inside. Fix: state the two deltas (+0.79 qwen, -1.17 nemotron) with no repeat-variance estimate available.
- **F3 (polish).** summary.md:17 says cer/wer "are the benchmark's own"; the quoted values are the per-row mean, while the report also carries `weighted_cer` (run3 0.2738 vs quoted 0.2545). Name the aggregation.
- **F4 (polish).** The cycle-2 implementation Summary says "12 harness rows and three VM scorer invocations"; the directory holds 10 harness runs (1-6, 9-12) plus 3 VM invocations = 13 of 14 rows.
- **F5 (residual risk).** No test covers `scripts/score_trace.py`, the producer of every chrF number and every XCOMET request, including the direction-to-reference-column switch; today only my recomputation guards it.
- **F6 (polish).** Every `notes-<run>.json`, direction B included, says chrF is scored "against the en reference named in each trace row"; direction B scores `reference_zh`.

### Checks run (model-free; no cascade, no VM, no download)

`/tmp/verify_tier2_chrf.py` and `/tmp/verify_tier2_reports.py` (recompute both directions from traces/reports), reference tracing runs 9-12 against `ref/en.txt`/`ref/zh.txt` (0/919 and 0/30 mismatches, indices contiguous), direction-A reference against the `fleurs-90.json` en sibling (0 slews over 30 sources), the emitter's own `reference_join_correlation` (0.9477 at shift 0, 0.1578/0.1148/0.0973/0.1278 shifted), trace line counts (920/31/91/4), repeat invariance (0/30 differ in translation or hypothesis), report-vs-response XCOMET reconstruction, `git status` clean, `df` 3.82 GiB free, HF cache untouched in the run window, `pytest tests/test_iwslt_emitter.py` 9 passed.

### Acceptance-criterion evidence

- **AC-1** — direction A: 6 labelled product reports (runs 1-6) with 3 and 90 rows, `first_translation_time_s` non-null on 100% of 366 rows with `final >= first` on 366/366 (the trace carries `final_translation_time_s`; the base's `SampleResult` has no such field, so it is recorder-computed, not report-resident — the same split the chrF note documents), `reference_en` is the `sentence_id` en sibling on 30/30 sources, and `xcomet/7-{request,response}.json` scores run 3's 30 triples. Falsifier clear; the report-resident-versus-trace split for chrF and `final_translation_time_s` is the approved and documented deviation.
- **AC-2** — direction B: run 9 is 30/30 segments of `OiqEWDVtWk.wav` with contiguous indices 0-29; runs 11-12 carry 919/919 segments, 0/919 `reference_en` and 0/919 `reference_zh` mismatches against line *i* of the two reference files, 919/919 and 917/919 ok. Report rows join to trace rows by the `iwslt_<stem>_<index>` suffix (0 mismatches). Falsifier (a reference untraceable to its index) does not fire.
- **AC-3** — `require_offline_hub`, `require_free_space` and `require_library_from_this_checkout` are called by both runners; `git_dirty: false` on all ten reports; disk 2.26-2.28 GiB during the round and 3.82 GiB now against the 1.5 GiB floor; no `~/.cache/huggingface/hub` entry was modified inside the run window; NOTES records resume/pause around each of the three VM invocations. Falsifier clear.

### Summary

Every measured number in summary.md reproduces from the artifacts — chrF within 0.0005 on all ten scored runs, cer/wer and latency means exactly, XCOMET system scores as the mean of their own per-segment files, and all row/segment counts — and the two directions are cleanly separated with the missing qwen XCOMET stated. Validation recommends **REJECTED for a narrow documentation fix, not a rerun**: two sentences (summary.md:41-42 and :83-85 with NOTES.md:145-148) assert things the checked-in traces contradict — a "chrF does not fall" claim citing a fall justified by a noise band the round measured as zero, and a "sub-100 ms corpus" explanation for two segments that are 2.010 s and 11.507 s long. No AC falsifier fires, no number changes, and F3-F6 are optional polish. Entity frontmatter and status untouched; no code or artifact edited.

## Stage Report: implementation (cycle 3, the F1/F2 text correction)

- DONE: F1 is corrected in summary.md and NOTES.md: the two failed run-12 segments are described by their measured durations 2.010 s and 11.507 s, and the mechanism is named as a tail chunk below the decode floor that finish() guards and process_iter() does not, replacing the sub-100 ms corpus claim.
  summary.md:86-96 and NOTES.md:144-155 now read "the tail the 0.5 s feed leaves at the end of each (32160 and 184112 samples modulo 8000 give 160 and 112 samples)", "the finalize decode hands exactly that tail to `compute_features`", and "`_MIN_DECODE_SAMPLES = 400` is checked in `finish()` against the accumulated window (`_window_samples()` = context + tail), which a 2 s segment clears, and `process_iter()` has no such check at all". The "corpus facts" / "sub-100 ms" sentences are gone from both files (`grep -rn "sub-100\|0.010 s\|0.007 s"` over the worktree: no hits). Commit 787595b.
- DONE: F2 is corrected: the chrF-does-not-fall heading and its noise-band justification are replaced by the two measured deltas with no repeat-variance claim, because the round measured zero spread across three passes.
  summary.md:41-45 now heads the bullet "**chrF moves in opposite directions on the two backends**" with qwen 43.128 -> 43.915 (**+0.79**) and nemotron 42.726 -> 41.556 (**-1.17**), and states "no repeat-to-repeat spread is available … per-pass spread 0.0000 on runs 3-6". No variance band is asserted anywhere: `grep -rn "noise of a single"` over the worktree: no hits. Commit 787595b.
- DONE: Every changed sentence agrees with the result files: the numbers in the corrected text match report-*, trace-* and run*-chrf.json, no model run was started, the diff touches text only, and the worktree is clean.
  Recomputed from the artifacts (stdlib + the checkout's sacrebleu 2.6.0, no model, no VM): run*-chrf.json give the four chrF values and therefore +0.786867 / -1.169913; per-pass mean chrF recomputed from trace-run3/4/5/6 groups by `repeat` has spread 0.000000 on all four runs and 0 differing translations across 120 grouped rows; trace-run12.csv failed rows are index 213 (`duration_s` 2.010) and 901 (11.507) and their sample counts 32160/184112 mod the harness's 8000-sample (0.5 s) feed chunk are exactly the 160/112 samples named in the error; report-run11/12 `total_audio_s` 6283.891 / 6270.374, delta 13.517 = 2.010 + 11.507 (a failed row contributes no audio to the total: trace ok-only sum for run 12 equals its reported total). Code claims re-read at HEAD: `_MIN_DECODE_SAMPLES = 400` (asr_mlx_qwen3.py:37), `_window_samples()` = `len(audio_accum)+len(buffer)` (:215), guards only in `finish()` (:279, :286), none in `process_iter()` (:263-273), and the library's `finish_streaming` decodes `state.buffer` only (streaming.py:263 -> `compute_features`). `git diff --stat` = 2 markdown files; `git status --short` empty after 787595b.

### Summary

Both rejected statements are restated from the artifacts and nothing else moved: no number, table, heading, section or frontmatter changed, no model run or download, VM untouched, disk 3.7 GiB free (floor 1.5). One precision note for the gate: the F1 instruction's phrasing "a tail chunk below the decode floor that finish() guards" is only half true in the code — `finish()` holds the floor check but applies it to `_window_samples()` (accumulated context + tail), which a 2 s segment clears, so the check is what these two segments pass through before the finalize decode reaches the tail; the corrected text says exactly that plus the absence of any check in `process_iter()`, rather than claiming `finish()` catches small tails. F3-F6 were out of scope and untouched.

## Stage Report: validation (cycle 2, the F1/F2 text correction)

- DONE: F2 is gone and its replacement agrees with the artifacts: no chrF-does-not-fall claim and no noise-band justification remain, the two deltas are stated with their signs, and the variance statement matches what the three passes measured.
  `grep -rni "chrF does not fall|noise of a single|noise band|inside the noise"` over the evaluation directory returns no hits. summary.md:41-45 gives qwen 43.128 -> 43.915 (**+0.79**) and nemotron 42.726 -> 41.556 (**-1.17**), which are exactly `run3-chrf.json` 43.128024 -> `run5-chrf.json` 43.914891 (+0.786867) and `run4-chrf.json` 42.726186 -> `run6-chrf.json` 41.556273 (-1.169913). Per-pass means recomputed from each file's `per_row` grouped by `repeat` are identical to 6 dp inside all four runs (30 rows x 3 passes), so "per-pass spread 0.0000 on runs 3-6" is exact and the text asks no reader to weigh the deltas against a band.
- DONE: The correction is text only and every number outside it is unmoved.
  `git show --name-only 787595b` = summary.md + NOTES.md only (28 insertions, 12 deletions); no report, trace, chrf or xcomet file touched; `git status --porcelain` clean. Re-verified in the corrected text from the artifacts: 6270.374 / 6283.891 / 13.517 s against `report-run11/12.json` `summary.total_audio_s`, with run 12's own ok-only `duration_s` sum equal to 6270.374 while all 919 rows sum to 6283.891, so "a failed row contributes none of its audio" holds; 2.010 s / 11.507 s against `audio-segments.yaml` indices 213 (2.009999999999998) and 901 (11.50699999999999), whose sum is 13.517 s; and the two sample counts against the error strings in `report-run12.json` (F7).
- FAILED: F1's replacement agrees with the artifacts end to end. The durations, the sample counts and the `finish()`/`process_iter()` split all verify, but the sentence explaining *why* the tail is 160/112 samples asserts a mechanism the code does not implement (F7), and its "finalize decode" clause describes the library version this run used rather than the version whose guard the same paragraph cites (F8).

### Reviewer findings

- **F7 (material, doc).** summary.md:88-89 and NOTES.md:146-148 make the floor-crossing tail "the tail the 0.5 s feed leaves ... (32160 and 184112 samples modulo 8000 give 160 and 112 samples)". The 0.5 s / 8000-sample chunk is the *harness* feed granularity (`test_harness.py:418,627-644`, reached by `player.play(speed=...)` at `scripts/traced_bench.py:290`), not a decode-buffer boundary: `AudioInput` re-chunks PCM to `vac_chunk_size` (0.04 s = 640 samples, `audio_processor.py:136,176-180`), the VAC enqueues only active audio and skips silence (`audio_processor.py:1217-1245`, `_enqueue_active_audio` :471-477), and the library drains `state.buffer` in `chunk_size_samples` blocks (`feed_audio`, mlx_qwen3_asr 0.3.5 `streaming.py:208`) where `chunk_size_samples = mlx_qwen3_asr_chunk_sec * 16000 = 32000` (`config.py:84` default 2.0, passed at `asr_mlx_qwen3.py:192`, and recorded as `effective_config.mlx_qwen3_asr_chunk_sec: 2.0` on every run-12 row). Under that recorded configuration 184112 mod 32000 = 24112, so the paragraph's arithmetic does not reproduce 112 from the digits it cites; 112 is reachable only because the decoder never receives all 184112 samples. The counts themselves are correct and artifact-backed — `report-run12.json` carries the messages verbatim, "160 samples produced 1 STFT frame(s)." (213) and "112 samples produced 0 STFT frame(s)." (901). Fix: take the counts from the error text and call the tail what the code calls it — a leftover fragment of the decode buffer whose length follows where the pause or segment end landed (`asr_mlx_qwen3.py:31-36`) — and drop the modulo-8000 derivation unless the gated sample total is measured.
- **F8 (material, doc).** summary.md:89-90 and NOTES.md:148, "the finalize decode hands exactly that tail to `compute_features`", is true of mlx-qwen3-asr 0.3.5 — `finish_streaming` -> `_decode_chunk_incremental(state.buffer, ...)` (`streaming.py:263`), the version `report-run12.json` records in `backend_versions` — but not of the version HEAD declares, `mlx-qwen3-asr>=0.4.4,<0.5` (`pyproject.toml:71`), where `finish_streaming` folds the tail into the window and re-decodes the accumulated window (`_extend_window` + `_decode_and_update(state.audio_accum)`), which is exactly why the in-repo guard reads `_window_samples()` and why its comment says "keep the decoded window at twice that floor". In-repo corroboration is the pyproject floor plus `asr_mlx_qwen3.py:31-36` and commit d538a8e's message ("0.4.x replaced the finish-time tail refinement pass with a window re-decode that includes the pending tail"); the 0.4.4 sdist was read from `/private/tmp/q3asr044`, a local path, so it is supporting and not load-bearing. The paragraph mixes the two versions in consecutive sentences, and at HEAD "nothing caps the tail itself" does not follow, since the tail is never decoded alone. Fix: name 0.3.5 on the finalize-decode sentence, or restate it as what the run's version did.
- **F9 (polish).** Both files carry the same two sentences; one edit closes F7 and F8 in both.

### Checks run (model-free; no cascade, no VM, no download)

Recomputed with stdlib only from the checked-in artifacts: `report-run11/12.json` (total_audio_s, per-row `duration_s`/`status`, `effective_config`, and the verbatim error strings), `trace-run12.csv` (rows 213/901), `run3-chrf.json`..`run6-chrf.json` (values and per-repeat means), devset `audio-segments.yaml` (919 rows, indices 213/901, totals 6283.891 and 6270.374 with those two removed), `git show 787595b`. Code read at HEAD: `asr_mlx_qwen3.py:31-37,177-215,263-291`, `config.py:84`, `audio_processor.py:136,176-180,471-477,1217-1245`, `test_harness.py:418,627-644`, `scripts/traced_bench.py:284-295`, `pyproject.toml:71`, plus the installed mlx_qwen3_asr 0.3.5 `feed_audio`/`finish_streaming`. `df` 3.7 GiB free against the 1.5 GiB floor; no model load, no download, no install.

### Summary

F2 is fixed cleanly and the correction stayed inside two markdown files, and F1's substance now verifies: the segments are 2.010 s and 11.507 s, the counts 160 and 112 are the error text's own, run 12's `total_audio_s` gap is exactly those two durations, and the `finish()`-guards-`_window_samples()` / `process_iter()`-guards-nothing split is accurate at HEAD. But the F1 replacement introduces one derivation the code contradicts — the modulo-8000 "0.5 s feed" attribution for a buffer that is fed VAD-gated audio and drained at a 32000-sample chunk — and one version conflation, stating a 0.3.5 finalize-decode path beside a 0.4.4-era guard. Validation recommends **REJECTED for those two sentences, not a rerun**: no AC falsifier fires, no measured number changes, and the fix is a rewrite of summary.md:88-90 and NOTES.md:146-148 to cite the error text's counts and name the version. Entity frontmatter and status untouched; no code, artifact or document edited by this stage.
