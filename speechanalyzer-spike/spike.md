# SpeechAnalyzer streaming spike

## Status: BLOCKED-BY-SANDBOX for execution; instruments complete

The spike's runtime measurements could not execute from the agent sandbox.
The diagnosis chain below is itself a deliverable: it isolates exactly why,
and everything the captain needs to run the measurements in one command is
prepared. Re-dispatch or captain-side run is required for the numbers.

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
