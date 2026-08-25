# ASR streaming approaches & the translator coupling — a visual explainer

## The core difference: transducer vs encoder-decoder

```
TRANSDUCER (nemotron)                    ENCODER-DECODER (qwen3-asr)
─────────────────────                    ──────────────────────────

 audio frames in                         audio window in
      │                                       │
      ▼                                       ▼
 ┌─────────┐                            ┌─────────────┐
 │ encoder │ → frames                   │  encoder    │ → features
 │ forward │   (one     ┌─┐             │ re-encodes   │   (re-processes
 │  only)  │   pass)    │ │             │ the window   │    the whole
 └─────────┘           │j│             │ each chunk)  │    context)
      │                 │o│             └─────────────┘
      ▼                 │i│                    │
 ┌─────────┐  emits     │n│                    ▼
 │joiner + │  tokens    │t│             ┌─────────────┐
 │predict. │  ONE AT    │ │             │  decoder    │ → full hypothesis
 │  net    │  A TIME    │ │             │ (revises    │   (may change the
 └─────────┘  as audio │ │             │  the tail)  │    tail each pass)
      │       arrives  └─┘             └─────────────┘
      ▼                                 │
 tokens are                              ▼
 MONOTONIC.                         the hypothesis
 No revision.                       REVISES its tail.
 A token emitted                    A word in the tail
 is final.                           can change or vanish.
```

The transducer is built to stream: frames go in forward, tokens come out one at a time, done. The encoder-decoder is built for complete clips: give it the whole audio, get the whole text. To stream it, you feed a growing window and re-decode — but the decoder can revise its recent output as more context arrives.

## The wrapper's job: simulate monotonic emission

The encoder-decoder revises, but a streaming translator needs a committed prefix it can trust + an unstable tail it can draft over. The wrapper manufactures that split:

```
the decoder's raw output (revises the tail):
  "我们今天来讨论镭射在医学上的应用以及网络上的"
                    ↑ the decoder may revise everything after here

the wrapper's split (mlx-qwen3-asr / qwen3-asr-causal):
  committed prefix        │  unstable tail
  ─────────────────────── │ ──────────────────
  "我们今天来讨论镭射"     │  "在医学上的应用以及网络上的"
                          │
  emit as ASRToken(s)     │  emit as HypothesisTail
  (final, won't change)   │  (draft over it, can't commit against it)

  the split rule:
    mlx-qwen3-asr:      hold back the last N=5 units (string distance)
    qwen3-asr-causal:   hold back tokens that haven't agreed across
                        N=2 decode passes (LocalAgreement)
```

Both enforce **monotonicity**: the committed prefix never shrinks. The difference is *how robustly* they decide a unit is stable — agreement across passes (causal) is stronger than "last N units" (mlx-qwen3-asr). A word that flickers in/out stays unstable under the causal policy until it sticks; under the mlx policy it might commit then... no — both are monotonic, so "commit then retract" can't happen; the weaker policy just commits slightly earlier on less evidence.

## What the translator receives (the contract)

```
                ASR emits, per chunk:
                ┌─────────────────────────────────────────────┐
                │  committed: [ASRToken, ASRToken, ...]         │ → insert_tokens()
                │  unstable:  HypothesisTail(text=...)          │ → insert_tokens() if wants_hypothesis_tail
                └─────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
              TIER A (plain)                  TIER B (simultaneous)
              wants_hypothesis_tail=False     wants_hypothesis_tail=True
                    │                               │
                    ▼                               ▼
         ignores the tail                 drafts translation over the tail
         translates only when             but COMMITS only against the
         a segment closes                 committed prefix
                    │                               │
                    ▼                               ▼
         translation appears             translation streams DURING
         AFTER the utterance             the utterance; held tokens
         (silence boundary)              release without a new MT call
                                         when ASR commits the tail
```

## Tier A vs Tier B — the latency shape

```
TIER A (translate-on-close)          TIER B (simultaneous, overlap)
───────────────────────────          ───────────────────────────────

  speech:    ████████████████           speech:    ████████████████
  ASR:       ████████████████           ASR:       ████████████████
  MT:                    ████           MT:        ████░░░░████░░░░  ← overlapped
  en out:                    ▼          en out:    ▼           ▼
                             ↑                    ↑           ↑
                       utterance ends       prefix commits  final
                       (2-4s wait)          (streaming)    (small wait)

  MT runs AFTER ASR finalizes.         MT drafts DURING speech, commits
  Wait = ASR finalize + MT decode.      against the stable prefix as it grows.
                                        Wait ≈ MT decode of the final delta only.
```

Tier B is the ~1.4s win we measured in livecaption. It works with **either** ASR:
- with a transducer (nemotron): the tail is real timestamps, the commit is native
- with a wrapped encoder-decoder (mlx-qwen3-asr): the tail is the manufactured `stable_text`/`HypothesisTail`, the commit is the wrapper's split

The wrapper's commit-policy strength (agreement vs string-distance) affects Tier B *quality* (how often a provisional translation gets revised), not whether Tier B works.

## The three ASR backends on Apple Silicon, by what they emit

```
┌────────────────────┬──────────────┬───────────────┬──────────────────────┐
│ backend            │ runtime      │ encoder       │ what it emits         │
├────────────────────┼──────────────┼───────────────┼──────────────────────┤
│ mlx-qwen3-asr      │ pure MLX     │ windowed      │ stable_text prefix   │
│ (what we shipped)  │ no torch     │ (re-encode    │ + unstable tail       │
│                    │              │  the window)  │ (string-distance hold)│
├────────────────────┼──────────────┼───────────────┼──────────────────────┤
│ qwen3-streaming    │ torch +      │ windowed      │ committed prefix     │
│ (qwen3-asr-causal) │ transformers │ (re-encode)   │ + unstable tail      │
│                    │ 4.57.6 pin   │               │ (LocalAgreement)     │
├────────────────────┼──────────────┼───────────────┼──────────────────────┤
│ qwen3-vllm-metal   │ MLX via      │ causal        │ committed prefix     │
│ --audio-backend    │ vllm-metal   │ (append-only  │ + unstable tail      │
│  causal            │              │  KV, flat     │ (agreement,          │
│                    │              │  cost)        │  flat-cost emit)     │
├────────────────────┼──────────────┼───────────────┼──────────────────────┤
│ nemotron (mlx-audio│ pure MLX     │ transducer    │ monotonic tokens     │
│  not a WLK backend)│              │ (native)     │ + real timestamps     │
└────────────────────┴──────────────┴───────────────┴──────────────────────┘
```

All four emit the **same contract** (committed prefix + unstable tail) to the translator. The transducer gives it natively; the three encoder-decoder wrappers manufacture it. Tier A and Tier B both consume that contract — so the MT tier is decoupled from the ASR encoder choice.

## The dep-cleanup lever (where the latency win actually is)

```
  mlx-qwen3-asr (windowed)          qwen3-vllm-metal causal
  ────────────────────────          ────────────────────────
  per-chunk cost GROWS              per-chunk cost is FLAT
  (re-encodes the window)           (appends to KV, no re-encode)
        │                                  │
        ▼                                  ▼
  fine on short utterances           fine on long utterances
  slow on long (2-7s decodes)        (the causal tower + checkpoint)
        │                                  │
        ▼                                  ▼
  dep-clean (pure MLX, no torch)     needs vllm-metal install
  no transformers pin                (MLX runtime, no transformers pin)
                                     the causal encoder is pure mlx.nn;
                                     the dep cleanup = load the tower
                                     without vllm-metal's loader
```

The causal MLX encoder already exists in `metal.py` (pure `mlx.core`/`mlx.nn` + the fine-tuned tower safetensors). The only non-MLX line is `from vllm_metal.stt.loader import load_model`. Swapping that for a plain mlx-lm/`mlx_qwen3_asr` loader is the dep cleanup — not a reimplementation. That unlocks flat-cost causal ASR on Apple Silicon without the heavy wheel, which is the real ASR-side latency lever.
