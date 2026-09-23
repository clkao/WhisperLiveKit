Verdict: **BLOCKED**

## Review

CL, the branch has a release blocker and reproducible lifecycle, error-reporting, buffering, and timestamp defects. No edits, commits, or staging were performed. The complete report follows for persistence to the requested `GPT6-REVIEW.md`; the explicit read-only instruction took precedence over writing it.

### Findings — ranked by severity

1. **Blocker: the Git dependency prevents publishing WhisperLiveKit to PyPI.**

   `pyproject.toml:108` adds a direct Git URL to distribution dependencies. PyPI rejects direct dependencies, including optional ones. This affects publishing the entire project, not merely installing this extra.

   Evidence: `.github/workflows/publish-pypi.yml:69` builds the distribution for publication. Warehouse’s current `warehouse/forklift/metadata.py:252–261`, inspected directly, rejects `requires_dist` entries with `req.url`, reporting `Can't have direct dependency`.

   **Fix:** publish the dependency to an accepted package index and use a version requirement. A development-only uv source override can retain Git resolution without embedding that URL in published metadata. Changing the tag to a commit hash alone does not fix publication.

2. **High: disconnected sessions leak the shim subprocess and its threads.**

   The subprocess is created in `whisperlivekit/asr_apple_speech.py:92–98`; its only shutdown path is `finish()` at lines 201–212. `AudioProcessor.cleanup()` cancels tasks but never closes the transcription backend (`whisperlivekit/audio_processor.py:1012–1046`). WebSocket disconnects call this cleanup directly (`whisperlivekit/basic_server.py:168–187`), without guaranteeing EOF finalization.

   **Reproduced with the actual package and vendored shim:** after `AudioProcessor.cleanup()`, `child_alive=True`, `pump_alive=True`, `stream_closed=False`. The probe explicitly finished the processor afterward.

   **Fix:** introduce an idempotent session-backend close/abort hook and invoke it from unconditional cleanup, including cancellation and initialization failures. Add a disconnect regression asserting child termination and thread shutdown. The pinned package also lacks cleanup around handshake failures: `apple_asr/transport.py:381–425` can raise after spawning the child.

3. **High: backend failures are deliberately hidden from clients.**

   `whisperlivekit/asr_apple_speech.py:108–113, 151–164, 166–174` logs exceptions and returns empty results. Error events are also only logged at lines 146–149.

   This bypasses the pipeline’s existing failure propagation at `audio_processor.py:787–789`. Its silent-backend guard only logs, and stops checking permanently after any output (`audio_processor.py:296–306`). The adapter’s `heard_speech` attribute is not what this watchdog reads.

   **Reproduced:** after a partial/final, a simulated package `BackendError("child died")` produced `([], 1.0)` and `_ended=True`, without raising.

   **Fix:** propagate terminal failures into the existing processing-error path, close the stream, and preserve previously confirmed text. Test failure both before and after the first output. Avoid broadly swallowing programming/input errors as backend failures.

4. **High: finalized partials remain in the hypothesis buffer.**

   Finals append tokens but never clear or reconcile `_partial` (`whisperlivekit/asr_apple_speech.py:133–145`). `get_buffer()` consequently returns the previous partial indefinitely (`:215–227`).

   **Reproduced:** consuming `Partial("old guess", 0, 1)` followed by `Final("correct words", 0, 1, ())` leaves `get_buffer().text == "old guess"`.

   The pipeline’s prefix stripping cannot repair a revised hypothesis. Even when stripping succeeds, it modifies only the returned `Transcript`; the next idle refresh retrieves the stale partial again (`audio_processor.py:637–640, 730–733`). EOF fallback can then promote stale buffered text into additional committed tokens (`:559–586`).

   **Fix:** reconcile partials against final ranges and clear completed hypotheses, while preserving any genuinely newer tail. Test corrected partial → final → idle refresh → EOF, including no duplicate transcription or translation.

5. **High: synthesized silence moves package timestamps off WLK’s physical audio clock.**

   The adapter assumes package times require no mapping and advances its cursor by the declared pause duration (`whisperlivekit/asr_apple_speech.py:189–199`). However, pinned `apple_asr.Stream.pause_end()` advances by `max(synthesized_frames, declared_frames)` (`apple_asr/stream.py:391–418`).

   The adapter itself holds every pause open for its 300-ms collection window, allowing synthesized silence to exceed a short actual pause.

   **Reproduced:** push 0.4 s, `start_silence()`, then `end_silence(0.1, 0.4)`:
   - WLK cursor: **0.5 s**
   - Package session clock: **0.7 s**

   Short pauses are permitted: the VAD defaults to 100-ms minimum silence (`whisperlivekit/silero_vad_iterator.py:199`). Repeated short pauses, queued input, or slow scheduling can accumulate drift.

   **Fix:** preserve WLK’s sample-clock timeline when artificial silence overshoots. Prefer a package-level clock/input contract suitable for this integration rather than another untested drift calculation. Add repeated short-pause and delayed-consumer tests.

6. **High: blocking subprocess writes run on the server event loop.**

   `insert_audio_chunk()` calls synchronous `Stream.push()` (`whisperlivekit/asr_apple_speech.py:166–174`). WLK invokes this directly, not through its threaded inference helper (`audio_processor.py:712`). Package `write_audio()` performs blocking `stdin.write()` and `flush()` without a deadline (`apple_asr/transport.py:608–619`).

   A stalled child or cold locale initialization can fill the pipe and block all sessions. The real shim emits its handshake before downloading assets and preparing the analyzer (`apple_asr/shim/speechanalyzer.swift:472–518`). `end_silence()` similarly performs synchronous waits/writes on the event loop.

   **Fix:** move blocking transport operations off the event loop with bounded backpressure, deadlines, and cancellation-safe shutdown. Include a shim that handshakes but stops reading stdin. A destructive hang test was not run.

7. **Medium: the pause-commit guarantee ends at 300 ms; later finals are stranded.**

   `start_silence()` polls once for 300 ms (`whisperlivekit/asr_apple_speech.py:178–187`). Thereafter, idle pipeline iterations call only `get_buffer()`, which does not poll (`audio_processor.py:630–640`).

   **Reproduced with a scripted late final:** `start_silence()` returned no tokens; after another 0.7 s the package reported one final, but `get_buffer()` remained empty. The final appeared only after another `process_iter()`.

   **Fix:** support periodic collection and publication of asynchronous committed tokens during silence. Increasing the fixed wait merely moves the failure threshold. Test commits delayed beyond 300 ms and EOF immediately after such a pause.

8. **Medium: configured language can silently disagree with the actual recognizer—and benchmark labels.**

   Config validation checks only language membership (`whisperlivekit/config.py:270–280`). The engine ignores `config.lan` when constructing Apple Speech (`core.py:194–200`). The mismatch guard runs only for explicit session overrides (`core.py:455–480`).

   **Reproduced:** `WhisperLiveKitConfig(backend="apple-speech", lan="en")` accepts the default `apple_speech_locale="zh-TW"`.

   This also affects benchmarking: the runner selects each sample’s `lan`, but does not select the corresponding Apple locale (`whisperlivekit/benchmark/runner.py:81–85`).

   **Fix:** validate the effective server/session language against the configured locale; either map benchmark languages to explicit locales or reject unsupported locale/language combinations. Validate locale syntax/inventory and reject unsupported direct-ASR translation rather than implying it is honored.

9. **Medium: session context is advertised as supported and then discarded.**

   Apple Speech is absent from `_NON_PROMPT_BACKENDS` (`whisperlivekit/session_asr_proxy.py:19–27`). Under the default `simulstreaming` policy, `supports_session_context()` therefore returns true (`:54–61`), even though this backend bypasses SimulStreaming.

   **Reproduced:** the default Apple configuration advertises context support. The adapter’s `Stream(...)` call supplies no context (`whisperlivekit/asr_apple_speech.py:92–98`).

   **Fix:** reject context explicitly by registering this backend as unsupported, or intentionally map validated session context into `Stream(context=...)`. Add a capability/behavior consistency test.

10. **Medium: none of the nine new tests runs in the existing CI installation.**

    `tests/test_apple_speech_adapter.py:32` skips the entire module if `apple_asr` is absent. CI installs `.[test]`, not `.[apple-speech]` (`.github/workflows/ci.yml:127–128`); the test extra does not include the dependency.

    **Verified:** the installed local environment passes nine tests. Simulating an absent package yields **one module-level skip**, executing none of them.

    **Fix:** ensure the intended CI job installs the Python dependency and asserts that the adapter tests execute. Contrary to the task’s installation premise, the pinned source package has no Swift build hook: its ordinary installation is pure Python; compilation happens during explicit build or runtime shim resolution.

11. **Medium: positional configuration compatibility is broken for other backends.**

    New fields were inserted before existing trailing fields (`whisperlivekit/config.py:201–213`), immediately above a comment requiring append-only field placement.

    Comparing base and HEAD shows:
    - Position 116: `pause_segmentation_seconds` → `apple_speech_locale`
    - Position 117: `sortformer_max_speakers` → `apple_speech_mode`

    **Fix:** append the new fields after all existing fields. This is a concrete cross-backend regression even though keyword-based callers are unaffected.

### Test-double assessment

The double is **wire-compatible, but not sufficient behavioral evidence**.

- Verified against pinned commit `50290887ba269f347e5715eb4821fd114c25863e`: handshake shape, float32 PCM input, control-FD environment variable, event names, ranges, three-/four-element word runs, and mode-related argv agree with `apple_asr.protocol`, `transport.py`, and the Swift shim.
- Tests exercise the real package transport, not a mocked `Stream`. They genuinely cover word/confidence mapping, receiving partials, one successful pause final, simple EOF drainage, and explicit session-language rejection.
- They do **not** cover the defects above: cancellation, failure propagation, finalized-buffer clearing, late commits, short-pause timestamp divergence, stalled writes, or server-default language mismatch.
- The fake’s endpointer deterministically publishes once its synthetic quiet threshold is reached (`tests/fixtures/apple_speech_fake_shim.py:308–327`). That cannot establish real SpeechAnalyzer scheduling within 300 ms.
- The fake emits partials independently of the configured accurate mode (`:93, 328–338`), and its default handshake always advertises both reporting options (`:127–129`). Accurate-mode testing checks argv/state, not actual output behavior.
- Fixture configuration always supplies `pause_commit=0.08` (`tests/test_apple_speech_adapter.py:85`), which overrides the passed CLI value in the fake (`tests/fixtures/apple_speech_fake_shim.py:87–90`). Thus the test’s resolved-value assertion does not independently verify that adapter argument.
- `test_sep_follows_the_configured_locale` constructs a processor without finishing it (`tests/test_apple_speech_adapter.py:223–224`).
- The fake has its own shutdown race: it handles close commands before ensuring queued stdin has been consumed (`tests/fixtures/apple_speech_fake_shim.py:268–269, 282–283, 362–372`). The dependency README itself documents a related fake control/audio ordering flake.

**Fix direction:** retain focused transport-backed adapter tests, but extend actual pipeline regression scenarios. Remove unused emulator behavior rather than treating 457 lines of simulation as proof of Speech timing.

## Claim audit

`apple_asr/...` below refers to the pinned package source, not the draft specification.

| PR claim | Judgment | Evidence |
|---|---|---|
| macOS 26+ runtime gate | **VERIFIED** | `backend_support.py:48–89`; package `platform.require_supported()` checks Darwin and macOS major ≥26. Unsupported-host adapter test passes. |
| Backend not offered elsewhere | **VERIFIED**, for availability probing | `apple_speech_backend_available()` returns false on unsupported hosts. CLI choices still list the backend everywhere. |
| Other backends unaffected | **WRONG** | Positional config regression; direct dependency blocks publication of the whole distribution. No default-install Swift import regression found. |
| Released package pinned by tag | **VERIFIED**, for source identity | `uv.lock:1046–1053` and installed `direct_url.json` identify v0.1.2 / `50290887…`. Actual release-wheel contents were not inspected. |
| Thin adapter, approximately 230 lines | **VERIFIED** | New module is 227 lines. |
| Adapter contains “no timing logic” | **WRONG** literally | It imposes a 300-ms pause collection policy and a timed finish-drain loop (`asr_apple_speech.py:44–54, 187, 208–211`). |
| Ten files, +1093/−2 | **VERIFIED** | `git diff --stat origin/main..HEAD`. |
| “Purely additive” / nothing restructured | **WRONG** as a compatibility claim | Most changes are additions, but existing positional field meanings change. |
| Nine tests, zero skips | **VERIFIED** locally | Explicit adapter run: `9 passed in 3.69s`, with dependency already installed. |
| Those tests run in normal CI | **WRONG** | CI omits the dependency; missing-package probe skips the entire module. |
| Tests require no Speech, macOS 26, or Swift | **VERIFIED**, with Python dependency installed | Fake-backed tests passed without invoking real Speech or compilation. Linux execution itself was not run. |
| Every guard was mutation-checked | **UNVERIFIABLE** | No mutation-run artifacts supplied or rerun. |
| Backend and silent-guard tests are green | **VERIFIED** locally | Combined run: `53 passed, 3 warnings in 11.55s`. This does not test Apple’s swallowed errors. |
| `ruff check .` passes | **VERIFIED** | `All checks passed!` |
| Lock check passes, including Python 3.12 | **VERIFIED** without local uv configuration | Both `uv --no-config lock --check` variants passed. Ordinary commands failed because local `~/.config/uv/uv.toml` adds rolling `exclude-newer = "7 days"`; not attributed to this branch. |
| zh CER 13.19/11.23 versus 18.20 | **UNVERIFIABLE** | Dependency README repeats these numbers, but does not supply the referenced measurement record in this checkout. No scoring rerun. |
| en WER 13.94/9.51 versus 19.27 | **UNVERIFIABLE** | No inspectable per-sample report supporting these numbers in the reviewed artifacts; no scoring rerun. |
| Same first-10 protocol and reproduced comparison baseline | **UNVERIFIABLE** | No sample identities, hypotheses, normalization output, or baseline reproduction artifact supplied with the PR. |
| Package ships the scoring/baseline harness, making results reproducible | **WRONG** | Pinned README explicitly says the CER/WER harness is **not ported**, and results come from workspace `bench_cer.py`. Package scripts expose shim and replay, not that scoring harness. |
| Golden cadence 12 versus 12; first commit 3.6 versus 2.99 s; mean gaps 2.66 versus 2.97 s | **UNVERIFIABLE** | No adapter-run trace inspected establishing these figures; real-audio acceptance was prohibited. |
| Every golden segment carries a translation | **UNVERIFIABLE** | Adapter tests do not run MT or the relevant end-to-end pipeline. |
| First commit is pause-bound, approximately 0.1 s into a pause | **UNVERIFIABLE** as a runtime guarantee | Pause-only defaults verified; actual framework latency is not. Delayed-final probe demonstrates delivery can miss the adapter’s collection window. |
| `commit_interval=0` because interval commits corrupted text | **UNVERIFIABLE** as an experimental conclusion | Zero default verified; README repeats the rationale, but underlying experiment was not inspected or rerun. |
| Silence-stripping callers must announce pauses | **VERIFIED** | Package `stream.py:5–13, 364–418` documents and implements synthesized pauses; WLK sends silence boundary events. |
| “The adapter synthesizes” that silence | **WRONG** literally | The delegated package synthesizes it; the adapter announces pauses. |
| SpeechDetector was inert in testing | **UNVERIFIABLE** | Swift exposes sensitivity; an inertness observation requires the experiment. It is not a WLK adapter option. |
| No per-session language switching; explicit different-language request fails | **VERIFIED** narrowly | `core.py:464–480` and rejection tests. Server-default `lan` mismatch remains unhandled. |
| Default TestHarness aggregates one line despite 12 backend commits | **UNVERIFIABLE** numerically | Default five-second segmentation threshold supports the explanation, but no matching run trace was supplied. |
| MT chunking differs: 12 finals versus six, with identical source cadence | **UNVERIFIABLE** | Requires source/translation traces and the earlier fixture configuration. |
| Volatile partials and real timed final runs are available | **VERIFIED** at implementation level | Swift `speechanalyzer.swift:527–550` emits framework ranges/runs; transport and adapter map them. Not a real-audio quality verification. |
| Traditional-native zh-TW | **UNVERIFIABLE** as observed output quality | Locale defaults to zh-TW; output script/quality was not measured here. |
| Neural Engine, zero GPU memory, no MT contention | **UNVERIFIABLE** | No resource trace. Calling the framework does not establish these absolute resource claims. |
| Source installation compiles the shim | **WRONG** if referring to installation time | Pinned package uses ordinary hatchling packaging with no compilation hook. Runtime resolution or explicit build compiles it. |
| Wheel installation needs no Swift toolchain | **VERIFIED** as packaging design | Build script bundles the binary and resolver supports it. Released wheel contents were not independently inspected. |
| Delegated layer has 70 passing tests | **UNVERIFIABLE** | Dependency suite was not rerun; package tests cannot establish WLK integration correctness. |

## Upstream fit and remaining notes

- **Documentation is missing.** `docs/backends.md` has no Apple Speech setup, supported-host guidance, language/locale example, cold asset-download warning, or wheel installation instructions. PR prose is not installed documentation.
- **Availability is weaker than advertised.** The cheap probe checks package/platform, not a working shim or installed locale. “Harness and backend can never disagree” is overstated.
- **Metrics need qualification.** WLK measures polling/collection call duration, including the fixed wait, rather than the external recognizer’s execution cost. The dependency’s bounded event queue can drop finals; adapter metrics do not expose `Stream.stats.dropped`.
- **Local leftovers:** prototype references in adapter comments and CER figures in CLI help/config should be replaced by durable behavior documentation and linked reproducible evidence.
- **Maintainer decisions:** accepting a macOS-26-only backend; dependency ownership/release policy; explicit locale defaults; and the scope of asynchronous-backend lifecycle support. Those decisions do not excuse the concrete failures above.

### Top three fixes before opening

1. Remove the PyPI-incompatible published Git requirement and arrange a reproducible dependency/CI installation.
2. Fix teardown and error propagation; prove disconnect, cancellation, and child-failure behavior through `AudioProcessor`.
3. Fix partial/final reconciliation and pause delivery/timestamp accounting; add short-pause and delayed-final pipeline regressions.

### Verification limits

No real SpeechAnalyzer, microphone, ASR/MT acceptance, FLEURS scoring, or golden-cadence run was performed, as requested. No Linux host or release wheel was exercised. The full project/dependency suites and mutation suite were not run. These limits prevent validating accuracy, cadence, resource-isolation, and MT claims—not the defects reproduced above.