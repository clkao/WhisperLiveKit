---
title: "Tier 2: two labelled directions — product zh→en on FLEURS, comparison en→zh on the IWSLT devset, scored by XCOMET-XL"
status: implementation
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
