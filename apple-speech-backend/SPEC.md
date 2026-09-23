# apple-asr — interface spec (v1, draft for the first build order)

Status: design freeze candidate. Written by the FO from the working prototype
(`whisperlivekit/asr_apple_speech.py` + `_work/sa-spike/spike_speechanalyzer.swift`),
the live-path findings, and the prior-art review (`mac-speech-analyzer` is
file-only with finalised segments; `macos-stt`/`macstt`/pyobjc are the legacy
`SFSpeechRecognizer` stack). This spec is the thing order 1 builds against.

Decisions marked **[C]** are the captain's to confirm; everything else is the
FO's recommendation and can be changed by the builder with a note.

---

## 1. Purpose and scope

Streaming, on-device speech-to-text for macOS 26+ from Python, on Apple's
SpeechAnalyzer stack (SpeechTranscriber), with:

- **live/streaming** operation (fighting the incumbent's file-only scope),
- **volatile partials** as well as finalized segments (dimmable UI layer),
- **per-word timings** on finals (word-level alignment for caption/MT pipelines),
- **push-based audio** so external pipelines own capture and pacing,
- **pause-aware commits** so a pipeline that strips silence still gets
  phrase-cadence commits.

**Non-goals (v1):**

- A faithful binding of the Speech framework's type graph. No `SpeechTranscriber`,
  `SpeechModule`, `SpeechAnalyzer.Options`, `CMTime` mirrors in the public API.
- Per-session language switching. The locale is fixed at `Stream` construction;
  a second locale is a second `Stream`.
- Speaker diarization, translation, audio capture policy, file decoding beyond
  what the framework accepts.
- Windows/Linux. macOS 26+ only; refuse clearly elsewhere (§8).

## 2. Identity [C]

- Distribution name (proposed): **`apple-asr`**. Alternatives: `apple-speech-stream`,
  `speechanalyzer-stream`. Constraint: the PyPI namespace already holds
  `mac-speech-analyzer`, `macos-stt`, `macstt` — the name should read as
  *streaming*, not as another file transcriber.
- Import name: **`apple_asr`**.
- License: MIT (matches the incumbent and the ecosystem).
- Python: **>= 3.10**. Runtime deps: **numpy only** (plus stdlib).
  `opencc` only for the optional zh scoring extra, never for the library.
- Home/repo: separate from WhisperLiveKit. **[C]** — flagged because by the
  workflow-fit rule a standalone package does not belong in the WLK workflow.

## 3. Public API

### 3.1 Module surface

```python
from apple_asr import (
    Stream,                 # the session object
    Partial, Final, Word,   # event types (dataclasses, frozen)
    Ended, Error,           # terminal events
    list_locales,           # -> Locales(installed=[...], supported=[...])
    ensure_installed,       # (locale) -> None; raises AssetUnavailable
    shim_info,              # -> ShimInfo(path, version, protocol, build)
    PROTOCOL_VERSION,       # int
    # exceptions
    AppleAsrError, UnsupportedPlatform, ShimUnavailable, AssetUnavailable,
    ProtocolMismatch, SessionClosed, BackendError,
)
```

### 3.2 Session object

```python
class Stream:
    def __init__(
        self,
        locale: str = "en-US",           # BCP-47; validated against list_locales()
        *,
        preset: Literal["progressive", "transcription",
                        "timeIndexedProgressive"] = "progressive",
        context: Sequence[str] = (),      # AnalysisContext.contextualStrings (hotwords)
        pause_commit: float = 0.08,       # seconds of quiet before a pause commits
        commit_interval: float = 0.0,     # 0 = pause-only commits (measured best)
        confidence: bool = True,          # request per-run confidence when available
        shim: str | None = None,          # explicit shim path; else resolution order
        stderr: Literal["capture", "inherit", "null"] = "capture",
        queue_size: int = 256,            # bounded pending-final queue
    ) -> None: ...

    # lifecycle
    def prepare(self) -> None: ...        # prepareToAnalyze: warm the model
    def close(self) -> None: ...          # graceful: EOF + drain + terminate
    def __enter__/__exit__: ...           # close() on exit

    # input
    def push(self, pcm: np.ndarray) -> None:
        """float32 or int16, 1-D or (n,1); resampled by the caller to 16 kHz.
        Raises if the format is wrong or the stream is closed."""
    def pause_start(self) -> None: ...    # caller detected a VAD pause
    def pause_end(self, duration_s: float) -> None: ...  # ...and it ended

    # control
    def flush(self, through_s: float | None = None) -> None:  # finalize(through:)
    @property
    def audio_time(self) -> float: ...    # session clock: the caller's declared timeline

    # output
    def events(self) -> Iterator[Event]: ...        # blocking iterator
    async def aevents(self) -> AsyncIterator[Event]: ...  # asyncio bridge
    def poll(self, timeout_s: float = 0.0) -> list[Event]: ...  # non-blocking bulk

    # observability
    @property
    def stats(self) -> Stats: ...          # partials, finals, words, dropped, bytes
```

Notes:

- **Two input modes, both first-class.** A caller that has continuous audio
  (including silence) uses `push()` alone — pauses are real and the framework
  handles them. A caller whose upstream VAD strips silence (WhisperLiveKit does)
  uses `push()` for active audio plus `pause_start()`/`pause_end(d)`; the client
  synthesizes that silence for the framework at the audio rate. The second mode
  is why `pause_commit` exists and must be documented as such — it is not a hack
  hidden in the client, it is a declared capability.
- `push()` accepts int16 as a convenience (the framework's analyzer format is
  Int16 on macOS 26) but the canonical input is float32; conversion is defined
  as clamp-and-scale, no dithering.
- `events()` blocks; `poll()` never does; `aevents()` wraps the reader thread's
  queue for asyncio consumers. All three drain the same underlying stream and
  must not be mixed on one instance (assert).

### 3.3 Event types

```python
@dataclass(frozen=True)
class Word:
    text: str
    start: float           # seconds, session clock
    end: float
    confidence: float | None = None

@dataclass(frozen=True)
class Partial:             # volatile: text may be revised or replaced
    text: str
    start: float | None    # the range the partial covers, when known
    end: float | None
    words: tuple[Word, ...] = ()   # usually empty for partials

@dataclass(frozen=True)
class Final:               # committed, never revised for its range
    text: str
    start: float
    end: float
    words: tuple[Word, ...]
    reason: Literal["pause", "interval", "flush", "eof"] = "pause"

@dataclass(frozen=True)
class Error:
    message: str
    detail: str = ""

@dataclass(frozen=True)
class Ended:
    reason: Literal["closed", "shim_exit", "protocol_error"]
```

Semantics that must hold (and are testable):

- Later `Partial`s for the same range supersede earlier ones; consumers replace,
  never append.
- `Final` ranges never overlap and are never revised (so concatenating finals
  yields the transcript).
- `Final.reason` tells the caller *why* the commit landed — this is the
  observability that made the live latency debuggable and must survive.
- Timestamps are monotonic, in seconds, on a session clock that starts at 0
  and advances with the audio the **caller declares**: every pushed sample plus
  the pause durations reported at `pause_end(d)`, which advance the clock by
  exactly `d`. This is the caller's own VAD timeline, so it is the timeline every
  reported timestamp is on. (Amendment, v0.1.3: the clock was previously
  specified as advancing "with consumed audio (including synthesized pauses)".
  The client synthesizes the pause silence for the shim and may hold a pause
  open past the `d` it reports while it waits for a final, so the shim's
  consumed-audio timeline legitimately runs longer than the caller's; the
  declared timeline is compressed out of it and is the contract. See "Clock
  ownership" below and `SessionClock`.)

## 4. Shim CLI contract

The shim is a standalone executable and is also the package's engine.

```
apple-asr-shim --stdin [--locale L] [--preset P] [--context "a,b,c"]
               [--pause-commit S] [--commit-interval S] [--vad-sensitivity off|low|medium|high]
               [--fast] [--no-volatile]
apple-asr-shim --file PATH [...]      # batch: reads the file itself
apple-asr-shim --mic [...]            # self-captured microphone (needs mic TCC)
```

- Modes are mutually exclusive; `--stdin` is the mode the package uses.
- Exit 0 on clean EOF after finalization; nonzero with a diagnostic on stderr
  otherwise. The package treats a nonzero exit while a session is open as
  `BackendError` and surfaces the stderr tail.
- The shim must never exit silently mid-session.

## 5. Wire protocol (transport v1 — internal, not public API)

Channels:

| channel | direction | encoding |
|---|---|---|
| stdin (fd 0) | Python → shim | raw PCM, float32 LE, mono, 16 kHz (negotiated in `hello` as Int16 at the framework's analyzer format; the shim converts) |
| stdout (fd 1) | shim → Python | JSONL events, one object per line, flushed per event |
| stderr (fd 2) | shim → Python | human diagnostics (progress, commit decisions, errors) |
| control (fd 3) | Python → shim | JSONL commands, one object per line |

`hello` is the **first line** on stdout, always, before any audio is accepted:

```json
{"type":"hello","protocol":1,"shim_version":"0.1.0",
 "locale":"zh-TW","preset":"progressive",
 "format":{"sample_rate":16000,"channels":1,"common_format":"int16"},
 "capabilities":["volatile","word_runs","pause_commit","flush","context"],
 "reporting_options":["volatileResults","fastResults"]}
```

The client:
- refuses to proceed unless `protocol == PROTOCOL_VERSION` (`ProtocolMismatch`,
  naming both versions);
- refuses if the format is not the negotiated one;
- logs `capabilities` and degrades explicitly (never silently).

Events:

```json
{"type":"partial","text":"我們今天來","range":[0.0,2.94],"runs":[]}
{"type":"final","text":"我們今天來討論鐳射在醫學上的應用","range":[0.0,3.23],
 "runs":[["我們",0.0,0.5],["今天",0.5,1.1],...],"reason":"pause"}
{"type":"commit","through":3.23,"reason":"pause","wall":1.42}
{"type":"error","message":"...","detail":"..."}
{"type":"ended","reason":"eof"}
```

- `runs` is `[[word, start, end], ...]` in seconds, session clock; `[]` is legal.
- `commit` is an acknowledgement the shim emits when it acts on a finalize
  decision (from its own pause detection or from a `flush` command). The client
  uses it for `flush()` acknowledgement and for `Final.reason`.
- Unknown event types must be ignored with a warning, not a crash (forward
  compatibility within a protocol version).

Commands (fd 3):

```json
{"cmd":"prepare"}
{"cmd":"finalize","through":12.3}     // null/missing = through the current cursor
{"cmd":"context","strings":["鐳射"]}   // live hotword update
{"cmd":"close"}                        // graceful: finalize + end of input
```

Rules:
- Commands are processed in order; each `finalize` produces exactly one `commit`.
- `close` is idempotent; stdin EOF is equivalent to `close`.
- The client must not write commands after `close` (or after EOF).

Clock ownership (must be documented in the README, because it is the subtle part):
the shim owns its own audio timeline (frames written = its clock), which is
longer whenever the caller holds a pause open past the `d` it reports (the
pre-roll and the silence pump keep writing while the caller waits for the
transcriber's final). The session clock is the **caller's declared timeline**:
`pause_end(d)` advances it by exactly `d` and re-anchors unconditionally, so the
section after the pause runs 1:1 from the caller's cursor and the over-delivered
silence is compressed out of every later timestamp rather than carried into it.
The client maps shim time → session time with that boundary-anchored anchor
(refreshed at every `push()` / `pause_start()` / `pause_end(d)`); a final already
published mid-pause was mapped on the pre-pause line, so its start is clamped up
to the previous final's end to keep the published ranges monotone and
non-overlapping. Any future transport (C ABI, shared memory) must preserve the
§3.3 semantics, not the wire format.

## 6. Shim resolution, build, and packaging

Resolution order for the executable (first hit wins):

1. `Stream(shim=...)` / `--shim`
2. `APPLE_ASR_SHIM` env
3. the package cache: `~/.cache/apple_asr/<shim_version>/apple-asr-shim`
   (mirrors the `~/.cache/whisperlivekit/...` precedent)
4. `apple-asr-shim` on `PATH`
5. build-on-demand into the cache if a Swift toolchain is present
6. otherwise `ShimUnavailable` with the exact build command in the message

Packaging:
- The Swift source ships as package data (`apple_asr/shim/speechanalyzer.swift`);
  the binary is never committed.
- A build helper (`python -m apple_asr.build`) compiles via `swiftc -O
  -parse-as-library`, validates by asking the built shim for `hello`, and
  prints the resolved path.
- `shim_version` participates in the cache path so upgrades rebuild cleanly.
- **[C]** Preferred distribution: publish **macOS-26-arm64 wheels with the shim
  prebuilt** (a release job per tag; CI needs a macOS 26 runner) so users need
  no toolchain. Fallback: source distribution + build-on-demand. This is the
  single biggest ergonomic win over the incumbent and it is impossible inside a
  WhisperLiveKit PR — the reason the package comes first.

## 7. Capability map (exposed vs deliberately not)

| framework capability | v1 exposure |
|---|---|
| locale / preset | `Stream(locale=, preset=)` |
| volatile results | always on; `Partial` events |
| word timings (`audioTimeRange`) | `Final.words` |
| confidence (`transcriptionConfidence`) | `Word.confidence` when present |
| `AnalysisContext.contextualStrings` | `Stream(context=...)` + `{"cmd":"context"}` |
| `prepareToAnalyze` | `Stream.prepare()` |
| `finalize(through:)` | `Stream.flush()` |
| `finalizeAndFinishThroughEndOfInput` | `close()` / stdin EOF |
| `AssetInventory` (status/install) | `list_locales()`, `ensure_installed()` |
| `SpeechDetector` | `--vad-sensitivity`; documented **inert** in the prototype |
| `SpeechAnalyzer.Options` (priority, retention) | not exposed; internal defaults |
| module composition, per-session locale, `CMTime` | not exposed (non-goals) |

## 8. Platform gating and errors

- `UnsupportedPlatform` when `sys.platform != "darwin"` or macOS < 26
  (read via `platform.mac_ver()`), message naming the requirement.
- `ShimUnavailable` when §6 resolution fails, message containing the build command.
- `AssetUnavailable` from `ensure_installed()` when the locale cannot be installed
  or reserved.
- `ProtocolMismatch`, `SessionClosed`, `BackendError` as above.
- Every raise must be actionable: what failed, which version/path/locale, and the
  next command to run. No silent degradation anywhere.

## 9. Test plan (this is the acceptance bar for order 2)

Runs on any OS, no Speech, no macOS 26 — via a **fake shim** (a scripted JSONL
emitter shipped in `tests/fixtures/`, driven by a scenario file):

1. Handshake: accept matching protocol; refuse a mismatch naming both versions.
2. Event mapping: partials supersede; a final's runs become `Word`s with the
   documented clock mapping; `Final.reason` is propagated from `commit`.
3. Pause synthesis: `pause_start`/`pause_end(d)` produce `d` seconds of
   synthesized silence (frame count asserted) and a commit lands within
   `pause_commit + epsilon` of `pause_start` — the live-latency regression test.
4. Flush semantics: `flush(through=t)` emits exactly one `commit`; `flush()`
   uses the cursor; finals carry `reason="flush"`.
5. Close/EOF: `close()` is idempotent, drains pending finals, terminates the
   child, and yields `Ended(reason="closed")`; stdin EOF yields `reason="eof"`.
6. Failure paths: shim exits nonzero mid-session → `BackendError` with the stderr
   tail; a malformed line → warning, not a crash; a silent shim with audio
   pushed → the silent-backend guard fires (no `Final` and no `Partial` after N
   seconds of audio must raise, not hang).
7. Backpressure: a burst exceeding `queue_size` drops oldest with `stats.dropped`
   counted and one warning.
8. `List_locales`/`ensure_installed` parse real shim output (fake shim variants).
9. Platform gate: simulated non-darwin / macOS 25 → `UnsupportedPlatform`.

macOS-26 `skipif` integration tests (order 2, optional but wanted):
10. `--file` on a bundled short clip: finals ≥ 1, word runs present, timestamps
    monotonic, and the cadence compared against the WLK golden fixture
    (`tests/golden/zh_long_ideal.jsonl`) on the same audio.
11. Live-pattern replay: the real-time driver ported from
    `_work/sa-spike/drive_live.py` (active audio via `push`, pauses via
    `pause_start`/`pause_end`) asserts each commit lands within ~0.3s of its pause
    start — the end-to-end version of test 3.

## 10. Known limitations to declare in the README (not to fix in v1)

- macOS 26+ only; the framework is not available earlier.
- The synthesized-pause mode simulates audio the caller's VAD discarded; the
  analyzer's timeline then carries that silence. Preferred upstream fix (offered
  as a follow-up, not v1): a WhisperLiveKit-side capability flag so silence is
  fed through and this mode becomes unnecessary.
- First commit is pause-bound; a speaker who never pauses commits at
  `commit_interval` (default off — measured to cut mid-phrase and corrupt text).
- Commits depend on the framework's own endpointer accepting a pause as an
  utterance boundary; `flush()` is the escape hatch, not a mid-phrase force-cut.
- `SpeechDetector` VAD sensitivity is exposed but was inert in the prototype.

## 11. Work split (dispatchable orders)

**Order 1 — package skeleton, transport, API, packaging** (the acceptance
criteria are §3–§8):
1. New repo/package layout, pyproject, license, CI matrix (ubuntu py3.10-3.13 for
   the fake-shim tests; macOS 26 job for the integration tests).
2. Move+rename the Swift shim to `apple_asr/shim/speechanalyzer.swift`; add
   `hello`, the `commit`/`error`/`ended` events, the fd-3 command channel, and
   the `--stdin` pause-synthesis collaboration points. Keep `--file`/`--mic` modes.
3. Implement `apple_asr` (§3) over the protocol (§5): subprocess manager, reader
   thread, bounded queue, typed events, exceptions, gating, stats, the build
   helper, and shim resolution (§6).
4. Rename the CLI binary `sa-spike` → `apple-asr-shim`; keep the flags.
5. Port the instruments: the real-time driver → `apple_asr.replay` / a console
   script; the CER/WER harness → a console script (its `opencc` dep behind an extra).

**Order 2 — tests + docs** (§9, plus README/API docs, the mermaid channel
diagram, and the declared limitations of §10).

**Order 3 — integration (optional, after 1+2):** the thin WhisperLiveKit adapter
+ PR (import + `compat`/`config`/`core`/`parse_args`/`backend_support` entries),
or skip if our own products consume the package directly.

## 12. Open decisions for the captain

1. Package name + home + license confirmation (§2).
2. Prebuilt wheels vs source+build-on-demand (§6) — I recommend wheels.
3. Whether order 3 (the WLK adapter/PR) happens at all, or the package stands alone.
4. Whether to file the upstream bug report against `mac-speech-analyzer`
   (locale collapse → asset install failure → `Code=3`, observed here) as a
   small side order.
