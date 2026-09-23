# Order 3 design — retiring the WhisperLiveKit prototype into a thin adapter

Status: design note (not dispatched). Depends on order 2 landing and the package being
installable (PyPI or a pinned git URL).

## Why this order exists at all

The shim has forked. Two live copies exist:

| | WhisperLiveKit in-tree (committed `6b2112a`, fixes `2eaa7ae`/`12d4100`) | `apple-asr` package |
|---|---|---|
| shim | `_work/sa-spike/spike_speechanalyzer.swift` (432 lines), no handshake | `src/apple_asr/shim/speechanalyzer.swift` (703 lines), versioned `hello` + `commit`/`error`/`ended` + fd-3 commands |
| processor | `whisperlivekit/asr_apple_speech.py` — own pump, pre-roll, drift map | `apple_asr.Stream` — same behaviour, now inside the package with tests |
| protocol | old: bare `volatile`/`final` lines | v1: handshake, ack'd `flush()`, capability list |

They can no longer talk to each other. Maintaining both means every future fix lands twice,
and the in-tree copy is already the weaker one (no handshake, no `commit` ack, no live
`context`, no confidence in `runs`, no tests).

## Target shape

`whisperlivekit/asr_apple_speech.py` becomes a **thin adapter** that owns no protocol and no
timing logic. It implements WLK's `OnlineProcessor` contract by delegating to `apple_asr`:

| WLK contract | `apple_asr` |
|---|---|
| `insert_audio_chunk(pcm, stream_end)` | `Stream.push(pcm)` |
| `start_silence()` | `Stream.pause_start()`, then return the finals collected within the bounded window as the commit tokens (WLK commits `start_silence`'s return value) |
| `end_silence(d, offset)` | `Stream.pause_end(d)` |
| `process_iter(is_last)` | `Stream.poll(0)` → map `Final` → `ASRToken`s; keep `Partial` for `get_buffer()` |
| `get_buffer()` | `Transcript` from the latest `Partial` (and its range) |
| `finish()` | `Stream.close()` + drain remaining events |
| `new_speaker()` | no-op (returns `([], audio_end)`) |
| `asr.sep` | `""` for zh/ja/ko/yue, `" "` otherwise (unchanged) |
| `heard_speech` | set on the first event (watchdog disarm) |

Everything the in-tree version got wrong or hard-coded — the silence pump, the pre-roll, the
drift→session-clock mapping, the pause-onset token collection, the final-range invariants —
lives in the package now, with tests. The adapter should be ~120 lines with no timing code,
and the deleted WLK-side pump/preroll/drift is net-negative code.

## Registration changes in WhisperLiveKit

Small and mechanical, mirroring how `voxtral-mlx` / `nemotron-mlx-asr` are wired:

1. `config.py` — keep `apple_speech_locale`, rename/add `apple_speech_mode`
   (`streaming|accurate`), drop `apple_speech_spike` (resolution belongs to the package),
   add `APPLE_SPEECH_LANGUAGES` + validation (follow `FUNASR_LANGUAGES`).
2. `core.py` — the `Models` factory constructs the adapter from config; `online_factory`
   returns the adapter's processor. Session-language mismatch raises explicitly (as funasr does).
3. `parse_args.py` — `--backend apple-speech` + `--apple-speech-locale` / `--apple-speech-mode`.
4. `backend_support.py` — `apple_speech_backend_available()` delegates to the package's own
   platform/shim gate so the two can never disagree.
5. `benchmark/compat.py` — `BACKEND_LANGUAGES["apple-speech"]` + the availability probe, so
   the harness can run it.
6. `pyproject.toml` — an `[apple-speech]` extra: `apple-asr>=0.1,<0.2` (macOS-26-only
   dependency gated at runtime, not at install).

## Deletions in the adapter PR

- `whisperlivekit/asr_apple_speech.py`'s pump/drift/approval logic (replaced by delegation).
- The WLK-tree Swift copy + its build instructions (`_work/sa-spike/`), and any doc line
  telling users to build a shim inside the WLK checkout. One shim source, in one repo.
- Keep `bench_cer.py` + `drive_live.py`: they are the *evidence* instruments and they belong
  with the board protocol they implement. (Their package-side equivalents ship in `apple-asr`;
  the WLK copies stay as the board-protocol implementations.)

## Acceptance for order 3 (verification, not assertion)

1. **Cadence equivalence**: the golden comparison re-run through the adapter on `zh_long.wav`
   — expect the same 12 finals / first commit ≈3.5 s / mean gap ≈2.55 s as the in-tree
   version measured (if it differs, the adapter is losing or duplicating commits).
2. **Live path**: `scripts/lc_terminal.py --backend apple-speech --source file` renders
   phrase-level committed lines with translations, i.e. not the one-big-chunk regression.
3. **WLK test bar**: `tests/test_backends.py` + `tests/test_silent_backend_guard.py` green,
   plus a new adapter test using the package's fake shim (no Speech needed).
4. **Unsupported host**: `--backend apple-speech` on a non-macOS-26 host gives the gate's
   message, not an import error.
5. **Live ja/zh mic** on the captain's machine — the last behavioural check, shared between
   the package and the adapter.

## Open questions for the captain

1. Ship order 3 at all? If our products (terminal/overlay) consume `apple-asr` directly, the
   WLK backend is optional. The argument for doing it: the upstream PR becomes ~150 lines
   wrapping a released dependency, instead of a 900-line in-tree backend with a toolchain
   story — and WLK users get the backend without a fork.
2. If yes: does the adapter PR also delete the WLK-tree shim copy (recommended), or leave it
   as a documented fallback for one release cycle?
3. PyPI first or a pinned git URL for the PR? (PyPI is cleaner for review; a git URL avoids
   publishing before the live verification is signed off.)
