# FIXCI — stop testing the macOS-only apple-speech backend on generic CI

Branch `apple-speech-backend`, worktree `/Users/clkao/git/asr/WhisperLiveKit/.worktrees/apple-speech-backend`,
base `origin/main` @ `363e4f6`. Starting tip `21c957c`; ending tip `94ace5e` (17 commits). Tree clean, nothing
staged, no push / PR / tags. Mac host: macOS 26.6.2 (build 25G83), arm64; project venv CPython 3.13.12.

## 1. `.github/workflows/ci.yml` — full revert to upstream

The Pass A additions (commit `c8800d3`, tag bumped in `1b21c85`/`21c957c`) were reverted with
`git checkout origin/main -- .github/workflows/ci.yml` and committed in `5dc32cb`.

Reverted diff (what the branch *had* added, now gone):

```diff
@@ -125,13 +125,31 @@ jobs:
       - name: Install package with test deps
-        run: pip install -e ".[test]" qwen3-asr-causal
+        # apple-asr is installed from the pinned git tag rather than through the
+        # `apple-speech` extra: ... (4 comment lines)
+        run: pip install -e ".[test]" qwen3-asr-causal "apple-asr @ git+https://github.com/clkao/apple-asr@v0.1.4"
@@
+      # The regression suite below would stay green even if the adapter module
+      # skipped entirely ...
+      - name: Verify the Apple Speech adapter tests run rather than skip
+        run: |
+          set -o pipefail
+          pytest -q -rs tests/test_apple_speech_adapter.py | tee "${RUNNER_TEMP}/adapter-tests.txt"
+          if grep -qE "[0-9]+ skipped" "${RUNNER_TEMP}/adapter-tests.txt"; then
+            echo "::error::the apple-speech adapter tests skipped; apple_asr is not importable"
+            exit 1
+          fi
```

Post-revert state (evidence):

```
$ git diff origin/main..HEAD -- .github/workflows/ci.yml     # empty output
$ git diff --quiet origin/main..HEAD -- .github/workflows/ci.yml && echo identical
identical
$ grep -n "apple" .github/workflows/ci.yml
(no output; exit 1)
$ grep -n "pip install -e" .github/workflows/ci.yml
75:        run: pip install -e .
128:        run: pip install -e ".[test]" qwen3-asr-causal
```

Nothing else in the file changed: the `lint`, `package`, `import-check`, `diart-import`, `test` and
post-`test` steps (FFmpeg, regression suite, real-audio coalescing) are byte-identical to `origin/main`.
No macOS runner job was added.

## 2. `tests/test_apple_speech_adapter.py` — honest skip, no faked platform

The autouse `_supported_host` fixture that patched `sys.platform = "darwin"` and
`apple_asr.platform.macos_major -> 26` is **deleted**. The module now declares two explicit, distinct
skip reasons, and never neutralizes the adapter's real gate:

```python
import platform                      # newly imported (stdlib, isort order)

_HAS_APPLE_ASR = importlib.util.find_spec("apple_asr") is not None


def _host_is_macos_26() -> bool:
    """True when this host satisfies apple-asr's own platform gate."""
    if sys.platform != "darwin":
        return False
    try:
        return int(platform.mac_ver()[0].split(".")[0]) >= 26
    except (IndexError, ValueError):
        return False


# Two distinct, honest reasons: the dependency is missing, or the host is not
# one where the backend can run at all. Neither is a pass.
pytestmark = [
    pytest.mark.skipif(
        not _HAS_APPLE_ASR,
        reason=("the apple-asr package is not installed; "
                "`pip install 'whisperlivekit[apple-speech]'` to run the adapter tests"),
    ),
    pytest.mark.skipif(
        _HAS_APPLE_ASR and not _host_is_macos_26(),
        reason=("apple-asr runs only on macOS 26+ on Apple Silicon; this host reports "
                f"{sys.platform} {platform.mac_ver()[0] or 'unknown'}, so the adapter "
                "tests are skipped, not passed"),
    ),
]
```

Supporting prose corrected in the same commit: the module docstring (it no longer claims "needs no
macOS 26"; it now states the macOS-26-host + extra requirement and the CI skip), the header comment
above the skip marks, and the stale comment inside the `fake_shim` fixture ("the host gate is
neutralized by the autouse fixture" -> "the adapter's own macOS-26 gate is deliberately left intact;
the module-level skip above guarantees this host satisfies it"). The 24 test functions are otherwise
untouched — no assertion, fixture body, or fake-shim wiring changed. The adapter module, the package
pin (`v0.1.4`), the measured defaults and the tuned hold (`_PAUSE_COLLECT_S = 0.12`) are untouched.

## 3. Other apple-asr / CI references in the repo

`grep -rniE "apple" --include="*.yml" --include="*.md" --include="*.toml" --include="*.py"` over the
tracked tree (excluding `.venv/`, `build/`, `__pycache__/`) found:

| Location | Verdict |
|---|---|
| `.github/workflows/ci.yml` | Pass A only — reverted (above). |
| `tests/test_apple_speech_adapter.py` | Pass A prose only — corrected (above). |
| `pyproject.toml` `[tool.uv.sources]` comment | Said "uv (local runs, `uv lock`, CI) resolves it from the pinned git tag" — true but ambiguous (reads as "CI installs it"). **Corrected** in `94ace5e` to name the actual CI touch-point: "uv (local runs, `uv lock`, and CI's `uv lock --check`) resolves it from the pinned git tag. No CI test job installs it: the backend is macOS-26-only, so the adapter tests are skipped, not run, on the generic runner." Comment-only; lockfile unaffected. |
| `pyproject.toml` `[apple-speech]` extra comment | Describes the PyPI-publishability rationale only; makes no CI claim. Unchanged. |
| `pyproject.toml` `apple-asr = { git = ..., tag = "v0.1.4" }` | Development-only source override, not CI. Unchanged (pin stays `v0.1.4`). |
| `docs/backends.md` §Apple SpeechAnalyzer | User install instructions (release wheel / git tag / extra). Contains no statement that CI installs or runs anything. Unchanged. |
| `JARVISLAB_AGENTS.md:83` | Pre-existing upstream line about a macOS tar `com.apple.provenance` xattr warning. Unrelated. Unchanged. |

**Residual, accepted coupling (not a claim of coverage):** the `lint` job's `uv lock --check` validates
the committed `uv.lock`, which records the pinned git source
(`apple-asr 0.1.4` -> `github.com/clkao/apple-asr?tag=v0.1.4#73f0d31…`). That is a lockfile-resolution
touch-point, not an install and not a test run; if the lock and the pin ever disagree, the lint job
fails (locally too). Stated in the PR body so it is not mistaken for coverage.

## 4. PR body — `.spacedock/dev/.spacedock-state/apple-speech-backend/PR-apple-speech.md`

Testing section diff (old -> new):

```diff
-- `tests/test_apple_speech_adapter.py` — **24 tests, 0 skips** with `apple-asr` installed,
-  driving the adapter through a vendored protocol-v1 double
-  (`tests/fixtures/apple_speech_fake_shim.py`, 490 lines), so they need no macOS 26, no Speech
-  and no toolchain. The CI test job installs `apple-asr` and **fails if the module skips**, so
-  they run on the Ubuntu runner rather than silently passing. The module-level gate is
-  neutralized test-side only (an autouse fixture); the gate itself is untouched and still
-  asserted by the unsupported-host test. If the package is genuinely absent, the module skips
-  with an actionable message — the honest fallback, not the CI path.
+- `tests/test_apple_speech_adapter.py` — **24 tests, 0 skips** on macOS 26 with the
+  `apple-speech` extra installed, driving the adapter through a vendored protocol-v1 double
+  (`tests/fixtures/apple_speech_fake_shim.py`, 490 lines), so they need no Speech framework, no
+  Swift toolchain, no real audio and no writable `~/.cache`. Run them with:
+  `uv run --extra apple-speech pytest -q tests/test_apple_speech_adapter.py`.
+- **CI does not run these tests — an accepted, documented limitation.** The backend is
+  macOS-26-only and the project's CI is generic (`ubuntu-latest`): the dependency is deliberately
+  **not** installed there, no macOS runner job is added, and nothing in CI installs `apple-asr`
+  (`.github/workflows/ci.yml` is untouched by this PR). On that runner the module reports
+  itself as **skipped with an explicit reason** — "the apple-asr package is not installed; …" —
+  and on a macOS host older than 26, or any non-darwin host, it skips with the platform reason
+  instead. Neither is a pass and neither is a failure. **Consequence, stated plainly: CI does
+  not catch adapter regressions; only a local/`macOS-26` run does.** The adapter's platform gate
+  (`backend_support.require_apple_speech_backend()`) is never neutralized or faked by the tests;
+  it is asserted directly by the unsupported-host test.
```

Other PR-body corrections in the same file:

- Header "**15 commits**" -> "**17 commits**" (two fix commits this pass, one earlier).
- Files header "15 files, +1888 / −9" -> "14 files, +1886 / −8"; the `.github/workflows/ci.yml +19/-1`
  line is deleted from the per-file block; `pyproject.toml +25` -> `+27` (comment);
  `tests/test_apple_speech_adapter.py +711` -> `+726`, and its note now reads
  "24 tests, 0 skips on macOS 26 (dependency installed)".
- Dependency caveat: "uv users (and CI) resolve the `v0.1.4` git tag instead; CI installs it
  job-scoped from the git URL …" -> "uv users resolve the `v0.1.4` git tag instead … No CI job
  installs `apple-asr` … the only CI touch-point is the `lint` job's `uv lock --check` …".
- Evidence section: the re-run sentence now records both figures — "24 passed / 0 skipped on
  macOS 26 with the extra, and 24 skipped with the explicit reason in a `.[test]`-only environment
  that has no `apple-asr`."

## 5. Verification (run at final tip `94ace5e`)

### macOS 26, extra installed

```
$ UV_NO_CONFIG=1 uv run --extra apple-speech pytest -q -rs tests/test_apple_speech_adapter.py
........................                                                 [100%]
24 passed in 14.28s
```

Full count passing, **0 skips**, no skip reasons printed by `-rs`.

### Package absent (honest CI behaviour) — temp venv with `.[test]` only

```
$ rm -rf /tmp/wlk-noapple && UV_NO_CONFIG=1 uv venv /tmp/wlk-noapple --python 3.13
$ UV_NO_CONFIG=1 uv pip install --python /tmp/wlk-noapple/bin/python -e ".[test]" -q
$ /tmp/wlk-noapple/bin/python -c "import importlib.util;print('apple_asr spec:', importlib.util.find_spec('apple_asr'))"
apple_asr spec: None
$ UV_NO_CONFIG=1 /tmp/wlk-noapple/bin/python -m pytest -q -rs tests/test_apple_speech_adapter.py | tail -2
SKIPPED [1] tests/test_apple_speech_adapter.py:712: the apple-asr package is not installed; `pip install 'whisperlivekit[apple-speech]'` to run the adapter tests
24 skipped in 2.59s
```

All 24 reported **SKIPPED** with the dependency reason (one `SKIPPED [1]` line per test; 24 total).
This is what the ubuntu `test` job now reports — a visible skip, not a pass, not a failure.
(The venv was removed after the run; 1.2 GB.)

### Host-gate skip path (not macOS 26)

Exercised by stubbing the version the helper reads, via a throwaway pytest plugin
(`PYTHONPATH=/tmp/hostskip`, `-p macver25`, removed afterwards):

```
$ UV_NO_CONFIG=1 PYTHONPATH=/tmp/hostskip uv run --extra apple-speech pytest -q -rs -p macver25 tests/test_apple_speech_adapter.py | tail -1
24 skipped in 2.34s
# reason (per test): "apple-asr runs only on macOS 26+ on Apple Silicon; this host reports
#  darwin 25.1.0, so the adapter tests are skipped, not passed"
```

The `sys.platform != "darwin"` branch was **not** executed in-place: faking the whole platform on
this macOS host breaks unrelated collection (`OSError: cannot load library 'libsndfile.so'` from
`soundfile`, which is exactly the class of breakage platform-faking caused). On a real Linux host
`soundfile` installs its `.so` and the branch returns `False` from its first line; the branch that
CI actually hits is the package-absent one, verified above.

### Rest of the required checks

```
$ UV_NO_CONFIG=1 uv run --extra apple-speech pytest -q tests/test_backends.py tests/test_silent_backend_guard.py
44 passed, 3 warnings in 3.81s

$ UV_NO_CONFIG=1 uv run --extra apple-speech ruff check .
All checks passed!

$ UV_NO_CONFIG=1 uv lock --check
Resolved 407 packages in 138ms      # exit 0

$ git diff --quiet origin/main..HEAD -- .github/workflows/ci.yml && echo identical
identical
$ grep -n "apple" .github/workflows/ci.yml          # no output, exit 1
```

### File set and diffstat (must stay apple-speech-only; ci.yml gone)

```
$ git diff --name-only origin/main..HEAD
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

$ git diff --shortstat origin/main..HEAD
 14 files changed, 1886 insertions(+), 8 deletions(-)

$ git diff --numstat origin/main..HEAD
43      0       docs/backends.md
27      0       pyproject.toml
490     0       tests/fixtures/apple_speech_fake_shim.py
726     0       tests/test_apple_speech_adapter.py
15      1       uv.lock
329     0       whisperlivekit/asr_apple_speech.py
66      6       whisperlivekit/audio_processor.py
45      0       whisperlivekit/backend_support.py
10      0       whisperlivekit/benchmark/compat.py
22      0       whisperlivekit/benchmark/runner.py
69      0       whisperlivekit/config.py
26      0       whisperlivekit/core.py
14      1       whisperlivekit/parse_args.py
4       0       whisperlivekit/session_asr_proxy.py
```

`git status --porcelain` and `git diff --cached --name-only` are both empty at the end (clean tree,
nothing staged). The branch is **17 commits**, tip `94ace5e`, unpushed.

## Commits this pass

```
94ace5e docs(packaging): scope the apple-asr uv source note to what CI actually does
5dc32cb revert(ci): stop running the macOS-only apple-speech tests on Ubuntu CI
```

## Constraints honoured

- Adapter behaviour, package pin (`v0.1.4`), measured defaults (`pause_commit=0.08`,
  `commit_interval=0.0`, `mode=streaming`), and the tuned hold (`_PAUSE_COLLECT_S=0.12`) untouched —
  no file under `whisperlivekit/` was modified this pass.
- `apple-asr` repo not touched. No push, no PR, no tags.
- No macOS CI runner job added, as decided.

## Unresolved / notes for the reviewer

1. **`uv lock --check` still consults the pinned git source** (lockfile resolution, not an install).
   Accepted and documented in both `pyproject.toml` and the PR body. If the maintainers would rather
   the generic `lint` job not depend on a personal git tag at all, that is a separate decision
   (e.g. drop `[tool.uv.sources]` and let the extra be unresolvable locally too) — not taken here.
2. **The `sys.platform != "darwin"` skip branch is verified by inspection, not execution**, for the
   reason above (faking the platform on macOS breaks `soundfile`). The CI-relevant branch
   (package absent) and the version branch (`darwin 25.1.0`) were both executed.
3. **`docs/backends.md` was left unchanged**: it documents user install paths and makes no CI claim,
   so there was nothing to correct. Flagging it because it was in the grep set.
