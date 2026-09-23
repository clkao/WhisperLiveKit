# feat: Apple SpeechAnalyzer (`apple-speech`) ASR backend via the `apple-asr` package

Draft PR body for review. Target: `QuentinFuxa/WhisperLiveKit` `main`, from the fork,
branch `wlk/apple-speech-adapter` (cut from current `origin/main`). Not yet opened.

---

## Summary

Adds an `apple-speech` ASR backend that runs Apple's on-device SpeechAnalyzer stack
(macOS 26+) through the released **`apple-asr`** package. The in-tree file is a thin
adapter (~120 lines of logic) that implements WhisperLiveKit's `OnlineProcessor`
contract by delegating to `apple_asr.Stream` — push / pause_start / pause_end / poll /
close. No protocol code, no timing code, no Swift in this repo.

**Why it is a dependency and not an in-tree backend.** The stack is Swift-concurrency
native (actors, opaque `AsyncSequence` results, `finalize(through:)`); a faithful Python
binding is not practical, so the engine is a Swift shim behind a versioned JSONL
protocol, packaged separately. Keeping that out of this repo means no Swift toolchain
requirement here, no non-Python build step in CI, and a single implementation to fix
rather than two. Installing the extra pulls the released package.

## What it gives you

| | |
|---|---|
| zh CER (FLEURS, first-10 protocol) | **13.19** streaming / **11.23** accurate vs best MLX backend 18.20 |
| en WER (same protocol) | **13.94** streaming / **9.51** accurate vs 19.27 |
| volatile partials | yes (the dim/bright grammar maps directly) |
| per-word timings | yes — real word runs on finals |
| compute | the Neural Engine in a system process: **zero GPU memory**, no contention with the MT model |
| script | Traditional-native zh-TW (no conversion needed on the display path) |

Measured against the project's own golden fixture on the same audio: **12 committed
segments vs the golden's 12**, first commit 3.24 s vs 2.99 s, mean gap 2.69 s vs 2.97 s,
every segment carrying a translation.

## What changes here

- `whisperlivekit/asr_apple_speech.py` — the adapter (replaces the earlier prototype that
  carried its own shim and timing logic).
- Registration in `config.py` (`apple_speech_locale`, `apple_speech_mode` +
  `APPLE_SPEECH_LANGUAGES` validation), `core.py` (factory + session-language rejection),
  `parse_args.py` (`--apple-speech-locale`, `--apple-speech-mode`),
  `backend_support.py` (availability gate delegating to the package's own gate),
  `benchmark/compat.py` (`BACKEND_LANGUAGES` entry), `pyproject.toml` (the
  `[apple-speech]` extra) and `uv.lock`.
- `tests/test_apple_speech_adapter.py` + a small vendored fake shim, so the adapter's
  nine tests run in any install with **no skips** and need no macOS 26, no Speech and no
  toolchain.
- Net diff: **+557 / −753** (it deletes more than it adds).

## Requirements and limits (stated plainly)

- **macOS 26+ only**, checked at runtime; the backend is not offered elsewhere and other
  backends are unaffected.
- Installing the extra from git or source **compiles the shim once** (`swiftc`, Xcode
  command-line tools). Installing instead from the package's release wheel
  (`apple_asr-0.1.2-py3-none-macosx_26_0_arm64.whl`, attached to the `v0.1.2` release)
  needs **no toolchain at all**; that wheel is platform-tagged so it cannot install where
  it cannot run.
- The first commit is **pause-bound**: the transcriber commits when it sees a pause
  (≈0.1 s into one, measured), which is what makes the cadence match the golden. A
  speaker who never pauses waits for a flush; a `commit_interval` ceiling exists but is
  off by default because it cut mid-phrase and corrupted text in testing.
- A caller whose VAD strips silence (WhisperLiveKit does) must tell the adapter about the
  pause (`pause_start`/`pause_end`), because the transcriber's endpointer needs the
  silence. The adapter synthesizes it; the behaviour is a declared capability, documented
  in the package.
- `SpeechDetector` (VAD sensitivity) is exposed but was inert in testing.
- Per-session language switching is not supported: the locale is fixed per session, and a
  session requesting a different language fails explicitly.
- MT chunking differs from the golden fixture (`translation_final` 12 vs 6): this backend
  translates each committed source segment, where the golden coalesced pairs. Source
  cadence is identical; flagged as an open difference rather than a claim of parity.

## Testing

- `tests/test_apple_speech_adapter.py` — 9 tests, 0 skips, using a vendored fake shim
  (protocol v1) so they run without Speech or a toolchain. The canonical fake shim lives
  in the `apple-asr` project; this double keeps the PR self-contained. Each guard test was
  mutation-checked (breaking the pause-final collection and the per-word mapping each
  fail the corresponding test).
- `tests/test_backends.py`, `tests/test_silent_backend_guard.py` — green.
- End-to-end: `scripts/lc_terminal.py --backend apple-speech --source file --audio <clip>`
  renders phrase-level committed source lines each with its translation; the event log
  matches the golden's segment count.
- The package's own suite (transport, clock, protocol, 70 tests) covers the layer this
  adapter delegates to.
- Reproducing the measurements: the package ships a real-time replay driver and the
  baseline harness used for the CER/WER numbers above.

## Evidence and instruments

The board numbers use the same first-10 FLEURS samples, normalization and mean-per-sample
aggregate as the project's existing MLX comparison; the scoring path was anchored by
reproducing that comparison's own recorded results before scoring anything new.
