# feat: Apple SpeechAnalyzer (`apple-speech`) ASR backend via the `apple-asr` package

PR body for review. Target: `QuentinFuxa/WhisperLiveKit` `main`, from the fork.
Branch **`apple-speech-backend`**, cut from `origin/main` @ `363e4f6`, **17 commits**.
Not yet pushed, not yet opened.

---

## Summary

Adds an `apple-speech` ASR backend that runs Apple's on-device SpeechAnalyzer stack
(macOS 26+) through the released **`apple-asr`** package. `whisperlivekit/asr_apple_speech.py`
(329 lines) is an adapter: it implements the `OnlineProcessor` contract by delegating to
`apple_asr.Stream` — `insert_audio_chunk` / `start_silence` / `end_silence` / `process_iter` /
`get_buffer` / `finish` / `close`. It carries **no protocol or recognizer logic of its own** —
the Swift shim, the JSONL wire protocol, the pause synthesis and the session clock live in the
package — but it does own two bounded timing policies, described below: the pause-collection
window in `start_silence()` and the drain deadline in `finish()`. Availability is gated by `backend_support.require_apple_speech_backend()`, which
delegates to the package's own platform and shim gates, so the two can never disagree.

The adapter's behaviour as shipped:

- **Pause collection hold — `_PAUSE_COLLECT_S = 0.12 s` (tuned down from 0.30 s).**
  `start_silence()` returns the pause's final because WLK *commits that return value* and its
  transcribe loop is starved while a pause is open (the VAD strips silence), so the pause's
  final must be collected inside `start_silence()` to land *during* the pause rather than when
  the speaker resumes. 0.12 s covers the package's pre-roll (`_PAUSE_PREROLL_MIN_S = 0.10` at
  `pause_commit = 0.08`) instead of padding past it; a final that arrives later is no longer
  stranded, because the pipeline polls during the pause (see the shared-core item below).
  Measured effect of the retune: pause-commit latency mean **0.303 s → 0.127 s**, per-pause
  over-delivery mean **0.117 s → 0.028 s**.
- **The measured defaults are unchanged:** `pause_commit = 0.08 s`, `commit_interval = 0.0`
  (an interval commit cut mid-phrase and corrupted text in testing), `mode = "streaming"`.
- **Declared-timeline clock, no remapping.** `apple_asr` reports its session clock on the
  **caller's declared timeline**: every pushed sample plus exactly the silence durations
  reported at `pause_end(d)` (the 0.1.3 clock contract: `d` advances the clock by exactly `d`,
  with a forced reanchor at each input boundary and a monotone `Final.start` clamp). The
  adapter keeps `_audio_end` on that same timeline (`insert_audio_chunk` records the stream end;
  `end_silence` adds exactly `silence_duration`), so committed token times need no remapping.
  `get_buffer()` **clamps the volatile partial** to `_audio_end`: a partial published while a
  pause is open is mapped on the pause-onset anchor line and can read ahead by that pause's
  over-delivered silence (which the package compresses only at `pause_end`). The clamp is
  display-only — it never touches a committed token — and is a no-op during speech.
- **Teardown path.** `close()` is idempotent (safe after `finish()`, after a backend error, or
  when no session was ever created): it flips `_ended`, calls `apple_asr.Stream.close()` inside
  a guard, and joins the package's silence-pump thread (which `Stream.close()` only signposts).
  `AudioProcessor.cleanup()` now calls it — see the shared-core item below.
- **Failure propagation.** Only the package's error hierarchy (`AppleAsrError`) is treated as a
  backend failure; it is recorded stickily (`_error`) and re-raised from every subsequent call,
  so a dead shim fails the session visibly through the pipeline's processing-error path instead
  of looking like an idle backend returning "no tokens". Text already committed stays in the
  session state. A `ValueError`/`TypeError` is not a backend failure and propagates unchanged.
- **Partial reconciliation.** A `Final` drops the volatile `Partial` it supersedes (a partial
  whose `start` is at or after the final's end is a genuinely newer tail and is kept). Before
  this, `get_buffer()` kept returning the superseded guess forever and could promote it at EOF.
- **Language and locale decision.** The recognizer's locale is fixed per session, so
  `--language` must name the locale's language (or be `auto`) — a server-wide `--language` that
  disagrees is rejected at startup rather than mislabeling captions and benchmark samples, and a
  session query asking for another language is rejected by `online_factory()`. The locale's
  language must be one the framework ships (checked against `apple-asr-shim --list-locales`).
- **Context capability decision.** `apple-speech` is added to `session_asr_proxy`'s
  `_NON_PROMPT_BACKENDS`: the adapter passes no `AnalysisContext`, so advertising session
  context would be a lie; the probe reports it unsupported and a client sending context gets an
  explicit error.

## Two shared-core changes — review these first

1. **`AudioProcessor.cleanup()` calls a duck-typed `close()` on the backend.**
   *Why other backends are unaffected:* only `AppleSpeechOnlineProcessor` declares `close()`
   (it owns a shim subprocess and its threads); `LocalAgreement`/`SimulStreaming`/`FunASR`/
   `Voxtral*` processors have no such attribute, so `getattr(..., None)` is falsy and the call
   is a no-op for them. It is unconditional because a WebSocket disconnect, a cancelled task or
   an error path never reaches `finish()`, so before this the shim child leaked.
2. **A capability-gated silence pull point in `AudioProcessor.transcription_processor()`.**
   *Why other backends are unaffected:* the gate is one class attribute,
   `commits_during_silence`, declared by exactly one class in the tree. Backends without it keep
   the original idle path verbatim — the 0.5 s timeout and the "refresh `get_buffer()` and
   `continue`" branch. For the declaring backend only, while a VAD pause is open the idle
   timeout is 0.1 s and the timeout falls through to `process_iter()`, and `end_silence` drains
   once more (the top-up silence can itself provoke the commit). Those tokens flow through the
   **same** commit/translate/render path as any chunk-driven commit. Without it, a final that
   misses the 0.12 s onset window waits until speech resumes — the original "it spits out when I
   start the next sentence" symptom, merely moved past the collection window.

## What it gives you

| | |
|---|---|
| zh CER (FLEURS, first-10 protocol) | **13.19** streaming / **11.23** accurate vs best MLX backend 18.20 |
| en WER (same protocol) | **13.94** streaming / **9.51** accurate vs 19.27 |
| volatile partials | yes (`--apple-speech-mode streaming`, default) |
| per-word timings | yes — real word runs on finals, from 0.1.4 clamped so a final's first word can no longer start before the final |
| compute | the Neural Engine in a system process: no GPU memory, no contention with the MT model (asserted by design; not measured here) |
| script | Traditional-native zh-TW |

On the project's own golden audio the adapter produces **12 committed segments against the
golden's 12** (first commit 3.14–3.24 s vs 2.99 s, mean gap 2.57–2.58 s vs 2.97 s), every
segment carrying a translation.

## Files — 14 files, +1886 / −8, apple-speech only

```
whisperlivekit/asr_apple_speech.py            +329   the adapter (new)
whisperlivekit/audio_processor.py             +66/-6  the duck-typed close() + the silence pull point
whisperlivekit/backend_support.py             +45    availability gate (delegates to the package)
whisperlivekit/config.py                      +69    locale/mode fields + language validation (appended)
whisperlivekit/core.py                        +26    engine factory + online_factory branch
whisperlivekit/parse_args.py                  +14/-1 --apple-speech-locale/--apple-speech-mode
whisperlivekit/session_asr_proxy.py           +4     context capability: report unsupported
whisperlivekit/benchmark/compat.py            +10    BACKEND_LANGUAGES entry + probe
whisperlivekit/benchmark/runner.py            +22    skip a sample whose language mismatches the locale
docs/backends.md                              +43    user documentation
pyproject.toml                                +27    [apple-speech] extra + dev-only source override
uv.lock                                       +15/-1 regenerated for the extra
tests/test_apple_speech_adapter.py            +726   24 tests, 0 skips on macOS 26 (dependency installed)
tests/fixtures/apple_speech_fake_shim.py      +490   a minimal protocol-v1 double
```

The two new config fields are **appended** after the existing fields, so positional dataclass
construction is preserved. Nothing upstream is deleted; no pre-existing backend's behaviour
changes outside the two shared-core items above.

## Dependency: `apple-asr` >= 0.1.4

- **0.1.3** is the release that made the session clock follow the caller's **declared** timeline
  (`pause_end(d)` advances by exactly `d`, a forced reanchor at each boundary, a monotone
  `Final.start` clamp). That is the contract the adapter's "no remapping" assumption rests on.
- **0.1.4** is the release this branch pins. It adds the package-side **word-run clamp** (each
  run's start is clamped to the same floor as its `Final.start`, closing the measured
  −0.17 … −0.22 s word-start deficit this branch's review had flagged as a package residual),
  terminates the shim child when the handshake is rejected (closing the child-leak residual),
  and removes the dead `SessionClock.drift`. The floor is **`>=0.1.4`** because the word
  timings this backend hands out are only truthful from that release; the clock contract alone
  would be satisfied by 0.1.3.
- **The `apple-speech` extra's dependency is a plain version specifier**, `apple-asr>=0.1.4,<0.2`,
  so `requires_dist` stays publishable — Warehouse refuses a direct `git+https://…` dependency,
  which would have blocked publishing the whole distribution. The pinned git tag lives only in
  `[tool.uv.sources]` for development, and `uv build --no-sources` (what the release workflow
  runs) ignores it, so the built wheel carries the specifier and no URL.
- **Standing caveat: `apple-asr` is not on PyPI yet, so the extra cannot resolve from PyPI.**
  The documented manual path is the release wheel,
  `apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl` on the `v0.1.4` release — it is
  platform-tagged so it cannot install where it cannot run, and it needs **no Swift toolchain**.
  uv users resolve the `v0.1.4` git tag instead, through the development-only `[tool.uv.sources]`
  override. No CI job installs `apple-asr` (the `test` extra does not pull the `apple-speech`
  extra, and the `test` job is untouched by this PR); the only CI touch-point is the `lint`
  job's `uv lock --check`, which validates the committed `uv.lock` — and therefore the pinned
  git source recorded in it — without installing it or running any adapter test. A *source*
  install compiles the shim at **first use**, not at install time (`python -m apple_asr.build`).

## Requirements and limits (stated plainly)

- **macOS 26+ on Apple Silicon only**, checked at runtime; the backend is not offered elsewhere.
  The Speech framework downloads per-locale assets on first use, so a cold run can sit before
  the first caption.
- A caller whose VAD strips silence (as this project's does) must announce pauses
  (`pause_start`/`pause_end`), because the transcriber's endpointer needs the silence; the
  **package** synthesizes it from those events. Declared as a capability in the package.
- The first commit is **pause-bound** — the transcriber commits a fraction of a second into a
  pause, which is what makes the cadence match. A speaker who never pauses waits for a flush; a
  `commit_interval` ceiling exists but defaults to off because it cut mid-phrase and corrupted
  text in testing.
- **Commit cadence depends on the pipeline's pause segmentation.** Driving the adapter through
  this repo's own `TestHarness` on `origin/main`, the default pipeline aggregates the utterance
  into a single output line while the adapter still emits its 12 commits — a segmentation-policy
  difference in the default pipeline, not in the adapter.
- MT chunking differs from our earlier golden fixture (`translation_final` 12 vs 6): each
  committed source segment is translated, where the golden coalesced pairs. Source cadence is
  identical; flagged as an open difference, not claimed parity.
- `SpeechDetector` (VAD sensitivity) is exposed but was inert in testing. No per-session
  language switching: the locale is fixed per session and a session requesting a different
  language fails explicitly.

## Testing

- `tests/test_apple_speech_adapter.py` — **24 tests, 0 skips** on macOS 26 with the
  `apple-speech` extra installed, driving the adapter through a vendored protocol-v1 double
  (`tests/fixtures/apple_speech_fake_shim.py`, 490 lines), so they need no Speech framework, no
  Swift toolchain, no real audio and no writable `~/.cache`. Run them with:
  `uv run --extra apple-speech pytest -q tests/test_apple_speech_adapter.py`.
- **CI does not run these tests — an accepted, documented limitation.** The backend is
  macOS-26-only and the project's CI is generic (`ubuntu-latest`): the dependency is deliberately
  **not** installed there, no macOS runner job is added, and nothing in CI installs `apple-asr`
  (`.github/workflows/ci.yml` is untouched by this PR). On that runner the module reports
  itself as **skipped with an explicit reason** — "the apple-asr package is not installed; …" —
  and on a macOS host older than 26, or any non-darwin host, it skips with the platform reason
  instead. Neither is a pass and neither is a failure. **Consequence, stated plainly: CI does
  not catch adapter regressions; only a local/`macOS-26` run does.** The adapter's platform gate
  (`backend_support.require_apple_speech_backend()`) is never neutralized or faked by the tests;
  it is asserted directly by the unsupported-host test.
- **What the double does and does not prove.** It speaks the real wire protocol v1 (hello /
  partial / final with word runs / commit / ended, plus finalize and close commands) over
  stdin/stdout and the command fd, with both an emulate mode and a scripted mode. But its
  **endpointer is deterministic**, so it establishes the adapter's mapping onto that protocol —
  not real SpeechAnalyzer scheduling, latency, or recognition.
- **Mutation evidence** (local, not shipped): in the B2 pass, disabling the adapter's
  `commits_during_silence` declaration and separately breaking the core fall-through each make
  `test_a_late_final_commits_during_the_pause_via_the_pull_point` fail, and are restored
  afterwards. Earlier passes mutation-checked the pause-final collection and the per-word
  mapping the same way. The mutation log is not an artifact of this PR.
- `tests/test_backends.py`, `tests/test_silent_backend_guard.py` — green (44 passed).
- `UV_NO_CONFIG=1 uv lock --check` passes, including `--python 3.12`; `ruff check .` is clean.
- The delegated layer (transport, protocol, clock, and its own suite) is covered by the
  package's tests; this PR does not restate them.

## Evidence and reproducibility

Same first-10 FLEURS samples, normalization and mean-per-sample aggregate as the project's
existing MLX comparison; the scoring path was anchored by reproducing that comparison's own
recorded results before scoring anything new. **The scoring harness is not shipped with this
PR** (and is not part of the `apple-asr` package — its README says the harness was not ported;
the package ships the replay driver and the shim, not the scoring/baseline harness). Raw
per-sample results, sample identities, hypotheses and the baseline reproduction artifact are
not included here, so **the accuracy and cadence figures are motivating context, not verified
evidence shipped with the PR.** The golden-cadence numbers were re-measured on this branch
through `whisperlivekit.test_harness.TestHarness` against the real shim and are quoted in
*What it gives you*; the test counts and pass/skip figures in *Testing* were re-run on this
branch — 24 passed / 0 skipped on macOS 26 with the extra, and 24 skipped with the explicit
reason in a `.[test]`-only environment that has no `apple-asr`.

## Not resolved / out of scope

- **The cold-start pause outlier.** In one of two acceptance runs (a fresh process) the first
  pause's final landed outside the 0.12 s onset window and was committed by the pull point
  **0.501 s** after onset; the other run's worst was 0.145 s and the onset-only worst was
  0.13 s in both. This is SpeechAnalyzer's own first-pause latency (the shim published its
  final ~0.38 s after `pause_end`), not the adapter's hold. Recorded, not hidden.
- **The fake double's close-ordering race could not be reproduced by mutation.** The fix is on
  the code path (a threaded reader makes finalizing before stdin EOF unsound) and is covered by
  an invariant test, but with the pre-fix ordering restored the test still passed; it is not
  demonstrated by a failing mutation.
- **The fake's deterministic endpointer** means it cannot establish real SpeechAnalyzer
  scheduling behaviour.
- The clock wording contradiction in the package's own SPEC/README and the handshake child leak
  were package-side residuals this branch reported rather than fixed here; **0.1.4 closes the
  leak** and the word-run and `drift` items. Nothing in this PR changes the package.
