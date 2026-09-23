# Apple-speech adapter as a reviewable upstream PR branch

Base: `origin/main` @ `363e4f6` ("Merge pull request #445: unblock translation
cancellation under load"). Branch: `apple-speech-backend`, worktree
`.worktrees/apple-speech-backend`. Nothing pushed, no PR opened, no tags.

Source of the apple-speech content: the existing adapter branch
`.worktrees/wlk-apple-speech-adapter` @ `56eebd9`, whose apple-speech payload
sits 6 commits on top of `wlk/integration-2` @ `9d366f9`.

## 0. Worktree + commits

```
git worktree add .worktrees/apple-speech-backend -b apple-speech-backend origin/main
git -C .worktrees/apple-speech-backend submodule update --init third_party/qwen3-asr-causal
UV_NO_CONFIG=1 uv lock          # needed the submodule; a fresh worktree lacks it
```

```
286a275 chore(lock): regenerate uv.lock for the apple-speech extra
fc65d24 test(asr): cover the apple-speech adapter with a vendored fake shim
0a5ee5e feat(asr): add the apple-speech backend via the apple-asr package
363e4f6 Merge pull request #445: unblock translation cancellation under load
```

## 1. (a) File list and diffstat — `git diff origin/main..HEAD`

```
$ git diff --name-only origin/main..HEAD
pyproject.toml
tests/fixtures/apple_speech_fake_shim.py
tests/test_apple_speech_adapter.py
uv.lock
whisperlivekit/asr_apple_speech.py
whisperlivekit/backend_support.py
whisperlivekit/benchmark/compat.py
whisperlivekit/config.py
whisperlivekit/core.py
whisperlivekit/parse_args.py

$ git diff --stat origin/main..HEAD
 pyproject.toml                           |  11 +
 tests/fixtures/apple_speech_fake_shim.py | 457 +++++++++++++++++++++++++++++++
 tests/test_apple_speech_adapter.py       | 257 +++++++++++++++++
 uv.lock                                  |  16 +-
 whisperlivekit/asr_apple_speech.py       | 227 +++++++++++++++
 whisperlivekit/backend_support.py        |  45 +++
 whisperlivekit/benchmark/compat.py       |  10 +
 whisperlivekit/config.py                 |  31 +++
 whisperlivekit/core.py                   |  26 ++
 whisperlivekit/parse_args.py             |  15 +-
 10 files changed, 1093 insertions(+), 2 deletions(-)
```

Exactly the ten allowed paths, nothing else: no `_work/` file, no shim source, no
other backend, no `scripts/` file, no golden. The diff is additive except two
modified lines in `parse_args.py` (the `--backend` choices row) and one in
`uv.lock` (`provides-extras`), i.e. 1093 insertions / 2 deletions.

Compare with the PR that would have come from `wlk/apple-speech-adapter`:
`git rev-list --count origin/main..56eebd9` = **80 commits**, 72 files,
+25663/-5179 (it carries all 74 integration-2 commits plus every other backend).
`origin/main..HEAD` here is 3 commits, 10 files, +1093/-2.

The three new files are byte-identical to `56eebd9`:

```
whisperlivekit/asr_apple_speech.py            IDENTICAL (blob)
tests/test_apple_speech_adapter.py            IDENTICAL (blob)
tests/fixtures/apple_speech_fake_shim.py      IDENTICAL (blob)
```

`uv.lock` was regenerated on this base (`UV_NO_CONFIG=1 uv lock`), never copied.
Its diff adds one package and nothing else:

```
+[[package]] name = "apple-asr" version = "0.1.2"
+source = { git = "https://github.com/clkao/apple-asr?rev=v0.1.2#50290887…" }
+[package.optional-dependencies] apple-speech = [ { name = "apple-asr" }, ]
+{ name = "apple-asr", marker = "extra == 'apple-speech'", git = "…?rev=v0.1.2" },
-provides-extras = [… "canary", "diarization-diart"]
+provides-extras = [… "canary", "apple-speech", "diarization-diart"]
```

Deliberately **not** brought over from `56eebd9` (all excluded by the order):
`_work/sa-spike/*` (spike + its deletion), `scripts/lc_terminal.py`, every
`tests/golden/*` and every other backend's files. None of them exist on
`origin/main`, so there is nothing to delete.

## 2. (b) Per-hunk review of the shared files

`git diff origin/main..HEAD -- <the six shared files>` (152 lines of diff). Every
hunk is apple-speech-only, reviewed one by one. What `origin/main` differs from
`integration-2` on, and the adaptation each difference forced:

### `whisperlivekit/config.py` (+31)

| Hunk | Content | Adaptation |
|---|---|---|
| after `FUNASR_LANGUAGES` | `APPLE_SPEECH_LANGUAGES` + `APPLE_SPEECH_MODES` frozensets | verbatim; main has `FUNASR_LANGUAGES` at the same spot |
| after the canary fields | `apple_speech_locale: str = "zh-TW"`, `apple_speech_mode: str = "streaming"` before "Keep new fields at the end" | verbatim. Main's dataclass imports `dataclass, fields` — integration-2 added `field` for the *nemotron* `att_context`, which apple-speech does not need, so the import line was left alone |
| after the canary validation block | mode + language validation for `backend == "apple-speech"`, before `if self.backend != "funasr": return` | verbatim; the anchor line exists on main unchanged |

### `whisperlivekit/core.py` (+26)

| Hunk | Content | Adaptation |
|---|---|---|
| engine `__init__`, between `voxtral-mlx` and `voxtral` | `elif config.backend == "apple-speech":` → `AppleSpeechASR(apple_speech_locale=…, apple_speech_mode=…)` + log line | The `online_factory` and engine shapes are the same as integration-2's for everything apple-speech touches, so no shape adaptation was needed. On integration-2 this branch sat between `nemotron-mlx-asr` and `voxtral`; here it lands between `voxtral-mlx` and `voxtral`. The `mlx-qwen3-asr` / `nemotron-mlx-asr` branches that integration-2 also registers were **not** copied |
| `online_factory`, inside `if language is not None or context is not None:` after the funasr block | session-language rejection: a session asking for a language other than the configured locale raises `ValueError` | verbatim. Main **does** have the same session-language hook (the funasr rejection lives in the same `if`), so this is not a missing-hook case — main simply had no second occupant of that block |
| `online_factory`, after `qwen3-vllm-metal` and before `voxtral-mlx` | `if backend == "apple-speech": return AppleSpeechOnlineProcessor(asr)` | verbatim; main's dispatch chain lacks the qwen3-metal/nemotron entries integration-2 has, so the insertion point shifts but the shape is identical |

Not copied from integration-2's `core.py`: the `mlx-qwen3-asr`/`nemotron-mlx-asr`
branches, the `mlx-sortformer` diarization branch, and the simul time-frontier
wiring.

### `whisperlivekit/parse_args.py` (+15/-2)

| Hunk | Content | Adaptation |
|---|---|---|
| `--backend` `choices` | add `"apple-speech"` | Main's list is `[auto, mlx-whisper, faster-whisper, whisper, openai-api, funasr, voxtral, voxtral-mlx, qwen3-vllm, qwen3-vllm-metal, qwen3-streaming, canary]`; integration-2's additionally carries `mlx-qwen3-asr` and `nemotron-mlx-asr`, which are **not** added. The help string is unchanged (56eebd9 did not add apple-speech to it either) |
| after the canary group | `--apple-speech-locale` and `--apple-speech-mode` (choices streaming/accurate) | verbatim text from `56eebd9`. Placed after the canary group, where `56eebd9` had them (it had them between the nemotron group and the translation group — same relative position, before `translation_group`) |

Not copied: integration-2's `--second-pass`, `--vad-threshold`,
`--vad-min-silence-ms`, `--event-log`, the `mlx-shaper3*`/`mlx-qwen3*`/`nemotron*`
groups and the `--diarization-backend mlx-sortformer` choice.

### `whisperlivekit/backend_support.py` (+45)

One hunk: `apple_speech_backend_available()` + `require_apple_speech_backend()`,
inserted after `qwen3_streaming_backend_available`, verbatim from `56eebd9`. Both
depend only on `module_available()` (present on main) and on the `apple_asr`
package, so they are self-contained. `origin/main` had neither function;
integration-2's `QWEN_LANGUAGES` constant, `mlx_qwen3_asr_backend_available` and
`nemotron_mlx_asr_backend_available`, which the same diff region also carries,
were **not** copied. (The extra blank line before `faster_backend_available`
matches `56eebd9`.)

### `whisperlivekit/benchmark/compat.py` (+10)

| Hunk | Content | Adaptation |
|---|---|---|
| imports | `from whisperlivekit.backend_support import apple_speech_backend_available` | **adapted**: integration-2's version imports `QWEN_LANGUAGES, apple_speech_backend_available` because it moved the Qwen language set into `backend_support`; `origin/main` still defines a local `_QWEN_LANGUAGES` in this file. Only the apple-speech name is imported |
| `BACKEND_LANGUAGES` | `"apple-speech": {en, de, es, fr, it, ja, ko, pt, yue, zh}` | verbatim. Main's dict has no `mlx-qwen3-asr`/`nemotron-mlx-asr` entries, which were not added |
| `detect_available_backends()` | `if apple_speech_backend_available(): backends.append("apple-speech")` before `return` | verbatim |

### `pyproject.toml` (+11)

One hunk: the `apple-speech` extra (comment block + `apple-asr @
git+https://github.com/clkao/apple-asr@v0.1.2`), inserted after the `canary`
extra. On integration-2 it followed the `nemotron-mlx-asr` extra, which main
does not have, so the anchor moved; the content is verbatim. No `[tool.uv]`
`conflicts` entry is needed (apple-speech conflicts with nothing), and none was
added — integration-2's `conflicts` list has no apple-speech entry either.

**Summary of differences `origin/main` presented:** a `--backend` choice list
without the other new backends; a `benchmark/compat.py` that still owns
`_QWEN_LANGUAGES` locally instead of importing it from `backend_support`; a
config dataclass without the `field` import; a `pyproject.toml` without the
nemotron/qwen3 extras as insertion anchors; and a `core.py` engine/dispatch chain
without the mlx-qwen3/nemotron/simul-frontier wiring. The `online_factory`
session-language hook and the backend-registry shape are present on main
unchanged, so no apple-speech registration logic had to be reshaped.

## 3. (c) Lock checks

```
$ UV_NO_CONFIG=1 uv lock --check
Resolved 407 packages in 274ms            → exit 0
$ UV_NO_CONFIG=1 uv lock --check --python 3.12
Using CPython 3.12.9
Resolved 407 packages in 117ms            → exit 0
```

## 4. (d) Tests

Environment for the worktree (no `.venv` existed there):

```
UV_NO_CONFIG=1 uv sync --extra apple-speech --extra test
```

which installed `whisperlivekit==0.2.26 (from file://…/.worktrees/apple-speech-backend)`
plus `apple-asr` from the pinned git source (`importlib.metadata.version("apple-asr") == "0.1.2"`).

```
$ .venv/bin/python -m pytest -q tests/test_apple_speech_adapter.py -rs
.........                                                                [100%]
9 passed in 3.51s

$ .venv/bin/python -m pytest -q tests/test_backends.py tests/test_silent_backend_guard.py -rs
44 passed, 3 warnings in 4.33s
```

9 passed / **0 skipped** — the `pytest.importorskip("apple_asr")` gate is
satisfied because the extra is installed.

## 5. (e) Published-package acceptance — deviation, and the substitute run

**The command as written cannot run from this base.** `scripts/lc_terminal.py` is
not in `origin/main`:

```
$ git cat-file -e origin/main:scripts/lc_terminal.py
fatal: path 'scripts/lc_terminal.py' exists on disk, but not in 'origin/main'
```

and neither are the modules it imports (`whisperlivekit/src_buffer.py`,
`whisperlivekit/tui.py`, `whisperlivekit/caption_events.py` — all
integration-2-only), nor is the `--event-log` flag. Copied into the PR worktree
as an untracked file, it fails immediately:

```
$ APPLE_ASR_CACHE=/tmp/pr_apple_cache .venv/bin/python .tmp-acceptance/lc_terminal.py --backend apple-speech …
  File "…/.tmp-acceptance/lc_terminal.py", line 79, in <module>
    from whisperlivekit.src_buffer import ends_sentence
ModuleNotFoundError: No module named 'whisperlivekit.src_buffer'
```

`lc_terminal.py` is a prototype harness, and the order excludes it (step 2's file
list) and forbids it (step "NOTHING else: no `_work/` prototype files, no shim,
no bench scripts"; step (a) requires the file list to contain *only* the paths
above). So it was not added to the PR; bringing it would require dragging
integration-2's `src_buffer`/`tui`/`caption_events` along and would stop being
additive apple-speech content. **This is the one acceptance item that is a
substitute rather than the literal command.**

The substitute exercises the same property — the PR base's pipeline driving the
adapter against the *published* package — via the PR base's own harness
(`whisperlivekit.test_harness.TestHarness`, `backend="apple-speech"`,
`lan="zh"`, locale `zh-TW`, mode `streaming`), a fresh writable
`APPLE_ASR_CACHE=/tmp/pr_apple_cache`, and real audio
(`~/git/asr/_work/zh_long.wav`, 31.55 s). The published package built its shim
itself:

```
building shim: /usr/bin/swiftc -O -parse-as-library …/site-packages/apple_asr/shim/speechanalyzer.swift -o /tmp/pr_apple_cache/apple_asr/0.1.0/apple-asr-shim.tmp
shim ready: /tmp/pr_apple_cache/apple_asr/0.1.0/apple-asr-shim
```

Finals were counted at the adapter boundary (one `Final` == one transcription
commit, which is what the golden's `transcription_final` events count); events
written to `/tmp/pr_events.jsonl`:

```
audio length        = 31.55s
transcription_final = 12   (golden: 12)
first commit (end)  = 3.60s   (golden: 2.99s)
last  commit (end)  = 32.81s   (golden: 35.69s)
mean commit gap     = 2.66s   (golden: 2.97s)
  [  0.00 ->   3.60] 我們今天來討論鐳射在醫學上的應用
  [  3.60 ->   7.35] 鐳射技術可以精確地切除腫瘤組織
  [  7.40 ->  10.40] 減少對週圍健康組織的傷害
  [ 10.45 ->  12.25] 在眼科手術中
  [ 12.30 ->  14.45] 鐳射用來矯正視力
  [ 14.45 ->  16.45] 治療近視漢遠士
  [ 16.45 ->  19.90] 牙醫也使用鐳射來進行口腔手術
  [ 19.95 ->  21.95] 減少出血汗疼痛。
  [ 21.95 ->  25.25] 皮膚科用鐳射去除斑點和紋身
  [ 25.30 ->  26.25] 總之
  [ 26.25 ->  30.45] 雷射在現代醫學中扮演著越來越重要的角色。
  [ 30.50 ->  32.81] 未來的應用將更加廣泛
```

12 finals, matching the golden's 12, and the 12 shim-side `commit[pause]:
finalize(through: …)` lines (3.5, 7.3, 10.35, 12.2, 14.35, 16.35, 19.85, 21.85,
25.2, 26.15, 30.4 s) land on the golden's cadence. First/mean commit times are
close but not equal because the golden was recorded through integration-2's
VAD/segmentation; on this base main's own default pipeline merges the utterance
into a single harness *line* (`len(state.lines) == 1`, 132 chars) while the
adapter still emits 12 commits — a segmentation-policy difference in main's
default pipeline, not an adapter difference.

## 6. (f) Lint

```
$ .venv/bin/python -m ruff check .            # whole repo, this base
All checks passed!
$ .venv/bin/python -m ruff check <the 8 touched .py files>
All checks passed!
```

No pre-existing baseline noise to report: `origin/main` is clean under the pinned
`ruff==0.16.*`.

## 7. Constraints honoured

- Not pushed, no PR opened, no tag, no repo created. Branch tracks `origin/main`
  locally only.
- `wlk/integration-2` in the main checkout is untouched: still on
  `wlk/integration-2` @ `9d366f9`, same untracked `_work/…` set as before.
- `wlk/apple-speech-adapter` untouched: still @ `56eebd9`, clean worktree.
- The `apple-asr` repo was not modified (read-only source install; its shim was
  built into a throwaway cache at `/tmp/pr_apple_cache`).
- Adapter behaviour and the measured defaults are unchanged:
  `whisperlivekit/asr_apple_speech.py` is byte-identical to `56eebd9`
  (`pause_commit 0.08`, `commit_interval 0.0`, `mode streaming`), and
  `test_session_carries_the_measured_defaults_and_the_configured_mode` asserts
  `pause_commit == 0.08`, `--commit-interval 0.0`, and the mode→preset mapping.

## 8. Unresolved / flagged

1. **Acceptance (e) is a substitute, not the literal command** (§5). The literal
   command needs `scripts/lc_terminal.py` + `src_buffer` + `tui` +
   `caption_events`, none of which exist on `origin/main` and all of which the
   order excludes. The substitute agrees with the golden on the commit count (12)
   and cadence. If the intent was in fact to ship `lc_terminal.py` in the PR,
   that is a scope change and a decision for CL.
2. The golden (`tests/golden/zh_long_ideal.jsonl`) is an integration-2 artifact
   and is not in this PR, so its numbers can only be compared, not asserted, from
   this base.
3. `main`'s default pipeline produced 1 harness line where integration-2 produced
   12; the adapter emitted 12 finals either way. If upstream cares about that
   segmentation difference it is a separate investigation, out of scope here.
4. `uv.lock`'s apple-asr numpy dependency renders as long marker expressions
   (three `numpy` pins under `apple-asr`); that is uv's own output for this base's
   conflict matrix, not hand-edited.
