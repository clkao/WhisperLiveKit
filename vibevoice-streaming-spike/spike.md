# VibeVoice-ASR-Streaming spike: can one model replace qwen3-asr + mlx-sortformer?

Date: 2026-09-11. Question: VibeVoice-ASR-Streaming-1.5B claims streaming
speaker-attributed ASR with native hotwords, in MLX, covering zh + en.
Does it replace the qwen3-asr + mlx-sortformer combination for the live
captioning path?

## Setup

- mlx-audio 0.5.3, installed from git main (commit 67a3b58) into a scratch
  venv. The released 0.5.1 and 0.5.2 do NOT contain the true streaming
  interface (`init_streaming_state` / `streaming_generate_step` /
  `streaming_window_samples` are unreleased-main only; 0.5.1's
  `stream_transcribe` is output-token streaming of a full-utterance decode).
- Model: `microsoft/VibeVoice-ASR-Streaming-1.5B`, bf16, 5.6GB download,
  load 2.7s warm.
- Streaming protocol confirmed on the loaded model: 22 speech-token frames
  = 2.933s of new audio per window, plus 4 lookahead frames = 0.533s.
- Clips: `_work/zh_long.wav` (31.5s zh) and `_work/demo_en_30s.wav` (30s en).

## Measurement 1 — zh quality vs our production qwen3 path

VibeVoice full transcript (streaming, 11 chunks):

> 我们今天来讨论镭射在医学上的应用。镭射技术可以精确地切除肿瘤组织，减少对周围健康组织的伤害。在眼科手术中，镭射用来矫正视力、治疗近视和远视。牙医也使用镭射来进行口腔手术，减少出血和疼痛。皮肤科用镭射去除斑点、汗纹深。总之，镭射在现代医学中扮演着越来越重要的角色，未来的应用将更加广泛。

qwen3 golden (recorded production output):

> 我们今天来讨论镭射在医学上的应用。镭射技术可以精确的切除肿瘤组织减少对周围健康组织的伤害。在眼科手术中，镭射用来矫正视力治疗近视和远视。牙医也使用镭射来进行口腔手术减少出血。皮肤科用镭射去除斑点和纹身。总之，镭射在现代医学中扮演着越来越重要的角色未来的应用将更加广泛。

Assessment: content parity. VibeVoice produces cleaner punctuation
(real commas where qwen3 runs sentences together) and no
traditional-script leakage (qwen3 leaks 雷射/未來 variants). One character
error: 汗纹深 vs 纹身 (tattoo). Verdict: zh quality is at parity or
slightly better on this clip.

## Measurement 2 — speaker attribution

` Speaker 0:` prefixes appear natively in the streamed chunks and remain
`Speaker 0` throughout both single-speaker clips — no flips, no
fragmentation. Multi-speaker verification was not possible (no
multi-speaker clip locally); single-speaker consistency confirmed.

## Measurement 3 — streaming cadence and latency

Per-window wall time (2.933s of new audio per window):

- zh: ~2.0-2.4s per window (steady-state window RTF ~0.72; whole-file
  RTF 0.795 including load). The run finishes 7.2s "ahead" of the audio
  position — the model outpaces real-time playback.
- en: irregular and slower — chunks 6-10 took 5-7s each, whole-file
  RTF 1.442 without hotwords, 1.09 with hotwords. Latin-script output
  decodes noticeably more tokens per window than zh. The en run fell
  up to 13s behind the audio position: **en throughput is at or beyond
  the real-time limit on this machine**.
- First text: chunk 1 lands at 3.5s wall for 2.9s of audio — live latency
  is bounded by the 2.933s window + 0.533s lookahead (~3.5s inherent),
  which matches the design.

## Measurement 4 — timestamps

Confirmed absent in streaming output: each yielded chunk is text only
(speaker tag inline, no timing). The chunk boundary itself is a timing
anchor (each chunk covers exactly 2.933s of new audio), so chunk-granular
derived stamps are possible — same class of approximation as the canary-mlx
backend, weaker than nemotron's native word timestamps.

## Hotwords — the decisive bonus test

Without hotwords, the en clip mis-recognizes the domain terms:

> Perl is a 540 million parameter large language model ... colleagues from
> Go-Wit Translate.

With `context="PaLM, 540 billion parameters, Google Translate, Pathways"`:

> PaLM is a 540 billion parameters latent language model ... colleagues
> from Google Translate.

Both proper-noun errors fixed by the native hotword mechanism — the same
job our `mlx_qwen3_asr_context` biasing does for qwen3, but model-supported.
Residual errors: the speaker's name stays garbled (Ayeed Bilar), and one
figure drifts (700,000 documents vs the actual 780B tokens).

## Verdict on the headline question

**Complement, not replace — with one consolidation win.**

- Replace qwen3 for zh: NO on throughput certainty. zh quality is at
  parity and the streaming design is excellent, but en/window throughput
  sits at the real-time edge (RTF 1.09-1.44 vs zh's 0.72), and the
  production zh path is measured and stable. A quality A/B over more clips
  could flip this for zh specifically; today the safe call is qwen3 stays.
- Replace mlx-sortformer: PARTIALLY — for a VibeVoice-backed path, speaker
  attribution is native and the separate diarization pass is redundant.
  mlx-sortformer remains needed for the qwen3 path.
- The standout: one 1.5B model delivers streaming + speaker attribution +
  native hotwords with zh+en+8 languages. As a backend it eliminates two
  wiring seams (diarization, hotword biasing) for its supported languages.
- Blocker for production use: the true streaming interface is unreleased
  (git main only, 0.5.3-unreleased at spike time), and en throughput is
  marginal. Both are moving targets — re-check on the next mlx-audio
  release.

## Integration sketch (if pursued)

- Backend `vibevoice-streaming` mirroring the ASR contract: `feed(window)`
  / commit-stream shaped around the 2.933s windows; `ASRToken.speaker`
  filled from the inline `Speaker N:` tags; `ts_words()` from chunk-boundary
  derived stamps (chunk-granular, like canary-mlx).
- Extra: `vibevoice-asr` (mlx-audio from git or a release containing the
  streaming interface); model extra ~5.6GB bf16, 8-bit conversion halves it.
- `ASRToken.speaker` lets the caption display render [S1]/[S2] without
  mlx-sortformer for this path.

## Environment notes

- mlx-audio 0.5.1/0.5.2 lack the streaming interface; install from
  `git+https://github.com/Blaizzy/mlx-audio` (0.5.3-unreleased, 67a3b58).
- The released 0.4.8 present in the repo venv also lacks it; the repo venv
  was left untouched (scratch venv at /tmp/vv-venv, removed after the
  spike).
- The bf16 model cache (5.6GB) was deleted after measurement (re-downloadable).

## q8 re-measure attempt (follow-up): BLOCKED by an mlx-audio bug

Question: does 8-bit quantization fix the en-throughput blocker (bf16 en
RTF 1.09-1.44)?

What was done:
- `mlx_audio.convert` (git main) crashes on this checkpoint: its strict
  `load_weights` rejects params the MLX Model does not declare
  (`language_model.lm_head.weight` — untied head; then
  `semantic_tokenizer.encoder.*` keys). Worked around with a manual
  conversion script (load bf16 via `mlx_audio.stt.load_model`, quantize
  with an explicit predicate, save safetensors + config with a
  quantization block). Result: 2.46GB q8 (vs 5.6GB bf16), loads in 1.4s.
- Quantize-everything (Linear/Embedding with `to_quantized`, divisibility
  guard): model loads, but the FIRST forward pass crashes inside
  mlx-audio's `lm/models/qwen2.py` attention — `queries.reshape(B, L,
  n_heads, -1)` on an empty array (the layer input is empty).
- Quantize `language_model.*` ONLY (tokenizers/encoders stay bf16 — the
  input path is untouched): the SAME crash at the same place. So the bug
  is mlx-audio's qwen2 forward with QuantizedLinear/Embedding weights,
  not the tokenizer path and not the conversion.
- Also found en route: `mlx_audio.convert` cannot quantize this model
  family at all today, and no mlx-community q8/q4 of the streaming 1.5B
  exists (the 7B-4bit does; a 1.5B ONNX export exists separately).

Verdict update: the q8 re-measure is BLOCKED by the mlx-audio bug. The
bf16 en-throughput verdict (RTF 1.09-1.44, at/beyond real-time) stands as
measured. 8-bit remains a plausible-but-unverified lever: it should be
re-tested when mlx-audio fixes quantized inference for the VibeVoice
streaming path (or when an mlx-community q8 of the streaming 1.5B
appears). The conversion recipe above works up to the mlx-audio bug and
is reproducible in ~10 minutes.

Cleanup: scratch venv/worktree/branch removed; bf16 cache deleted; q8
output deleted (reproducible via the recipe).
