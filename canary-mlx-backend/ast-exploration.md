# Canary-AST exploration: direct speech translation vs the cascade (ASR + MT)

Date: 2026-09-11. Exploration task (captain question): canary-1B-v2
translates speech directly (AST, 25 European languages → en). How does that
compare with our cascade (ASR commits → AlignAtt commit policy → MT layer)
for simultaneous captioning?

## Setup

- Model: `Mediform/canary-1b-v2-mlx-q8` (8-bit MLX checkpoint) via
  mlx-audio 0.4.8 (`mlx_audio.stt.load`). Loaded from HF directly; the
  loader also claims NeMo-native layout support, but the extracted NeMo
  `.nemo` weights lack the MLX-style `config.json` the loader requires
  (`FileNotFoundError: Config not found`) — community MLX checkpoints are
  the practical path.
- Clips: 3 French FLEURS test clips (6.4s / 10.9s / 21.8s), pinned to the
  corpus revision, with the manifest's French references.
- Arms:
  - **AST full-utterance**: `generate(source_lang="fr", target_lang="en")`
    on the whole clip.
  - **AST chunked**: 5-second windows, one generate per window,
    concatenated (pseudo-streaming: measures "first text after the first
    window").
  - **Cascade (serial)**: canary ASR `fr→fr` transcript → Hy-MT2-1.8B-8bit
    `fr→en` via `MlxLlmTranslation._translate_text` (translate-on-finalize,
    no simul policy — our fr→en direction has no calibrated heads).

## Results

### Latency (seconds; after the clip's audio is fully available)

| clip (dur) | AST full | AST chunked: first text | AST chunked: total | cascade: ASR | cascade: MT | cascade total |
|---|---:|---:|---:|---:|---:|---:|
| 6.4s  | 0.94 | 0.24 | 0.31 | 0.29 | 0.90 | 1.19 |
| 10.9s | 1.08 | 0.60 | 1.05 | 0.93 | 1.19 | 2.12 |
| 21.8s | 2.32 | 0.21 | 1.68 | 3.71 | 5.12 | 8.83 |

Canary RTF ≈ 0.17 (ASR and AST both). Hy-MT2 8-bit MT on a 1-3 sentence
transcript: ~1-5s.

### Quality (vs the FLEURS French reference)

| clip | AST full | AST chunked | cascade (canary ASR → Hy-MT2) |
|---|---|---|---|
| 1 (6.4s) | WRONG: "thinner than the foot... farther from the mountains" (misheard) | correct: "thinner at sea level and thicker under the continent" | correct + idiomatic: "thinner near the seas, but thicker beneath the continents" |
| 2 (10.9s) | drift: "cavalry horses have a slightly straight... heel and sole" | broken franglais: "Premiere hand, the most cavaliers wear bottles of equipment" | transcript BETTER than the manifest reference (captured the truncated tail); MT: "most riders wear equestrian boots with a heel and a smooth, relatively narrow sole" |
| 3 (21.8s) | widest coverage (translated content beyond the truncated reference) but with drift; garbled phrase structure mid-way | garbled: dropped clauses, "By reacting actively to online content" chain broken | transcript complete and accurate; MT fluent and faithful end to end |

**Cascade wins quality 3/3.** The canary ASR transcript was reference-grade
on all three clips (on clip 2 it captured words the FLEURS reference
truncated). The MT layer's output was fluent and faithful. The AST arm
degraded on 2 of 3 clips (mishearing at 6.4s; hallucination/drift on the
10.9s and 21.8s clips), and the chunked AST degraded badly on anything
longer than one sentence — window boundaries cut the acoustic context the
decoder needs.

### Latency structure (the decisive axis)

- The mlx-audio canary `generate()` has `stream: Not supported yet` — AST
  is structurally an offline, utterance-level operation. No partial output
  exists before the encoder has the whole utterance and the decoder
  finishes.
- End-of-utterance latency FAVORS AST on long clips (2.3s vs the serial
  cascade's 8.8s on the 21.8s clip) — one autoregressive decode beats
  ASR + MT serially.
- But during-speech visibility favors the cascade by construction: the
  commit policy releases drafts while the speaker is still talking. In this
  experiment the cascade ran serial (no calibration for fr→en), and even
  then the cascade's transcript exists before the utterance ends. With the
  simul policy and calibrated heads, the cascade shows dim text during
  speech; AST shows nothing until the utterance is over.

## Structural analysis

What the cascade gives that canary-AST cannot:

1. **Progressive captions**: commit-driven drafts during speech (the core
   WLK behavior). AST is one-shot per utterance.
2. **The commit policy**: AlignAtt's attention-based commit decisions, the
   dim/bright draft grammar, amend-not-swap corrections. AST has no partial
   state to correct — its failure mode (drift/hallucination on clip 3)
   ships to the reader as-is.
3. **Word timestamps**: the MLX canary returns
   `segments=[{start: 0.0, end: 0.0}]` — hardcoded zeros. No word timing
   exists in the MLX implementation (relevant for the backend dispatch:
   the NeMo contract's `ts_words()` cannot be filled from mlx-audio output
   without deriving timing from decoder steps).
4. **Backend separation**: the cascade swaps ASR and MT independently;
   canary-AST couples them (and covers no zh — our production direction is
   untouched by canary either way).

What canary-AST offers that the cascade does not:

1. **No calibration required**: it translates any of the 25 languages → en
   out of the box. Our fr→en cascade arm ran WITHOUT calibrated heads —
   for uncalibrated directions, canary-AST is a working direct-translation
   mode where the simul cascade currently deactivates.
2. **End-of-utterance latency** on long clips (one decode vs serial
   ASR+MT).
3. **Simplicity**: one model, one call.

## Recommendation

1. **Do not build canary-AST as a simultaneous mode** — mlx-audio provides
   no streaming, and one-shot-per-utterance output is architecturally
   outside the commit-policy/caption-display design.
2. **Canary-AST has a real niche as a non-simultaneous direct-S2T mode for
   uncalibrated directions**: when no (model, direction) calibration exists
   (today: everything except zh→en, en→zh, ja→zh), a canary-AST fallback
   delivers translations where the simul cascade currently deactivates —
   trading the simultaneous experience for availability. This is a cheap
   follow-up on the canary-mlx backend (the same `generate()` call with
   `target_lang="en"`).
3. **The cascade remains the quality and simultaneity winner for
   calibrated directions** — and the canary ASR transcript proved
   reference-grade as the cascade's front end, so canary-mlx ASR (if it
   gains word timing) + Hy-MT2 is the strong European-language cascade
   once the MT side has calibrations.
4. **For the canary-mlx backend dispatch**: the timestamp finding above is
   the binding constraint — `ts_words()` cannot be filled from mlx-audio
   output as-is; the backend is reduced (segment-level) unless timing is
   derived from decoder step counts.

## Method notes

- The mlx-audio loader requires an MLX-style `config.json`; the extracted
  NeMo `.nemo` weights lack it — community MLX checkpoints
  (`Mediform/canary-1b-v2-mlx-q8`, ~1.2GB) are the practical path.
- FLEURS French test clips were fetched per-member from the corpus tarball
  at the pinned revision (`test/<id>.wav` naming; the manifest's `file`
  field uses a different prefix convention).
- Model load: canary q8 loads fast (small download, 17s fetch); Hy-MT2
  8-bit was already cached.
