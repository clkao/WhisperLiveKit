---
theme: seriph
title: zh-tw → EN Caption Overlay on Apple Silicon
class: text-center
highlighter: shiki
transition: slide-left
mdc: true
---

# zh-tw → EN Caption Overlay

Apple Silicon. MLX. On-device.

```
Mic → ASR → MT → Overlay above Keynote
```

---

# Why

- English captions for Mandarin talks
- Cloud adds delay and privacy risk
- Must float over fullscreen slides
- Must run on a laptop, offline

---

# Cascade speech translation

Two architectures:

**End-to-end**: one model, audio in, text out. Lower delay. Harder to tune.

**Cascade**: ASR → MT. Each stage tuned alone. Higher delay — MT waits for ASR.

```
Speech → ASR (stream) → text → MT → translation
                         ↑
                   MT waits here
```

---

# Overlap ASR + MT

How to know what ASR has committed:

| Way | Timestamps | Cost |
|---|---|---|
| Text prefix stability | None | Free |
| Forced alignment | Per-word | Extra model |
| Transducer native | Per-token | Free |

AlignAtt4LLM (IWSLT 2026): the decoder drafts while ASR streams. It commits only tokens whose attention lands on ASR-committed words. Runs on CUDA/vLLM.

NeMo (IWSLT 2026): transducer + LLM MT, but local-agreement, not AlignAtt.

Transducer + AlignAtt has not been tried before.

---

# The pipeline

```
┌──────┐  ┌───────────┐  ┌────────┐  ┌─────────┐
│ Mic  │─▶│ Qwen3-ASR │─▶│ Hy-MT2 │─▶│ Overlay │
│ 16k  │  │  0.6B 8bit│  │ 1.8B   │  │ NSWindow│
└──────┘  └───────────┘  └────────┘  └─────────┘
               │             │
               ▼             ▼
          OpenCC s2twp   Simul-MT
          zh→zh-tw      AlignAtt
```

All models run via MLX on Apple Silicon GPU. No network after first cache.

---

# What we added

**1. MLX Q/K capture** — mlx-lm discards attention weights. We rebuild `softmax(QK^T)` and capture 8 head indices. Bit-identical output.

**2. Calibrated zh→en heads** — AlignAtt4LLM ships en→{de,it,zh}. We ran the detection on `tencent/Hy-MT2-1.8B` (MPS, PyTorch):
- 23 heads, top L9/H5, TS = 0.79
- 3/3 stability splits passed
- 8 production heads seeded

**3. No-timestamp adapter** — qwen3 has no timestamps. We map its `stable_text` onto AlignAtt's boundary contract.

---

# ASR: Qwen3-ASR

Pure MLX.

| | 8bit | 4bit |
|---|---|---|
| RTF | 0.04 | 0.06 |
| Load | 2.4s | 3.5s |
| zh-tw | 镭射 | 雷射 |

Also wired: Nemotron transducer (native timestamps, but zh too poor — `讨论าาา`).

---

# MT: Hunyuan-MT

| | 8bit | 4bit |
|---|---|---|
| RTF | 0.04 | 0.06 |
| Simul | 8 heads | Off (48.9% match) |
| Quality | Clean | Clean |

In-loop stop at the placeholder token (id 120020).

---

# Simul-MT: AlignAtt

Provisional EN appears during speech. Final corrects it.

```
ASR:  我们今天来讨论━━━━━━━━━━━━
               ↓ committed
MT:   Today we will discuss━━━━━━
                ↑ held (uncommitted)
```

- `mass` commit beats `argmax` (more provisional, less lag)
- Long utterance (~20s): MT delay 1.70s → 0.30s (80% hidden)

---

# Overlay

Borderless window above Keynote. Two rows: current + previous.

```
┌──────────────────────────────┐
│  [dimmer] Previous sentence  │
│  [large white] Current line  │
└──────────────────────────────┘
```

- Model/view split (testable state machine + thin AppKit view)
- Word-by-word stream on growth; hard-swap on new text
- CJK pairs per step; Latin words whole
- Green corrections, dimmed drafts
- All AppKit updates on main thread

---

# Diarization: MLX Sortformer

Pure MLX. Works offline.

| | Value |
|---|---|
| Load | 3.6s |
| RTF | 0.13 |
| Speakers | 4 max |

`mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16` via mlx-audio.

---

# Latency

```
Speak → VAD → ASR → MT → Draw
 0.3s    0.1s  0.4s  0.4s  0.05s
                   ─────────────
                   ~1.3s with simul
                   ~1.7s serial
```

Simul saves ~0.4s. `--no-second-pass` saves ~0.5–1.5s more.

---

# Upstream PRs

| PR | Scope | Status |
|---|---|---|
| #422 | mlx-llm-mt backend | Open, re-review |
| #423 | Simul-MT (AlignAtt) | Open, rebased |
| p0 | mlx-qwen3-asr backend | Tests pass, PR next |
| n5 | Nemotron transducer | PR next |
| dg | MLX diarization | Filed |

Target: `QuentinFuxa/WhisperLiveKit`

---

# Next

- Full eval: 21 audio, BLEU + CHRF + AL/LAAL (~4h)
- Nemotron + AlignAtt with native timestamps
- Post-hoc ASR correction (Jaro-Winkler)
- Tauri app (signed, no terminal)

---

# Thanks

WhisperLiveKit · mlx-audio · mlx-lm · mlx-qwen3-asr · AlignAtt4LLM

All on-device. Apple Silicon GPU. No network after cache.
