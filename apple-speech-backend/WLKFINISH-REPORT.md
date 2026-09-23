# WLKFINISH — apple-speech adapter repointed at the PUBLISHED apple-asr v0.1.2

Repo: `/Users/clkao/git/asr/WhisperLiveKit`, branch `wlk/apple-speech-adapter` (was `9ac8960`
after the 3 adapter commits). Nothing pushed, no tag, no PR, no repo created; the `apple-asr`
repo was read only.

## 1. Diff summary

```
748e7fc fix(packaging): pin the apple-speech extra to the published apple-asr v0.1.2
 pyproject.toml | 11 ++++++-----
 1 file changed, 6 insertions(+), 5 deletions(-)

81a04eb chore(lock): regenerate uv.lock for apple-speech (UV_NO_CONFIG=1 uv lock)
 uv.lock | 20 +++++++++++++++-----
 1 file changed, 15 insertions(+), 5 deletions(-)
```

`pyproject.toml`, `[project.optional-dependencies].apple-speech`:

```diff
-    # TODO: the repo and its v0.1.1 tag are not published yet. Until they are,
-    # install the workspace checkout (`uv pip install -e ../apple-asr`); swap this
-    # for the PyPI release (`apple-asr>=0.1,<0.2`) or this pinned git URL once
-    # they exist.
-    'apple-asr @ git+https://github.com/clkao/apple-asr@v0.1.1',
+    # Installing this extra pulls the released package from the v0.1.2 GitHub
+    # release. `pip install apple-asr` from that release's platform wheel
+    # (apple_asr-0.1.2-py3-none-macosx_26_0_arm64.whl) needs no Swift toolchain;
+    # a git/source install compiles the shim with the local toolchain instead
+    # (`python -m apple_asr.build`).
+    'apple-asr @ git+https://github.com/clkao/apple-asr@v0.1.2',
```

The two `# The Swift shim .../gate is at runtime` lines above it are unchanged.

`uv.lock` (from the regeneration, not hand-edited):

* `+ [[package]] name = "apple-asr" version = "0.1.2" source = { git = "https://github.com/clkao/apple-asr?rev=v0.1.2#50290887ba269f347e5715eb4821fd114c25863e" }`
  (its only dependency is `numpy`, on the lock's existing three numpy branches).
* `+ apple-speech = [{ name = "apple-asr" }]` added to `whisperlivekit`'s `[package.optional-dependencies]`,
  `+ { name = "apple-asr", marker = "extra == 'apple-speech'", git = "...?rev=v0.1.2" }` in
  `[package.metadata].requires-dist`, and `apple-speech` in `provides-extras`.
* `- [options] exclude-newer = "2026-09-04T01:31:27.343311Z"` / `exclude-newer-span = "P7D"` — the
  machine's global `~/.config/uv/uv.toml` had been baked into a previously committed lock. Dropping
  it is what makes the committed lock match what a CI runner (no such config) computes; nothing else
  re-resolved (the `name = ` diff for the whole lock is exactly the one added `apple-asr` package).

Grep for the now-wrong strings, over tracked files (`git grep`): `v0.1.1`, `not published`,
`workspace checkout` → **no hits**. The adapter module docstring, `backend_support`, the tests, the
README and `docs/` never named a pin or an unpublished state, so nothing else needed touching. The
`TODO` block in `pyproject.toml` was the only place making the false claim.

## 2. Lockfile

Command (exactly as specified — `UV_NO_CONFIG=1`, so the global `exclude-newer = "7 days"` is not
applied):

```
$ cd /Users/clkao/git/asr/WhisperLiveKit
$ UV_NO_CONFIG=1 uv lock
Resolving despite existing lockfile due to removal of global exclude newer
Resolved 415 packages in 15.94s
Added apple-asr v0.1.2 (50290887)
$ git diff --stat uv.lock
 uv.lock | 20 +++++++++++++++-----
```

Verify, for the CI python versions (CI `lint` job = `python-version: "3.12"` + `pip install uv==0.10.*`
+ `uv lock --check`; local uv is 0.10.7, same minor):

```
$ UV_NO_CONFIG=1 uv lock --check
Resolved 415 packages in 308ms            # exit 0

$ UV_NO_CONFIG=1 uv lock --check --python 3.12
Using CPython 3.12.9
Resolved 415 packages in 127ms            # exit 0

$ UV_NO_CONFIG=1 uv lock --check --python 3.13
Resolved 415 packages in 131ms            # exit 0
```

Both are covered by one lock because `[tool.uv].environments` already declares
`python_version < '3.13'` and `python_version >= '3.13'`; the two extra runs pin the interpreter
explicitly and pass. A `uv lock --check` that fails prints "The lockfile at `uv.lock` needs to be
updated"; none did.

## 3. Resolution / install evidence

The tag and the release exist and the pinned commit is the release commit:

```
$ git ls-remote --tags https://github.com/clkao/apple-asr
84af4d1... refs/tags/v0.1.2
50290887ba269f347e5715eb4821fd114c25863e refs/tags/v0.1.2^{}
$ curl -sS https://api.github.com/repos/clkao/apple-asr/releases/tags/v0.1.2
tag: v0.1.2, asset: apple_asr-0.1.2-py3-none-macosx_26_0_arm64.whl (131350 bytes)
```

Install of the extra (the venv already had `apple_asr` 0.1.1 editable from the workspace checkout —
the old, pre-publication arrangement):

```
$ UV_NO_CONFIG=1 uv pip install --python .venv/bin/python -e '.[apple-speech]'
   Building whisperlivekit @ file:///Users/clkao/git/asr/WhisperLiveKit
   Updating https://github.com/clkao/apple-asr (v0.1.2)
    Updated https://github.com/clkao/apple-asr (50290887ba269f347e5715eb4821fd114c25863e)
   Building apple-asr @ git+https://github.com/clkao/apple-asr@50290887...
      Built apple-asr @ git+https://github.com/clkao/apple-asr@50290887...
Prepared 2 packages in 1.76s
Uninstalled 2 packages in 3ms
Installed 2 packages in 2ms
 - apple-asr==0.1.1 (from file:///Users/clkao/git/asr/apple-asr)
 + apple-asr==0.1.2 (from git+https://github.com/clkao/apple-asr@50290887...)
 ~ whisperlivekit==0.2.26 (from file:///Users/clkao/git/asr/WhisperLiveKit)

$ .venv/bin/python -c "import apple_asr; print(apple_asr.__version__, apple_asr.__file__)"
0.1.2 /Users/clkao/git/asr/WhisperLiveKit/.venv/lib/python3.13/site-packages/apple_asr/__init__.py

$ cat .venv/lib/python3.13/site-packages/apple_asr-0.1.2.dist-info/direct_url.json
{"url":"https://github.com/clkao/apple-asr","vcs_info":{"vcs":"git",
 "commit_id":"50290887ba269f347e5715eb4821fd114c25863e","requested_revision":"v0.1.2"}}
```

No resolution error anywhere; the extra installs from the published tag. `uv pip freeze` before/after
differs by exactly one line (the `apple-asr` line), so nothing else in the venv moved.

Behaviour of the two install flavours, both observed:

* **git/source install (what the extra does here)**: the built wheel ships only
  `apple_asr/shim/speechanalyzer.swift`, no prebuilt binary, so the shim is compiled on first use.
  With a fresh `APPLE_ASR_CACHE`, the acceptance run printed
  `building shim: /usr/bin/swiftc -O -parse-as-library .../site-packages/apple_asr/shim/speechanalyzer.swift -o /tmp/apple_asr_cache_finish/apple_asr/0.1.0/apple-asr-shim.tmp`
  and the artifact landed at `/tmp/apple_asr_cache_finish/apple_asr/0.1.0/apple-asr-shim`. This is
  exactly the "git/source install compiles the shim" half of the new comment.
* **release wheel**: downloaded `apple_asr-0.1.2-py3-none-macosx_26_0_arm64.whl`
  (sha256 `473812a32cb899ac692cf368706abccd175b273788721d9af96be95ad3fbe358`) and listed it — it
  bundles `apple_asr/shim/apple-asr-shim` (255968 bytes) next to the Swift source, `Tag:
  py3-none-macosx_26_0_arm64`. That verifies the comment's "no Swift toolchain" half; the tag also
  means a plain `pip install apple-asr` is refused on a pre-macOS-26 host (as documented).

## 4. Acceptance cadence vs the golden

```
$ export APPLE_ASR_CACHE=/tmp/apple_asr_cache_finish   # ~/.cache is not writable in the sandbox
$ .venv/bin/python scripts/lc_terminal.py --backend apple-speech --source file \
    --audio ~/git/asr/_work/zh_long.wav --event-log /tmp/finish_events.jsonl
...
format=16000.0Hz 1ch int16 vad=off preset=progressive fast=true
control: channel on fd 11
commit[pause]: finalize(through: 3.5s) ... (11 pause commits, last through: 30.55s)
control: close requested
done
[event-log] saved 58 events -> /tmp/finish_events.jsonl
rc=0
```

Counted from `/tmp/finish_events.jsonl` against `tests/golden/zh_long_ideal.jsonl`:

| metric | this run | golden | task expectation |
|---|---|---|---|
| `transcription_final` | **12** | 12 | 12 |
| first final (`audio_t`) | **3.24 s** | 2.99 s | ≈3.5 s |
| mean gap between finals | **2.694 s** (gaps 4.16, 2.76, 1.85, 2.27, 2.15, 3.41, 2.26, 3.12, 0.89, 4.54, 2.22) | 2.973 s | ≈2.6 s |
| `transcription_provisional` | 34 | 37 | — |
| `translation_final` | 12 | 9 | — |

Numbers match the pre-repoint adapter run (`ADAPTER-REPORT.md`: 12 finals / first 3.24 / mean 2.675)
and the golden's 12. Boundaries are placed slightly differently from the golden (it commits
"在眼科手術中" / "鐳射用來矯正視力" separately, as the earlier run did) — the real shim's endpointer
on this audio, not an adapter difference. All 12 committed lines came out with a translation, e.g.
`3.24 我們今天來討論鐳射在醫學上的應用` → `We are here today to discuss the applications of
lasers in medicine`.

The one number that differs from `ADAPTER-REPORT.md` is `translation_final`: 12 here (every final
translated) vs 9 there and 9 in the golden. Nothing on the adapter or MT path was changed by this
order — only the packaging pin, a comment, and the lock — so this is a run-length/drain difference
in the MT stage, not a regression; flagged below rather than diagnosed.

## 5. Tests and lint

```
$ .venv/bin/python -m pytest -q tests/test_apple_speech_adapter.py
3 passed, 6 skipped in 3.21s
  # 6 skipped: the fake shim lives in apple-asr's tests/fixtures, which the wheel/git
  # install does not ship (the fixture only exists in a source checkout)

$ APPLE_ASR_FAKE_SHIM=~/.cache/uv/git-v0/checkouts/6b4de617d19c8783/5029088/tests/fixtures/fake_shim.py \
    .venv/bin/python -m pytest -q tests/test_apple_speech_adapter.py
9 passed in 4.60s
  # the same fixture from the uv git checkout of the PINNED commit 5029088 (== v0.1.2),
  # used read-only; this is the suite actually exercising the published code

$ .venv/bin/python -m pytest -q tests/test_backends.py
34 passed in 5.91s

$ .venv/bin/ruff check .            # ruff 0.16.6
Found 17 errors.  (10 fixable)
  # none in a file this order touched (it touched no .py file). 13 of them are in
  # UNTRACKED _work/ scratch files (_work/capture_attention_golden.py, _work/sa-spike/analyze.py)
  # that do not exist in a CI checkout; the rest are the pre-existing baseline:

$ git worktree add -f --detach /tmp/wlk_head_check HEAD && (cd /tmp/wlk_head_check && ruff check .)
_work/sa-spike/bench_cer.py:40:1: I001 ...   tests/test_voxtral_mlx_compile.py:10:18: F401 ...
Found 4 errors.
  # identical at HEAD before this order -> `ruff check .` was already red on this branch;
  # this order neither caused nor fixed it.  (worktree removed afterwards)
```

`git status --porcelain` after committing: no modified/staged files. The untracked `_work/…` and
`outputs/` entries were already untracked before this order and are left alone (this report is one
of them); they are scratch, not branch content.

## 6. What I could not verify / residual risk

1. **A real CI run.** `uv lock --check` was reproduced locally with the same uv minor as CI
   (0.10.7 vs `uv==0.10.*`) and with `UV_NO_CONFIG=1`, but CI runs it on `ubuntu-latest` with
   Python 3.12. The git dependency resolves platform-independently here (no Linux-only failure
   surfaced: the resolve only reads `apple-asr`'s metadata, and its wheel tag never enters the
   lock), and `--check` passed on both declared environments — still, the first green CI run is the
   only proof that the ubuntu resolver agrees.
2. **The 3 `translation_final` events** (12 vs the earlier run's/golden's 9) are unexplained; see §4.
3. **`tests/test_apple_speech_adapter.py`'s skip path** is now the normal case for anyone installing
   the extra (git/wheel installs carry no `tests/fixtures/fake_shim.py`), so 6 of its 9 tests skip
   unless `APPLE_ASR_FAKE_SHIM` is set or the package is installed editable from a checkout. That
   was already true before this order and the skip is deliberate in the test
   (`pytest.skip("apple-asr's fake shim is not available (not a source checkout)")`), but the extra
   being the documented install path makes it worth a test-side note or a packaged fixture later.
   Not changed here — outside this order's scope.
4. **The release wheel was inspected, not installed** (its `macosx_26_0_arm64` tag and the local
   macOS are compatible, but the extra's pin is the git tag, so the wheel path is the "no Swift
   toolchain" claim only; the wheel contents were verified by listing it).
5. `~/.cache/apple_asr` is still not writable in this sandbox, so all shim builds went to
   `APPLE_ASR_CACHE=/tmp/apple_asr_cache_finish` as documented; the default cache path was not
   exercised here.

No push, no tag, no PR, no repo creation; `apple-asr` repo untouched (`git -C ../apple-asr status`
clean, HEAD `5029088` == v0.1.2).
