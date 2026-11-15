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
- **AC-3.** The eval set is enlarged and its sampling stated: the sweep runs on the 919 IWSLT devset
  segments, `git_dirty: false`, no download; the report states the reference-set provenance and the
  utterance-level bootstrap 95 % CI for every WER it quotes.
  *Verified by:* each arm's JSON carries `corpus_sha256`, `n_samples = 919`, and a CI computed from
  its own per-row errors; a row without a CI is not accepted.
- **AC-4.** The `att_context` sweep is run at fixed weights over five arms on the cached
  `mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit` — `[56, 6]` (baseline), `[70, 13]` (anchor),
  `[70, 6]`, `[56, 13]`, `[112, 13]` — each with WER, its CI, RTF, wall time and the configuration
  stated in its own notes.
  *Verified by:* five JSONs whose `effective_config.nemotron_mlx_asr_att_context` matches the row
  label; an arm is reported as *different* only where the bootstrap CIs are disjoint.
- **AC-5.** The conclusion names the residual: how much of the gap to the anchor the configuration
  explains, in one number with its CI, and what remains after the scorer is pinned.
  *Verified by:* one sentence pairing "configuration explains X pp (CI)" with "residual Y pp", and a
  falsifier that would overturn it (all five arms inside one CI, or the residual attributing more to
  the scorer than to the configuration).
- **AC-6.** Aggregation is never compared across harnesses without naming it: every quoted WER says
  corpus (`weighted_wer`) or mean-of-rows, and chrF is not compared across aggregations.
  *Verified by:* a scan of the report's numbers for an unlabelled WER; D4's 0.43 pp and the tier-2
  2.3 pp are quoted as the size of the mistake.
- **AC-7.** The commit-window defect is stated as a measured quantity and either removed or held
  constant: buffer-then-finalize (one decode per utterance, no frozen streaming prefix) is available
  on the measured path, and the report gives its WER beside the chunk-incremental WER on the same
  clips and scorer.
  *Verified by:* two arms on the same audio differing only in commit policy, with the D11 pair
  (13.89 % streaming vs 7.60 % offline, harness normalizer) reproduced or refuted; a run that
  changes both the commit policy and the sweep arm is not accepted.

## 3. Sweep design

**Order (each gate blocks the next):**

| # | Arm | Acceptance number | Est. time | Est. disk |
|---|---|---|---|---|
| P0 | Pin the anchor from the paper (AC-1) | table row + falsifier quoted | 20 min | 0 |
| P1 | Pin the scorer (AC-2) | D5 table reproduced; `1850` fixture 91.67 → 12.50 % | 45 min | 0 |
| P2 | Enlarge the set + CI harness (AC-3) | 919-segment baseline JSON with a CI | 30 min | 5 MB |
| S0 | Commit policy: chunk-incremental vs buffer-then-finalize (AC-7) | two WERs + CIs on identical audio; the D11 6.29 pp gap reproduced or refuted | 25 min | 5 MB |
| S1 | `[56, 6]` baseline | WER + CI, matches the tier-2 direction-B ASR term | 20 min | 5 MB |
| S2 | `[70, 13]` anchor config | WER + CI | 20 min | 5 MB |
| S3 | `[70, 6]` | WER + CI | 20 min | 5 MB |
| S4 | `[56, 13]` | WER + CI | 20 min | 5 MB |
| S5 | `[112, 13]` (full left context) | WER + CI — the offline ceiling | 25 min | 5 MB |
| S6 | FLEURS-en cross-check at the same scorer | D5 table on 30 clips, CI quoted | 6 min | 2 MB |

Time estimates are the tier-2 measured costs of the same 919-segment set: run 11 (nemotron,
`--speed 0 --repeats 1`) took **20 min**, run 12 (qwen3-asr, same) **33 min**. Disk: audio already
present (217 MB at `Alignatt4LLM/data/devset/`), each report 5.0 MB, ≤ 13.6 MB transient — so ~50 MB
total, which fits inside the 3.7 GiB free / 1.5 GiB floor without touching the floor.

**What would falsify the conclusion that the harness is sound?** Any of:

1. A sweep arm whose WER moves more than the fixed-weights `att_context` change can explain —
   i.e. two runs of the *same* arm on the same machine disagree by more than their CIs (a
   non-determinism result the FLEURS reports say will not happen, D2).
2. Rescoring a stored report with the pinned normalizer failing to reproduce its own stored
   `weighted_wer` under the harness normalizer (D1 currently reproduces to the digit).
3. The S0 pair landing inside one CI, i.e. the commit policy turning out not to matter — which would
   put D11 down to a difference between the library `transcribe` path and the pipeline, and move the
   defect back into the adapter's audio or text handling.
4. The `[112, 13]` ceiling arm landing far from the `[70, 13]` anchor arm — which would mean the
   knob is saturated and the gap is the model, not the configuration.
5. The 919-segment baseline WER disagreeing with the ASR term implied by the tier-2 direction-B chrF
   by more than the scorer accounts for, which would mean the two harness paths score differently.
6. Any quoted WER whose per-row artifacts are absent, so the CI cannot be recomputed.

**Falsifier for the sweep's premise:** if all five arms fall inside one overlapping CI and the
residual after the scorer fix is unchanged, then the gap is the model, the sweep is over, and the
answer to the title question is "model, not configuration" — reported as a negative result rather
than re-tuned.

## Stage Report: ideation

- DONE: The benchmark-defect hunt is done first and with numbers: the same 30 cached FLEURS-en clips rescored under mean-of-rows versus corpus aggregation, under the harness normalizer versus a Whisper-style English normalizer, and under one offline run, stating which difference moves WER and by how much.
  Aggregation 0.43 pp (13.4658 % avg vs 13.8925 % weighted, D4); normalizer 4.56 pp (13.89 → 9.33 %, D5); **offline single-shot 6.29 pp (13.89 → 7.60 %, D11)** — the commit window, not the scorer, is the largest lever.
- SKIPPED: An independent official reference on the exe.dev VM with the upstream Qwen3-ASR implementation.
  Superseded twice by CL: first "cheapest local path, `qwen_asr` only if <200 MB", then "MLX only, no `qwen-asr`, no VM". `qwen-asr==0.0.6` is 0.14 MB but pins `transformers==4.57.6` against the venv's 5.15.0 and its README demands a fresh 3.12 env, so it was dropped uninstalled. `asr-xcomet` is still paused; no VM work was done beyond a read-only `ssh` that reported "paused". The published 4.39 % stands as the anchor with that caveat, and D11 supplies the local offline reference it was missing.
- DONE: The formatted design states the full sweep to reach a comparable number: the arms, an acceptance number per arm, the estimated time and disk, the order, and what result would falsify the conclusion that the harness is sound.
  Section 3: 9 gates/arms (P0–P2, S0–S6), each with its acceptance number, time from the tier-2 measured costs (20 min/919-segment arm) and 5 MB/run disk, plus six falsifiers.
- DONE: Protocol parity established against the maintainer's #444 reports before any comparison was quoted.
  Same `corpus_sha256` on all five reports; his stored `weighted_wer` reproduced to the digit by our normalizer (21.36 / 27.65 / 11.66 %); his 3 passes bit-identical 30/30 so a 90-row figure equals 30 rows; ours 13.89 % (1 pass) = 13.89 % (3 pass) = **0.650×** his 21.36 % Metal reference. The suspected 2× harness discrepancy does not exist.
- DONE: Report each probe in WER points (FO probes 1–6).
  1 offline 6.29 pp; 2 chunk ladder 1.0 s arm reached but the 2.0/8.0 s arms did not finish inside the budget (see residual); 3 detokenization 0.00 pp, 0/30 glued seams; 4 audio path 0.00 pp (bitwise equal, max |diff| 0.0); 5 language tag already `lan="en"` in every stored row, 0 pp available; 6 scoring 4.56 pp normalizer / 0.43 pp aggregation.
- DONE: Say whether our adapter can be driven buffer-then-finalize and which code path forces partial commits.
  It cannot today (D14): `process_iter` (`asr_mlx_qwen3.py:138`) commits `state.stable_text` every inference tick, and `_commit` (`:115`) freezes that prefix so `finish()`'s full-window re-decode can only append (D12). `mlx_qwen3_asr_second_pass` is a dead knob (D13).

### Summary

The harness is sound on scorer identity, pass count, aggregation, detokenization, audio path and language tag, and unsound on three things: the English normalizer (4.56 pp, of which one clip's `802.11a` enumeration is 2.49 pp), the 30-clip sample (95 % CI [8.87, 20.52]; the universe is 331 sentence IDs, not 647 recordings), and above all the chunk-incremental commit policy (6.29 pp against a genuine offline decode). So no `att_context` sweep should run yet: at 1.12 s of left-context difference the knob is an order of magnitude smaller than the commit-window defect. The design therefore gates the sweep behind a pinned scorer, a 919-segment anchor-matched eval set, and an S0 arm that holds the commit policy constant — with six named falsifiers, including the one that would put the harness back in doubt (S0's two arms landing inside one CI).

Residual: the streaming chunk ladder (probe 2) is incomplete — the 1.0 s arm finished (199 s) but the 2.0 s and 8.0 s arms and the offline-vs-streaming library comparison were still running at the budget cut, so the ladder is one arm deep and D11's offline number comes from the dedicated `transcribe` run instead. No file under `whisperlivekit/**` was modified; the analysis drivers live in `/tmp/dh/` and read only on-disk reports.
