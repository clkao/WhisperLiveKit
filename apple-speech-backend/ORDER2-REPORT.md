# ORDER 2 REPORT — `apple-asr` package: tests + docs

Status: **implemented and verified on this machine** (macOS 26.6.2, arm64,
Speech framework available; CPython 3.12.9 for the main runs).
Repo: `/Users/clkao/git/asr/apple-asr` (order 1 at `3901c94`; this order leaves
the tree dirty — nothing staged, nothing committed, see §10.1).
Contract: `_work/apple-asr-package/SPEC.md` §9 (acceptance bar) + §10, the six
amendments in the order-2 task, `MEASUREMENTS.md`, and the order-1 report's §3
deviations / §4 open questions.

---

## 0. Result in one paragraph

All eleven §9 tests are implemented and green: nine against a scripted fake shim
(run anywhere, no macOS 26, no Speech, no writable `~/.cache`) and two macOS-26
integration tests that **ran here** (not skipped) against the real shim on the
bundled clip. All seven amendments are implemented. The silent-backend guard is
feed-rate aware. The order-1 `Final.start` clamp decision was settled by
experiment: the clamp is **kept** — the accounting test fails without it (a real
0.05 s overlap appears in the ordinary push/pause/pause_end cycle). One order-1
transport bug was found and fixed (stdout lines arriving in the same pipe read as
`hello` were discarded). Six guard tests were each mutated to prove they can
fail; every mutation was reverted. `ruff check .` is clean; the suite runs on
3.10-3.13; a fresh venv install plus the README quickstart block runs verbatim.

---

## 1. Files added / changed

### Added

| file | what / why |
|---|---|
| `src/apple_asr/replay.py` | the real-time replay driver (port of `_work/sa-spike/drive_live.py`): `load_wav`, `segment` (the crude RMS VAD), `replay()` returning measurements as data (`ReplayResult`, `PauseCommit`), and `main()` for the `apple-asr-replay` console script |
| `tests/fixtures/fake_shim.py` | the scripted fake shim (560 lines): speaks wire protocol v1 with no Apple framework, driven by a JSON scenario file, dumps observable state on exit |
| `tests/fixtures/audio/zh_long.wav` | the bundled 31.55 s / 16 kHz mono clip the golden fixture was scored on (992 KB) |
| `tests/golden/zh_long_ideal.jsonl` | the WhisperLiveKit golden cadence fixture for that audio (copied in; WLK itself untouched) |
| `tests/support.py` | `FakeBackend` harness (installs the fake shim into a tmp `APPLE_ASR_CACHE`, mirrors §6 resolution order 3), `speech`/`silence`/`drain`/`wait_for` helpers, `macos26_available()` |
| `tests/conftest.py` | the `fake` fixture, the integration skip hook, the `zh_long_audio` fixture |
| `tests/test_handshake.py` (6) | §9 test 1 + the buffer-loss regression |
| `tests/test_events.py` (4) | §9 test 2 |
| `tests/test_pause.py` (3) | §9 test 3 |
| `tests/test_control.py` (5) | §9 tests 4 + 5 |
| `tests/test_failures.py` (5) | §9 test 6 incl. the silent-backend guard |
| `tests/test_backpressure.py` (2) | §9 test 7 |
| `tests/test_locales.py` (5) | §9 test 8 |
| `tests/test_platform.py` (4) | §9 test 9 |
| `tests/test_config.py` (10) | amendment 1 (`mode`) + amendment 7 (measured defaults) + locale/context wiring |
| `tests/test_clock_accounting.py` (2) | amendment 4 (exact accounting + the clamp's documented case) |
| `tests/test_cli.py` (4) | amendment 6 (`--help` must not build) + the replay parser |
| `tests/test_replay.py` (5) | the replay driver, on the fake shim (so it is covered off-macOS too) |
| `tests/test_integration_file.py` (2) | §9 test 10 (`--file`, macOS 26 only) |
| `tests/test_integration_replay.py` (4) | §9 test 11 (real-time replay + golden cadence, macOS 26 only) |

61 tests total: 55 in the fake-shim suite, 6 integration.

### Changed

| file | change |
|---|---|
| `src/apple_asr/stream.py` | `mode`, `reporting_option`, `silent_timeout` parameters; `_resolve_config`/`_mode_for`; the silent-backend guard (`_check_silent_backend`, `_wait_slice`, non-blocking `poll`/`_next_event` loops that re-check it); docstrings |
| `src/apple_asr/transport.py` | `build_argv(..., fast_results=)`; liveness clocks (`last_event_monotonic`, `first_audio_monotonic`); **bugfix**: hello's bulk read no longer discards trailing lines (`_readline_with_timeout` -> `(line, leftover)`, new `_handle_line`, raw-fd `_read_loop`); the clamp comment now documents the case and names the regression test |
| `src/apple_asr/cli.py` | `--help`/no-args are special-cased to print the flag list without resolving or building; the full flag list moved into `USAGE`, with `--fast` marked deprecated |
| `src/apple_asr/shim/speechanalyzer.swift` | `--help` text: `--no-fast`/`--no-confidence` listed, `--fast` marked deprecated/ignored (rebuilt: the binary changed) |
| `src/apple_asr/shim.py` | expanded docstrings on `list_locales`/`ensure_installed`/`shim_info` |
| `src/apple_asr/__init__.py` | module docstring points at `mode` and `apple_asr.replay` |
| `pyproject.toml` | `apple-asr-replay` console script; `[tool.pytest.ini_options]` (testpaths, `-ra`, markers, a DeprecationWarning filter); ruff per-file ignore for the fake-shim script |
| `README.md` | rewritten: install, both quickstarts, the clock-ownership section, input modes, the public API, the protocol section (incl. the 4-element `runs` extension), measured modes table, limitations, `APPLE_ASR_CACHE`, dev/test instructions |
| `.github/workflows/ci.yml` | the ubuntu matrix now runs `pytest -q -m "not integration"`; the macOS job is documented (no public macOS 26 runner exists yet) |
| `.gitignore` | ignore `.pi-subagents/` (agent-runtime artifacts) |

### How the fake shim works (so the tests can be judged)

`tests/fixtures/fake_shim.py` reads a scenario JSON from `APPLE_ASR_FAKE_SCENARIO`
and writes an observability JSON (frames consumed, commands, every wire event,
argv) to `APPLE_ASR_FAKE_STATE` on exit — so assertions are made against *the
wire*, not against the client's own bookkeeping. Three modes:

* `emulate` (default) — reads float32 PCM, emits a `partial` every N frames, and
  runs an **endpointer** that commits a `final` + `commit` once it has seen
  `pause_commit` seconds of consecutive silence. Faithful to the measured
  behaviour in two ways that matter: (a) it *arms* at the quiet threshold and
  fires on the **next chunk**, so a lump of silence at the pause onset does not
  publish a final (order 1 measured >1.2 s for a pre-roll alone, 0.05-0.15 s with
  the pump); (b) its final ranges **tile** the timeline (`[0, 0.5]`, `[0.5, 1.0]`),
  the worst case for the clock mapping.
* `scripted` — emits exactly the listed steps, each once, on a trigger
  (`start`, `frames`, `bytes`, `cmd`, `eof`) with `emit`/`raw`/`count`/`repeat`/
  `sleep`/`exit`.
* `silent` — consumes stdin, emits nothing after `hello` (the guard's input).

The harness installs it as `<tmp>/apple_asr/<shim_version>/apple-asr-shim` and
points `APPLE_ASR_CACHE` at `<tmp>`, so tests exercise §6 resolution step 3 and
never touch `~/.cache` (which is still not writable from this sandbox).

---

## 2. §9 coverage

| §9 | test | file |
|---|---|---|
| 1 handshake | `test_handshake_accepts_matching_protocol`, `..._rejects_protocol_mismatch_naming_both_versions`, `..._rejects_negotiated_format_mismatch`, `..._rejects_a_first_line_that_is_not_hello`, `test_capabilities_are_logged_not_assumed`, `test_lines_emitted_with_hello_are_not_lost` | test_handshake.py |
| 2 event mapping | `test_partials_supersede_and_runs_become_words`, `test_final_reason_is_propagated_from_the_commit_ack`, `test_confidence_is_optional_and_reaches_the_shim`, `test_runs_are_optional_and_unknown_event_types_are_ignored` | test_events.py |
| 3 pause synthesis | `test_pause_commit_lands_within_pause_commit_plus_epsilon`, `test_a_pause_writes_exactly_its_reported_duration_as_silence` (frame count == `round(d*16000)`, and the shim's consumed-frame count == client bytes/4), `test_the_pump_delivers_silence_while_the_pause_is_open` | test_pause.py |
| 4 flush | `test_flush_through_emits_exactly_one_commit_and_flush_reason` (one `commit` per `finalize`, `Final.reason == "flush"`), `test_flush_without_through_uses_the_cursor` | test_control.py |
| 5 close/EOF | `test_close_is_idempotent_and_drains_pending_finals` (Ended(closed), exactly one terminal event), `test_input_after_close_raises_session_closed`, `test_child_exit_without_ended_yields_eof` (Ended(eof)) | test_control.py |
| 6 failure paths | `test_nonzero_exit_mid_session_raises_backend_error_with_stderr_tail`, `test_malformed_and_unknown_lines_warn_but_do_not_crash`, `test_silent_backend_guard_fires_when_fed_at_real_time`, `test_guard_does_not_fire_on_a_fast_fed_burst`, `test_guard_is_off_when_silent_timeout_is_zero` | test_failures.py |
| 7 backpressure | `test_burst_beyond_queue_size_drops_oldest_with_one_warning` (newest kept, `stats.dropped == BURST - delivered`, exactly one warning), `test_no_drop_when_the_caller_keeps_up` | test_backpressure.py |
| 8 locales | `test_list_locales_parses_shim_output`, `..._tolerates_an_empty_install_set`, `test_ensure_installed_succeeds`, `..._raises_asset_unavailable_with_stderr`, `test_shim_info_reports_the_hello_identity` | test_locales.py |
| 9 platform gate | `test_non_darwin_raises_unsupported_platform`, `test_macos_25_raises_unsupported_platform`, `test_gate_applies_to_the_module_helpers`, `test_supported_platform_is_a_noop` | test_platform.py |
| 10 `--file` (macOS 26) | `test_file_mode_commits_with_word_runs`, `test_file_mode_timestamps_are_monotonic_and_never_overlap` | test_integration_file.py |
| 11 live replay (macOS 26) | `test_every_pause_commit_lands_within_a_third_of_a_second`, `test_replay_produces_a_full_transcript_with_word_runs`, `test_cadence_matches_the_wlk_golden_fixture`, `test_load_wav_matches_the_session_contract` | test_integration_replay.py |

Items 10-11 carry the `integration` marker **and** an explicit
`@pytest.mark.skipif(not macos26_available())`, so the ubuntu job never runs
them; that same job also selects `-m "not integration"`. On macOS 26 they can
only fail, never skip.

### Amendments

1. **`mode`** — `Literal["streaming","accurate"] | None = None` (documented:
   `None` behaves as `"streaming"`), plus `reporting_option`. A small deviation
   in the literal default is explained in §9.1; the *behaviour* asked for
   (streaming = progressive + fastResults / accurate = transcription, no
   fastResults; explicit knobs keep working; conflicts rejected) is exact.
   Verified end-to-end: the fake shim's argv shows `--no-fast` only in accurate
   mode and `preset=transcription`, and `Stream(preset="transcription")` (the
   order-1 spelling) still works.
2. **4-element `runs`** — kept and documented in the README protocol section;
   `test_confidence_is_optional_and_reaches_the_shim` asserts 3-element runs map
   to `confidence=None` and that `--no-confidence` reaches the shim.
3. **Silent-backend guard** — `Stream.silent_timeout: float = 30.0` (0 disables).
   Fire condition: *no shim line for `silent_timeout` seconds* **and** audio fed
   at no faster than real time (`audio_s <= elapsed * 1.05 + 1.0`; the 1.0 s
   grace covers pipelines that hand over 0.1-0.5 s chunks, whose whole duration
   is credited at push time). It raises from `poll()`/`events()`/`aevents()` (with
   a bounded wait slice so a blocked consumer still notices), names the shim path
   and the disable knob.
4. **Exact accounting + the clamp** — §6 below (decision D-4).
5. **`--fast`** — documented as a **deprecated, ignored** flag (kept: SPEC §4
   lists it; removal is a future major). Stated in `cli.py --help`, the Swift
   `--help`, and the README; `test_help_prints_the_flags_without_building`
   asserts the deprecation text is present.
6. **`--help` never builds** — `cli.main()` prints `USAGE` for `--help`/`-h` and
   for no arguments and returns 0 *before* `resolve_shim()`; verified with a
   cache dir that is never created.
7. **Measured defaults untouched** — `pause_commit 0.08`, `commit_interval 0.0`,
   `preset`/`mode` streaming; asserted in code and on the wire by
   `test_measured_defaults_are_not_improved`.

---

## 3. Verification (commands + observed output)

All commands were run from `/Users/clkao/git/asr/apple-asr` with
`APPLE_ASR_CACHE=/Users/clkao/git/asr/apple-asr/.cache` (the sandbox cannot
create `~/.cache`; that is exactly the documented escape hatch) and the venv
`/tmp/apple-asr-venv` (CPython 3.12.9) unless stated.

### 3.1 Full suite, fake shim **and** macOS-26 integration (no skips)

```
$ APPLE_ASR_CACHE=$PWD/.cache /tmp/apple-asr-venv/bin/python -m pytest -q -rs
.............................................................            [100%]
61 passed in 43.59s
```

`-rs` is there to prove nothing was skipped: no skip summary is printed, and the
integration tests genuinely ran (`§9 test 10`: 2 passed in 0.79 s, `--file` on the
real shim; `§9 test 11`: 6 passed/55 deselected in 31.83 s, ~31 s of which is
real-time audio).

### 3.2 The fake-shim suite alone (what the ubuntu CI job runs)

```
$ /tmp/apple-asr-venv/bin/python -m pytest -q -m "not integration"
.......................................................                  [100%]
55 passed, 6 deselected in 11.68s
```

Well under the one-minute budget.

### 3.3 Integration cadence vs the WLK golden (same audio)

```
$ /tmp/apple-asr-venv/bin/python -m pytest -q -m integration -s
....
cadence: ours=spans=23 events=145 partials=132 finals=12 wall=30.9s audio=32.0s
ended=closed pauses=11 missed=0 max_pause_latency=0.107s first_commit=3.40s
mean_commit_gap=2.60s golden(finals=12, first=2.99s)
..
6 passed, 55 deselected in 31.83s
```

Reproduces the measured order-1 numbers: 12 finals vs the golden's 12, first
commit 3.40 s vs 2.99 s (asserted within ±1.5 s), mean gap 2.60 s vs the
recorded 2.55 s, 11/11 pauses committed, worst pause→commit latency 0.107 s
(§9 test 11 asserts ≤ 0.3 s — the end-to-end version of test 3).

`--file` mode (test 10) on the same clip: 2 finals, 129 word runs, all 4-element,
timestamps monotone and non-overlapping, 0.44 s wall.

### 3.4 `ruff check .`

```
$ /tmp/apple-asr-venv/bin/ruff check .
All checks passed!
```

### 3.5 Python matrix (3.10 - 3.13)

```
$ for V in 3.10 3.11 3.12 3.13; do uv venv --python $V /tmp/ord2-$V; \
    VIRTUAL_ENV=/tmp/ord2-$V uv pip install -e '.[dev]'; \
    /tmp/ord2-$V/bin/python -m pytest tests/ -q -m "not integration"; done
== python 3.10: Python 3.10.19
55 passed, 6 deselected in 14.08s
== python 3.11: Python 3.11.14
55 passed, 6 deselected in 13.97s
== python 3.12: Python 3.12.9
55 passed, 6 deselected in 13.84s
== python 3.13: Python 3.13.12
55 passed, 6 deselected in 14.12s
```

### 3.6 Fresh venv install + the README quickstart, verbatim

```
$ uv venv --python 3.12 /tmp/ord2venv && VIRTUAL_ENV=/tmp/ord2venv uv pip install -e '.[dev]'
 + apple-asr==0.1.0 (from file:///Users/clkao/git/asr/apple-asr)
 + pytest==9.1.1
 + ruff==0.16.7
$ /tmp/ord2venv/bin/python -c "import apple_asr; print(apple_asr.__version__)"
0.1.0

# the README's first quickstart block, extracted from README.md and run as-is:
$ APPLE_ASR_CACHE=$PWD/.cache /tmp/ord2venv/bin/python /tmp/fsw/quickstart.py
session clock: 1.4
$ echo $?
0
```

`1.4` is exactly 1.0 s pushed + the reported 0.4 s pause — the clock accounting
the README describes. The README's accurate-mode block and the public-API import
block were extracted and run the same way (both exit 0).

Also verified from the fresh venv, into a *fresh* cache:

```
$ APPLE_ASR_CACHE=/tmp/ord2buildcache /tmp/ord2venv/bin/python -m apple_asr.build
building shim: /usr/bin/swiftc -O -parse-as-library .../speechanalyzer.swift -o /tmp/ord2buildcache/...
shim ready: /tmp/ord2buildcache/apple_asr/0.1.0/apple-asr-shim
$ APPLE_ASR_CACHE=/tmp/ord2buildcache /tmp/ord2venv/bin/apple-asr-shim --stdin < /dev/null | head -1
{"type":"hello","protocol":1,"shim_version":"0.1.0",...}
```

### 3.7 Amendment 6 — `--help` does not build

```
$ APPLE_ASR_CACHE=/tmp/empty-cache-ord2 /tmp/ord2venv/bin/apple-asr-shim --help | head -3
apple-asr-shim - Apple SpeechAnalyzer streaming shim (console script)

usage: apple-asr-shim {--stdin|--file PATH|--mic} [options]
help exit=0
$ ls /tmp/empty-cache-ord2
ls: /tmp/empty-cache-ord2: No such file or directory
```

### 3.8 The replay console script, end to end on the real shim

```
$ APPLE_ASR_CACHE=$PWD/.cache /tmp/ord2venv/bin/apple-asr-replay \
      tests/fixtures/audio/zh_long.wav --locale zh-TW --pace 0 --max-latency 0.3
[  3.40s] pause 0.22s -> +0.229s  FINAL[pause] '我們今天來討論鐳射在醫學上的應用'
[  7.12s] pause 0.28s -> +0.059s  FINAL[pause] '鐳射技術可以精確地切除腫瘤組織'
...
[ 29.54s] pause 0.28s -> +0.097s  FINAL[pause] '雷射在現代醫學中扮演著越來越重要的角色'
spans=23 events=144 partials=131 finals=12 wall=1.6s audio=32.0s ended=closed
pauses=11 missed=0 max_pause_latency=0.229s first_commit=3.25s mean_commit_gap=2.61s
cli exit=0
```

---

## 4. Falsifiability — mutation table

Harness: `/tmp/fsw/mutate.py` — apply one edit, run the one guard test with `-x`,
print the failure, restore the file in a `finally`. Every source file was
confirmed byte-identical afterwards (`grep -rn MUTATION src/ tests/` is empty, and
`git diff` contains no mutation text). All six mutations made their test **fail**.

| # | guard test | file | exact mutation | observed failure line |
|---|---|---|---|---|
| a | `tests/test_pause.py::test_pause_commit_lands_within_pause_commit_plus_epsilon` (§9 test 3) | `stream.py` | in `_silence_pump`, replaced `self._write_silence(tick_frames)` with `pass  # MUTATION: silence pump disabled (pre-roll only)` (the pre-roll alone must not publish a final) | `E AssertionError: no Final landed during the pause` / `E assert None is not None` / `1 failed in 2.31s` |
| b | `tests/test_clock_accounting.py::test_final_ranges_never_overlap_in_normal_use` | `transport.py` | in `_make_final`, `if start < self._last_final_end:` -> `if start < self._last_final_end and False:  # MUTATION: clamp removed` | `E AssertionError: final ranges overlap: 0.362 > 0.31200000000000006` / `E assert 0.31200000000000006 >= (0.362 - 1e-09)` / `1 failed in 0.80s` |
| c | `tests/test_backpressure.py::test_burst_beyond_queue_size_drops_oldest_with_one_warning` (§9 test 7) | `transport.py` | in `_EventQueue.put`, dropped `self._dq.popleft()`/`append` and `return True` immediately — i.e. **drop-newest** instead of drop-oldest | `E AssertionError: the newest events are kept (drop-oldest)` / `E assert 'p299' in ['p0', 'p1', 'p2', ...]` / `1 failed in 10.75s` |
| d | `tests/test_handshake.py::test_handshake_rejects_protocol_mismatch_naming_both_versions` (§9 test 1) | `transport.py` | in `_read_and_validate_hello`, `if theirs != PROTOCOL_VERSION:` -> `if False:  # MUTATION: protocol check removed` | `E Failed: DID NOT RAISE ProtocolMismatch` / `1 failed in 0.25s` |
| e | `tests/test_failures.py::test_nonzero_exit_mid_session_raises_backend_error_with_stderr_tail` (§9 test 6) | `transport.py` | in `_finish`, `if code not in (0, None) and not saw_ended:` -> `... and False:  # MUTATION` | `E Failed: DID NOT RAISE BackendError` / `1 failed in 5.25s` |
| f | `tests/test_failures.py::test_silent_backend_guard_fires_when_fed_at_real_time` | `stream.py` | in `_check_silent_backend`, `if silent_s >= timeout:` -> `if silent_s >= timeout * 1000:  # MUTATION: guard never fires` | `E AssertionError: guard took 30.11s` / `E assert 30.106733417138457 < (0.6 + 1.5)` / `1 failed in 30.36s` |

Notes on (f): with the guard neutered the test does not hang — the fake shim's
own 30 s wall cap kills the child, so a `BackendError` (about the child's exit)
arrives 30 s later, long past the 0.6 s + 1.5 s budget, and the timing assertion
fails. That is the correct detection: the guard's job is to fire *early*.

Extra structure behind (b): the same clamp-removal mutation also fails
`test_overlap_is_repaired_when_the_drift_diverges_between_finals`
(`got 0.3999999999999999 vs 0.4`), i.e. both the ordinary and the engineered case
are guarded.

---

## 5. The exact-clock-accounting experiment and the clamp decision (D-4)

**What was asked:** add an exact-clock-accounting test (final ranges must not
overlap without clamping), then either remove the clamp (if the test passes
without it) or keep it and document the exact case plus a regression test.

**What I did:** wrote `tests/test_clock_accounting.py` with two tests, then ran
the clamp-removal mutation (row b above) against both:

* `test_final_ranges_never_overlap_in_normal_use` — an ordinary
  push(0.5 s)/pause_start/pause_end(0.5) ×3 + flush cycle. It asserts the §3.3
  invariant, that the shim's ranges tile, that the mapped ends stay inside
  `audio_time`, and that the clock equals `3*(0.5+0.5)+0.5 = 3.5 s` exactly.
  **With the clamp removed it fails**: `final ranges overlap: 0.362 > 0.312` — a
  0.05 s (one pump tick) real overlap.
* `test_overlap_is_repaired_when_the_drift_diverges_between_finals` — the same
  case engineered deterministically: final 1 fires right after the 0.10 s pause
  pre-roll; final 2 fires after the pause has been open ~0.25 s longer (more
  synthesized silence written before its arrival, i.e. a more negative drift).
  Without the clamp, final 2's start maps to 0.2 instead of 0.4 (a 0.2 s
  overlap); with it, `second.start == first.end` exactly.

**Decision: KEEP the clamp.** Rationale: the accounting test does **not** pass
without it, and the failure is not an artifact of the fake shim — the mechanism is
structural. Session time is the caller's timeline (pushed audio + the reported
pause duration), the shim's is its frame timeline, and the two differ by the
synthesized silence while a pause is open. A commit that lands *during* a pause is
mapped with the drift of its arrival instant, so two consecutive finals are mapped
with slightly different drifts and the later start can fall before the earlier
end. Order 1 saw the same thing against the real shim and patched it with exactly
this clamp. Removing it would violate the §3.3 invariant ("final ranges never
overlap") that downstream consumers rely on when concatenating finals.

**Documented in code:** the comment in `Transport._make_final` now states the
mechanism, the measured magnitudes (0.05 s typical, up to the 0.10 s pre-roll),
and names `tests/test_clock_accounting.py` as the regression test.
**Documented in the README:** the clock section explains the drift and why the
clamp exists. **Cost, stated plainly:** a clamped final's `start` can be nudged
later (up to the drift divergence) than the shim's own range start; the invariant
is bought with that nudge, not with a re-derived mapping.

---

## 6. Bug found and fixed while building the tests

**Transport dropped stdout lines that arrived with `hello`.**
`_readline_with_timeout` read up to 64 KB from the pipe, returned the first line,
and *discarded the rest of the buffer*. The real shim emits `hello` early and
nothing else for a while, so order 1 never hit it — but a shim that emits
`hello + partial + final` immediately (entirely legal; `hello` is only required to
be *first*) had those events silently lost, which made the first version of the
fake-shim tests flaky. Fixed by returning the leftover bytes and feeding them to
the reader thread first; `test_lines_emitted_with_hello_are_not_lost` is the
regression test. This is a correctness fix in the client, not test scaffolding.

---

## 7. Deviations and interpretation notes

1. **`mode`'s default value is `None`, not `"streaming"`** (the literal is
   `Literal["streaming","accurate"] | None = None`; `None` behaves as
   `"streaming"` and is documented as such). Reason: with a literal default of
   `"streaming"` there is no way to tell `Stream()` from
   `Stream(mode="streaming")`, so the conflict check ("reject conflicting
   explicit kwargs") would have to reject the *order-1* spelling
   `Stream(preset="transcription")` — which the task forbids ("do not break
   existing kwargs"). With `None` as the sentinel: `Stream(preset="transcription")`
   still works (the explicit knob is authoritative when `mode` is not passed),
   and `Stream(mode="accurate", preset="progressive")` raises a `ValueError`
   naming both values and the fix. `Stream.mode` always reports the resolved
   label. If the literal default matters more than order-1 compatibility, this is
   a one-line change plus a test update — flagged as an open question (§9.2).
2. **`reporting_option` is a new keyword**, not an order-1 one (order 1 had only
   the shim's `--fast`/`--no-fast`). Values `"volatileResults" | "fastResults" |
   None`. It is never passed as `--fast`; `fast_results=False` is expressed on the
   wire as `--no-fast`.
3. **`--fast` was documented as deprecated, not removed** (amendment 5 offers the
   choice): SPEC §4 lists it, and removing a documented CLI flag in a test/docs
   order would be a compatibility break. Stated in three places (shadow CLI help,
   Swift help, README).
4. **The golden cadence comparison lives in test 11, not test 10.** `--file` is
   batch mode: the analyzer commits at file boundaries (2 finals here, 129 word
   runs), so its commit *cadence* is not comparable to a streaming golden (12
   finals). Test 10 therefore asserts the structural properties the spec asks for
   (finals ≥ 1, word runs present, monotone, non-overlapping) and test 11 — the
   real-time push/pause path, same audio — asserts the cadence (12 vs 12, first
   commit 3.40 s vs 2.99 s within ±1.5 s, mean gap 2.60 s vs the recorded 2.55 s).
   Documented in the test module docstring.
5. **Integration skips are implemented twice on purpose**: an explicit
   `@pytest.mark.skipif(not macos26_available())` in each integration module *and*
   a `pytest_collection_modifyitems` hook in conftest. The hook exists so a future
   integration module cannot forget the guard; neither mechanism skips on macOS 26.
6. **The bundled clip is 992 KB** (`tests/fixtures/audio/zh_long.wav`, 31.55 s).
   The spec says "a bundled short clip"; trimming it would break the golden
   comparison, which was produced from exactly this audio. If repo size is a
   concern, the alternative is to fetch it in a fixture (network in tests).
7. **The CER/WER harness is still not ported** (order 1 §11 item 5 split it off;
   the task's order-2 scope names only the replay driver). The README quotes the
   measured numbers and says where they come from.
8. **`apple-asr-shim --help` now prints the console script's own flag list**
   (a static copy in `cli.py`) instead of exec'ing the shim's `--help`. That is
   the point of amendment 6 (no build), and the flag list is complete; the Swift
   `--help` remains for direct binary use.
9. **`finalize`'s `Final.reason` pairing is unchanged**: a wire `reason` wins, else
   the pending `commit` ack reason, else `"pause"`. Tested.
10. **The `runs` 4-element form is unchanged** (kept per amendment 2) and now
    documented in the README's protocol section.
11. **Context/locale wiring asserted on the wire** (`test_context_and_locale_reach_the_shim`),
    since `Stream(context=...)` goes through `--context` at construction, and
    `{"cmd":"context"}` remains transport-reachable but not public (order 1 D9).

---

## 8. Residual risks

* The pause-latency test asserts `≤ pause_commit + 0.25 s` (measured ~0.07 s
  here). The slack is for a loaded CI runner; the observed margin is >3×.
* Test 3's "quiet start frame" is quantized to the shim's read-chunk boundary, so
  it asserts `8000 ≤ frame ≤ 10000` with the reason documented, rather than
  exact equality.
* The silent-guard threshold is a policy choice (`1.05× + 1.0 s grace`). A caller
  that feeds genuinely in >1 s chunks faster than real time could keep the guard
  suppressed; the knob (`silent_timeout=0`, or a larger value) is the escape.
* Integration tests need a built shim and (here) `APPLE_ASR_CACHE`, because the
  sandbox cannot write `~/.cache`. They fail loudly rather than skipping on macOS
  26, which is intended but means the command in the README must be followed.
* `--mic` is still untested (no mic TCC in the sandbox) — unchanged order-1 risk.

---

## 9. Open questions

1. **Commit or not?** Order 1 was committed (`3901c94`); this order leaves the
   work uncommitted (nothing staged) because committing was not requested. Say the
   word and I will commit it as one changeset (source + tests + docs).
2. **`mode` sentinel:** keep `mode: ... | None = None` (order-1-compatible) or
   switch to the literal `= "streaming"` default from the amendment and accept
   that `Stream(preset="transcription")` becomes an error? Current choice is
   documented above; it is the only genuine interpretation call in this order.
3. **The 992 KB wav fixture**: keep it committed, or move it behind an env var /
   download step? Currently committed because the golden comparison needs it.
4. **macOS 26 CI job**: no public GitHub runner exists (`macos-15` is newest), so
   the workflow documents the manual invocation instead of declaring a red job. If
   a self-hosted macOS 26 runner is ever added, the job is two lines.
5. **`--help` flag list duplication**: `cli.py`'s `USAGE` is a hand-maintained copy
   of the shim's flags. A generated list (or a `--shim-help` escape that does
   build) would remove the drift risk; not done because it needs a shim.

---

## 10. Housekeeping

1. `git status --porcelain` (repo `/Users/clkao/git/asr/apple-asr`): 11 modified
   files, 2 new paths (`src/apple_asr/replay.py`, `tests/`), **0 staged**.
   Nothing was committed.
2. WhisperLiveKit was **not modified** by this order; the only file written under
   it is this report. (The golden fixture and the audio clip were *copied out of*
   WLK/`_work` into the package repo.)
3. `.pi-subagents/` (this session's agent-runtime artifacts) was added to
   `.gitignore` so it does not pollute `git status`.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "All 11 SPEC §9 tests + 7 amendments + 6 falsifiability mutations implemented inside /Users/clkao/git/asr/apple-asr only: 14 test modules (61 tests), src/apple_asr/replay.py, README/pyproject/ci/workflow edits. No WhisperLiveKit file touched except this report; no new runtime deps (numpy+stdlib); order-1 API only widened (mode/reporting_option/silent_timeout/fast_results kwarg, apple-asr-replay script)."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Full suite 61 passed / 43.59s incl. the 6 macOS-26 integration tests (no skips, -rs), fake-shim-only 55 passed / 11.68s, ruff clean, py3.10-3.13 all pass, fresh-venv install + README quickstart executed verbatim ('session clock: 1.4'), shim rebuilt and --file/--help/replay CLI run against the real shim, 6/6 guard tests falsified by mutation with pasted failure lines (all reverted)."
    }
  ],
  "changedFiles": [
    "src/apple_asr/stream.py",
    "src/apple_asr/transport.py",
    "src/apple_asr/cli.py",
    "src/apple_asr/shim.py",
    "src/apple_asr/__init__.py",
    "src/apple_asr/shim/speechanalyzer.swift",
    "src/apple_asr/replay.py",
    "README.md",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    ".gitignore",
    "tests/conftest.py",
    "tests/support.py",
    "tests/fixtures/fake_shim.py",
    "tests/fixtures/audio/zh_long.wav",
    "tests/golden/zh_long_ideal.jsonl",
    "tests/test_handshake.py",
    "tests/test_events.py",
    "tests/test_pause.py",
    "tests/test_control.py",
    "tests/test_failures.py",
    "tests/test_backpressure.py",
    "tests/test_locales.py",
    "tests/test_platform.py",
    "tests/test_config.py",
    "tests/test_clock_accounting.py",
    "tests/test_cli.py",
    "tests/test_replay.py",
    "tests/test_integration_file.py",
    "tests/test_integration_replay.py",
    "WhisperLiveKit/_work/apple-asr-package/ORDER2-REPORT.md"
  ],
  "testsAddedOrUpdated": [
    "tests/test_handshake.py",
    "tests/test_events.py",
    "tests/test_pause.py",
    "tests/test_control.py",
    "tests/test_failures.py",
    "tests/test_backpressure.py",
    "tests/test_locales.py",
    "tests/test_platform.py",
    "tests/test_config.py",
    "tests/test_clock_accounting.py",
    "tests/test_cli.py",
    "tests/test_replay.py",
    "tests/test_integration_file.py",
    "tests/test_integration_replay.py"
  ],
  "commandsRun": [
    {"command": "APPLE_ASR_CACHE=$PWD/.cache python -m pytest -q -rs", "result": "passed", "summary": "61 passed in 43.59s (55 fake-shim + 6 macOS-26 integration; no skips)"},
    {"command": "python -m pytest -q -m \"not integration\"", "result": "passed", "summary": "55 passed, 6 deselected in 11.68s"},
    {"command": "python -m pytest -q -m integration -s", "result": "passed", "summary": "6 passed; 12 finals vs golden 12, first commit 3.40s vs 2.99s, 11/11 pauses, max latency 0.107s"},
    {"command": "ruff check .", "result": "passed", "summary": "All checks passed!"},
    {"command": "uv venv + uv pip install -e '.[dev]' (3.10/3.11/3.12/3.13)", "result": "passed", "summary": "55 passed, 6 deselected on every interpreter"},
    {"command": "fresh venv install (py3.12) + README quickstart block verbatim", "result": "passed", "summary": "apple-asr 0.1.0 installed; 'session clock: 1.4'; exit 0"},
    {"command": "python -m apple_asr.build (fresh venv, fresh cache)", "result": "passed", "summary": "swiftc build into /tmp/ord2buildcache + valid hello first line"},
    {"command": "APPLE_ASR_CACHE=/tmp/empty-cache-ord2 apple-asr-shim --help", "result": "passed", "summary": "exit 0, help printed, cache dir never created (no build-on-demand)"},
    {"command": "apple-asr-replay tests/fixtures/audio/zh_long.wav --locale zh-TW --pace 0 --max-latency 0.3", "result": "passed", "summary": "11 pauses, 0 missed, max 0.229s, exit 0"},
    {"command": "/tmp/fsw/mutate.py (6 mutations, each reverted)", "result": "passed", "summary": "all 6 guard tests FAILED under their mutation; sources restored (grep MUTATION empty)"}
  ],
  "validationOutput": [
    "61 passed in 43.59s; 55 passed, 6 deselected in 11.68s; All checks passed!",
    "cadence: ours=spans=23 events=145 partials=132 finals=12 wall=30.9s audio=32.0s ended=closed pauses=11 missed=0 max_pause_latency=0.107s first_commit=3.40s mean_commit_gap=2.60s golden(finals=12, first=2.99s)",
    "mutation a: 'AssertionError: no Final landed during the pause'; b: 'AssertionError: final ranges overlap: 0.362 > 0.31200000000000006'; c: \"AssertionError: the newest events are kept (drop-oldest)\"; d: 'Failed: DID NOT RAISE ProtocolMismatch'; e: 'Failed: DID NOT RAISE BackendError'; f: 'AssertionError: guard took 30.11s'",
    "clamp decision: REMOVING the clamp makes test_final_ranges_never_overlap_in_normal_use fail (0.05s overlap) -> clamp KEPT, documented in Transport._make_final + README, regression tests in tests/test_clock_accounting.py",
    "bug fixed: transport discarded stdout lines read in the same pipe read as `hello` (order-1 latent); regression test test_lines_emitted_with_hello_are_not_lost",
    "full suite also run green on macOS 26 with the real shim for --file (2 finals / 129 4-element word runs / 0.44s) and the live replay path"
  ],
  "residualRisks": [
    "Integration tests require macOS 26 + a built shim and (in this sandbox) APPLE_ASR_CACHE, since ~/.cache is not writable; they fail rather than skip there by design.",
    "Pause-latency budget is pause_commit + 0.25s (measured ~0.07s) - slack for loaded CI runners.",
    "The silent-guard feed-rate rule (1.05x + 1.0s chunk grace) is a policy choice, tunable via silent_timeout.",
    "The bundled 992KB wav is committed; trimming it would break the golden comparison.",
    "mode's documented default is None (behaves as 'streaming') to keep Stream(preset='transcription') working; switching to the literal '= \"streaming\"' default would make that order-1 spelling raise.",
    "--mic remains untested (no mic TCC in the sandbox), unchanged from order 1."
  ],
  "noStagedFiles": true,
  "diffSummary": "Adds the order-2 test suite (scripted fake shim + 14 test modules, 61 tests, incl. 6 macOS-26 integration tests using the real shim and the bundled clip) and the replay console script; wires mode/reporting_option/silent_timeout into Stream, makes the transport's hello read lossless, special-cases `apple-asr-shim --help` to avoid build-on-demand, documents `--fast` as deprecated, and rewrites the README (install, both modes with measured CER, clock ownership, protocol incl. the 4-element runs extension, limitations, APPLE_ASR_CACHE, dev/test instructions).",
  "reviewFindings": [
    "no blockers",
    "note: interpretation call - mode defaults to None (== 'streaming') instead of the literal 'streaming' so the conflict check cannot break Stream(preset='transcription'); documented in the report §7.1 and README",
    "note: the clamp removal path of amendment 4 was tested and rejected on evidence (test fails without it); kept + documented + regression-tested",
    "note: `--fast` was documented as deprecated rather than removed (amendment 5 allows either)"
  ],
  "manualNotes": "Everything requested was executed on this machine: the macOS-26 integration tests really ran (no skip lines with -rs) and reproduce the measured cadence (12 finals vs golden 12, first commit 3.40s vs 2.99s). Two things a reviewer should consciously accept: (1) mode's default is None-as-streaming for order-1 compatibility, and (2) the Final.start clamp stays, because removing it produces a real overlap in the ordinary push/pause/pause_end cycle - that is the amendment-4 decision, taken from the experiment rather than from taste. One order-1 transport bug was found and fixed on the way (stdout lines sharing a pipe read with hello were dropped)."
}
```
