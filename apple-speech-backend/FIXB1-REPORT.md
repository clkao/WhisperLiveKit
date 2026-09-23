# Pass B1 — apple-speech correctness remediation (session teardown, failure propagation, partial reconciliation, capability honesty, re-pin, docs)

Branch `apple-speech-backend`, worktree `/Users/clkao/git/asr/WhisperLiveKit/.worktrees/apple-speech-backend`.
Base `origin/main` @ `363e4f6`; Pass A tip `aa01520`; tip after B1 `022411a`.
Pass B2 (pause-delivery cadence / late-final pull point / timestamp edge cases) not attempted (out of scope by instruction). The adapter's 300 ms pause-collection hold is untouched.

No push, no PR, no tags, no repo creation. The apple-asr package and other branches/worktrees were not modified.

---

## STEP 0 — re-pin to the released package

**Change.** `apple-asr` v0.1.3 released (tag `v0.1.3`, wheel `apple_asr-0.1.3-py3-none-macosx_26_0_arm64.whl`). Its session clock is now the caller's declared timeline (`pause_end(d)` advances by exactly `d`, forced `reanchor()`, monotone `Final.start` clamp).

- `pyproject.toml` `[tool.uv.sources]`: `apple-asr = { git = "https://github.com/clkao/apple-asr", tag = "v0.1.3" }`.
- `pyproject.toml` `apple-speech` extra floor: `'apple-asr>=0.1.2,<0.2'` → `'apple-asr>=0.1.3,<0.2'`, and the wheel-comment example `0.1.2` → `0.1.3`. The floor bump is required for correctness: the adapter's corrected clock sentence relies on 0.1.3 semantics, so installing 0.1.2 would contradict the documented contract. (The specifier does not resolve on PyPI yet; the package is only on the GitHub release, and `uv build --no-sources` still emits the bare specifier, so the publication property from Pass A is unchanged.)
- `.github/workflows/ci.yml`: the job-scoped git install `...@v0.1.2` → `...@v0.1.3`, so CI tests the same revision the lock pins.
- Adapter module docstring: replaced the now-wrong sentence. Kept the correct half (“Token and buffer times need no remapping”) and gave the new reason: “``apple_asr`` reports its session clock on the caller's own declared timeline (``pause_end(d)`` advances by exactly ``d``), which is the same clock WLK feeds it through the boundary calls.”

**Evidence — lock pins 0.1.3:**

```
$ UV_NO_CONFIG=1 uv lock
Resolved 407 packages in 6.94s
Updated apple-asr v0.1.2 (50290887) -> v0.1.3 (04de6c94)

$ UV_NO_CONFIG=1 uv lock --check
Resolved 407 packages in 312ms          # exit 0

$ grep -n -A1 'name = "apple-asr"' uv.lock
1047:name = "apple-asr"
1048-version = "0.1.3"
1049-source = { git = "https://github.com/clkao/apple-asr?tag=v0.1.3#04de6c94ffb4fbc02562cb67aa90c74c0460ecce" }
12886:    { name = "apple-asr", marker = "extra == 'apple-speech'", git = "https://github.com/clkao/apple-asr?tag=v0.1.3" },

$ .venv/bin/python -c "import apple_asr; print(apple_asr.__version__)"
0.1.3
# direct_url.json: commit_id 04de6c94…, requested_revision v0.1.3
```

---

## FIX 1 — session teardown (review finding 2)

**Change.**
- `whisperlivekit/asr_apple_speech.py`: added an idempotent `AppleSpeechOnlineProcessor.close()`. It flips `_closed`/`_ended`, calls `apple_asr.Stream.close()` (itself idempotent — finalize, end input, terminate child), logs-and-continues if that raises (teardown must never raise), and joins the package's silence-pump thread (`getattr(stream, "_pump", None)`, defensive) so teardown is deterministic; `Stream.close()` only flips the pump's stop flag. Safe to call twice, after `finish()`, after a mid-session failure, or when `_stream` is `None`. `finish()` was left as the EOF path (drain then return); it no longer swallows close errors (`transport.shutdown()` never raises anyway).
- `whisperlivekit/audio_processor.py` `cleanup()`: after cancelling and gathering tasks, unconditionally calls a duck-typed hook — `close_backend = getattr(self.transcription, "close", None); if callable(close_backend): close_backend()` inside `try/except` (logged). This sits on the same cleanup path `basic_server` uses for disconnects, and is reached even when no EOF finalization happened.

**Why it cannot regress other backends.** No other online processor defines `close` (grep: only `processing_queue.py`, `translation_alignatt.py`, `translation_mlx_llm_mt.py` define `close`, none of which is ever `self.transcription`). `getattr(..., "close", None)` returns `None` for `OnlineASRProcessor`, `SimulStreamingOnlineProcessor`, `FunASROnlineASRProcessor`, `Voxtral*OnlineProcessor`, and `_ASRTokenNormalizer` (its `__getattr__` raises `AttributeError` for a missing `close`, which `getattr` with a default absorbs). So the hook is a literal no-op for every other backend.

**Regression tests** (`tests/test_apple_speech_adapter.py`, vendored fake shim):
- `test_cleanup_terminates_the_shim_and_its_thread` — drives a real `AudioProcessor` with the real adapter, runs `cleanup()`, asserts the shim child is reaped, the pump thread is dead, and the stream reports closed.
- `test_cleanup_is_safe_when_the_backend_never_started` — a processor whose `_stream` is `None` (init failed before a session existed); `cleanup()` must not raise.
- `test_close_is_idempotent_and_safe_after_a_backend_error` — kill the child, call `close()` twice.
- `test_close_is_safe_when_no_session_was_ever_created` — `close()` twice with `_stream = None`.

**Observed output:**

```
tests/test_apple_speech_adapter.py::test_cleanup_terminates_the_shim_and_its_thread PASSED
tests/test_apple_speech_adapter.py::test_cleanup_is_safe_when_the_backend_never_started PASSED
tests/test_apple_speech_adapter.py::test_close_is_idempotent_and_safe_after_a_backend_error PASSED
tests/test_apple_speech_adapter.py::test_close_is_safe_when_no_session_was_ever_created PASSED
```

(Each asserts `child.poll() is not None`, `pump.join(2) → not pump.is_alive()`, `stream._closed is True`.)

---

## FIX 2 — backend-failure propagation (review finding 3)

**Change.** `whisperlivekit/asr_apple_speech.py`:
- Replaced the log-and-return `_fail()` with `_terminal(what, exc)`: records the first terminal failure (`_error`), logs once, sets `_ended`, and **re-raises**. `_poll()` raises the stored `_error` first (sticky), so a later call cannot silently become “no tokens”. `finish()` no longer catches close errors, so a terminal drain failure propagates through the EOF path too.
- Only `apple_asr.AppleAsrError` is treated as a backend failure (`poll`, `push`, `pause_start`, `pause_end` catch that type). Programming/input errors (`ValueError`, `TypeError`, `np.asarray` errors, …) are not caught anywhere and propagate as themselves.
- This routes into the existing path: `transcription_processor`'s `except Exception` → `_fail_processing(e)` → `results_formatter` yields `FrontData(status="error", error="ASR failed: BackendError: …")`, and already-committed tokens remain in `state.tokens`.

**Regression tests** (fake shim exits with `exit_code: 7`):
- `test_backend_failure_before_any_output_is_raised` — no token emitted before the dead child; `process_iter()` raises `BackendError("shim exited with status 7 …")`; a second call raises again (sticky).
- `test_backend_failure_after_a_committed_final_keeps_the_text` — a `Final` is delivered and returned, then the child dies; the next drain raises.
- `test_backend_failure_surfaces_through_the_pipeline_and_keeps_text` — full `AudioProcessor`: the client receives `status == "error"` containing `BackendError`, the committed “confirmed” line survives in an earlier response, and `process_audio` re-raises `RuntimeError("ASR failed: BackendError…")`.

**Observed output:**

```
tests/test_apple_speech_adapter.py::test_backend_failure_before_any_output_is_raised PASSED
tests/test_apple_speech_adapter.py::test_backend_failure_after_a_committed_final_keeps_the_text PASSED
tests/test_apple_speech_adapter.py::test_backend_failure_surfaces_through_the_pipeline_and_keeps_text PASSED
```

(In the pipeline test the dead child can surface either as the transport's exit error or the racing failed `push` (`shim stdin is gone (Broken pipe)`); both are the package's terminal `BackendError`, which is what the assertion matches — `"BackendError" in records[-1].error`. The two adapter-level tests assert the exact `exited with status 7` message.)

---

## FIX 3 — partial/final reconciliation (review finding 4)

**Change.** `whisperlivekit/asr_apple_speech.py`: added `_reconcile_partial(final)`, called from `_consume()` in the `Final` branch. A stored partial whose range overlaps the final (start before the final's end, or unknown start) is dropped; a partial whose start is at/after the final's end is a genuinely newer tail and is kept. This stops `get_buffer()` returning a superseded hypothesis forever and stops the EOF fallback promoting stale buffered text into extra committed tokens.

**Regression test:** `test_final_reconciles_the_partial_it_superseded` — scripted fake: `Partial("old guess", [0,0.25])` → `Final("correct words", [0,0.5])` → two idle `get_buffer()` refreshes → `finish()`.
Assertions: final tokens are exactly `["correct","words"]`; both idle refreshes return `""`; `finish()` tail is empty; the concatenated committed texts contain `correct`/`words` exactly once each (no duplicate tokens/translations).

**Observed output:**

```
tests/test_apple_speech_adapter.py::test_final_reconciles_the_partial_it_superseded PASSED
```

---

## FIX 4 — language/locale consistency (review finding 8)

**Change.**
- `whisperlivekit/config.py`: added `APPLE_SPEECH_DEFAULT_LOCALE = "zh-TW"` and `apple_speech_locale_language(locale)` (BCP-47 primary subtag). In `__post_init__` for `backend == "apple-speech"`: reject a locale whose language Apple does not ship; reject `direct_english_translation`; and reject a `lan` that disagrees with the locale's language (with an actionable message naming the fix). `lan in (None, "auto")` still defers to the locale.
- `whisperlivekit/benchmark/runner.py`: chosen behavior for the benchmark path is **reject** (not map). `_run_sample` skips a sample whose language does not match the effective locale (`harness_kwargs["apple_speech_locale"]` or the default `zh-TW`) with an actionable message, instead of constructing a config that would now fail or mislabel the sample. Rationale: Apple's locale is fixed per session and the repo has no vetted language→locale table; inventing region codes (especially `yue`) would be a speculative decision. A user can still run other languages by passing `--config '{"apple_speech_locale": "..."}'`.

**Observed behavior (matching vs mismatching):**

```
locale zh-TW language: zh
match  (lan=zh, loc=zh-TW):  ACCEPTED  -> lan 'zh'
auto   (lan=auto, loc=zh-TW): ACCEPTED -> lan 'auto'
mismatch (lan=en, loc=zh-TW):
  REJECTED -> --language 'en' does not match the configured --apple-speech-locale 'zh-TW' (language 'zh').
             Apple SpeechAnalyzer's locale is fixed per session; set --language 'zh' (or 'auto'),
             or start with a locale for 'en'.
unsupported locale (lan=ru, loc=ru-RU):
  REJECTED -> --apple-speech-locale 'ru-RU' names a language Apple SpeechAnalyzer does not ship.
             Supported languages: de, en, es, fr, it, ja, ko, pt, yue, zh.
direct translation:
  REJECTED -> Apple SpeechAnalyzer does not support direct English translation; use the translation backend instead.
```

**Regression tests:** `test_config_rejects_language_that_disagrees_with_the_locale`, `test_config_rejects_a_locale_language_apple_does_not_ship`, `test_benchmark_skips_a_sample_that_mismatches_the_locale`.

```
tests/test_apple_speech_adapter.py::test_config_rejects_language_that_disagrees_with_the_locale PASSED
tests/test_apple_speech_adapter.py::test_config_rejects_a_locale_language_apple_does_not_ship PASSED
tests/test_apple_speech_adapter.py::test_benchmark_skips_a_sample_that_mismatches_the_locale PASSED
```

---

## FIX 5 — context capability honesty (review finding 9)

**Change.** `whisperlivekit/session_asr_proxy.py`: added `"apple-speech"` to `_NON_PROMPT_BACKENDS`. Chosen option: **register as context-unsupported** (not forward context). Rationale: the adapter builds one `Stream` per session with no `AnalysisContext`, and forwarding validated context would require per-session `Stream` construction plus revalidation against the locale fixed at `AppleSpeechASR` construction — more surface than the capability is worth now. Telling callers the truth is the honest default: `supports_session_context()` and `session_context_capability()` now return `False`, and `validate_session_context()` raises an actionable `ValueError` when a caller supplies a context.

**Regression test:** `test_session_context_is_reported_unsupported` (asserts `supports_session_context(...) is False`, `session_context_capability(...)["supported"] is False`, and `validate_session_context` raises `"not supported by backend"`).

```
tests/test_apple_speech_adapter.py::test_session_context_is_reported_unsupported PASSED
```

---

## FIX 6 — backend documentation

**Change.** `docs/backends.md`: added an “Apple SpeechAnalyzer (macOS 26+)” section, proportionate to the existing backend sections: macOS 26 / Apple-Silicon requirement; install via the released platform wheel (no Swift toolchain) or the pinned git tag, with a note that a **source** install compiles the shim at first use; `--apple-speech-locale` / `--apple-speech-mode`; the cold per-locale asset-download caveat; the language-must-match-locale contract; and that session context is unsupported. No code change.

---

## STEP LAST — SPEC amendment (state dir, not the repo)

`.spacedock/dev/.spacedock-state/apple-speech-backend/SPEC.md`:
- §3.3 clock bullet rewritten: the session clock now “advances with the audio the **caller declares**: every pushed sample plus the pause durations reported at `pause_end(d)`, which advance the clock by exactly `d`.” It carries an explicit `(Amendment, v0.1.3: …)` note stating the previous wording and the over-held-pause/compression rationale.
- §3.2: `audio_time` comment `# seconds consumed (the session clock)` → `# session clock: the caller's declared timeline`.
- “Clock ownership” paragraph rewritten: the shim owns its own (longer) audio timeline; the session clock is the caller's declared timeline, `pause_end(d)` advances by exactly `d` and re-anchors unconditionally, an anchor is refreshed at every `push()`/`pause_start()`/`pause_end(d)`, and a mid-pause final's `start` is clamped up to the previous final's end to keep ranges monotone/non-overlapping.

---

## File list (`git diff --name-only origin/main..HEAD`)

```
.github/workflows/ci.yml
docs/backends.md
pyproject.toml
tests/fixtures/apple_speech_fake_shim.py
tests/test_apple_speech_adapter.py
uv.lock
whisperlivekit/asr_apple_speech.py
whisperlivekit/audio_processor.py
whisperlivekit/backend_support.py
whisperlivekit/benchmark/compat.py
whisperlivekit/benchmark/runner.py
whisperlivekit/config.py
whisperlivekit/core.py
whisperlivekit/parse_args.py
whisperlivekit/session_asr_proxy.py
```

The file set is apple-speech-only. `SPEC.md` lives in the state dir and is intentionally not part of the repo diff.

## Shared-core changes and why they cannot regress other backends

1. `audio_processor.py::cleanup()` — duck-typed `close()` on `self.transcription`. No other backend's online processor defines `close`; `getattr(..., "close", None)` plus `try/except` makes it a no-op (and `_ASRTokenNormalizer.__getattr__` raises `AttributeError`, absorbed by the `getattr` default). Only EOF already-finalized sessions had a teardown path before; this adds one for disconnect/cancel/error without touching any backend-specific code.
2. `config.py` — all new validation is inside `if self.backend == "apple-speech":`. Non-apple configurations are untouched.
3. `session_asr_proxy.py` — added `"apple-speech"` to `_NON_PROMPT_BACKENDS` only. `supports_session_context` for every other backend is unchanged.
4. `benchmark/runner.py` — the new block is gated on `self.backend == "apple-speech"`; other backends take the identical prior path.

## Verification

```
$ .venv/bin/python -m pytest -q -rs tests/test_apple_speech_adapter.py
21 passed in 9.18s            # 0 skipped

$ .venv/bin/python -m pytest -q tests/test_apple_speech_adapter.py tests/test_backends.py tests/test_silent_backend_guard.py
65 passed, 3 warnings in 10.72s

$ .venv/bin/python -m pytest -q tests/           # full repo suite
335 passed, 15 skipped, 17 warnings, 17 errors in 25.33s
# The 17 errors are collection/setup errors in the pre-existing integration tests
# (tests/test_pipeline.py, tests/test_asr_coalescing_pipeline.py) that download
# LibriSpeech/AMI samples: "401 Client Error" -> "Failed to download any test
# samples". This is the sandbox's network, not this branch. No apple-speech test
# errored or skipped.
# `pytest -q` at the repo root additionally tries to collect third_party/qwen3-asr-causal
# (submodule) and aborts with duplicate-basename/missing-jiwer collection errors; the
# project's CI runs `pytest -q tests/`, which is what is reported above.

$ UV_NO_CONFIG=1 uv lock --check
Resolved 407 packages in 298ms          # exit 0

$ .venv/bin/python -m ruff check .
All checks passed!
```

## Unresolved / notes

- `AppleAsrError` is distinguished from programming/input errors, but a shim `error` **event** (non-terminal per the package) is still only logged, not surfaced. It is not established as terminal, so forcing a session failure on it would be a behavior change beyond the review finding; flagged for a future decision.
- The package's `Stream.__init__` spawns the child before it validates `hello` and does not kill it if the handshake fails (a package-level leak). WLK cannot close a `Stream` it never received; the adapter's `close()` is safe when no session was created, but the child leak on handshake failure remains an upstream issue.
- The package's silence-pump thread is joined via a defensive `getattr(stream, "_pump")` (private attribute). `Stream.close()` sets the pump's stop flag but does not join it; the adapter's join makes teardown deterministic. If a future package renames `_pump`, the join silently no-ops (pump is a daemon thread that still stops via `_closing`).
- The re-pin bumped the `apple-speech` extra floor to `>=0.1.3` (necessary because the documented clock contract is 0.1.3's). The specifier still cannot resolve on PyPI (package not published there); `uv build --no-sources` continues to emit the bare specifier, so the publication property from Pass A is preserved.
- Fixes 4/5 changed the default-config capability/validation surface for apple-speech; the measured runtime defaults (`pause_commit 0.08`, `commit_interval 0.0`, `mode streaming`) and the 300 ms collection hold are unchanged.
