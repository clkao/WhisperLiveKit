# CIFIX-REPORT — apple-asr red CI on ubuntu (fake-shim suite)

Repo: `https://github.com/clkao/apple-asr` (public). Base: `37bf498` on `main` (= pushed `v0.1.1`).
Result: two local commits on `main`, tree clean, no push, no tag.

| Commit | Subject |
|---|---|
| `6674da2` | tests: make the fake-shim suite OS-independent |
| `5029088` | release: 0.1.2 |

Diffstat `37bf498..HEAD`:

```
 pyproject.toml            |  2 +-
 src/apple_asr/__init__.py |  2 +-
 tests/conftest.py         | 80 +++++++++++++++++++++++++++++++++++++++++++++--
 tests/support.py          | 29 +++++++++++++++++
 tests/test_events.py      | 14 ++++++---
 tests/test_failures.py    | 25 +++++++++------
 tests/test_platform.py    |  6 +++-
 7 files changed, 139 insertions(+), 19 deletions(-)
```

Host: macOS 26.6.2 (25G83), venv Python 3.13.12, pytest 9.1.1, ruff 0.16.7.
No product file other than the version string was touched. `SHIM_VERSION` stays `0.1.0`; `PROTOCOL_VERSION` stays `1`.

---

## Root cause (read from the real log, confirmed by faithful repro)

CI's ubuntu log: `42 failed, 21 passed, 1 skipped, 6 deselected`, every failure
`apple_asr.errors.UnsupportedPlatform: apple-asr requires macOS 26+ (Apple SpeechAnalyzer); this platform is 'linux'.`
`Stream.__init__` calls `require_supported()` (src/apple_asr/stream.py:246) before any
transport work, so the OS-independent fake-shim suite never reached the client logic.

The two non-gate failures (`test_events.py::test_runs_are_optional_and_unknown_event_types_are_ignored`
and `test_failures.py::test_malformed_and_unknown_lines_warn_but_do_not_crash`, `Failed: DID NOT WARN.`)
are **the same root cause, not separate dedup bugs**: the `UnsupportedPlatform` raise happens *inside*
`pytest.warns(...)`, and pytest 9.1.1 reports that as `DID NOT WARN` rather than surfacing the raise:

```
tests/test_events.py:142: in test_runs_are_optional_and_unknown_event_types_are_ignored
    with pytest.warns(RuntimeWarning, match="unknown event type"):
src/apple_asr/stream.py:246: in __init__
    require_supported()
src/apple_asr/platform.py:34: in require_supported
    raise UnsupportedPlatform(...)
During handling of the above exception, another exception occurred:
E   Failed: DID NOT WARN. No warnings of type (<class 'RuntimeWarning'>,) were emitted.
```

The dedup hardening was applied anyway (per the task), for robustness.

---

## (a) Pre-fix simulated-Linux reproduction — faithful

Two ways, both give the CI's exact count.

**A1. Before any change, forcing `sys.platform` before pytest starts:**

```
$ APPLE_ASR_CACHE=$PWD/.cache ./.venv/bin/python -c "
import sys; sys.platform='linux'
import pytest; raise SystemExit(pytest.main(['-q','-m','not integration','--tb=line','-rf']))"
FAILED tests/test_backpressure.py::test_burst_beyond_queue_size_drops_oldest_with_one_warning
FAILED tests/test_backpressure.py::test_no_drop_when_the_caller_keeps_up - ap...
... (42 lines) ...
FAILED tests/test_replay.py::test_replay_result_summary_reports_the_measurements
42 failed, 21 passed, 1 skipped, 6 deselected in 0.75s
```

**A2. After the knob landed, with the new neutralization explicitly disabled** (the task's
"with the neutralization disabled" path):

```
$ APPLE_ASR_TEST_PLATFORM=linux APPLE_ASR_TEST_NEUTRALIZE_GATE=0 APPLE_ASR_CACHE=$PWD/.cache \
    ./.venv/bin/python -m pytest -q -m "not integration" --tb=line -rf
FAILED tests/test_replay.py::test_replay_drives_the_pause_pattern_and_measures_latency
FAILED tests/test_replay.py::test_replay_result_summary_reports_the_measurements
42 failed, 21 passed, 1 skipped, 6 deselected in 0.84s
```

Identical `42 failed, 21 passed, 1 skipped, 6 deselected` to the real ubuntu job.
Rerun after the whole fix (same command): still `42 failed, 21 passed, 1 skipped, 6 deselected`,
i.e. the knobs themselves did not change the unfixed-gate repro.

---

## Changes

### `tests/conftest.py`
New autouse fixture `neutralized_platform_gate(request, monkeypatch)`: for every test except the
`real_platform_gate`-marked ones it stubs `require_supported` **where it is bound** —
`apple_asr.platform.require_supported`, `apple_asr.stream.require_supported`,
`apple_asr.shim.require_supported` (`stream`/`shim` do `from .platform import require_supported`,
so patching only the defining module would miss them). It returns early (no-op) when
`APPLE_ASR_TEST_NEUTRALIZE_GATE=0`, so the real gate can be put back in force for the repro.

New `pytest_configure`/`pytest_unconfigure` + `_force_simulated_platform(config)`: when
`APPLE_ASR_TEST_PLATFORM` is set, it patches `sys.platform` and `apple_asr.platform.macos_major`
for the session — at configure time, *before collection*, so the integration-skip decision and the
gate agree — and restores them in `pytest_unconfigure`. An unknown value raises `pytest.UsageError`
with the allowed set.

New marker `real_platform_gate` registered.

### `tests/support.py`
`SIMULATED_PLATFORMS = {"linux": ("linux", 0), "macos25": ("darwin", 25), "macos26": ("darwin", 26)}`,
`TEST_PLATFORM_ENV = "APPLE_ASR_TEST_PLATFORM"`, and `forced_platform()` (returns the forced pair or
`None`; raises `ValueError` on a bad value). `macos26_available()` now consults it first, so
`macos25` correctly skips the integration tests instead of letting them run.

### `tests/test_platform.py`
`pytestmark = pytest.mark.real_platform_gate` — this module keeps exercising the **real** gate and
still asserts the raise. No test body changed.

### `tests/test_events.py`, `tests/test_failures.py`
Each warning assertion is now wrapped in `warnings.catch_warnings()` + `warnings.simplefilter("always")`,
so it cannot depend on Python's per-location `"default"` dedup.

### `pyproject.toml`, `src/apple_asr/__init__.py`
`0.1.1` → `0.1.2`. `SHIM_VERSION` untouched at `0.1.0`.

---

## (b) Post-fix green runs

**Simulated Linux (neutralization on) — fully green:**

```
$ APPLE_ASR_TEST_PLATFORM=linux APPLE_ASR_CACHE=$PWD/.cache ./.venv/bin/python -m pytest -q -m "not integration" -rs
....................................................s...........         [100%]
SKIPPED [1] tests/test_platform.py:56: this machine is not macOS
63 passed, 1 skipped, 6 deselected in 17.24s
```

63 passed = all 64 non-integration tests minus the one legitimately platform-conditional
skip (`test_supported_platform_is_a_noop` self-skips off macOS), which is the same `1 skipped`
the real ubuntu run reports. Zero failures. Compare pre-fix: 21 passed / 42 failed.

**Real macOS 26 full suite (integration running, no skips):**

```
$ APPLE_ASR_CACHE=$PWD/.cache ./.venv/bin/python -m pytest -q --tb=line -rf
......................................................................   [100%]
70 passed in 49.06s
```

70 passed, 0 skipped, 0 failed (64 non-integration + 6 integration; baseline before the change was
also 70 passed — no test count change, only the two warning tests' contexts and the gate wiring).

**Knob coverage:**

```
$ for p in linux macos25 macos26; do APPLE_ASR_TEST_PLATFORM=$p pytest -q tests/test_platform.py -rs; done
linux   -> 3 passed, 1 skipped   (SKIPPED: this machine is not macOS)
macos25 -> 3 passed, 1 skipped   (SKIPPED: this machine reports macOS 25)
macos26 -> 4 passed

$ APPLE_ASR_TEST_PLATFORM=bogus pytest -q tests/test_platform.py
ERROR: APPLE_ASR_TEST_PLATFORM must be one of ['linux', 'macos25', 'macos26']; got 'bogus'
```

---

## (c) Falsifiability — gate mutation

Applied `return  # MUTATION: gate disabled` as the first statement of
`src/apple_asr/platform.py::require_supported`, ran under simulated Linux:

```
$ APPLE_ASR_TEST_PLATFORM=linux pytest -q tests/test_platform.py --tb=line -rf
E   Failed: DID NOT RAISE UnsupportedPlatform
.../tests/test_platform.py:31: Failed: DID NOT RAISE UnsupportedPlatform
E   Failed: DID NOT RAISE UnsupportedPlatform
.../tests/test_platform.py:40: Failed: DID NOT RAISE UnsupportedPlatform
E   Failed: DID NOT RAISE UnsupportedPlatform
.../tests/test_platform.py:47: Failed: DID NOT RAISE UnsupportedPlatform
FAILED tests/test_platform.py::test_non_darwin_raises_unsupported_platform
FAILED tests/test_platform.py::test_macos_25_raises_unsupported_platform
FAILED tests/test_platform.py::test_gate_applies_to_the_module_helpers
3 failed, 1 skipped in 0.48s
```

Mutation reverted from the saved copy; `git diff -- src/apple_asr/platform.py` is empty and
`tests/test_platform.py` is back to `3 passed, 1 skipped` under simulated Linux.

## No product behaviour change

`APPLE_ASR_TEST_PLATFORM` / `APPLE_ASR_TEST_NEUTRALIZE_GATE` appear nowhere under `src/`
(`grep -rn` → no hits). The real gate, run with no test scaffolding:

```
$ ./.venv/bin/python -c "import sys; sys.platform='linux'; from apple_asr.platform import require_supported; require_supported()"
RAISED: apple-asr requires macOS 26+ (Apple SpeechAnalyzer); this platform is 'linux'. Nothing to install here.

$ ./.venv/bin/python -c "import apple_asr.platform as p; p.macos_major=lambda: 25; p.require_supported()"
RAISED: apple-asr requires macOS 26+ (Apple SpeechAnalyzer); this system reports macOS 26.6.2.
```

## (d) Lint

```
$ ./.venv/bin/ruff check .
All checks passed!
```

(`ruff format` is not a CI gate and the repo has pre-existing deviations in untouched files; the
files I edited are format-clean under `ruff format --check`.)

## (e) What remains unverifiable here

Docker is unavailable on this machine, so **I cannot run the actual ubuntu runner**. The evidence
produced here is the local simulated-Linux run (a) A2 / (b), which reproduces the CI's failure
count byte-for-byte pre-fix and is fully green post-fix. The real Ubuntu confirmation is the `ci`
workflow's `fake-shim` job after the parent pushes. No other item is unverified.

## Residual risks / notes

- `README.md:31` still names the `apple_asr-0.1.1-...whl` artifact. Left untouched deliberately
  (the task scoped the bump to `pyproject.toml` + `__init__.py`, and v0.1.2 has no wheel yet).
  The README reference stays correct for the currently published release.
- `tests/test_locales.py` keeps its local `ungate` fixture (`apple_asr.shim.require_supported`
  stubbed to `None`); it is now redundant with the autouse fixture but harmless and left alone to
  keep the diff narrow. Both stub the same symbol.
- The autouse neutralization also covers the 6 integration tests. On real macOS 26 the gate is
  already a no-op, so this changes nothing there; those tests self-skip off macOS 26. The gate's
  real behaviour is owned by `tests/test_platform.py` (un-neutralized) plus the process-level
  checks above.
- Not pushed, no tags created, no staged files; working tree clean at `5029088`.
