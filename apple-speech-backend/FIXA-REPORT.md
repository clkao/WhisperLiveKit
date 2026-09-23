# Pass A remediation report — apple-speech backend

Branch `apple-speech-backend`, worktree `/Users/clkao/git/asr/WhisperLiveKit/.worktrees/apple-speech-backend`.
Base `origin/main` @ `363e4f6`; branch tip before this pass `286a275`; after this pass `aa01520`.
Review artifact read: `GPT6-REVIEW.md` (findings 1, 10, 11 + claim audit).

Scope: FIX 1 (PyPI blocker), FIX 2 (CI test wiring), FIX 3 (PR-body claim corrections),
FIX 4 (positional dataclass regression). **PASS B (adapter lifecycle/error/partial/timestamp)
was NOT attempted** — no adapter code changed, no measured default changed.

## Commits (three coherent steps, so partial progress is durable)

```
aa01520 fix(config): append the apple-speech fields after the existing ones
c8800d3 test(asr): make the apple-speech adapter tests run in CI, on any host
d20663d fix(packaging): publish the apple-speech extra as a version specifier
286a275 chore(lock): regenerate uv.lock for the apple-speech extra   (pre-existing)
fc65d24 test(asr): cover the apple-speech adapter with a vendored fake shim (pre-existing)
0a5ee5e feat(asr): add the apple-speech backend via the apple-asr package (pre-existing)
```

Nothing staged (`git diff --cached --name-only` empty), working tree clean, no push/PR/tags.

## FIX 1 — packaging release blocker

`pyproject.toml`:

- `[project.optional-dependencies] apple-speech` now declares `'apple-asr>=0.1.2,<0.2'`
  (was `'apple-asr @ git+https://github.com/clkao/apple-asr@v0.1.2'`). Comment explains the
  direct-URL / Warehouse reason and that a source install resolves/compiles the shim at
  **first use**, not at install time.
- `[tool.uv.sources]` gained a development-only override:
  `apple-asr = { git = "https://github.com/clkao/apple-asr", tag = "v0.1.2" }`, with a comment
  stating it is NOT distribution metadata (`uv build --no-sources` skips it; pip/build never
  read `[tool.uv.sources]`).

### Evidence

`UV_NO_CONFIG=1 uv build --no-sources --wheel` → `whisperlivekit-0.2.26-py3-none-any.whl`,
METADATA:

```
82:Provides-Extra: apple-speech
83:Requires-Dist: apple-asr<0.2,>=0.1.2; extra == "apple-speech"
URLs in metadata (git+ / @ http): 0
```

Note on the acceptance string: the task asked to see
`Requires-Dist: apple-asr>=0.1.2,<0.2 ; extra == "apple-speech"`. setuptools normalizes the
specifier through `packaging.SpecifierSet`, which **sorts** it — the emitted form is
`apple-asr<0.2,>=0.1.2; extra == "apple-speech"`. Same constraint set, no URL, publishable.
The order cannot be forced via PEP 621.

`UV_NO_CONFIG=1 uv lock` → `Resolved 407 packages`; `UV_NO_CONFIG=1 uv lock --check` →
`Resolved 407 packages in 319ms` (pass). Lock diff is only `?rev=v0.1.2` → `?tag=v0.1.2`
(uv records the source kind); the pin is unchanged:

```
name = "apple-asr"
version = "0.1.2"
source = { git = "https://github.com/clkao/apple-asr?tag=v0.1.2#50290887ba269f347e5715eb4821fd114c25863e" }
```

So the resolved package is still the pinned v0.1.2 git commit `50290887…`.

## FIX 2 — the 9 adapter tests actually run in CI

### (a) host-independent, explicit dependency check — `tests/test_apple_speech_adapter.py`

- Removed `apple_asr = pytest.importorskip(...)` (blanket skip). Replaced with an explicit,
  actionable guard:

```python
_HAS_APPLE_ASR = importlib.util.find_spec("apple_asr") is not None

pytestmark = pytest.mark.skipif(
    not _HAS_APPLE_ASR,
    reason=("the apple-asr package is not installed; "
            "`pip install 'whisperlivekit[apple-speech]'` to run the adapter tests"),
)

if _HAS_APPLE_ASR:
    import apple_asr
    from apple_asr.protocol import SAMPLE_RATE, SHIM_VERSION
else:  # placeholders; never used because every test skips
    SAMPLE_RATE, SHIM_VERSION = 16_000, "0"
```

- Added a module-**autouse** fixture that neutralizes the macOS-26 gate for these tests only
  (test-side patch; `require_supported` itself untouched):

```python
@pytest.fixture(autouse=True)
def _supported_host(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr("apple_asr.platform.macos_major", lambda: 26)
```

- Removed the same two `monkeypatch.setattr` calls from the `fake_shim` fixture (they are now
  in the autouse fixture, so they cover every test, including the ones that don't request
  `fake_shim`). No product code touched.

### (b) CI wiring

Chosen: **job-scoped explicit git install**, not `-e ".[test,apple-speech]"`.

`.github/workflows/ci.yml`, `test` job:

```yaml
      - name: Install package with test deps
        # apple-asr is installed from the pinned git tag rather than through the
        # `apple-speech` extra: the extra carries a plain version specifier so the
        # published metadata stays publishable to PyPI, and apple-asr is not on
        # PyPI yet, so that specifier cannot resolve on this runner. The git URL
        # lives here (job-scoped), never in the distribution metadata.
        run: pip install -e ".[test]" qwen3-asr-causal "apple-asr @ git+https://github.com/clkao/apple-asr@v0.1.2"
```

and a guard step so a silent module skip fails the job:

```yaml
      - name: Verify the Apple Speech adapter tests run rather than skip
        run: |
          set -o pipefail
          pytest -q -rs tests/test_apple_speech_adapter.py | tee "${RUNNER_TEMP}/adapter-tests.txt"
          if grep -qE "[0-9]+ skipped" "${RUNNER_TEMP}/adapter-tests.txt"; then
            echo "::error::the apple-speech adapter tests skipped; apple_asr is not importable"
            exit 1
          fi
```

Why not the extra: `apple-asr` is **not on PyPI** (verified: `pypi.org/pypi/apple-asr/json`
→ HTTP 404). After FIX 1 the extra intentionally carries a plain version specifier, so
`pip install -e ".[test,apple-speech]"` on an Ubuntu runner would fail to resolve it. The
git install is job-scoped and never enters project metadata. `apple-asr` ships a
`py3-none-any` pure-Python wheel, so it installs and imports on Linux (its
`Operating System :: MacOS :: MacOS X` classifier is not an install restriction; the
macOS-26 gate is enforced at runtime, and the autouse fixture neutralizes it for the fake-shim
tests). The CI test job is the one that runs `tests/`, so the module now executes there.

### Evidence

```
### FIX2 installed run
.........                                                                [100%]
9 passed in 9.49s

### FIX2 simulated non-macOS host (sys.platform=linux)
.........                                                                [100%]
9 passed in 5.21s

### FIX2 genuinely-absent package
sssssssss                                                                [100%]
9 skipped in 1.35s

### gate really raises on non-macOS
apple_asr.errors.UnsupportedPlatform: apple-asr requires macOS 26+ (Apple SpeechAnalyzer); this platform is 'linux'. Nothing to install here.
```

Non-macOS simulation mechanics: a throwaway pytest plugin (`/tmp/simulate_linux.py`) flips
`sys.platform` to `"linux"` in `pytest_collection_finish` — after test-module imports (so
third-party libraries that branch on `sys.platform` at import, e.g. `soundfile`, are not
confused by the simulation) and before each test runs. That is exactly the state a Linux CI
runner would present to the test bodies. The gate-raising one-liner above proves the
neutralization is load-bearing rather than vacuous.

Genuinely-absent package → **9 skipped** (one skip reason per test, same message), which is
honest. It is not the CI path any more, because the CI test job now installs `apple_asr` and
the guard step fails the job on any skip.

## FIX 4 — positional dataclass regression

`whisperlivekit/config.py`: `apple_speech_locale` / `apple_speech_mode` moved from above the
"Keep new fields at the end…" comment to after `sortformer_max_speakers`.

### Evidence (AST field order, `origin/main` vs branch tip)

```
WhisperLiveKitConfig: base=118 head=120
  appended: ['apple_speech_locale', 'apple_speech_mode']
  pre-existing index changes: NONE
  head[:len(base)] == base -> True
  tail: ['pause_segmentation_seconds', 'sortformer_max_speakers', 'apple_speech_locale', 'apple_speech_mode']
```

Before this fix (branch @ `286a275`) the same script reported
`position 116: pause_segmentation_seconds -> apple_speech_locale` and
`position 117: sortformer_max_speakers -> apple_speech_mode`. After: no pre-existing field
changed index; the two new fields are the last two.

## FIX 3 — PR-body corrections (`.spacedock/.../PR-apple-speech.md`)

Not a repo file (outside the worktree; untracked by git), so it is not in any commit. Audit
claims corrected:

| Claim (was) | Now |
|---|---|
| "thin adapter … **no timing logic**" | "carries no protocol or recognizer logic of its own. It does have two timing policies … a bounded **300 ms** window in which `start_silence()` collects the pause's final … and a bounded 10 s drain in `finish()`." |
| "**purely additive** — 10 files, +1093 / −2 … nothing upstream is deleted or restructured" | "**mostly additive** — 11 files, +1159 / −3 … no pre-existing backend's behaviour changes: the two new config fields are **appended** after the existing fields so positional dataclass construction is preserved. A first cut inserted them above that append-only boundary (shifting `pause_segmentation_seconds` and `sortformer_max_speakers`); that is corrected before opening." Plus the FIX 1 metadata change (URL → version specifier) spelled out. |
| "installing from git or source **compiles the shim once**" | "A source install does **not** compile the shim at install time — plain hatchling, no build hook. The shim is resolved at **first use** … or via an explicit build (`python -m apple_asr.build`)." |
| "**the package ships the scoring harness** … so both are reproducible" (heading "Evidence for the numbers above") | Rewritten as "**Evidence and reproducibility**": the CER/WER + cadence measurements were run in the workspace; the scoring harness is **not shipped with this PR** and is **not part of the `apple-asr` package** (its README says the harness was not ported); raw per-sample results, sample identities, hypotheses and the baseline reproduction artifact are **not yet included**, so the accuracy/cadence figures are stated as motivating context, not verified evidence. |
| "other backends are unaffected" (requirements bullet) | "No pre-existing backend's behaviour changes. The two new config fields are appended after the existing fields, so positional dataclass construction is preserved." |
| "the **package … the adapter synthesizes it**" | "the **package** synthesizes it from those events" (the adapter only forwards `pause_start`/`pause_end`). |
| "They run in CI like any other test" | "The CI test job installs `apple-asr` and **fails if the module skips** … The module-level gate is neutralized test-side only … If the package is genuinely absent, the module skips with an actionable message — that is the honest fallback, not the CI path." Also qualified the mutation-check claim as a "local, unreproduced run". |
| Resource table "**no GPU memory**, no contention with the MT model" | "... (asserted by design; not measured here)". |

Also added: commit count `3` → `6`; per-file `Files` table updated to the real diffstat
(pyproject +25, config +31 unchanged, tests +290, ci.yml +20/−1, uv.lock +16/−1, 11 files);
and an explicit bullet: "**Not resolved in this PR (deliberately out of scope, tracked as
follow-up):** session teardown on disconnect, propagation of terminal backend failures,
partial/final buffer reconciliation, and pause-delivery/timestamp edge cases. Nothing below
should be read as claiming those are fixed." — this is the PASS B boundary and is stated as
unresolved, not resolved.

## Verification commands run

```
UV_NO_CONFIG=1 uv build --no-sources --wheel --out-dir /tmp/wlkdist2
UV_NO_CONFIG=1 uv lock ; UV_NO_CONFIG=1 uv lock --check
.venv/bin/python -m pytest -q -rs tests/test_apple_speech_adapter.py          # 9 passed
PYTHONPATH=/tmp .venv/bin/python -m pytest -q -p simulate_linux tests/test_apple_speech_adapter.py   # 9 passed
PYTHONPATH=/tmp .venv/bin/python -m pytest -q -p simulate_missing tests/test_apple_speech_adapter.py # 9 skipped
.venv/bin/ruff check .                                                        # All checks passed!
.venv/bin/python -m pytest -q tests/test_backends.py tests/test_silent_backend_guard.py tests/test_apple_speech_adapter.py
                                                                              # 53 passed, 3 warnings in 7.59s
python3 <AST field-order comparison script>                                    # no pre-existing index changes
```

`53 passed` = 44 (backends + silent guard) + 9 (adapter), i.e. the third file contributes
9 passed / 0 skipped.

## What could NOT be verified here

- **The real GitHub Ubuntu CI run.** No push was permitted, so the `.github/workflows/ci.yml`
  change is validated only by YAML parse + the local Linux-simulated run. The Linux simulation
  patches `sys.platform` rather than running on a Linux kernel; `soundfile` etc. are real
  macOS builds. The pure-Python status of `apple-asr` (`py3-none-any` wheel, no import-time
  darwin branch outside `apple_asr/platform.py`) is the reason the module should import on
  Linux, but that was not executed on Linux.
- `pip install "apple-asr @ git+https://github.com/clkao/apple-asr@v0.1.2"` was not run into a
  fresh Linux environment (the local venv already had it git-installed). The URL/tag is the
  same one `uv.lock` resolves.
- The maintainer's `uv lock --check` in CI runs without `--no-config`; this machine's
  `~/.config/uv/uv.toml` (rolling `exclude-newer`) is why all local lock commands use
  `UV_NO_CONFIG=1`. This is pre-existing and unrelated to the branch.

## Residual risks / open items

1. `Requires-Dist` specifier ordering is setuptools-normalized (`<0.2,>=0.1.2`), not the
   literal `>=0.1.2,<0.2` in the acceptance text. Functionally identical, URL-free.
2. After FIX 1, `pip install whisperlivekit[apple-speech]` from PyPI will not resolve until
   `apple-asr` is published to an index. That is inherent to removing the direct reference and
   is what the `[tool.uv.sources]` override + CI git install cover for dev/CI. Publishing
   `apple-asr` is a package-side/owner decision (out of scope; the separate order owns the
   package-side clock cap).
3. The CI guard greps pytest's summary for a skip count. If a future pytest changes the
   summary wording, the guard silently stops guarding (it would not fail the job). Low risk,
   but it is a textual guard, not a pytest API assertion.
4. `apple-asr` needs to remain installable as a pure-Python wheel from the `v0.1.2` tag on
   Linux; if the package later adds a build-time platform restriction, the CI install step
   breaks (correctly, loudly).
5. PR-body accuracy claims (CER/WER, golden cadence, pause-onset ~0.1 s) remain
   **unreproducible from the PR**; the body now says so explicitly rather than implying
   reproducibility.
6. `tests/test_apple_speech_adapter.py` carries an unnecessary `# noqa: SIM108` comment on the
   guarded import (ruff has no SIM rules enabled; it is harmless and was left rather than
   rewriting the already-committed history).
