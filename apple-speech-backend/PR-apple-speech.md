# feat: Apple SpeechAnalyzer (`apple-speech`) ASR backend via the `apple-asr` package

Branch `apple-speech-backend`, cut from `origin/main` @ `363e4f6`, **17 commits**, 14 files,
+1886 / −8. Target: `QuentinFuxa/WhisperLiveKit` `main`. Not pushed; intended as a draft.
Written against `.github/pull_request_template.md`.

## Summary

Adds an `apple-speech` ASR backend that runs Apple's on-device SpeechAnalyzer stack (macOS 26+,
Apple Silicon) through the released **`apple-asr`** package.
`whisperlivekit/asr_apple_speech.py` (329 lines) is an adapter: it implements the
`OnlineProcessor` contract by delegating to `apple_asr.Stream` — `insert_audio_chunk` /
`start_silence` / `end_silence` / `process_iter` / `get_buffer` / `finish` / `close`. It carries
**no protocol or recognizer logic of its own** — the Swift shim, the JSONL wire protocol, the
pause synthesis and the session clock live in the package — but it does own two bounded timing
policies, described below: the pause-collection window in `start_silence()` and the drain
deadline in `finish()`. Availability is gated by
`backend_support.require_apple_speech_backend()`, which delegates to the package's own platform
and shim gates, so the two can never disagree.

Why: this project's zh/en quality question has been answered so far by MLX backends that contend
for GPU memory with the MT model. SpeechAnalyzer runs on the Neural Engine in a system process,
so it costs no GPU memory (recorded, not asserted — see *Validation*) and is a large quality
improvement over the MLX backends on the same corpus. The Swift toolchain and the macOS-26-only
code stay out of this repository: they live in `apple-asr`, and this PR is a dependency-backed
adapter over its released, platform-tagged wheel.

### Adapter behaviour as shipped

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

### Two shared-core changes — review these first

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

### Files

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

## User impact

### What it gives you

| | |
|---|---|
| volatile partials | yes (`--apple-speech-mode streaming`, the default) |
| per-word timings | yes — real word runs on finals, from `apple-asr` 0.1.4 clamped so a final's first word can no longer start before the final |
| compute | the Neural Engine in a system process: **no MLX/GPU memory at all** (`mlx_active_bytes` and `mlx_peak_bytes` are `None` for all 30 benchmark samples, i.e. MLX was never initialized), RSS peak 271–326 MB |
| accuracy | see *Validation* — zh CER **10.85%** weighted, en WER **11.93%** weighted with `vac: false`; with the default `vac: true` the en path is broken (**27.92%**, unresolved) |
| script | Traditional-native `zh-TW`; `zh-CN` also available (and directly comparable in the harness — see the script note in *Validation*) |
| platform | macOS 26+ on Apple Silicon only, refused elsewhere at startup |

### Dependency: `apple-asr` >= 0.1.4

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

### Requirements and limits (stated plainly)

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
  this repo's own `TestHarness`, the default pipeline aggregates the utterance into a single
  output line while the adapter still emits its 12 commits — a segmentation-policy difference in
  the default pipeline (`pause_segmentation_seconds = 5.0` in the benchmark's effective config),
  not in the adapter. For per-pause rendering the setting must be smaller; the adapter itself is
  unchanged either way.
- MT chunking differs from our earlier golden fixture (`translation_final` 12 vs 6): each
  committed source segment is translated, where the golden coalesced pairs. Source cadence is
  identical; flagged as an open difference, not claimed parity.
- `SpeechDetector` (VAD sensitivity) is exposed but was inert in testing. No per-session
  language switching: the locale is fixed per session and a session requesting a different
  language fails explicitly.
- **Compatibility:** additive. Both new config fields are appended (positional construction
  intact), `--apple-speech-locale` / `--apple-speech-mode` are new flags, and the only changes to
  shared code are the two review items above, each gated so non-declaring backends keep the
  original path.

## Validation

Hardware/OS for every number below: **macOS 26.6.2, arm64 (Apple Silicon), Python 3.13.12**,
`whisperlivekit` 0.2.26 at commit **`94ace5e` (branch tip, `git_dirty: false`)** as recorded by
the benchmark report's own `system_info`. Recognizer: system SpeechAnalyzer (no model weights
downloaded by this repo); locales are named per run.

### Tests

- `tests/test_apple_speech_adapter.py` — **24 tests, 0 skips** on macOS 26 with the
  `apple-speech` extra installed, driving the adapter through a vendored protocol-v1 double
  (`tests/fixtures/apple_speech_fake_shim.py`), so they need no Speech framework, no Swift
  toolchain, no real audio and no writable `~/.cache`:
  `uv run --extra apple-speech pytest -q tests/test_apple_speech_adapter.py`.
- `tests/test_backends.py`, `tests/test_silent_backend_guard.py` — green (44 passed).
- `UV_NO_CONFIG=1 uv lock --check` passes, including `--python 3.12`; `ruff check .` is clean.
- **What the double does and does not prove.** It speaks the real wire protocol v1 (hello /
  partial / final with word runs / commit / ended, plus finalize and close commands) over
  stdin/stdout and the command fd, with both an emulate mode and a scripted mode. But its
  **endpointer is deterministic**, so it establishes the adapter's mapping onto that protocol —
  not real SpeechAnalyzer scheduling, latency, or recognition. It is a protocol double, not a
  model substitute.
- **CI does not run these tests — an accepted, documented limitation.** The backend is
  macOS-26-only and the project's CI is generic (`ubuntu-latest`): the dependency is deliberately
  **not** installed there, no macOS runner job is added, and nothing in CI installs `apple-asr`
  (`.github/workflows/ci.yml` is byte-identical to `origin/main` — this PR does not touch it). On
  that runner the module reports itself as **skipped with an explicit reason** ("the apple-asr
  package is not installed; …"), and on a macOS host older than 26, or any non-darwin host, it
  skips with the platform reason instead. Neither is a pass and neither is a failure.
  **Consequence, stated plainly: CI does not catch adapter regressions; only a local macOS-26
  run does.**
- **Mutation evidence** (local, not shipped): in the B2 pass, disabling the adapter's
  `commits_during_silence` declaration and separately breaking the core fall-through each make
  `test_a_late_final_commits_during_the_pause_via_the_pull_point` fail, and are restored
  afterwards. Earlier passes mutation-checked the pause-final collection and the per-word
  mapping the same way. The mutation log is not an artifact of this PR.

### Benchmark: this project's own protocol (`wlk bench`, report schema 3.1)

The corpus is the in-tree pinned manifest; the audio was already cached, so no download happened
during a measured run.

```bash
# sandbox note: ~/.cache is read-only here, so point the shim cache elsewhere
export APPLE_ASR_CACHE=/tmp/apple_asr_cache
echo '{"apple_speech_locale":"zh-CN","apple_speech_mode":"streaming"}' > cfg_zhcn.json

wlk bench --backend apple-speech --languages zh \
  --manifest benchmarks/corpora/fleurs-90.json --warmup --repeats 1 --speed 1 \
  --config cfg_zhcn.json --json bench-zh-CN.json
```

| locale | samples | failed | weighted CER | mean per-sample CER | ASR RTF |
|---|---|---|---|---|---|
| `zh-CN` | 30 | 0 | **10.85%** | **10.52%** | 0.045 (per-sample 0.026–0.054) |
| `zh-TW` | 30 | 0 | 38.69% | 38.19% | 0.031 |

Every sample's `effective_config` in the report records `apple_speech_locale` and
`apple_speech_mode`, so the locale behind each row is not ambiguous; the report also carries the
audio hash, the corpus hash, per-sample hypotheses and references, and the commit/dirty state
quoted above. The raw JSON reports are not committed (generated data), but the commands above
reproduce them exactly, and the reports accompany this branch locally.

### The `zh-TW` score is a script artifact — and this is measured, not assumed

The harness scores a hypothesis against the manifest's reference through
`whisperlivekit.metrics.normalize_text` and then char-level Levenshtein
(`benchmark/runner.py`: whitespace removed, so the CJK string is a single token; punctuation and
case are normalized away). **It performs no script conversion.** FLEURS zh references are
Simplified; `zh-TW` emits Traditional, so every converted character is scored as an error.

Two checks, both reproducible:

1. **Feed speed is not the cause:** `--speed 0` gives 38.54% and `--speed 1` gives 38.69% on the
   same 30 zh-TW samples — a 0.15-point difference.
2. **Script conversion closes the gap.** Reimplementing the scorer verbatim from
   `whisperlivekit/metrics.py` reproduces the report to 0.01% (38.70% vs 38.69%; 10.85% vs
   10.85%), and converting only the zh-TW hypotheses with OpenCC `t2s` before scoring gives:

| zh hypotheses (same 30 samples, project scorer) | weighted CER | mean per-sample |
|---|---|---|
| `zh-TW` raw | 38.70% | 38.19% |
| `zh-TW` converted with OpenCC `t2s` | **11.31%** | **10.83%** |
| `zh-CN` native | **10.85%** | **10.52%** |

Conversion recovers **27.4 of the 27.9 points** (98% of the gap) and lands **0.46 points** from
the natively-Simplified run. So the locale difference is writing system, not recognition
quality: this backend recognizes zh at roughly 10.9–11.3% CER either way.

**Consequence for readers of the project's existing comparison:** a Traditional-emitting backend
is penalised by ~28 CER points in this harness, and that penalty is not a quality difference.
The accuracy claim in this PR is therefore stated on `zh-CN` (directly comparable to the MLX
backends' numbers in the same report format); `zh-TW` is what our captions use for
Taiwan-native vocabulary, and its 10.83% is only visible through the conversion above. If you
would rather not carry this nuance in the harness, the alternative is to score zh with a script
normalization — I have not proposed that here, since it would change published numbers for
every backend.

Reproduce the conversion check (installs only the converter, not part of this PR):

```bash
pip install opencc-python-reimplemented
python - <<'PY'
import json
from opencc import OpenCC
from whisperlivekit.metrics import compute_wer, normalize_text
score = lambda r, c=None: compute_wer(*[(" ".join("".join(normalize_text(x).split()))) for x in
    (r["reference"], c(r["hypothesis"] or "") if c else (r["hypothesis"] or ""))])["wer"]
d = json.load(open("bench-zh-TW.json")); cc = OpenCC("t2s")
rs = [r for r in d["results"] if r["language"] == "zh" and r["cer"] is not None]
print("raw", sum(score(r)*1 for r in rs)/len(rs), "t2s", sum(score(r, cc.convert) for r in rs)/len(rs))
PY
```

### `en` — and the `vac: true` interaction that has to be stated

Same corpus, same 30-sample span, `en-US` locale, only the config differs:

| en-US config | weighted WER | mean per-sample | hypotheses with dot/dash runs | transcription calls |
|---|---|---|---|---|
| `vac: true` (bench default), `pause_segmentation_seconds` 5.0 | 27.92% | 25.09% | **18 / 30** | 306 |
| `vac: true`, `pause_segmentation_seconds` 600 | 26.21% | 24.28% | 19 / 30 | 306 |
| `vac: false`, `pause_segmentation_seconds` 5.0 | **11.93%** | **10.98%** | 0 / 30 | 90 |
| `vac: false`, `pause_segmentation_seconds` 600 | **11.93%** | **10.98%** | 0 / 30 | 90 |

With the default `vac: true`, hypotheses carry runs of dots and dashes where content was lost —
e.g. `fleurs_en_1700`, reference *"It is thinner under the maria and thicker under the
highlands."*, hypothesis *"It is thinner under the.-... Maria and thicker under the highlands."* —
and the 12 artifact-free samples average 11.8%, i.e. the underlying recognition is fine and the
default path is corrupting it. `vac` is the only variable that matters: turning it off halves the
WER and removes every artifact, while `pause_segmentation_seconds` changes nothing in either
direction and the call count drops 306 → 90. **`zh-CN` and `zh-TW` are unaffected** (0/30
artifacts; 10.85% and 38.69% weighted), on the same pause code path — so this is not the adapter's
pause handling failing in general, it is an en-US-specific interaction with the silence the VAC
path presents to the recognizer. It is **unresolved** (see *not resolved* below); the en row of the
summary table is therefore the `vac: false` number, and no en claim is made for the default
configuration.

Reproduce: the *Benchmark* command above with `--languages en` and
`{"apple_speech_locale":"en-US","apple_speech_mode":"streaming","vac":false}` in the config
file.

### Cadence on the project's golden audio

Through `whisperlivekit.test_harness.TestHarness` against the **real** shim (not the double), the
adapter produces **12 committed segments against the golden's 12**; first commit 3.14–3.24 s vs
2.99 s; mean gap 2.57–2.58 s vs 2.97 s; every segment carrying a translation.

### Not run, and this is the gap

- **`tests/test_pipeline.py -k whisper` and `tests/test_asr_coalescing_pipeline.py` were not
  run.** CONTRIBUTING asks for the real-model scenarios when streaming, buffering, timestamps or
  silence handling change, and this PR touches all four. Both tests need model and audio
  downloads that this development sandbox cannot reach; they should be run before merge, and I
  will run and report them if someone can confirm they are expected to pass in an environment
  with network access.
- The `--repeats 3` variant of the benchmark above (the example in `benchmarks/README.md`) is not
  what the tables report: every row is `--repeats 1`. Quality is deterministic for this backend
  across repeats; the repeat count would add latency variance, which the tables do not claim.
- The `en` figures are all in the `vac` ablation table, and the summary table quotes the
  `vac: false` row deliberately: the default configuration is broken for en and no en claim is
  made for it — see *not resolved* below.
- The MT stage is out of scope: the figures above are ASR-only (`translate_on_complete: false`,
  no translation backend engaged).

### Not resolved / limits of this evidence

- **`vac: true` (this project's default) corrupts en-US output for this backend.** Measured and
  isolated above: 27.92% weighted WER with 18/30 artifact-bearing hypotheses and content dropped
  around the artifacts, versus **11.93% / 0 artifacts** with `vac: false`. `zh-CN` and `zh-TW` are
  unaffected, so it is locale-specific rather than a general failure of the shared pause path; the
  transcription-call count tripling (90 → 306) points at the repeated finalize/re-decode cycles the
  VAC's silence announcements provoke. I have not yet determined whether the fix belongs in the
  adapter (the pause window and drain), in the package (how announced silence is presented to the
  recognizer), or in how this backend should declare itself incompatible with VAC. **Until it is
  understood, this backend's en output should not be used with `vac` enabled**, and I would rather
  state that plainly than put an en number in this PR that only holds in a non-default
  configuration. This is the one finding here I would hold a merge for.
- **The cold-start pause outlier.** In one of two acceptance runs (a fresh process) the first
  pause's final landed outside the 0.12 s onset window and was committed by the pull point
  **0.501 s** after onset; the other run's worst was 0.145 s and the onset-only worst was
  0.13 s in both. This is SpeechAnalyzer's own first-pause latency (the shim published its
  final ~0.38 s after `pause_end`), not the adapter's hold. Recorded, not hidden.
- **The fake double's close-ordering race could not be reproduced by mutation.** The fix is on
  the code path (a threaded reader makes finalizing before stdin EOF unsound) and is covered by
  an invariant test, but with the pre-fix ordering restored the test still passed; it is not
  demonstrated by a failing mutation.
- The clock wording contradiction in the package's own SPEC/README and the handshake child leak
  were package-side residuals this branch reported rather than fixed here; **0.1.4 closes the
  leak** and the word-run and `drift` items. Nothing in this PR changes the package.
- The benchmark's zh scoring is script-sensitive (above). That is a property of the harness that
  this PR documents rather than changes.

## Checklist

- [x] I searched for an existing issue or discussion and linked it when relevant.
  — Searched the issue tracker (terms: "SpeechAnalyzer", "apple", "on-device", "speech
  framework", "macOS 26") and all 24 existing discussions. **Nothing covers this.** The nearest
  are #346 (Qwen3-ASR support, closed) and #366 (FunASR backend for lower streaming latency,
  closed) — both backend additions, cited as related, not as the issue this closes.
- [x] I added or updated tests for behavior changes. — `tests/test_apple_speech_adapter.py`
  (24 tests) plus the protocol-v1 double; both shared-core changes and the timing policies have
  tests that fail when the behaviour is removed (mutation-checked locally).
- [x] I updated documentation for user-facing changes. — `docs/backends.md` (+43), including the
  macOS-26 gate, the locale requirement and the manual install path while `apple-asr` is off
  PyPI.
- [x] I ran `ruff check .`. — Clean.
- [x] I ran the relevant pytest suite. — Adapter suite 24 passed / 0 skipped (macOS 26 with the
  extra); `tests/test_backends.py` + `tests/test_silent_backend_guard.py` 44 passed;
  `UV_NO_CONFIG=1 uv lock --check`. **Not run:** the real-model pipeline scenarios named under
  *Validation → Not run*, which is the one gap in this checklist.
- [x] I did not commit credentials, model weights, generated caches, or private data. —
  `git diff --name-only origin/main..HEAD` contains no audio, JSONL, weights, caches, or logs;
  the commit messages carry no generated attribution trailers.
