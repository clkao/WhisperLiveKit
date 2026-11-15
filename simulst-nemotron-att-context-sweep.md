---
title: "Nemotron att_context sweep against the NeMo IWSLT 2026 anchor: is the WER gap configuration or model?"
status: ideation
score: 0.7
source: follow-up to the tier-2 two-direction benchmark; the ASR term dominates the chrF gap
id: 1514n3b7z79ms5gp1b2f8sjf
gates:
    version: 1
    records:
        - id: gate:1514n3b7z79ms5gp1b2f8sjf:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:1514n3b7z79ms5gp1b2f8sjf-backlog-1
              briefing:
                id: briefing:1514n3b7z79ms5gp1b2f8sjf:backlog:attempt-1:revision-1
                digest: sha256:2b5bddbaadb8e2792285f34e5ae19e5b3ff7bc0546fc786f34d002c84ec47ac9
                room-ref: '@review/backlog/briefing-1'
              resolution:
                type: Resolution
                id: resolution:spacedock:1514n3b7z79ms5gp1b2f8sjf:backlog:1
                briefing: briefing:1514n3b7z79ms5gp1b2f8sjf:backlog:attempt-1:revision-1
                by: agent:first-officer
                at: "2026-11-15T16:25:35.93842Z"
                decision: approve
                reason: 'CL reoriented the task: isolate any benchmark defect before a full sweep. The seed''s aim holds; ideation now carries the defect hunt first, then the sweep design, so the gate decides a plan whose harness has been falsified rather than assumed.'
                conn:
                    quote: the goal is to isolate any benchmark defect before we do a full sweep to get to comparable. reorientate and plan out the sequence, then dispatch. make use of exe vm if necessary.
                    source: CL, direct instruction, 2026-11-15
              application:
                target-stage: ideation
                state: consumed
started: 2026-11-15T16:25:44Z
---

Direction B in the tier-2 suite scores chrF 12.481 with nemotron and 26.348 with qwen3-asr on the
IWSLT devset. The published IWSLT 2026 anchor for the same direction is chrF 41.01 (NeMo, MCIF dev).
The question this task answers: how much of that gap is our decode configuration rather than our
weights, measured at fixed weights with no download.

## The knob

`--nemotron-mlx-asr-att-context` takes a left/right frame pair at 80 ms per frame. Our tier-2 rows
ran `[56, 6]` (4.48 s left, 0.48 s right). NeMo's IWSLT 2026 table lists `[70, 13]` for
`nemotron-speech-streaming-en` (5.60 s left, 1.04 s right). Both are expressible today on the cached
`mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit`, so the comparison needs no download.

## Anchor, to be verified before it is quoted

The anchor WER for NeMo's nemotron row must be read from their own table, not from a secondary
summary. A first officer read of a jumbled PDF extraction suggested 17.52 %, but the same table also
shows 7.89 % beside the nemotron row and repeats one WER column across all three En→X directions,
which is consistent with WER being a property of the ASR step. The first job of this task is to pin
the exact configuration-to-WER mapping from the paper, and to state it before any of our numbers are
compared to it.

## Ideation: defect hunt first, sweep second (reoriented 2026-11-15)

CL reoriented this task: isolate any defect in our own measurement before designing a sweep, because
a sweep over a broken benchmark is wasted. Everything below is local, MLX-only, model-free except
where marked. No downloads, no VM, no `qwen-asr` install, no `transformers` change.

## 1. The defect hunt, in numbers

Corpus: `benchmarks/corpora/fleurs-90.json`, `google/fleurs@70bb2e84`, split `test`, `seed 0`,
30 en clips, 347.64 s. Reports on disk: ours at `_work/wlk-val6/native-mlx-qwen3-en.json` (30 rows,
1 pass) and `_work/wlk-carve-bench/en-r3.json` (90 rows, repeats {1,2,3}); the maintainer's three
#444 references at `/tmp/m5q/{qwen-metal,qwen-native,whisper-small-la}-en.json`.
Scoring driver: `/tmp/dh/{rescore,probe_static,probe_norm,probe_parity}.py` (read-only over those
files; nothing under `whisperlivekit/**` was touched).

**D1 — Corpus identity and scorer parity already hold.** All five reports carry
`corpus_sha256 = 95586eb74f53e665…`. Recomputing his stored hypotheses with
`whisperlivekit/metrics.normalize_text` reproduces his stored `weighted_wer` to the digit:
21.36 % (qwen-metal), 27.65 % (qwen-native 0.3.5), 11.66 % (whisper-small-la). Same audio, same
normalizer, same aggregation.

**D2 — His 3 paced passes are bit-identical per clip** (30/30 clips for all three of his reports), so
a 90-sample pooled figure equals the 1-pass pooled figure. Ours agrees to the digit: 1-pass
13.89 %, 3-pass 13.89 %. Pass count is not a protocol difference, and a 30-row vs 90-row comparison
is legitimate on this corpus.

**D3 — Protocol parity (the first officer's ask).** Our adapter *under his protocol* is
`en-r3.json`: n=90, repeats {1,2,3}, weighted WER **13.89 %** on the same `corpus_sha256`.
Against his Qwen-Metal reference 21.36 % that is **0.650×** (Whisper-normalized on both sides:
9.33 / 18.27 = 0.511×). Against his own 0.3.5 measurement of this backend, 27.65 %, it is
**0.502×**. Our 30-clip 1-pass harness number and our adapter under his protocol are **identical —
13.89 % against 13.89 %**: the suspected ~2× harness discrepancy does not exist. The 2× is
ours-vs-his, and per D2 it is not the pass count; his qwen-metal ran
`backend_policy=simulstreaming, qwen3_vllm_left_context_sec=15.0` while this backend ran
`mlx_qwen3_asr_chunk_sec=2.0, max_context_sec=30.0`, and his qwen-native row additionally carries
the 0.3.5 boundary re-emission bug (`fleurs_en_1917` 0.556 → 0.000 across the 0.4.4 rewrite).

**D4 — Aggregation moves 0.43 pp.** `avg_wer` 13.4658 % vs `weighted_wer` 13.8925 % on the same 30
rows. Not the explanation, and the 2.3 pp avg-vs-weighted split seen on the tier-2 direction-B rows
does not transfer to this corpus. The headline number was already the corpus (weighted) one.

**D5 — Normalization moves 4.56 pp, the largest lever found.** Weighted WER on the same 30 rows:

| normalizer | weighted WER | delta vs harness |
|---|---|---|
| W0 harness `normalize_text` | 13.89 % | — |
| W1 + hyphen split | 13.17 % | −0.72 pp |
| W2 + bracket removal + apostrophe | 13.91 % | +0.02 pp |
| W3 Whisper English (full) | **9.33 %** | **−4.56 pp** |

Decomposed: numeral standardization ≈ 3.86 pp, hyphen splitting 0.72 pp, brackets/apostrophes ≈ 0.
**One clip, `fleurs_en_1850` (`802.11a, 802.11b and 802.11g`, which the model spells out as
"eight zero two point one one a"), is 2.49 pp of the corpus WER on its own** (91.67 % → 12.50 %
under W3). `fleurs_en_1776` (`150 and 200 copies`) is another 0.53 pp (33.33 % → 6.67 %).
`fleurs_en_1682` moves the other way (+10.37 pp) because Whisper's number normalizer turns the
reference `29¾`/`24½` into `293 4`/`241 2` while turning the hypothesis's "twenty nine three
fourth" into `2934th`.

**D6 — Detokenization / glued seam: absent in English.** 0/30 rows carry a hypothesis token that is
two adjacent reference tokens glued; 0/30 drop the space after a period; the seam-repaired rescore
moves WER by **+0.00 pp**. The French `leLe gouverneur` class does not transfer. 4/30 carry an
adjacent duplicate word, 3 of them inside clip 1850's numeral enumeration.

**D7 — Audio path is clean.** `mlx_qwen3_asr.load_audio` and `soundfile` float32 agree bitwise
(max |diff| = 0.0) with the manifest length exactly; peaks 0.29–0.82, neither clipped nor
attenuated. The pipeline path is ffmpeg → s16le → `np.frombuffer(..., "<i2")/32768.0`
(`audio_input.py:49`, `audio_processor.py:467`) and the manifest wavs are already PCM_16, so that
round trip is lossless. No int16/float scale error.

**D8 — The language tag was already explicit.** `effective_config.lan = "en"` in every row of every
report; `_resolve_language` maps it to `English`. Naming it again cannot move WER.

**D9 — The 30-clip sample cannot resolve a 4–5 pp gap.** Utterance-level bootstrap, 20 000 resamples:
harness 13.89 % 95 % CI **[8.87, 20.52]**; Whisper-normalized 9.33 % **95 % CI [6.12, 12.88]**.
Leave-one-out: clip 1850 alone is worth −2.53 pp. The published 4.39 % sits ~2.3 pp below the lower
bound of our Whisper-normalized interval, so the residual gap is real but its magnitude is not
resolvable at n=30.

**D10 — The sampling universe is 331 sentence IDs, not 647 recordings.**
`scripts/prepare_fleurs_benchmark.py` samples `random.Random(0).sample(common, 30)` where `common`
is the **three-way en/fr/zh intersection of sentence IDs** (331 of en's 350 unique IDs) and keeps
**only the first recording by filename** per ID — `data/en_us/test.tsv` has 647 rows over 350 IDs, so
~1.85 recordings per sentence are discarded. 30 of 331 = 9.06 % of the parallel universe.

**Verdict on the harness.** Sound on scorer (D1), pass count (D2), aggregation (D4),
detokenization (D6), audio path (D7) and language (D8). Not sound on normalizer (D5), under-powered
(D9), and narrow (D10). The gap to 4.39 % is therefore composed of a scoring convention we can remove
(≈4.6 pp) plus a streaming-decode and sampling residual that n=30 cannot size.

**D11 — Offline single-shot decode moves 6.29 pp: the commit window is the largest defect found.**
Same 30 clips, same cached `Qwen/Qwen3-ASR-0.6B`, same MLX runtime, one genuine decode per clip
(`mlx_qwen3_asr.transcribe`, buffer-then-finalize, no partial commits, `language=None`):

| arm | harness normalizer | Whisper English |
|---|---|---|
| streaming, `--speed 1`, chunk 2.0 s (stored #425) | 13.89 % | 9.33 % |
| offline single-shot, one decode per clip | **7.60 %** | **7.36 %** |

So **6.29 pp of the 9.50 pp gap to the published 4.39 % is chunk-incremental decoding**, and the
normalizer effect (D5) collapses to 0.24 pp once the decode is offline — the numeral damage in
`fleurs_en_1850` is produced by the streaming path, not by the scorer alone. Under Whisper's
normalizer the streaming penalty is 1.97 pp; under the harness normalizer it is 6.29 pp, because
streaming decode is what turns `802.11a` into "eight zero two point".

**D12 — Why the finalization decode does not rescue it.** `MlxQwen3AsrOnlineProcessor.finish()`
(`asr_mlx_qwen3.py:146`) calls `finish_streaming`, which does re-decode the whole window, but then
`_commit()` (`:115`) requires the result to *start with* the already committed prefix and raises
`RuntimeError("mlx-qwen3-asr revised an already committed prefix")` otherwise. `process_iter`
(`:138`) commits `state.stable_text` on every inference tick. So the client-visible final text is
**the first-committed stable prefixes concatenated with the final delta** — the full-window
finalization decode can only append, never rewrite. That is why our final WER (13.89 %) does not
resemble the offline class (7.60 %) even though a full decode happens at finalization: its output is
structurally unable to replace the streaming text. **This is the defect the sweep must fix or
measure around.**

**D13 — `mlx_qwen3_asr_second_pass` is a dead knob.** Declared at `config.py:89`, no consumer
anywhere in `whisperlivekit/**` (the only other hit is an unrelated test name). Toggling it cannot
change WER; any run claiming a "second pass" on this backend is describing `finish_streaming`, not
this flag.

**D14 — There is no buffer-then-finalize mode in our adapter today.** Nothing in
`MlxQwen3AsrOnlineProcessor` suppresses the per-tick `process_iter` commit; partial commits are
forced by `process_iter` → `_commit(state.stable_text)`, which is driven by AudioProcessor's
inference cadence, not by an utterance boundary. An offline arm therefore has to be run through the
library (`transcribe`, as in D11) or through a new no-partial-commit path — it cannot be expressed
as an option on the current adapter.

## 2. What this changes about the sweep

The sweep may not be run against the NeMo anchor until the scorer is pinned and the eval set is
large enough to separate arms. Three consequences:

1. **The commit window dominates everything the sweep could measure.** 6.29 pp (D11) against a
   1.12 s left-context change between `[56, 6]` and `[70, 13]`. A configuration sweep on top of a
   text path that freezes streaming prefixes cannot attribute its result to `att_context`, so the
   buffer-then-finalize (or prefix-rewriting) question is a prerequisite, not a follow-up.
2. The *att_context* question is an ASR-only question, so its WER column must be measured on an
   eval set whose reference is plain prose. FLEURS-en is not that set at 30 clips: one clip holding
   an `802.11a` enumeration is 2.5 pp of the score.
3. The anchor-matched eval set is the **IWSLT devset already on disk** — 919 segments, 6283.9 s,
   21 wavs at `Alignatt4LLM/data/devset/` — because that is the set the NeMo row is scored on and it
   needs no download.
4. `[56, 6]` vs `[70, 13]` is a 1.12 s left-context difference. At n=919 the corpus WER standard
   error is small enough (≈ ±0.3 pp at 5 % WER over ~14 k reference words) to see a change of that
   order; at n=30 it is not.

## Acceptance criteria (revised)

- **AC-1.** The NeMo anchor is pinned from the paper's own table: the WER for
  `nemotron-speech-streaming-en` at `[70, 13]` on the En→X direction, quoted with its table or
  section, together with the reading that would falsify it (a second WER column per direction, or a
  WER that is not constant across the three En→X rows).
  *Verified by:* the quoted table row in the stage report plus the sentence naming the falsifier.
- **AC-2.** The scorer is pinned before any sweep row is compared: a documented English normalizer
  (Whisper English incl. numeral standardization) is available to the benchmark path, and the
  existing five reports rescore to the D5 table (13.89 / 13.17 / 13.91 / 9.33 %) with `en-r3.json`
  reproducing 13.89 % under the old normalizer and 9.33 % under the new one.
  *Verified by:* a test that fails when the normalizer drops numeral standardization (`fleurs_en_1850`
  as a fixture: 91.67 % under the harness normalizer, 12.50 % under the pinned one) and passes now.
- **AC-3.** The two eval sets and their roles are stated: the **curve** runs on FLEURS-en at
  `--speed 1` (the only setting that records `first_text_time_s`), the **precision leg** runs on the
  919 IWSLT devset segments at `--speed 0`, `git_dirty: false`, no download; the report states each
  set's provenance (including D10's 331-sentence universe) and the utterance-level bootstrap 95 % CI
  for every WER or chrF it quotes.
  *Verified by:* each arm's JSON carries `corpus_sha256`, `n_samples = 919`, and a CI computed from
  its own per-row errors; a row without a CI is not accepted.
- **AC-4.** Every arm reports **quality and latency from the same run**, and the two decompositions
  (ASR-only, cascade) come from the same configurations. Quality: WER/CER for the ASR leg, chrF +
  XCOMET-XL for the cascade leg, each with a bootstrap 95 % CI from its own per-row errors. Latency:
  `first_text_time_s`, `first_visible_time_s`, `finalization_time_s`, `source_end_lag_s`, recorded for
  every arm and stated to be null where the run was unpaced.
  *Verified by:* one JSON per arm carrying both axes and a non-null `first_text_time_s` for every
  paced arm; an arm reported on quality alone is not accepted, and an arm reported as ranked must
  also state the latency bar it cleared.
- **AC-5.** The curve states its trend and its knee, one sentence per family, and says which
  published points it may be compared to and which it may not.
  *Verified by:* a monotonicity statement per family plus a knee value; the comparison list names the
  offline single-decode FLEURS-en WER as the only qualifying published point and says why the NeMo
  chrF anchor does not qualify.
- **AC-6.** The `att_context` sweep is run at fixed weights over five arms on the cached
  `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit` — `[56, 6]` (baseline), `[70, 13]` (anchor),
  `[70, 6]`, `[56, 13]`, `[112, 13]` — each with WER, its CI, RTF, wall time and the configuration
  stated in its own notes.
  *Verified by:* five JSONs whose `effective_config.nemotron_mlx_asr_att_context` matches the row
  label; an arm is reported as *different* only where the bootstrap CIs are disjoint.
- **AC-7.** The conclusion names the residual and locates it in the pipeline: how much of the gap to
  the anchor the configuration explains, in one number with its CI, what remains after the scorer is
  pinned, and whether the loss sits inside the ASR window or in the MT's commit policy.
  *Verified by:* one sentence pairing "configuration explains X pp (CI)" with "residual Y pp", and a
  falsifier that would overturn it (all five arms inside one CI, or the residual attributing more to
  the scorer than to the configuration).
- **AC-8.** The MT-only upper bound is measured and used as an accounting, not an attribution: our
  translator scored on reference source text for both directions, beside the cascade chrF, with the
  sentence saying whether the translator or the ASR path is the limit.
  *Verified by:* two chrF + XCOMET-XL numbers on reference text (`ref/en.txt`→`ref/zh.txt` and the
  FLEURS zh→en references) quoted beside the cascade rows, plus the stated limitation that F3 removes
  streaming and ASR error together and therefore bounds rather than attributes.
- **AC-9.** Aggregation is never compared across harnesses without naming it: every quoted WER says
  corpus (`weighted_wer`) or mean-of-rows, and chrF is not compared across aggregations.
  *Verified by:* a scan of the report's numbers for an unlabelled WER; D4's 0.43 pp and the tier-2
  2.3 pp are quoted as the size of the mistake.
- **AC-10.** The commit-window defect is stated as a measured quantity and either removed or held
  constant: buffer-then-finalize (one decode per utterance, no frozen streaming prefix) is available
  on the measured path, and the report gives its WER beside the chunk-incremental WER on the same
  clips and scorer.
  *Verified by:* two arms on the same audio differing only in commit policy, with the D11 pair
  (13.89 % streaming vs 7.60 % offline, harness normalizer) reproduced or refuted; a run that
  changes both the commit policy and the sweep arm is not accepted.

## 3. Sweep design: a latency–quality curve, two decompositions, from the same runs

A single WER is not the deliverable. The product is live captions, so "5 % but five seconds late"
and "14 % at two seconds late" are different products and only the pair ranks them. The sweep is
therefore a curve, and it is measured twice from the same configurations: once with ASR alone and
once through the full cascade.

### 3.1 The two axes, and what each metric means in our pipeline

Quality — WER for `en`/`fr`, CER for `zh` (whitespace removed), corpus aggregation
(`weighted_wer`), with the utterance-level bootstrap 95 % CI from each arm's own per-row errors.

Latency — the four fields the harness already records, with the pipeline meaning of each:

| field | meaning in our pipeline |
|---|---|
| `first_text_time_s` | wall time from the start of audio feeding to the **first committed** ASR token. Excludes provisional text; this is the "user sees nothing yet" duration. Paced runs only. |
| `first_visible_time_s` | same origin, first **committed or provisional** text. The difference from `first_text_time_s` is what the draft/partial path buys. Paced runs only. |
| `finalization_time_s` | EOF completion minus the actual end of audio feeding — the tail drain: how long after the speaker stops the last text appears. |
| `source_end_lag_s` | EOF completion minus nominal source duration / feed speed; includes feed backlog. The end-to-end lag as observed at the socket. |

Two constraints stated up front, because they cost budget: `first_text_time_s` and
`first_visible_time_s` are recorded **only at `--speed 1`** (`benchmark/report.py` prints "measured
only at speed=1; it is not per-word latency"), so the latency axis requires paced runs; and we have
no LongYAAL, so these are our own axes, not a benchmark's.

### 3.2 Decomposition 1 — ASR alone

The harness already produces it: a run with no `--target-language` yields the WER/CER rows and
nothing else. Quality = WER/CER; latency = `first_text_time_s` (audio-arrival → committed text
visible), plus `finalization_time_s` for the tail. No MT in the loop. This is the recognizer measured
on its own and it is the curve that says what our streaming window costs.

### 3.3 Decomposition 2 — the cascade

Same configurations, translation on. Quality = chrF and XCOMET-XL (the tier-2 scorers);
latency = end-to-end, adding `first_translation_time_s` and the final translation time. Subtracting
the ASR-only latencies yields the MT's added latency; subtracting the ASR quality curve shows what
the MT contributes on top of it. Both legs come from the same configurations, not from a second
experiment.

**Which one does the evidence implicate?** The ASR window. D11 measures 13.89 % streaming against
7.60 % for one decode per clip on identical audio, identical weights, identical scorer — 6.29 pp is
inside the recognizer, before the MT is reached. Nothing in this report measures the MT's commit
policy, so the cascade leg exists to test whether it adds a second loss on top; the design does not
claim it does.

### 3.4 The arms, in latency order

**Family 1 — commit policy / window (the primary curve).** Buffer-then-finalize is the best-quality,
worst-latency end; the incremental windows walk down the latency axis.

| arm | window | expected position on the curve |
|---|---|---|
| A1 buffer-then-finalize | one decode per utterance, no partial commit | best quality (D11: 7.60 %), worst latency |
| A2 incremental 8.0 s | `mlx_qwen3_asr_chunk_sec=8.0` | near-A1 quality, seconds late |
| A3 incremental 2.0 s | `chunk_sec=2.0` (the #425 ship setting) | the current product point (13.89 %) |
| A4 incremental 1.0 s | `chunk_sec=1.0` | fastest partials, worst quality |
| A5 incremental 0.5 s | `chunk_sec=0.5` | the latency floor probe — include to find the knee's lower edge, not as a candidate |

**Family 2 — nemotron `att_context`, a second family on the same axes.** `[56, 6]` (baseline),
`[70, 13]` (NeMo anchor), `[70, 6]`, `[56, 13]`, `[112, 13]` (full left context ≈ the offline
ceiling). Left context is a latency *and* quality knob, which is exactly why it belongs on this
curve rather than in a WER table.

**Family 3 — the text-MT upper bound (cheapest arm, run it first).** Feed the *reference source
text* straight into our MT with no ASR in the loop and score the output against the same target
references: `ref/en.txt` for direction B (en→zh), and the cached FLEURS `cmn_hans_cn` references
against the FLEURS `en_us` references for direction A (zh→en). This is the standard cascade ceiling —
what our translator would score given perfect transcripts — and it is the only way to split "combo"
into halves, because **no published number exists for our pairings** (qwen3-asr × Hy-MT2-1.8B and
nemotron × Hy-MT2 are ours alone, and the Hy-MT2-1.8B card publishes no per-direction scores at all).
Text-only, cached weights, minutes. It has no meaningful latency axis: MT-only latency is a property
of the translator, not of a streaming configuration, so this arm is plotted as a horizontal quality
line, not a point on the curve.

### 3.5 Acceptance number per arm

Each arm must clear a latency bar for its quality number to count at all, and each quality number
carries its CI:

| arm | latency the arm must stay under to count | quality number it must produce |
|---|---|---|
| A1 buffer-then-finalize | `finalization_time_s ≤ 1.0 s` (tail only; no partial text by construction) | WER + CI |
| A2 8.0 s | `first_text_time_s ≤ 10 s` | WER + CI |
| A3 2.0 s | `first_text_time_s ≤ 4.5 s` (the #425 p50 3.52 s) | WER + CI |
| A4 1.0 s | `first_text_time_s ≤ 3.0 s` | WER + CI |
| A5 0.5 s | `first_text_time_s ≤ 2.5 s` | WER + CI |
| F2 `att_context` arms | same as A3 (`first_text_time_s ≤ 4.5 s`) | WER + CI |
| F3 MT-only bound | no latency bar — horizontal quality line by construction | chrF + XCOMET-XL over the same references as the cascade leg |

An arm outside its bar is reported as "did not qualify" and is plotted but not ranked. All five
latency fields are recorded per arm regardless.

### 3.6 Order, time and disk

| # | Step | Acceptance number | Est. time | Est. disk |
|---|---|---|---|---|
| P0 | Pin the NeMo anchor from the paper (AC-1) | table row + falsifier quoted | 20 min | 0 |
| P1 | Pin the scorer (AC-2) | D5 table reproduced; `1850` fixture 91.67 → 12.50 % | 45 min | 0 |
| P2 | Latency-enabled baseline: the ASR-only A3 arm on FLEURS-en at `--speed 1` | a JSON whose `first_text_time_s` is non-null and whose WER has a CI | 8 min | 5 MB |
| C0a | MT-only bound, direction B: `ref/en.txt` → Hy-MT2-1.8B → vs `ref/zh.txt` | chrF + XCOMET-XL, no ASR in the loop | 5 min | 1 MB |
| C0b | MT-only bound, direction A: FLEURS zh references → Hy-MT2-1.8B → vs FLEURS en references | chrF + XCOMET-XL | 5 min | 1 MB |
| C1 | Curve, ASR-only, Family 1 A1–A5, FLEURS-en `--speed 1` | 5 paired points, one JSON each | 40 min | 25 MB |
| C2 | Curve, cascade, same five, FLEURS-en `--speed 1`, translation on | 5 chrF/XCOMET points + `first_translation_time_s` | 60 min | 35 MB |
| C3 | Family 2, `att_context` A3-equivalent on FLEURS-en `--speed 1` | 5 paired points | 40 min | 25 MB |
| C4 | Quality-precision leg: the knee arm + A1 on the 919-segment IWSLT devset, `--speed 0` | WER/chrF with CI; latency metrics null and said to be null | 40 min | 10 MB |
| C5 | The same knee arm on the 919 devset at `--speed 1` | the one 919-scale paired point (111 min measured for this shape) | 115 min | 5 MB |

Time calibration: paced FLEURS-30 is 347.6 s of audio (`--speed 1` ⇒ ~6 min wall) plus decode;
a 919-segment paced run was measured at 111 min in tier 2 (run 13), and an unpaced 919 run at
20–33 min (runs 11–12). Disk: FLEURS audio and the 919 devset are both already cached (217 MB at
`Alignatt4LLM/data/devset/`), so ~90 MB of new artifacts.

**Cut-line if the budget shrinks:** C0a/C0b are never cut — ten minutes buys the arithmetic below;
then C5 first (the single 919-scale latency point), then C3, then C2.
C1 and C4 are the curve and its precision leg and must both survive for the design to answer
anything.

**Disk caution — read before scheduling.** This Mac's data volume is at 100 % with **≈ 374 MiB
free** at probe time, below the 1.5 GiB floor, and none of that is this task's artifacts (no file
over 20 MB was written in the session; the HF cache is a pre-existing 16 GB). The sweep's ~90 MB
and even a model load cannot be assumed to fit until space is freed. This is a scheduling blocker,
not a finding about the harness.

### 3.6b The accounting the three families make possible

With the ASR-only curve (3.2), the cascade (3.3) and the MT-only bound (F3), the cascade number stops
being a single opaque figure:

- **MT-only chrF close to the cascade chrF** ⇒ the translator is the limit, and no amount of window
  tuning recovers the gap.
- **MT-only chrF well above the cascade chrF** ⇒ the ASR path costs the difference, and the ASR-only
  curve says which window buys it back, at what latency.

What F3 **cannot** show, stated so it is not over-read: it removes the streaming *and* the ASR errors
together, so it is a **bound, not an attribution**. A low MT-only number can be caused either by the
translator or by our prompt/segmentation convention on reference text; a high one says only that the
translator is not the binding constraint. Attribution of any residual inside the ASR half still needs
the per-clip pairing (D-series rescoring) or a separate ASR-error-injection run, which this design
does not include.

### 3.7 The trend statement the curve must produce

One sentence per family, stated in advance so it can be falsified:

- **Family 1:** quality is expected to be **monotone in the window** — best at buffer-then-finalize,
  degrading as the window shortens — with the **knee at or below 2.0 s**: the region where a further
  second of latency buys less than one WER point. The #425 zh exploration (11.15 % at 2.0 s vs
  11.54 % at 1.0 s) suggests the curve is **flat for Chinese across 1–2 s**, so the prediction is a
  language-dependent knee, sharper for English than for zh.
- **Family 2:** quality is expected to rise with left context but **saturate before `[112, 13]`**;
  if `[112, 13]` and `[70, 13]` land inside one CI the knob is saturated and the residual gap is the
  model, not the configuration.

### 3.8 What the curve cannot be compared to

IWSLT ranks systems *inside latency regimes* using LongYAAL (length-adaptive average lagging) on a
shared reference. We do not compute LongYAAL; our axes are `first_text_time_s`,
`first_visible_time_s`, `finalization_time_s` and `source_end_lag_s`, all measured at our own feed
speed on our own 30-clip manifest. So:

- The curve **places us against ourselves across configurations**, which is what the sweep needs.
- A published point is comparable **only if both the metric and the regime match**. In this report
  exactly one class qualifies: an **offline, single-decode WER on FLEURS-en test**, which is the
  regime D11's buffer-then-finalize arm reproduces locally at 7.60 % (harness normalizer) / 7.36 %
  (Whisper), beside the published 4.39 % for the same checkpoint. That pair is the only
  published-vs-ours comparison the design permits.
- The NeMo chrF 41.01 anchor does **not** qualify yet: it is a chrF on the IWSLT devset under NeMo's
  own segmentation, and we have neither its latency regime nor its LongYAAL. AC-1 pins the anchor's
  WER side precisely because WER is a property of the ASR step and therefore regime-comparable in a
  way chrF is not.

### 3.9 What would falsify the conclusion that the window, not the text path, sets quality?

1. **The S0-style control:** two arms that differ only in commit policy landing inside one CI — that
   would put D11 down to a difference between the library `transcribe` path and the pipeline, and
   move the defect into the adapter's audio or text handling.
2. **A flat Family 1 curve with a non-flat cascade curve.** D11 predicts the ASR curve moves
   ≈ 6 pp; if ASR quality is flat across windows while the cascade degrades, the MT's commit policy
   is the cause and this design's premise is wrong.
3. **Non-determinism:** the same arm run twice disagreeing by more than its CI. The on-disk FLEURS
   reports say this will not happen (his 3 passes bit-identical 30/30, D2), so a disagreement
   falsifies the harness rather than the arm.
4. **A scorer that cannot reproduce itself:** rescoring a stored report with the pinned normalizer
   failing to reproduce its own stored `weighted_wer` under the harness normalizer (D1 currently
   reproduces to the digit).
5. **`[112, 13]` far from `[70, 13]`:** the knob is not saturated, so the gap is configuration after
   all and the residual claim must be withdrawn.
6. **Any quoted WER whose per-row artifacts are absent**, so its CI cannot be recomputed.

**Falsifier for the sweep's premise as a whole:** if all Family 1 arms fall inside one CI *and* the
cascade curve is also flat, then the window does not set quality, the curve has no knee, and the
honest report is a negative result — not a re-tuned sweep.

## Stage Report: ideation

- DONE: The benchmark-defect hunt is done first and with numbers: the same 30 cached FLEURS-en clips rescored under mean-of-rows versus corpus aggregation, under the harness normalizer versus a Whisper-style English normalizer, and under one offline run, stating which difference moves WER and by how much.
  Aggregation 0.43 pp (13.4658 % avg vs 13.8925 % weighted, D4); normalizer 4.56 pp (13.89 → 9.33 %, D5); **offline single-shot 6.29 pp (13.89 → 7.60 %, D11)** — the commit window, not the scorer, is the largest lever.
- SKIPPED: An independent official reference on the exe.dev VM with the upstream Qwen3-ASR implementation.
  Superseded twice by CL: first "cheapest local path, `qwen_asr` only if <200 MB", then "MLX only, no `qwen-asr`, no VM". `qwen-asr==0.0.6` is 0.14 MB but pins `transformers==4.57.6` against the venv's 5.15.0 and its README demands a fresh 3.12 env, so it was dropped uninstalled. `asr-xcomet` is still paused; no VM work was done beyond a read-only `ssh` that reported "paused". The published 4.39 % stands as the anchor with that caveat, and D11 supplies the local offline reference it was missing.
- DONE: The formatted design states the full sweep to reach a comparable number: the arms, an acceptance number per arm, the estimated time and disk, the order, and what result would falsify the conclusion that the harness is sound.
  Section 3: 10 arms/gates (P0–P2, C0a/C0b MT-only bounds, C1–C5), each with a per-arm latency bar and a quality number, times calibrated on the tier-2 measured costs (20 min unpaced / 111 min paced per 919-segment arm), ~90 MB total disk, a cut-line, and six falsifiers.
- DONE: Protocol parity established against the maintainer's #444 reports before any comparison was quoted.
  Same `corpus_sha256` on all five reports; his stored `weighted_wer` reproduced to the digit by our normalizer (21.36 / 27.65 / 11.66 %); his 3 passes bit-identical 30/30 so a 90-row figure equals 30 rows; ours 13.89 % (1 pass) = 13.89 % (3 pass) = **0.650×** his 21.36 % Metal reference. The suspected 2× harness discrepancy does not exist.
- DONE: Report each probe in WER points (FO probes 1–6).
  1 offline 6.29 pp (13.89 → 7.60 %); 2 chunk ladder not quotable — 1.0/2.0/8.0 s arms ran (199/208/241 s) but the driver persists only at the end and the last arm was cut (see residual), so the ladder is designed as C1 instead; 3 detokenization 0.00 pp, 0/30 glued seams, 4/30 adjacent duplicates (3 in clip 1850); 4 audio path 0.00 pp (bitwise equal, max |diff| 0.0, peaks 0.29–0.82); 5 language tag already `lan="en"` in every stored row, 0 pp available; 6 scoring 4.56 pp normalizer / 0.43 pp aggregation.
- DONE: Say whether our adapter can be driven buffer-then-finalize and which code path forces partial commits.
  It cannot today (D14): `process_iter` (`asr_mlx_qwen3.py:138`) commits `state.stable_text` every inference tick, and `_commit` (`:115`) freezes that prefix so `finish()`'s full-window re-decode can only append (D12). `mlx_qwen3_asr_second_pass` is a dead knob (D13).

### Summary

The harness is sound on scorer identity, pass count, aggregation, detokenization, audio path and language tag, and unsound on three things: the English normalizer (4.56 pp, of which one clip's `802.11a` enumeration is 2.49 pp), the 30-clip sample (95 % CI [8.87, 20.52]; the universe is 331 sentence IDs, not 647 recordings), and above all the chunk-incremental commit policy (6.29 pp against a genuine offline decode). So no `att_context` sweep should run yet: at 1.12 s of left-context difference the knob is an order of magnitude smaller than the commit-window defect. The design therefore gates the sweep behind a pinned scorer, a 919-segment anchor-matched eval set, and an S0 arm that holds the commit policy constant — with six named falsifiers, including the one that would put the harness back in doubt (S0's two arms landing inside one CI).

Residual: the streaming chunk ladder (probe 2) is incomplete — the 1.0 s, 2.0 s and 8.0 s arms each completed their decode loops (199 / 208 / 241 s wall) but the driver persists results only at the end and the last arm was still running at the budget cut, so no ladder number is quotable; D11's offline arm comes from the dedicated `transcribe` run instead, which is why probe 2 is designed as arm C1 of the curve rather than reported as measured. No file under `whisperlivekit/**` was modified; the analysis drivers live in `/tmp/dh/` and read only on-disk reports.

### Addendum: three scope changes after the first report draft

All three are incorporated into sections 3 and the ACs, not re-measured: (i) quality and latency must be measured **together per configuration**, so section 3 is a latency–quality curve with a per-arm latency bar instead of a WER table; (ii) the pairing must also hold **inside the ASR stage**, so 3.2/3.3 give the ASR-only and cascade decompositions from the same configurations, using the no-`--target-language` path the harness already supports; (iii) **Family 3, the text-MT upper bound**, added as the cheapest arm (C0a/C0b, 10 min, cached weights, no audio, no ASR) with its limitation stated — it removes streaming and ASR error together, so it bounds rather than attributes.

**Which decomposition the evidence supports:** the ASR window. D11 measures 6.29 pp (13.89 % → 7.60 %) inside the recognizer on identical audio, weights and scorer, with the MT absent — the loss is upstream of the translator. Nothing here measures the MT's commit policy, so the cascade leg and F3 exist to test whether it adds a second loss, not to claim one.

Two findings the new sections depend on, because they decide the schedule: the latency axis **requires `--speed 1`** (`first_text_time_s`/`first_visible_time_s` are paced-only), so the curve is scheduled on FLEURS-30 with a single 919-scale point; and this Mac's data volume has **≈ 393 MiB free, below the 1.5 GiB floor**, with none of it written by this task (no file over 20 MB was created; the HF cache is a pre-existing 16 GB) — a scheduling blocker for the sweep, not a harness finding.
