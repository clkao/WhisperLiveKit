# en→zh / zh→en ASR+MT baseline: qwen3-asr vs nemotron

**Measured 2026-08-29** on the integration branch (`feat/apple-silicon-backends`)
after the CJK commit fix (`bbb70c1`) and token-based MT hysteresis (`bf383db`).

## Setup
- qwen3-asr: `mlx-community/Qwen3-ASR-0.6B-8bit`, `chunk_size_sec=2.0` (prod
  default), wrapped with `StableCommitTransform(prefer_native_stable=True)`
  — the real `online_factory` chain (native `stable_text` commit).
- nemotron: `mlx-community/nemotron-3.5-asr-streaming-0.6b`, native transducer,
  bare `NemotronMLXOnlineProcessor` (native per-token timestamps).
- MT: `MlxLlmTranslationSimul(hy-mt2-1.8b-8bit)`, `commit_mode="mass"`,
  `MIN_SOURCE_TOKENS=15` (token-based hysteresis).
- Audio: `demo_en_30s.wav` (en→zh), `zh_long.wav` (zh→en).
- 4 trials per combo, interleaved A/B, first = warmup (discarded), 8s sleep
  between runs. One (ASR, MT) combo per subprocess (GPU memory freed).
- Reported: mean ± stdev of 3 measured trials.

## Results

| Combo | RTF | finals | provs | firstProv | firstFinal |
|---|---|---|---|---|---|
| en→zh qwen3 | 0.76±0.13 | 8 | 44 | 2.0±0.6s | 1.2±0.3s |
| en→zh nemotron | 0.67±0.07 | 4 | 50 | 0.6±0.0s | 6.4±0.6s |
| zh→en qwen3 | 1.20±0.68 | 12 | 42 | 2.2±0.6s | 1.7±0.4s |
| zh→en nemotron | 0.76±0.04 | 3 | 55 | 1.1±0.1s | 6.3±0.2s |

Provisional text samples:
- en→zh qwen3: `大家好。我叫……我会很高兴的。` (fragmented — 8 finals from one sentence)
- en→zh nemotron: `你好，永远` (rough but coherent — 4 complete-sentence finals)
- zh→en qwen3: `Today we will discuss laser. Its applications in medicine, lasers. The` (good)
- zh→en nemotron: `We` (early, complete sentences at final)

## Findings

### nemotron wins firstProv on both directions
nemotron's native per-token timestamps let AlignAtt commit earlier: 0.6s
(en→zh) and 1.1s (zh→en) vs qwen3's 2.0s and 2.2s. This is the simul-MT
provisional signal — the transducer's fine-grained audio-time frontier
commits target earlier than qwen3's text-prefix proxy.

### qwen3's firstFinal advantage is a fragmentation artifact
qwen3 emits 8-12 short punctuated fragments as "finals" (e.g. `大家好。` then
`我叫……` = 8 finals from one sentence). nemotron emits 3-4 complete
sentences. firstFinal is gameable by fragmentation — a caption overlay
showing 8 flickering fragments is worse UX than 1 complete sentence at 6s.
The metric that matters (AL/LAAL) isn't gameable this way; the 21-audio
devset eval will measure it properly.

### zh→en qwen3 was dead before the CJK fix
Before `bbb70c1`: 0 provisionals, 1 final at 8.8s (finish). The
`StableCommitTransform` used whitespace-only `split_text_units`, which
collapsed a 30s CJK transcript into one unit → LCP always 0 → never
committed during streaming. After the fix (prefer native `stable_text`):
11 streaming commits, 42 provisionals at 2.2s, 12 finals at 1.7s.

### Throughput
nemotron is faster and more stable (RTF 0.67-0.76, stdev 0.04-0.07).
qwen3 zh→en has a thermal outlier (62.3s = RTF 1.98 in one trial, stdev
0.68) — the two-pass re-decode on long zh utterances is compute-heavy and
throttles under sustained heat.

### No language-specific specialization needed
native `stable_text` (the default commit path) is language-agnostic — the
model's own field works on CJK and Latin alike. The only lang-aware code is
CJK Unicode-range detection in the fallback char-split (applies to zh/ja/ko
equally, not a `lang=="zh"` switch).

## The n5 case (justified)

For simul-MT with AlignAtt's time-based commit policy, the ASR must provide
a continuously-advancing source frontier. nemotron's native per-token
timestamps give this on both directions (earlier provisionals, real audio
time). qwen3's native `stable_text` now also works on both directions (CJK
fix), but is a text-prefix proxy (no audio time, coarser).

The `AccessibleBoundary` adapter direction:
- **en→zh (Latin source)**: nemotron's timestamps are the natural fit
  (fine-grained, audio-time). qwen3's `stable_text` works but is coarser.
- **zh→en (CJK source)**: qwen3's native `stable_text` works well (good
  provisional text, 11 commits). nemotron also works (earlier provisionals)
  but rougher text ("ReiSha" for 雷射).

Both backends now drive the simul-MT pipeline on both directions. The n5
PR (nemotron backend) is justified by the provisional-latency win (0.6-1.1s
vs 2.0-2.2s) and the architectural fit (native timestamps for AlignAtt).

## Reproducers
- `scripts/bench_e2e_asr_mt.py [trials] [sleep_s]` — thermal-safe
  interleaved A/B with warmup discard.
- `scripts/bench_en_asr_ab_thermal.py` — ASR-only A/B.
- `scripts/spike_min_source_delta.py` — MT hysteresis threshold sweep.

## Caveats
- Throughput is thermally loaded (this session ran many benchmarks).
  Relative ordering is valid; absolute RTFs are warm-state.
- No reference translations → no quality scores (BLEU/COMET). The 21-audio
  devset eval (next step #8z) measures AL/LAAL + COMET/BLEU.
- firstFinal is gameable by fragmentation (see above); don't over-read it.
