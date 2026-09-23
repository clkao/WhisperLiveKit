# apple-asr — measured evidence (feeds the README, the PR body, and the API defaults)

Protocol for every row: the first 10 zh samples of `benchmarks/corpora/fleurs-90.json`
(shared FLEURS sentence IDs), upstream harness normalization, **mean per-sample
CER** (the board's own aggregate), Traditional hypothesis t2s-converted to the
Simplified references. The scoring path is anchored: `bench_cer.py --verify`
reproduces the board's recorded qwen3-1.7B 18.20 (zh) and 21.30 (en) before
scoring anything we produced.

## zh CER / en WER — two modes, both languages

All rows measured with the **package's own shim** (`apple-asr` `0.1.0`,
`apple_asr.build`, file mode), same protocol as the board below.

| engine / config | zh CER | en WER | note |
|---|---|---|---|
| **apple framework — accurate** (`transcription`, no `fastResults`) | **11.23** | **9.51** | finals only |
| `mac-speech-analyzer` 0.1.2 (prior art, file-only) | 11.23 | 9.51 | identical to ours — same framework, same config |
| **apple framework — streaming** (`progressive` + `fastResults`) | **13.19** | **13.94** | volatile partials + emission speed |
| qwen3-1.7B (MLX board anchor) | 18.20 | 21.30 | best MLX zh |
| nemotron-0.6B | 22.62 | **19.27** | best MLX en |
| Voxtral-4.4B | 20.31 | 22.78 | |
| qwen3-0.6B | 23.84 | 20.37 | |

## Findings

1. **The configuration, not the engine, accounts for the whole delta.** Our shim
   in the accurate config and `mac-speech-analyzer` in its one-shot mode agree to
   the digit in both languages (11.23 zh / 9.51 en, identical per-sample values).
   Independent engines driving the same framework converge, which also validates
   our scoring chain.
2. **Streaming costs are language-dependent**: zh 11.23 → 13.19 (−2.0 CER) but en
   9.51 → 13.94 (−4.4 WER). Worth telling users plainly: for English, if the
   session does not need live partials, accurate mode is much better; for live
   captioning streaming is the price of being live, and it still leads the best
   MLX backend by 5.3 WER.
3. **Both modes beat every MLX backend on the board** (best zh 18.20, best en
   19.27). Even the streaming config clears the MLX field by ~5 points in each
   language.
4. **Consequence for the API**: `mode` is explicit and documented rather than
   leaving users to discover that `fastResults` costs accuracy.
   - `mode="streaming"` (default) → `preset=progressive` + `fastResults`
   - `mode="accurate"` → `preset=transcription`, no `fastResults`
   Order 2 implemented this with `mode=None` meaning streaming, so order 1's
   explicit `preset=` spelling keeps working.

## Commit cadence (measured against the project's golden, same audio)

`tests/golden/zh_long_ideal.jsonl` vs our shim through WhisperLiveKit:

| | ours | golden |
|---|---|---|
| transcription_final count | 12 | 12 |
| first commit | 3.53 s | 2.99 s |
| mean commit gap | 2.55 s | 2.97 s |

Verified at real-time pace in WLK's exact call pattern via
`_work/sa-spike/drive_live.py`: every commit lands **0.02–0.15 s after its pause
starts** (not at the next utterance). `--commit-interval` (a ceiling for
continuous speakers) was measured WORSE — mid-phrase cuts corrupt characters
(越→月) and poison translations — so it defaults to 0 (pause-only).

## Prior art (checked 2026-09-22)

- **`mac-speech-analyzer`** (paraversal, MIT, 0.1.2): the only Python package on
  the new SpeechAnalyzer stack. **Files only**; progressive output = finalized
  segments only ("non-overlapping and never revised", i.e. no volatiles); its
  roadmap lists live-stream transcription as still to do. Architecture: in-process
  C-ABI Swift bridge (CMake + Package.swift); ships a prebuilt dylib in the wheel —
  which validates the prebuilt-wheel distribution plan. Works correctly (verified
  here; an earlier failure in this workspace was our own sandbox's mach-lookup
  restriction, not the package).
- **`macos-stt`**, **`macstt`**, **`pyobjc-framework-Speech`**: the legacy
  `SFSpeechRecognizer` stack — batch/file oriented, different (older) engine.

Differentiation we own: live streaming, volatile partials, per-word timings,
push-based audio for external pipelines, pause-aware commits, and published
measurements. The incumbent leaves streaming as an open roadmap item.
