# apple-asr — install without a Swift toolchain (platform wheel)

Order: make `apple-asr` installable WITHOUT a Swift toolchain, via a
platform-tagged wheel with the shim prebuilt, built by a GitHub Actions job.

Repo: `/Users/clkao/git/asr/apple-asr` (was at HEAD `8ab4ff7`, version 0.1.1).
Committed on `main` as two commits (no push, no repo created, no credentials):

| commit | contents |
|---|---|
| `ca36e51` | `wheel: prebuilt shim in a platform-tagged wheel (no Swift toolchain to install)` |
| `37bf498` | `docs: installing from the platform wheel vs from source` |

`git status` after the work: **clean** (the built wheel lives in `dist/`, which is
git-ignored; the staged shim binary under `src/apple_asr/shim/` was removed after
the last build, `scripts/build_wheel.sh` recreates it).

## 1. What changed

* `src/apple_asr/shim.py` — new resolution step 5 (the wheel's bundled shim,
  between `PATH` and build-on-demand), new `bundled_path()` and
  `ensure_executable()`; the cache and bundle paths are chmod +x-ed on first use.
* `pyproject.toml` — `[tool.hatch.build.targets.wheel] artifacts =
  ["src/apple_asr/shim/apple-asr-shim"]`, so the git-ignored build product is
  still package data (and still absent from the sdist).
* `.gitignore` — the staged binary.
* `scripts/build_wheel.sh` (new, 111 lines) — the whole build, runnable locally
  and by CI: swiftc → `uv build --wheel` → retag → assertions.
* `.github/workflows/wheel.yml` (new) — the CI job (below).
* `tests/test_shim_resolution.py` (new, 6 tests).
* `README.md` — Install split into wheel vs source, resolution order, exec-bit
  note, "Building a platform wheel yourself".
* `.github/workflows/ci.yml` — its stale "no public macOS 26 runner exists yet"
  comment updated (comment only).

Nothing else: the shim's behaviour, the public API, the defaults
(`pause_commit 0.08`, `commit_interval 0.0`, `mode="streaming"`) and the version
(`0.1.1`, shim `0.1.0`/protocol 1) are untouched.

### The workflow

`.github/workflows/wheel.yml`:

```yaml
name: wheel

# Builds the platform wheel with the Swift shim *prebuilt*, so that
# `pip install apple_asr-<version>-py3-none-macosx_26_0_arm64.whl` needs no
# Xcode/CLT, no swiftc, and no build step.
#
# Runs on `macos-26` (GitHub's native arm64 macOS 26 image), which is the only
# place the combination "macOS 26 SDK + Speech framework headers + swiftc" and
# the target platform coincide. Publishes nothing to PyPI and needs no stored
# credential: a workflow artifact plus, for a tag, an asset on that tag's GitHub
# release (the actions-provided GITHUB_TOKEN, which is not a secret to manage).

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

permissions:
  contents: write # attach the wheel to the release for the tag

jobs:
  wheel:
    name: platform wheel (macos-26, arm64)
    runs-on: macos-26
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - uses: astral-sh/setup-uv@v5

      # swiftc -O -parse-as-library -> package data -> uv build --wheel ->
      # wheel tags --platform-tag macosx_26_0_arm64 -> assertions. The same
      # script a developer runs locally; see scripts/build_wheel.sh.
      - name: Build the platform wheel (shim prebuilt)
        run: bash scripts/build_wheel.sh

      - name: Show the artifact
        run: ls -l dist

      - uses: actions/upload-artifact@v4
        with:
          name: apple-asr-wheel-macosx_26_0_arm64
          path: dist/*.whl
          if-no-files-found: error

      - name: Attach the wheel to the release for the tag
        if: startsWith(github.ref, 'refs/tags/')
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # --verify-tag: never create a release for a tag that does not exist
          # (workflow_dispatch runs are excluded by the `if:` above anyway).
          gh release view "$GITHUB_REF_NAME" >/dev/null 2>&1 ||
            gh release create "$GITHUB_REF_NAME" --verify-tag --generate-notes
          gh release upload "$GITHUB_REF_NAME" dist/*.whl --clobber
```

`scripts/build_wheel.sh` (the step that actually builds, shared by CI and by
hand) does, in order:

1. `swiftc -O -parse-as-library src/apple_asr/shim/speechanalyzer.swift -o src/apple_asr/shim/apple-asr-shim` + `chmod +x`
2. assert `file` says arm64 (an Intel runner must never get the arm64 tag)
3. `rm -rf dist && uv build --wheel`
4. `uvx --quiet --from wheel python -m wheel tags --remove --platform-tag macosx_26_0_arm64 <wheel>`
   (`--remove` deletes the `py3-none-any` original — it must never be shipped)
5. assert: the tag is platform-specific, `apple_asr/shim/apple-asr-shim` is in
   the zip, and `dist/` holds exactly one wheel

### Packaging decision: retag, not `has_ext_modules()`

`wheel tags --platform-tag macosx_26_0_arm64 --remove` (task's option 2). The
package is pure Python with one bundled binary, so one wheel should serve CPython
3.10–3.13 on macOS 26 arm64 — `py3-none-macosx_26_0_arm64`. A setuptools
`BinaryDistribution.has_ext_modules()` override would emit an interpreter-specific
`cp313-cp313-macosx_...` wheel (one per Python version) and mean changing the
build backend off hatchling. Rationale is in the script header and README.

Hatchling has no tag hook, so `artifacts` is what puts the binary in the zip: it
re-includes files that `.gitignore` excludes, and a tree *without* the binary
still builds a plain `py3-none-any` wheel (verified). The sdist never carries it.

## 2. Verification (run here, on this Mac, macOS 26.6.2 arm64)

### Wheel filename + tag

```
$ bash scripts/build_wheel.sh
wheel: /Users/clkao/git/asr/apple-asr/dist/apple_asr-0.1.1-py3-none-macosx_26_0_arm64.whl
exit 0            # three consecutive runs, identical result
```

Wheel filename: **`apple_asr-0.1.1-py3-none-macosx_26_0_arm64.whl`**
(131,351 bytes). Only the retagged wheel is left in `dist/` — the
`py3-none-any` original is deleted by `--remove` and the script fails if any
other wheel is present.

```
$ unzip -l dist/apple_asr-0.1.1-py3-none-macosx_26_0_arm64.whl
  Length      Date    Time    Name
---------  ---------- -----   ----
     1735  02-02-2020 00:00   apple_asr/__init__.py
     1247  02-02-2020 00:00   apple_asr/build.py
     3109  02-02-2020 00:00   apple_asr/cli.py
     1145  02-02-2020 00:00   apple_asr/errors.py
     2146  02-02-2020 00:00   apple_asr/events.py
     1273  02-02-2020 00:00   apple_asr/platform.py
      953  02-02-2020 00:00   apple_asr/protocol.py
    14867  02-02-2020 00:00   apple_asr/replay.py
    10299  02-02-2020 00:00   apple_asr/shim.py
    25233  02-02-2020 00:00   apple_asr/stream.py
    27797  02-02-2020 00:00   apple_asr/transport.py
   255968  02-02-2020 00:00   apple_asr/shim/apple-asr-shim        <-- the shim
    32187  02-02-2020 00:00   apple_asr/shim/speechanalyzer.swift
    17591  02-02-2020 00:00   apple_asr-0.1.1.dist-info/METADATA
      102  02-02-2020 00:00   apple_asr-0.1.1.dist-info/WHEEL
       95  02-02-2020 00:00   apple_asr-0.1.1.dist-info/entry_points.txt
     1079  02-02-2020 00:00   apple_asr-0.1.1.dist-info/licenses/LICENSE
     1433  09-23-2026 04:39   apple_asr-0.1.1.dist-info/RECORD

$ unzip -p dist/*.whl apple_asr-0.1.1.dist-info/WHEEL
Wheel-Version: 1.0
Generator: hatchling 1.32.0
Root-Is-Purelib: true
Tag: py3-none-macosx_26_0_arm64
```

The tag is enforced (this is the point of it — the wheel must not install where
the binary cannot run):

```
$ pip install --dry-run --no-deps --only-binary=:all: --platform macosx_15_0_arm64 \
    --target /tmp/nope dist/apple_asr-0.1.1-py3-none-macosx_26_0_arm64.whl
ERROR: apple_asr-0.1.1-py3-none-macosx_26_0_arm64.whl is not a supported wheel on this platform.
```

The artifact in `dist/` is the artifact verified below (`apple_asr/shim.py` sha256
`7c598b2c…` = the committed file; the bundled binary sha256 `aaa6b809…` = the
binary in the verified fresh install).

### Fresh venv, NO toolchain — real transcription

```
$ uv venv --python 3.13 --seed /tmp/asr-fresh2
$ /tmp/asr-fresh2/bin/python -m pip install -q \
    /Users/clkao/git/asr/apple-asr/dist/apple_asr-0.1.1-py3-none-macosx_26_0_arm64.whl
INSTALL OK                                   # pip 26.2.1, CPython 3.13.12

$ ls -l /tmp/clean-bin                       # the whole sanitized PATH
lrwxr-xr-x  true -> /usr/bin/true

$ env -i PATH=/tmp/clean-bin /bin/sh -c 'command -v swiftc || echo "swiftc: NOT FOUND"'
swiftc: NOT FOUND
$ ... 'command -v apple-asr-shim || echo "apple-asr-shim: NOT FOUND"'
apple-asr-shim: NOT FOUND

$ env -i HOME="$HOME" PATH=/tmp/clean-bin APPLE_ASR_CACHE=/tmp/fresh-cache2 \
    /tmp/asr-fresh2/bin/python /tmp/verify_no_toolchain.py
package : /tmp/asr-fresh2/lib/python3.13/site-packages/apple_asr/__init__.py
version : 0.1.1
shim    : /private/tmp/asr-fresh2/lib/python3.13/site-packages/apple_asr/shim/apple-asr-shim
shim ver: 0.1.0 protocol 1
audio   : 31.55 s
resolved: /private/tmp/asr-fresh2/lib/python3.13/site-packages/apple_asr/shim/apple-asr-shim
final [flush] 0.00-19.20: 我們今天來討論鐳射在醫學上的應用雷射技術可以精確地切除腫瘤組織減少對週圍健康組織的傷害在眼科手術中雷射用來矯正視力治療近視和遠視牙醫也使用雷射來進行口腔手術
audio_time: 31.55 partials seen: 126 stats: Stats(partials=126, finals=1, words=204, dropped=0, bytes=2019320)

TRANSCRIPT: 我們今天來討論鐳射在醫學上的應用雷射技術可以精確地切除腫瘤組織減少對週圍健康組織的傷害在眼科手術中雷射用來矯正視力治療近視和遠視牙醫也使用雷射來進行口腔手術
EXIT=0

$ find /tmp/fresh-cache2                     # nothing: no build happened, no cache
                                             # dir was even created
```

Key acceptance met: **the bundled binary is what ran.** The resolved path is the
wheel's package data inside `site-packages`, the cache was empty, and `swiftc`
was not on `PATH` at all — a build was impossible. `shim_info()` (a module helper,
same resolver) also resolved the bundle, and `hello` matched (protocol 1, shim
0.1.0) or `Stream()` would have refused.

The same install also ran the shim's own `--file` mode on the bundled clip, under
the same sanitized PATH (`EXIT=0`, two `final` events, 100 word runs with
confidence, full text including the tail sentence
`雷射在現代醫學中扮演著越來越重要的角色未來的應用將更加廣泛`).

### The chmod path

Zip members do carry a mode (hatchling writes 0755) and pip/uv on POSIX honour it
today, so a plain install landed executable. I then forced the failure the chmod
guards against:

```
--- installed mode (as pip left it):
-rwxr-xr-x@ .../site-packages/apple_asr/shim/apple-asr-shim
--- forced to no exec bit:
$ chmod 644 .../apple_asr/shim/apple-asr-shim
-rw-r--r--@ .../site-packages/apple_asr/shim/apple-asr-shim
--- direct exec attempt:
/bin/sh: .../apple_asr/shim/apple-asr-shim: Permission denied
--- public API, sanitized PATH + empty cache:
final [flush] 0.00-19.20: 我們今天來討論鐳射在醫學上的應用雷射技術…
TRANSCRIPT: 我們今天來討論鐳射在醫學上的應用雷射技術可以精確地切除腫瘤組織…
EXIT=0
--- mode after (resolver repaired it):
-rwxr-xr-x@ .../site-packages/apple_asr/shim/apple-asr-shim
```

A concrete way the bit really is lost (this is what the comment/README cite):
`python -m zipfile -e dist/apple_asr-0.1.1-py3-none-macosx_26_0_arm64.whl .`
leaves `apple_asr/shim/apple-asr-shim` at `-rw-r--r--` — zipfile does not restore
modes, and the result then fails as `EACCES` ("no shim") rather than as a mode
problem. Hence the resolver, not the installer, owns the exec bit.

### Tests, lint, workflow validation

```
$ APPLE_ASR_CACHE=$PWD/.cache pytest -q --tb=line -rf -m "not integration"
64 passed, 6 deselected in 21.40s

$ APPLE_ASR_CACHE=$PWD/.cache pytest -q --tb=line -rf          # full suite, integration included
70 passed in 53.27s

$ ruff check .
All checks passed!

$ uvx --from pyyaml python -c '<safe_load both workflows>'
.github/workflows/wheel.yml -> parsed; jobs: ['wheel'] ; on: ['push', 'workflow_dispatch']
  runs-on: macos-26  steps: checkout@v4, setup-python@v5, setup-uv@v5, build,
                            upload-artifact@v4, release attach
.github/workflows/ci.yml    -> parsed; jobs: ['fake-shim']

$ /tmp/actionlint .github/workflows/wheel.yml   # actionlint 1.7.12, darwin/arm64
wheel.yml: actionlint clean
$ /tmp/actionlint .github/workflows/ci.yml
ci.yml: actionlint clean
```

New tests (`tests/test_shim_resolution.py`, 6): bundled shim resolves without
calling `build_shim`; the bundle is chmod-ed on first use; an already-executable
bundle is left byte-for-byte alone; the version cache still wins over the bundle;
build-on-demand is intact when no bundle exists; the empty-machine error names
both the bundle path and the build command.

## 3. Not verified (and why)

* **The CI run itself.** The workflow has never executed: this workspace has no
  GitHub repo/remotes, and the task forbids creating one. Validated only as far
  as static analysis goes (YAML parses, `actionlint` clean, careful read). Unverified
  until the repo exists and is public: the `macos-26` label being available to the
  account, that runner having a macOS 26 SDK with the Speech framework, the action
  pins (`checkout@v4`, `setup-python@v5`, `astral-sh/setup-uv@v5`,
  `upload-artifact@v4`), `bash scripts/build_wheel.sh` succeeding on a fresh
  runner (network fetch of hatchling + `wheel` for `uv build`/`uvx`), and the
  `gh release create/upload` step (GITHUB_TOKEN permissions, release naming).
* **A negative arm64/build-assertion run.** I verified the assertions pass; I did
  not stage a fake Intel binary to watch them fail. The `pipefail`+`grep -q`
  SIGPIPE race in those assertions **was** observed live (one spurious failure out
  of the first two runs) and is fixed by matching on captured output instead of a
  pipeline — see the comments in the script.
* **Quarantine/Gatekeeper for the shipped binary.** Not exercised. Reasoning (not
  tested): pip extracts wheels with `zipfile`, which does not copy xattrs, so a
  `com.apple.quarantine` on a browser-downloaded `.whl` should not follow the
  binary into `site-packages`. The binary is unsigned/not notarized; the host
  process still needs the Speech asset/TCC the same as before.
* **Intel macOS 26 / other arches.** Scope per the order: arm64 only, and Intel
  Macs are refused by the tag (they keep the source path `python -m apple_asr.build`).
* **The known integration flake.** `tests/test_integration_replay.py::
  test_every_pause_commit_lands_within_a_third_of_a_second` (a 0.22 s pause at
  21.3 s that never committed) failed the first full-suite run and 2/3 isolated
  runs here; the final full run was green (70 passed). It reproduces on a
  pristine `8ab4ff7` worktree (1 of 2 runs failed there), so it is **pre-existing
  and unrelated** to this change — the replay test resolves the cache shim, which
  is untouched. Not fixed, not documented in the README (out of scope) — worth a
  follow-up.
* `uv.lock`: an untracked file appeared during my earlier `uv` probing (not from
  `uv build`, not from the script or `uvx` — re-verified). Removed; tree clean.

## 4. Notes for review

* Resolution order changed in one place only: the bundle sits **after** `PATH` and
  **before** build-on-demand, so every previously documented hit keeps priority
  (the wheel's cache and a user's `PATH` shim still win) and a wheel install with
  nothing else present never reaches `swiftc`. Docstring and README updated to
  match.
* Only paths the package owns are chmod-ed (cache + bundle). `Stream(shim=...)`,
  `$APPLE_ASR_SHIM` and a `PATH` hit are left as the caller set them.
* `ensure_executable` returns `False` rather than raising when it cannot chmod
  (e.g. a root-owned read-only `site-packages`), so resolution falls through to
  build-on-demand / `ShimUnavailable` instead of handing out a path that cannot
  exec.
* The wheel is `Root-Is-Purelib: true` with a platform tag — i.e. "pure Python,
  platform-restricted by the bundled binary", which is what the tag conveys.
* Reproduce the whole thing:
  `cd /Users/clkao/git/asr/apple-asr && bash scripts/build_wheel.sh`, then the
  fresh-venv sanitized-PATH run above.
