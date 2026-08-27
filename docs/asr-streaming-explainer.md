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

## The MT backend landscape (three approaches, one contract)

All three WLK translation backends implement the same 5-method contract:
`insert_tokens`, `process`, `validate_buffer_and_reset`, `insert_silence`,
`wants_hypothesis_tail`. The audio processor calls these; it does not know
which backend is behind them.

```
┌────────────────┬──────────────┬───────────────┬──────────────────────┐
│ backend        │ engine       │ runtime       │ wants_hypothesis_tail │
├────────────────┼──────────────┼───────────────┼──────────────────────┤
│ nllb (default) │ 600M enc-dec │ CPU/transformers│ False (Tier A)       │
│                │ via nllw     │               │ classic NMT           │
├────────────────┼──────────────┼───────────────┼──────────────────────┤
│ alignatt       │ Gemma 4 E4B  │ vLLM/CUDA      │ True (Tier B)         │
│ (reference)    │ decoder LLM  │ sidecar (WS)  │ simultaneous MT       │
├────────────────┼──────────────┼───────────────┼──────────────────────┤
│ mlx-llm-mt     │ Hunyuan-MT   │ mlx-lm         │ False (Tier A)        │
│ (ours)         │ decoder LLM  │ in-process     │ True when --simultaneous│
└────────────────┴──────────────┴───────────────┴──────────────────────┘
```

NLLB is an encoder-decoder (the original NLLB-200). AlignAtt and mlx-llm-mt
are decoder LLMs with a translation prompt. The contract is the same; the
model and runtime differ. NLLB needs `nllw`; AlignAtt needs a CUDA sidecar;
mlx-llm-mt needs `mlx-lm` (the `[hunyuan-mlx]` extra).

## AlignAtt internals — what model, why sidecar, what's portable

**The model is Gemma, not NLLB.** The reference AlignAtt server uses
`google/gemma-4-E4B-it` as its MT model. There is also a Qwen3-1.7B backend.
Both are decoder LLMs running on vLLM/CUDA. The repo ships calibrated head
files for three models (Gemma, Qwen3, MiLMMT) across several directions.

**Why sidecar: the Q/K-capture runtime is CUDA/vLLM-locked.** `vllm_qk/observer.py`
is a `torch.nn.Module` that hooks vLLM's attention to capture the query/key
tensors at runtime. There is no MLX/CPU port. The whole engine is bound to a
CUDA+vLLM process, so it ships as a WebSocket server. WLK's `translation_alignatt.py`
is the client half — it speaks the WebSocket protocol and implements the WLK
contract on top.

**The pattern is runtime-agnostic; the reference implementation is not.** The
commit policy (draft over unstable tail, commit via attention alignment) is
stdlib+numpy (`alignment/base.py`, `attention_trace.py`, `source_frontier.py`,
`emission.py`). The model config (prompt, EOS, heads) is data. Only the decode
loop and the Q/K observer are runtime-specific. Our Tier B port reimplements
the Q/K observer in MLX (hooking `mlx_lm`'s forward); the policy is reused as-is.

**Heads are model + language-pair specific (with cross-pair reuse).** Each head
file is calibrated to one (model, direction) pair. Gemma en-zh has 82 heads;
en-cs has 68. But 54 heads recur across all 5 shipped directions (the shared
kernel). Recalibration per model is required (Gemma heads don't work on Qwen3);
per-direction within a model is cheap (the shared kernel retains the high-ts
heads). No zh→en heads ship for any model — that's the gap our Hunyuan
calibration filled.

## nemotron + AlignAtt — contract-compatible Tier A, mismatched Tier B

nemotron is a transducer: tokens are monotonic, emitted once, no revision.
For Tier A (`wants_hypothesis_tail=False`): cleanly compatible — committed
tokens + real timestamps, no wrapper needed. It's the best Tier A ASR.
For Tier B (`wants_hypothesis_tail=True`): structurally mismatched. The
simultaneous-MT win is "overlap MT with the ASR's *revising* tail." A
transducer doesn't revise — its tail only grows. There's nothing to draft
over; you'd translate the partial, then re-translate when it commits =
Tier A with redundant work. The simultaneous pattern recovers latency the
encoder-decoder's revision imposes; a transducer doesn't impose it.

## Fun-ASR-Nano-2512 — spiked, not viable

Fun-ASR-Nano-2512 (Tongyi Lab, 800M, 4bit via mlx-audio-plus) is an LLM-based
encoder-decoder ASR: SenseVoice encoder + LLM decoder. It covers zh/en/ja + 7
Chinese dialect groups / 26 regional accents (Taiwan Mandarin is an accent).

**Spike result (2026-08-25):**
- `translate` task (zh→en): BROKEN. The system prompt is correct ("Translate it
  into English") but the model outputs Chinese. Instruction-following failure
  in the 4bit quantization.
- Transcription: TRUNCATED. A 6.3s sample yields 10 tokens / 1.48s of content.
  Streaming produces the same 10 chunks. max_tokens=1024 doesn't help (EOS
  early stop).
- Taiwan vocab: present but inconsistent (鐳射/雷射, 滑鼠 both appear; 雨華鼠
  is a misrecognition).

Verdict: not viable as a single-model pipeline. The built-in `translate` task
does not work; transcription truncates. Stay with the current plan (qwen3-asr
+ Hunyuan-MT via mlx-llm-mt).

## FunASR framework vs FunASR model

FunASR (Alibaba DAMO) is a multi-model ASR framework — `funasr.AutoModel` is a
unified loader that wraps many architectures (Paraformer, SenseVoice, Conformer,
Whisper) behind one API. WLK's `funasr` backend uses `AutoModel` but hardcodes to
one model: `iic/SenseVoiceSmall`. So WLK's "FunASR support" is really SenseVoice
support loaded via the FunASR framework. The framework's multi-model nature is
latent — wired but not exposed in flags. It routes through the same LocalAgreement
wrapper as Whisper, so it's a candidate for the generalized wrapper's
second-provider proof (proves cross-framework, not just cross-model).

## The generalized wrapper layer (two jobs, five duplicates)

Every non-transducer ASR backend in WLK duplicates two jobs that a streaming
translator needs:

- **Job 1 — stable/unstable split** (for revising models): commit only a prefix
  that stays stable across decode passes. Five backends implement this inline
  (Whisper/LocalAgreement, Voxtral-MLX, Voxtral-HF, qwen3-causal, mlx-qwen3-asr).
  Only `qwen3-asr-causal/stable_commit.py` is factored.
- **Job 2 — timestamp manufacture** (for forward-emit-no-timing models): assign
  start/end times from the decode position. Voxtral-MLX implements this inline.

A transducer (nemotron) needs neither — it emits monotonic tokens with real
timestamps natively. The generalized wrapper factors these into shared modules
(`asr_commit.py` + `asr_timestamps.py`) and a composable chain (`asr_wrapper.py`).
A backend declares which jobs it needs; `online_factory` builds the chain.

This is orthogonal to PR #395 (which refactors the orchestration *above*
`self.transcription`). The wrapper layer is *below* it. They don't conflict.

## The mlx-llm-mt shape (generic decoder-LLM, not HY-specific)

Our translation backend is almost entirely a common decoder-LLM shape. The
HY-specific parts are thin and externalized:
- the prompt (Hunyuan's Chinese "把下面的文本翻译成{target_lang}")
- the EOS token string (`<|im_end|>`)
- the model registry (maps short names to `mlx-community/Hy-MT2-*` repos)

Everything else is generic: `mlx_lm.load`, `apply_chat_template`,
`stream_generate`, the 5-method WLK contract. The refactor extracts a generic
`MlxLlmTranslation` base; Hunyuan / TranslateGemma / Aya / Qwen-MT are configs.
This keeps Tier B (the `CapturedAttention` + commit policy) model-agnostic — it
works on any decoder LLM with alignment heads.

## OpenAI's translation surfaces (the comparison point)

OpenAI ships three translation surfaces:
- `/v1/audio/translations` (Whisper-1, batch): audio file → English text.
- `/v1/audio/transcriptions` (Whisper-1, batch): audio → original-language text.
- `gpt-realtime-translate` (streaming): source audio in → translated audio +
  transcript deltas out. Cloud, speech-to-speech, one model, priced by audio
  duration.

`gpt-realtime-translate` is the real WLK competitor — both do live streaming
translation synced to speech. Differences: cloud vs local, speech-to-speech vs
text captions, one model vs pluggable backends, opaque commit vs explicit
`wants_hypothesis_tail` + `validate_buffer_and_reset`.

The `gpt-realtime-translate` commit boundary is opaque (the model decides).
WLK's contract makes it explicit — the audio processor flushes at silence /
speaker-change, and `wants_hypothesis_tail` gates the simultaneous-MT seam.
That seam (draft over the revising ASR tail, commit against the stable prefix)
is the thing a text→text or cloud speech-to-speech API has no analog for.
