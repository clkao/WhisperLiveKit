# feat: Apple SpeechAnalyzer (`apple-speech`) ASR backend via the `apple-asr` package

Draft PR body for review. Target: `QuentinFuxa/WhisperLiveKit` `main`, from the fork.
Branch **`apple-speech-backend`**, cut from `origin/main` @ `363e4f6` (3 commits).
Not yet pushed, not yet opened.

---

## Summary

Adds an `apple-speech` ASR backend that runs Apple's on-device SpeechAnalyzer stack
(macOS 26+) through the released **`apple-asr`** package. `whisperlivekit/asr_apple_speech.py`
is a thin adapter (~230 lines with docstrings, no timing logic) that implements the
`OnlineProcessor` contract by delegating to `apple_asr.Stream` — push / pause_start /
pause_end / poll / close.

**Why a dependency rather than an in-tree engine.** The stack is Swift-concurrency native
(actors, opaque `AsyncSequence` results, `finalize(through:)`), so the engine is a Swift
shim behind a versioned JSONL protocol, packaged separately. Keeping it out of this repo
means no Swift toolchain in this project's CI and no non-Python build step here — and one
implementation to maintain rather than two.

**Shape of the diff: purely additive — 10 files, +1093 / −2.** One new backend module, its
registration, its tests, and an extra. Nothing upstream is deleted or restructured.

## What it gives you

| | |
|---|---|
| zh CER (FLEURS, first-10 protocol) | **13.19** streaming / **11.23** accurate vs best MLX backend 18.20 |
| en WER (same protocol) | **13.94** streaming / **9.51** accurate vs 19.27 |
| volatile partials | yes |
| per-word timings | yes — real word runs on finals |
| compute | the Neural Engine in a system process: **no GPU memory**, no contention with the MT model |
| script | Traditional-native zh-TW |

On the project's own golden audio the adapter produces **12 committed segments against the
golden's 12** (first commit 3.6 s vs 2.99 s, mean gap 2.66 s vs 2.97 s), every segment
carrying a translation.

## Files

```
whisperlivekit/asr_apple_speech.py            +227   the adapter (new)
whisperlivekit/config.py                       +31   locale/mode fields + language validation
whisperlivekit/core.py                         +26   engine factory + online_factory branch
whisperlivekit/parse_args.py                   +15/-2  --apple-speech-locale/--apple-speech-mode
whisperlivekit/backend_support.py              +45   availability gate (delegates to the package)
whisperlivekit/benchmark/compat.py             +10   BACKEND_LANGUAGES entry + probe
pyproject.toml                                 +11   [apple-speech] extra
uv.lock                                        +16/-1 (regenerated for the extra)
tests/test_apple_speech_adapter.py            +257  9 tests, 0 skips
tests/fixtures/apple_speech_fake_shim.py      +457  a minimal protocol-v1 double
```

## Requirements and limits (stated plainly)

- **macOS 26+ only**, checked at runtime; the backend is not offered elsewhere and other
  backends are unaffected.
- Installing the extra from git or source **compiles the shim once** (`swiftc`, Xcode
  command-line tools). Installing instead from the package's release wheel
  (`apple_asr-0.1.2-py3-none-macosx_26_0_arm64.whl` on the `v0.1.2` release) needs **no
  toolchain**; that wheel is platform-tagged so it cannot install where it cannot run.
- The first commit is **pause-bound** — the transcriber commits roughly 0.1 s into a pause,
  which is what makes the cadence match. A speaker who never pauses waits for a flush; a
  `commit_interval` ceiling exists but defaults to off because it cut mid-phrase and
  corrupted text in testing.
- A caller whose VAD strips silence (as this project's does) must announce pauses
  (`pause_start`/`pause_end`), because the transcriber's endpointer needs the silence; the
  adapter synthesizes it. Declared as a capability in the package.
- **Commit cadence depends on the pipeline's pause segmentation.** Driving the adapter
  through this repo's own `TestHarness` on `origin/main`, the default pipeline aggregates
  the utterance into a single output line while the adapter still emits its 12 commits —
  a segmentation-policy difference in the default pipeline, not in the adapter.
- MT chunking differs from our earlier golden fixture (`translation_final` 12 vs 6): each
  committed source segment is translated, where the golden coalesced pairs. Source cadence
  is identical; flagged as an open difference, not claimed parity.
- `SpeechDetector` (VAD sensitivity) is exposed but was inert in testing.
- No per-session language switching: the locale is fixed per session, and a session
  requesting a different language fails explicitly.

## Testing

- `tests/test_apple_speech_adapter.py` — 9 tests, **0 skips**, driving the adapter through a
  minimal vendored protocol-v1 double (`tests/fixtures/apple_speech_fake_shim.py`), so they
  need no macOS 26, no Speech, and no toolchain. They run in CI like any other test. Each
  guard was mutation-checked: breaking the pause-final collection and the per-word mapping
  each fail the corresponding test. The canonical fake shim lives in the `apple-asr`
  project's own suite; this double exists so the PR is self-contained.
- `tests/test_backends.py`, `tests/test_silent_backend_guard.py` — green.
- `uv lock --check` passes (including `--python 3.12`); `ruff check .` is clean on this base.
- The delegated layer (transport, protocol, clock, 70 tests) is covered by the package's own
  suite.

## Evidence for the numbers above

Same first-10 FLEURS samples, normalization and mean-per-sample aggregate as the project's
existing MLX comparison. The scoring path was anchored by reproducing that comparison's own
recorded results before scoring anything new. The package ships a real-time replay driver
and the baseline harness used for these measurements, so both are reproducible.
