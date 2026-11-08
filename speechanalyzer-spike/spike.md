# SpeechAnalyzer streaming spike

## Status: RUNTIME VERIFIED (2026-09-21) — mechanism works, latency cost measured

The shim now compiles + runs end-to-end on CL's terminal (Xcode/toolchain exec
enabled for the sandbox; the agent compiles it directly). Both modes work:
file (full transcript) and mic (incremental volatile + final). The open
questions below are answered; the remaining decision is a product call, not
a technical one.

## Measured results (zh-TW, macOS 26, CL's terminal)

- **Locale/quality:** zh-TW works, **Traditional-native output** (鐳射, 醫學,
  腫瘤 — correct Traditional, no Simplified→Traditional post-conv needed).
  鐳射 (laser, the medical homophone) recovered WITHOUT hotwords — the base
  model handles it.
- **Volatile cadence — the preset is the lever.** `SpeechTranscriber.Preset`:
  - `.transcription` (default): **0 volatiles, batch finals only** — the
    zh-TW "buffers to endpoint" symptom. This is why zh-TW felt broken.
  - `.progressiveTranscription`: **131 volatiles, streams incrementally**
    (我 → 我們 → 我們今 → …, growing text + range). Fixed.
  - Wired as `--preset default|progressive|timeIndexedProgressive|transcription`.
- **First-emission latency — TWO more levers found (web research + interface):**
  - `analyzer.prepareToAnalyze(in: fmt)` — explicit model preheat. Cuts
    decoder startup **0.707s → 0.053s** wall-clock in file mode. Always on
    now (non-fatal on failure).
  - `.fastResults` ReportingOption — added to the preset's reportingOptions
    (Preset has a settable `reportingOptions` var; SpeechTranscriber itself
    does not). A/B via `--no-fast`.
  - **Mic result with both levers:** first volatile at **3.1s after
    "mic live"**; the model's own speech-region detection (final range
    start = 1.44s) says speech began ~1.44s in → **~1.7s after speech
    onset**. Then clean **~1s incremental cadence** (53 volatiles across
    15.7s, range growing ~1s per emission — real streaming, not a burst).
  - Before the levers: 4.9s to first volatile (~5s accumulation threshold).
    After: ~3s of audio (~1.7s of speech).
  - `--fast` file mode is the WRONG instrument for live latency (instant
    feed lets the decoder run arbitrarily far ahead — ranges inflate to the
    whole file). Use mic for the live numbers.
- **Word timestamps: CONFIRMED.** Final results carry per-word `[start,end]`
  in `runs` (e.g. 測 2.330-3.170, 試 3.170-3.170). This is the time-frontier
  input qwen3 lacks — apple-speech is a timestamps-equipped backend.
- **SpeechDetector (VAD): inert in our config.** Wired with
  `reportResults:true` + sensitivity low/med/high; `vad-consumer` started but
  emitted **zero events** at any sensitivity. Not the zh-TW lever; the preset
  is. Detector left wired (behind `--vad-sensitivity`) but not relied on.

## zh CER: 13.19 — apple-speech leads the board (measured 2026-09-21)

`_work/sa-spike/bench_cer.py --locale zh-TW` — same protocol as the board
(same first-10 zh manifest samples, harness normalization, mean per-sample
CER; the Traditional hypothesis t2s-converted before scoring since the
FLEURS refs are Simplified; the scorer reproduces qwen3-1.7B's 18.20 from
the board's own raw results):

  apple-speech (zh-TW + t2s) **13.19** < qwen3-1.7B 18.20 < Voxtral-4.4B 20.31
  < nemotron-0.6B 22.62 < qwen3-0.6B 23.84

Per-sample: 5/10 perfect (qwen3: 2/10); worst two (35.71, 39.13) are the
same hard clips where qwen3 also faltered (17.86, 52.17). Caveats, honestly:
n=10 (the same caveat the whole board carries); t2s-on-hypothesis is a
protocol delta vs the native-Simplified backends (near-lossless for
scoring); CER measured in FILE mode — live finals should match but the live
wiring drops VAD silence (untested delta); the audio is mainland-accented
(cmn_hans_cn) and Apple's zh-TW model still leads.

Combined with the latency levers (~1.7s after speech onset, ~1s cadence),
the production picture for zh: apple-speech is now the BEST zh backend by
quality AND costs zero GPU memory (ANE system process — no MLX footprint,
no contention with the MT model), AND emits word timestamps (time-frontier
input qwen3 lacks) AND outputs Traditional natively (no OpenCC on the
display path). First-emission is its one deficit vs qwen3 (1.7s vs 0.8s).

## Verdict on the apple-speech backend (revised after the CER + latency levers)

- **For live captioning (production):** the earlier "5s = not production"
  call was too pessimistic. With progressive preset + prepareToAnalyze +
  fastResults: **~1.7s after speech onset to first emission, ~1s incremental
  cadence after**. qwen3 is ~0.8s first-emission — apple-speech is slower on
  the first word but competitive in steady-state, and brings word
  timestamps + Traditional-native zh-TW + ANE (no GPU contention with MLX
  MT). A plausible production backend for zh-TW, pending a CER number.
- **Caveats:** single mic run (utterance-dependent; the two levers were not
  isolated — both on by default); no zh CER measurement vs qwen3-1.7B's
  18.20 anchor yet.
- **For the simul-MT time-frontier (research):** per-word timestamps make
  apple-speech a THIRD candidate alongside nemotron (timestamps) and qwen3
  (no timestamps) for the AlignAtt commit-policy driver — see next-step #2
  in _work/COMPACTION_SURVIVAL.md. The improved first-emission makes it
  more viable there too.
- **Decision:** the spike's feasibility + latency questions are answered.
  A full WLK backend dispatch is now a real option — but should be driven
  by the zh CER measurement (needs a corpus run) + the time-frontier
  comparison (next-step #2), not dispatched blind.

## Code (the shim, build-clean)

`_work/sa-spike/spike_speechanalyzer.swift` — compiles `swiftc -O
-parse-as-library`. Key API facts (hard-won):
- `analyzeSequence(from: AVAudioFile)` — file mode; analyzer reads+converts
  itself (do NOT manual read/convert/slice — the slicer's `floatChannelData`
  is nil for the Int16 analyzer format → silent slices → "few words").
- Mic: contiguous timestamps in the ANALYZER frame domain (running counter,
  NOT hardware sampleTime — hardware-anchored overlaps: 1664fr@16k = 0.104s
  per 4800fr@48k = 0.100s chunk → SFSpeech Code=2 "timestamp overlaps").
- `SpeechTranscriber(locale:preset:)` — use `.progressiveTranscription` for
  volatile streaming; the default `.transcription` buffers (0 volatiles).
- `analyzer.prepareToAnalyze(in: fmt)` — preheat before feeding; cuts
  first-result startup. `Preset.reportingOptions` is settable — `.fastResults`
  is inserted there (SpeechTranscriber has no settable options in the preset
  form).
- analyzer format: `AVAudioCommonFormat(rawValue: 3)` = **Int16**, not Float64.
- `SpeechDetector(detectionOptions:reportResults:true)` — wired but inert.

## Play-now commands (captain, from Terminal.app)

```bash
cd ~/git/asr/WhisperLiveKit/_work/sa-spike
# file (full transcript, progressive streaming)
./sa-spike --locale zh-TW --preset progressive --file ~/git/asr/_work/zh_long.wav --fast | head
# mic (speak ~10s, Ctrl-C) — ~1.7s after speech onset, then ~1s cadence
./sa-spike --locale zh-TW --preset progressive
# A/B the buffering preset (0 volatiles) vs progressive
./sa-spike --locale zh-TW --preset transcription --file ~/git/asr/_work/zh_long.wav --fast | head
# A/B fastResults (--no-fast) for the first-emission latency
./sa-spike --locale zh-TW --preset progressive --no-fast
```

## WLK + lc_terminal wiring (prototype, 2026-09-21 late)

The apple-speech backend is wired into wlk as a subprocess wrapper:
- `_work/sa-spike/spike_speechanalyzer.swift` gained `--stdin`: wlk feeds raw
  float32 16k mono chunks; the shim converts to Int16 (same rate) and feeds
  the analyzer with contiguous timestamps; stdin EOF finishes + finalizes.
- `whisperlivekit/asr_apple_speech.py`: `AppleSpeechASR` (engine: config +
  `.sep` by locale) + `AppleSpeechOnlineProcessor` (per-session: spawns the
  shim, reader thread parses JSONL; **finals -> ASRTokens with real word
  timestamps**, volatiles -> get_buffer tail; finish() closes stdin + drains).
  Mirrors the nemotron processor contract exactly.
- Wired: `config.py` (apple_speech_locale/preset/spike fields), `core.py`
  (Models factory + online_factory), `parse_args.py` (--backend
  apple-speech + 3 flags), `scripts/lc_terminal.py` (--backend apple-speech
  + --apple-speech-locale/--apple-speech-spike).
- Prototype limitations (honest): VAD silence is not fed to the shim (wlk
  drops Silence chunks) — the analyzer sees speech-only audio and endpoints
  on intra-utterance silences; token times mapped via a running silence
  offset; hotwords (AnalysisContext) not yet exposed through the engine.
- The scorer `_work/sa-spike/bench_cer.py` VERIFIES against the board: it
  reproduces qwen3-1.7B's 18.20 from the recorded raw results (mean of
  per-sample CER, first-10 zh manifest samples, harness normalization, t2s
  on the Traditional hypothesis).

## What works from here (verified)

- macOS 26.6.2, Apple M4 — platform requirements met.
- `mac-speech-analyzer` PyPI wheel (0.1.2) ships a PREBUILT Swift dylib
  (`libmacspeechanalyzer_core.dylib`) — Python file-mode transcription
  WITHOUT any local Swift toolchain. Installed to /tmp/sa_pkg; loads clean.
- The wheel's API: `transcribe(path, locale=..., on_segment=...)`.

## The blocked path — diagnosis chain (evidence, not conjecture)

1. Every file format is rejected: `SFSpeechErrorDomain Code=3 "Audio
   format is not supported"` — tried: 16k/48k mono/stereo, 32-bit PCM and
   proper IEEE-f32 WAV (written with a hand-built format-3 RIFF header
   after finding that Python's wave module CANNOT write float32), and
   Apple-native m4a (afconvert AAC). Universal failure including en-US.
2. Full logging exposed the swallowed root cause: the dylib's locale
   resolution COLLAPSES to the fallback `en-Latn_ZZ` for every requested
   locale (zh-TW, zh-Hant-TW, zh-CN, yue-Hant-HK, en-US), then the locale
   ASSET DOWNLOAD FAILS — and the dylib swallows it
   (`catch { msaLog("so this failed...") }` in its core.swift). No assets
   -> no usable audio format -> the misleading Code=3.
3. Cross-check via the legacy API (pyobjc-framework-Speech):
   `SFSpeechRecognizer.supportedLocales()` = 63 locales with ZERO zh/yue —
   in this process. Combined with: the sandbox cannot even LIST
   /Applications/Xcode.app and has no reachable swift toolchain
   (`xcode-select` fails, CLT binaries exec-denied), the agent-safehouse
   sandbox is restricting the process's speech-subsystem and toolchain
   visibility. The same commands from Terminal.app (no sandbox) are the
   natural next step.

## Play-now commands (captain, from Terminal.app)

### A. File mode via simonw/speech-analyzer-cli (measurements + zh quality)

```bash
cd /tmp && git clone https://github.com/simonw/speech-analyzer-cli
cd speech-analyzer-cli && ./scripts/install.sh   # builds app bundle w/ TCC metadata
speech-analyzer --list-locales                    # verify zh-TW present
speech-analyzer --locale zh-TW --format json /Users/clkao/git/asr/_work/zh_long.wav > /tmp/sa_zh.json
speech-analyzer --locale en-US --format json /Users/clkao/git/asr/_work/demo_en_30s.wav > /tmp/sa_en.json
```

Read: full text in `.text`, per-word start/end/confidence in `.words`.
Check: (1) zh CER eyeball vs the known 鐳射 medical transcript; (2) script
variant — Traditional natively?; (3) word-timestamp density.

### B. Streaming shim (mic demo + volatile cadence + hotwords)

```bash
cd ~/git/asr/WhisperLiveKit/_work/sa-spike
swiftc -O spike_speechanalyzer.swift -o sa-spike
./sa-spike                          # mic, zh-TW, volatile dim / final bright JSONL
./sa-spike --file /Users/clkao/git/asr/_work/zh_long.wav            # paced file
./sa-spike --file .../zh_long.wav --fast                            # full-speed file
./sa-spike --context "鐳射,雷射,紋身" --file .../zh_long.wav          # hotword A/B
```

JSONL per event: `{"t": wall, "audio_t": sec, "type": "volatile"|"final",
"text", "range": [start,end], "runs": [[word, start, end], ...]}`.
Hotword A/B: run with and without `--context` — same test VibeVoice passed
(鐳射 homophone recovery).

### C. If speech-analyzer-cli's zh-TW is rejected

`--list-locales` is the authority (exact BCP-47 matching). If zh-TW is
absent there but present on iOS 26 reports, try `zh-Hant-TW` via the shim
(`--locale zh-Hant-TW`) and record the finding.

## Instrument provenance

- The shim embeds the VERIFIED-WORKING patterns from
  butthead0819-beep/marvin-voice-core macos_stt_v2.swift (zh-TW proven on
  macOS 26: 455ms/4s file, AssetInventory install path, AnalysisContext
  contextualStrings[.general] via analyzer.setContext) + WWDC25 session
  277 patterns (.volatileResults, .audioTimeRange) + the simonw CLI's
  app-bundle TCC approach for file mode.
- Key API facts confirmed from Apple docs (doc-json): bestAvailableAudioFormat
  is dynamic ("from assets installed on the device") — the missing-asset
  failure masquerading as a format error is a REAL failure mode to guard
  in any backend implementation (query the format, install assets
  explicitly, never swallow AssetInventory errors).

## Recommendation

A full WLK backend (apple-speech) remains justified ON PAPER (native
volatile/final = our dim/bright grammar; word timestamps = the time-frontier
input qwen3 lacks; ANE = no GPU contention with MLX MT; zh-TW locale).
CONFIRM with the two command blocks above before dispatching the backend
task. The numbers to bring back: zh/en transcript quality vs qwen3-1.7B's
18.20 zh CER anchor, first-final latency, volatile cadence, drain.

## Residual risks / unknowns

- zh-TW locale availability on THIS machine unverified (sandbox hid the
  list). `--list-locales` settles it in one command.
- Shim syntax unverified (no swiftc here) — expect small compile fixes.
- simonw CLI's zh-TW support: untested here (build blocked); its locale
  matching is exact-match, may need `zh-Hant-TW` form.
- The legacy-API 63-locale-no-zh observation could ALSO mean zh speech
  assets are simply not installed on this Mac; System Settings ->
  SpeechTranscription (or the shim's AssetInventory path) resolves it.
