# FIXFINAL — re-pin to apple-asr v0.1.4, PR body refresh, final acceptance

Branch `apple-speech-backend`, worktree `/Users/clkao/git/asr/WhisperLiveKit/.worktrees/apple-speech-backend`.
Base `origin/main` @ `363e4f6`; tip before this pass `b303f79`; **tip after this pass `21c957c`**
(15 commits). No push, no PR, no tags; the apple-asr repo was not modified or written to.

---

## STEP 1 — re-pin to the released 0.1.4

Release verified first (tag view reports a stale empty asset array, exactly as warned; the id
endpoint is authoritative):

```
$ gh api repos/clkao/apple-asr/releases --jq '.[] | {id, tag_name, published_at}'
{"id":394429135,"name":"v0.1.4","published_at":"2026-09-23T08:09:48Z","tag_name":"v0.1.4"}
$ gh api repos/clkao/apple-asr/releases/394429135/assets --jq '.[] | {name, size}'
{"browser_download_url":"https://github.com/clkao/apple-asr/releases/download/v0.1.4/apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl","name":"apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl","size":133474}
$ gh api repos/clkao/apple-asr/releases/tags/v0.1.4 --jq '.assets'
[]
```

Edits:

| file | change |
|---|---|
| `pyproject.toml` | `[tool.uv.sources]` tag `v0.1.3` → `v0.1.4`; extra floor `'apple-asr>=0.1.3,<0.2'` → `'apple-asr>=0.1.4,<0.2'`; the wheel-name example in the extra's comment `0.1.3` → `0.1.4` |
| `.github/workflows/ci.yml` | job-scoped install `apple-asr @ git+…@v0.1.3` → `@v0.1.4` |
| `docs/backends.md` | the documented manual path: release-wheel URL and the commented git-tag pin `v0.1.3` → `v0.1.4` |
| `uv.lock` | regenerated |

`docs/backends.md` was not in the task's list of three edit sites but documents the same pin as
the manual install path; leaving it at v0.1.3 would have made the PR body's "the release wheel is
the documented manual path" point at a superseded release. It is a version-string-only change
(4 lines) and is inside the re-pin's scope.

Lock regeneration and checks:

```
$ UV_NO_CONFIG=1 uv lock
Resolved 407 packages in 6.78s
Updated apple-asr v0.1.3 (04de6c94) -> v0.1.4 (73f0d31f)

$ grep -n -A2 'name = "apple-asr"' uv.lock
1047:name = "apple-asr"
1048-version = "0.1.4"
1049-source = { git = "https://github.com/clkao/apple-asr?tag=v0.1.4#73f0d31f33ec8cf8ea56c55f3fa4ae48a6dbddeb" }
12886:    { name = "apple-asr", marker = "extra == 'apple-speech'", git = "https://github.com/clkao/apple-asr?tag=v0.1.4" },

$ UV_NO_CONFIG=1 uv lock --check            # exit 0
Resolved 407 packages in 366ms
$ UV_NO_CONFIG=1 uv lock --check --python 3.12   # exit 0
Using CPython 3.12.9
Resolved 407 packages in 113ms
```

**Pinned commit: `73f0d31f33ec8cf8ea56c55f3fa4ae48a6dbddeb`** — matches the stated `v0.1.4` @
`73f0d31`.

Installed version (after `uv run --extra apple-speech`, which builds the git source):

```
$ UV_NO_CONFIG=1 uv run --extra apple-speech python -c "import apple_asr; print(apple_asr.__version__)"
Uninstalled 1 package in 2ms
Installed 1 package in 1ms
0.1.4
```

The three 0.1.4 changes are present in the installed package (read from site-packages, not from
the apple-asr repo): `Transport._make_words(..., floor=…)` clamps each word run's start to the
same boundary `_make_final` clamped `Final.start` to (`transport.py:585-653`); the rejected-`hello`
path terminates the child (`transport.py:411, 738, 815`); `drift` appears only in the docstring
that records its removal (`transport.py:71`).

**Note on the shim binary.** The shim cache key is the *protocol* version (`apple_asr/0.1.0/`),
not the package version, so the acceptance runs reused the binary built for the 0.1.3 run
(`/tmp/b2_cache`, built 00:36). That is correct here: all three 0.1.4 changes are Python-side, and
`SHIM_VERSION` is unchanged ("0.1.0"), so the wire protocol is identical. The independence of this
claim is confirmed by measurement rather than by inference — see `word_start_deficit_min_s` below.

## STEP 2 — PR body refreshed

`.spacedock/dev/.spacedock-state/apple-speech-backend/PR-apple-speech.md` was rewritten (it had
predated B1/B2: 6 commits, `+1159/−3`, 11 files, "Not resolved in this PR" for four things that
B1/B2 fixed, `apple-asr>=0.1.2`, the 300 ms hold, 9 tests).

New structure (lede first):

1. **Summary** — adapter scope (329 lines, no protocol/timing code) + the behaviour as shipped:
   the pause-collection hold at `_PAUSE_COLLECT_S = 0.12 s` with the retune's measured effect
   (0.303 → 0.127 s mean, over-delivery 0.117 → 0.028 s); the unchanged measured defaults; the
   declared-timeline clock with the reanchor/clamp rationale and the display-only
   `get_buffer()` clamp; teardown; failure propagation; partial reconciliation; the language/
   locale decision; the context-capability decision.
2. **"Two shared-core changes — review these first"** — the `AudioProcessor.cleanup()` duck-typed
   `close()` and the capability-gated silence pull point, each with its one-line
   why-other-backends-are-unaffected justification.
3. **What it gives you** — accuracy table (motivating context) + the golden cadence re-measured on
   this branch.
4. **Files — 15 files, +1888 / −9, apple-speech only** — numstat table; the append-only config
   guarantee.
5. **Dependency: `apple-asr` >= 0.1.4** — what 0.1.3 ships (the declared-timeline clock contract
   the adapter relies on) and what 0.1.4 adds (word-run clamp, handshake child termination, dead
   `drift` removal); why the floor is 0.1.4; the plain-specifier/Warehouse rationale; the standing
   caveat that the extra cannot resolve from PyPI yet and the release wheel is the manual path.
6. **Requirements and limits (stated plainly)** — macOS 26+/Apple Silicon, pause synthesis,
   pause-bound first commit, the default-pipeline segmentation difference, the MT-chunking
   difference, inert `SpeechDetector`, no per-session language switching.
7. **Testing** — 24 tests / 0 skips; the double's scope *and* its limits (deterministic
   endpointer); mutation evidence and that it is local/not shipped; backend suites; lock/ruff.
8. **Evidence and reproducibility** — the accuracy/cadence numbers are explicitly motivating
   context, not evidence shipped with the PR; the scoring harness is not shipped.
9. **Not resolved / out of scope** — the cold-start pause outlier (0.501 s, with its cause), the
   unreproducible fake-shim close race, the deterministic endpointer, and the package-side
   residuals (now closed by 0.1.4).

Everything in the old body that the passes *had* fixed is no longer listed as unresolved; the
boundary is now: package-side items are closed by 0.1.4, and the remaining honest limits are the
three above.

## STEP 3 — acceptance (all commands from this worktree at `21c957c`)

```
$ APPLE_ASR_CACHE=/tmp/b2_cache UV_NO_CONFIG=1 uv run --extra apple-speech pytest -q tests/test_apple_speech_adapter.py -rs
........................                                                 [100%]
24 passed in 13.43s                     # 0 skips (no "skipped" line under -rs)
$ APPLE_ASR_CACHE=/tmp/b2_cache UV_NO_CONFIG=1 uv run --extra apple-speech pytest -q tests/test_backends.py tests/test_silent_backend_guard.py
44 passed, 3 warnings in 2.04s
$ UV_NO_CONFIG=1 uv run --extra apple-speech ruff check .
All checks passed!
$ APPLE_ASR_CACHE=/tmp/b2_cache UV_NO_CONFIG=1 uv run --extra apple-speech pytest -q tests/
338 passed, 15 skipped, 17 warnings, 17 errors in 18.87s
```

The 17 errors are the **pre-existing network-download failures**, reported separately exactly as
B1/B2 did:

```
ERROR tests/test_asr_coalescing_pipeline.py::test_sample_decodes_without_ffmpeg
ERROR tests/test_asr_coalescing_pipeline.py::test_deferred_audio_survives_a_long_silence
ERROR tests/test_asr_coalescing_pipeline.py::test_deferred_audio_survives_a_speaker_change
ERROR tests/test_asr_coalescing_pipeline.py::test_end_of_stream_transcribes_deferred_audio   (×4)
ERROR tests/test_pipeline.py::test_*[whisper]  (×13)
    RuntimeError: Failed to download any test samples / 401 Client Error (LibriSpeech)
```

No test file was modified for them; the counts match B2's run (338/15/17) on the pre-pin tip.

**Golden cadence** through this repo's own harness (`whisperlivekit.test_harness.TestHarness`,
`backend="apple-speech"`, `lan="zh"`, `apple_speech_locale="zh-TW"`, mode streaming,
`feed(~/git/asr/_work/zh_long.wav, speed=1.0)`; real shim, real Speech; the adapter's
`start_silence`/`end_silence`/`process_iter`/`finish`/`get_buffer` instrumented with
`/tmp/b2_measure.py`). Two fresh-process runs on the pinned 0.1.4:

| metric | run `final_after` | run `final_pr` | golden |
|---|---|---|---|
| `transcription_final` count | **12** | **12** | **12** |
| first commit (audio time) | 3.24 s | 3.14 s | 2.99 s |
| mean commit gap (audio) | 2.57 s | 2.58 s | 2.97 s |
| pauses | 11 (10 at onset, 1 by pull) | 11 (10 at onset, 1 by pull) | — |
| pause-commit latency, mean | **0.127 s** | **0.161 s** | — |
| pause-commit latency, max | 0.145 s | **0.501 s** (pause #1, by pull) | — |
| latency max, onset-window commits only | 0.130 s | 0.130 s | — |
| over-delivery mean / max | 0.028 / 0.222 s | 0.028 / 0.222 s | — |
| `zero_width_finals` | 0 / 12 | 0 / 12 | — |
| `partial_over_max_s` (volatile clamp) | 0.100 | 0.100 | — |
| **`word_start_deficit_min_s`** | **0.0** | **0.0** | was −0.172 (0.1.3) |
| `word_end_over_max_s` | 0.0 | 0.0 | 0.0 |
| `committed_chars` | 130 | 131 | — |

Readings:

- **No regression.** Cadence matches B2's post-fix rows exactly (12 finals vs golden 12; first
  commit 3.14–3.24 s; mean gap 2.57–2.58 s), and the pause-commit latency mean sits at the same
  0.127 s (run 1) with the onset-window worst at 0.13 s in both.
- **The 0.1.4 word-run clamp is live and observable**: `word_start_deficit_min_s` is **0.0** in
  both runs, against the −0.172 s B2 measured on 0.1.3. This is the strongest evidence the runs
  used 0.1.4 semantics, and it is exactly the residual B2 reported as package-side (FIXC §8.3).
- **The documented cold-start outlier reproduced in the second run**: pause #1 (the first pause of
  a fresh process) was not caught by the 0.12 s onset window and was committed by the pull point
  **0.501 s** after onset, i.e. the same ~0.5 s figure B2 recorded. The pull point is what turns
  that outlier from "stranded until speech resumes" into "late by half a second", so it is a
  retained behaviour, not a new defect. The PR body states it with its cause.

```
$ git diff --name-only origin/main..HEAD        # 15 files
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
$ git diff --shortstat origin/main..HEAD
 15 files changed, 1888 insertions(+), 9 deletions(-)
$ git rev-list --count origin/main..HEAD
15
```

## STEP 4 — commit

```
$ git add .github/workflows/ci.yml docs/backends.md pyproject.toml uv.lock
$ git commit -m "chore(apple-speech): re-pin apple-asr to the released v0.1.4"
21c957c chore(apple-speech): re-pin apple-asr to the released v0.1.4
$ git status --short          # (empty — tree clean, nothing staged)
```

No behaviour change in this pass: the only diff is the pin in four files plus the lock. The
measured defaults (`pause_commit 0.08`, `commit_interval 0.0`, streaming), the tuned hold
(`_PAUSE_COLLECT_S = 0.12`), `_SILENCE_POLL_INTERVAL_S = 0.1`, and the shared-core code paths are
untouched. The PR body lives in the state directory, not the repo, so it is not part of the
commit. Not pushed, not opened, not tagged.

## Anything that no longer matches the body

- Nothing in the body is contradicted by the acceptance numbers; the two runs differ only in the
  max pause-commit latency, and the body quotes the outlier honestly (0.501 s, with its cause)
  rather than only the mean.
- One wording caveat for a maintainer reading both: the body says 0.1.3's contract is "a monotone
  `Final.start` clamp" — the package's earlier CLOCKFIX work removed a clamp and a later release
  reinstated one on the declared-timeline model. The body describes the **shipped 0.1.4**
  semantics without relitigating history; the adapter's assumption (no remapping needed) holds
  under both.
- The extra's floor at `>=0.1.4` is deliberately stricter than the adapter's correctness minimum
  (0.1.3's clock contract). The body says so explicitly — the reason is that word timings are
  only truthful from 0.1.4, not that 0.1.3's clock is unsuitable.

## Residual risks

1. Cold-start pause-commit outlier (~0.5 s on the first pause of a fresh process) — package/
   framework latency, documented in the body, bounded by the onset window + poll interval.
2. The fake double cannot establish real SpeechAnalyzer scheduling; the real-shim cadence runs
   are the evidence for that, and they are not re-runnable in CI.
3. Accuracy figures remain unreproducible from the PR alone (the scoring harness is not shipped);
   stated as motivating context.
