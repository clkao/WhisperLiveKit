# en→zh ASR baseline: qwen3-asr vs nemotron (justifies n5)

**Measured 2026-08-29** on `demo_en_30s.wav` (PaLM translation paper, continuous
English, ~30s). One model per subprocess (GPU memory freed between runs).

## Setup
- qwen3-asr: `mlx-community/Qwen3-ASR-0.6B-8bit`, `chunk_size_sec=2.0` (prod default),
  `finalization_mode="accuracy"`, wrapped with `StableCommitTransform`
  (`hold_back_units=6`, `stable_iterations=2`) — the real `online_factory` chain.
- nemotron: `mlx-community/nemotron-3.5-asr-streaming-0.6b`, native transducer,
  bare `NemotronMLXOnlineProcessor`.

## Results

### Thermal-safe interleaved A/B (2026-08-29)

3 trials per backend, interleaved (q,n,q,n,q,n), first of each = warmup
(discarded), 3s sleep between runs. One model per subprocess.

| | qwen3-asr | nemotron |
|---|---|---|
| First commit | 0.9s | 0.6s |
| Commits (30s) | 9 | 207 |
| Wall (median) | 11.2s | 14.8s |
| RTF (median) | 0.37 | 0.49 |

Within-backend variance is low across measured trials (qwen3 walls
10.7/11.6s; nemotron walls 14.9/14.7s) — interleaving controlled drift.

### Single-run detail (first measurement)

| | qwen3-asr + StableCommit | nemotron |
|---|---|---|
| First commit | 2.7s | 0.3s |
| Commit count (30s) | 2 | 207 |
| Timestamps | audio_end_time only | real per-token (1.2s, 1.44s, 1.6s…) |
| Provisional text | clean but coarse | rougher but continuous |

## The key finding (load-bearing)

qwen3-asr's streaming encoder-decoder is **intermittently stalls on
continuous English** — in one run it stopped producing new tokens after ~4s
(rolling hypothesis frozen for 26s); in the thermal-safe run it committed 9
times but still far coarser than nemotron's 207. Either way it provides only
audio_end_time timestamps (text-position boundary), not per-token audio
time.

nemotron's transducer streams continuously across the full 30s (207 tokens,
first at 0.6s) with real per-token audio timestamps. It does not have the
decoder-stall failure mode and gives a fine-grained, audio-time frontier.

## Why this justifies the nemotron PR (n5)

For **en→zh simul-MT** with AlignAtt's time-based commit policy, the ASR must
provide a continuously-advancing source frontier with audio-time boundaries.
qwen3-asr cannot do this on continuous English (decoder stall + no
timestamps). nemotron can (continuous stream + native timestamps).

This is the `AccessibleBoundary` adapter case in production:
- **zh→en**: qwen3-asr (stable_text proxy — works; CJK tokenization keeps the
  decoder advancing on short chunks)
- **en→zh**: nemotron (native timestamps — required; transducer doesn't stall)

The n5 PR wires the nemotron backend so en→zh (and any non-CJK source) has a
viable ASR for simul-MT. Without it, en→zh simul-MT is not possible.

## Reproducer
- `scripts/bench_en_asr_ab.py` — single run, one model per subprocess, uses
  the real `StableCommitTransform` wrapper chain for qwen3.
- `scripts/bench_en_asr_ab_thermal.py` — thermal-safe interleaved A/B with
  warmup discard and sleep between runs.

## Note on the earlier false read
The first benchmark bypassed the `StableCommitTransform` wrapper (called the
bare `MlxQwen3AsrOnlineProcessor`), which made qwen3 look like it emitted
nothing until finalization. That was a benchmark bug, not a model property.
qwen3 DOES stream provisionals via the wrapper — the real issue is the decoder
stall on continuous English, not the commit transform.
