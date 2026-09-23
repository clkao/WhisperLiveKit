# Self-contained apple-speech adapter tests — report

Branch `wlk/apple-speech-adapter`. New HEAD **`56eebd9`** (one commit over `81a04eb`).
Pin unchanged: `[apple-speech]` still `apple-asr @ v0.1.2` (`pyproject.toml:87`).

## What changed

| file | change |
|---|---|
| `tests/fixtures/apple_speech_fake_shim.py` | **new**, 457 lines (369 non-comment/non-docstring SLOC), 16.5 KB — the vendored double |
| `tests/test_apple_speech_adapter.py` | 15 insertions / 27 deletions — use the double unconditionally, delete the source-checkout lookup + skip |

Commit: `56eebd9 test(asr): vendor a fake shim so the apple-speech adapter tests run in any install`.
No tracked modifications remain after the commit; the pre-existing untracked `_work/`, `outputs/`,
`scripts/bench_simul_mt.sh` files were left as they were.

## The vendored double

`tests/fixtures/apple_speech_fake_shim.py` speaks the `apple-asr` **wire protocol v1** on
stdin/stdout plus the **fd-3 command channel**, with no Speech, no macOS 26, no swiftc:

- emits: `hello` (protocol / shim_version / locale / preset / format{sample_rate:16000,channels:1} /
  capabilities / reporting_options), `partial` (text + range), `final` (text + range + word `runs`,
  with `confidence` when `--confidence`), `commit` (through + reason + wall), `ended` (reason)
- commands read from fd 3: `finalize` (emulate mode → flush final + commit), `close` (→ finalize +
  commit + ended, idempotent)
- scenario JSON via `APPLE_ASR_FAKE_SCENARIO`: `emulate` (float32 PCM in, partial every
  `partial_every_frames`, endpointer committing after `pause_commit` of consecutive silence, latched
  per quiet run) and `scripted` (steps fired at most once on `start` / `frames`)
- `APPLE_ASR_FAKE_STATE` dumps the observable state on exit: `argv`, `locale`, `preset`,
  `confidence`, `fast_results`, `pause_commit`, `mode`, `frames`, `commands`, `emitted`

It is a **strict subset** of the canonical shim (`apple-asr` `tests/fixtures/fake_shim.py`,
569 lines / 454 SLOC): dropped are the `locales` / `--help` / `--ensure-installed` CLI modes,
`raw`/`count`/`sleep`/`exit` scripted-step features, `quiet_commits` bookkeeping, `--file`/`--mic`/
`--vad-sensitivity` parsing, and the `cmd`/`eof` step triggers. No new behaviour: the wire objects
it emits are the canonical ones, so every existing assertion was kept verbatim (only one stale
comment about the endpointer latch was corrected to match the canonical `fired` latch semantics).

The module docstring now states that the canonical shim lives in the `apple-asr` project's own
suite and that this vendored double exists so the WLK PR is self-contained.

## 0-skipped run

The environment is the **published package, no source checkout**: `apple_asr.__file__` is
`.venv/lib/python3.13/site-packages/apple_asr/__init__.py`. The old lookup walked
`Path(apple_asr.__file__).parents` for `tests/fixtures/fake_shim.py`, found nothing, and skipped 6.
That lookup is gone.

```
$ .venv/bin/python -m pytest -q tests/test_apple_speech_adapter.py -rs
.........                                                                [100%]
9 passed in 5.84s

$ APPLE_ASR_FAKE_SHIM=/nonexistent/fake_shim.py pytest -q tests/test_apple_speech_adapter.py
.........                                                                [100%]
9 passed in 3.12s        # the old env hook is ignored; the vendored double is the only source
```

Re-run three times to check the state-file/timing path for races: `9 passed in 3.74s`,
`3.69s`, `3.57s`.

The module keeps `pytest.importorskip("apple_asr")` at import time: with the `[apple-speech]` extra
installed (the normal install these tests target) there are **0 skips**; without the extra the whole
module is skipped, like every other optional backend (`tests/test_asr_nemotron_mlx.py`,
`tests/test_translation_mlx.py`). This is a package-availability gate, not a shim-availability skip.

## Falsifiability (mutation evidence)

Mutation 1 — `start_silence()` returns without collecting the pause final:

```
# whisperlivekit/asr_apple_speech.py
-        return self._poll(_PAUSE_COLLECT_S), self._audio_end
+        return [], self._audio_end  # MUTATION: drop the pause final

$ pytest -q tests/test_apple_speech_adapter.py::test_start_silence_returns_the_pause_final_as_word_tokens
>           assert tokens, "start_silence() must return the pause's final"
E           AssertionError: start_silence() must return the pause's final
E           assert []
1 failed in 6.96s
```

Mutation 2 — drop the per-word mapping in `_tokens_from_final` (return `[]` for a `Final` with
`words`):

```
$ pytest -q tests/test_apple_speech_adapter.py::test_process_iter_maps_one_token_per_word_run
>           assert [(t.text, round(t.start, 3), round(t.end, 3)) for t in tokens] == [
                ("镭射", 0.0, 0.25),
                ("在", 0.25, 0.4),
                ("医学上", 0.4, 0.5),
            ]
E           AssertionError: assert [] == [('镭射', 0.0, ...上', 0.4, 0.5)]
1 failed in 2.74s
```

Both reverted (`git diff --stat whisperlivekit/asr_apple_speech.py` reverted to empty before the
commit; the adapter file is byte-identical to `81a04eb`).

## Suites

```
$ pytest -q tests/test_backends.py tests/test_silent_backend_guard.py tests/test_apple_speech_adapter.py
53 passed, 3 warnings in 8.01s
```

## Acceptance cadence (unchanged)

```
$ export APPLE_ASR_CACHE=/tmp/apple_asr_cache_selfcontained
$ .venv/bin/python scripts/lc_terminal.py --backend apple-speech --source file \
    --audio ~/git/asr/_work/zh_long.wav --event-log /tmp/selfcontained_events.jsonl
rc=0 ... [event-log] saved 58 events
```

| metric | this run | prior (`WLKFINISH-REPORT.md`) | golden |
|---|---|---|---|
| `transcription_final` | **12** | 12 | 12 |
| first final (`audio_t`) | **3.24 s** | 3.24 s | 2.99 s |
| mean gap between finals | **2.689 s** | 2.694 s | 2.973 s |
| `transcription_provisional` | 34 | 34 | 37 |
| `translation_final` | 12 | 12 | 9 |

Final times: `3.24, 7.14, 10.16, 12.01, 14.28, 16.31, 19.79, 22.05, 25.17, 26.06, 30.55, 32.82`.
Nothing behavioural moved — only the test scaffolding.

## Lint

```
$ ruff check tests/fixtures/apple_speech_fake_shim.py tests/test_apple_speech_adapter.py
All checks passed!

$ ruff check .
Found 17 errors.
```

The 17 whole-repo errors are the pre-existing red baseline elsewhere (neither touched file
contributes); the touched files are clean.

## Anything that could not run without a skip

Nothing. All 9 tests run. The only remaining skip path is the module-level
`importorskip("apple_asr")`, which is the package-availability gate shared with the repo's other
optional backends; it does not fire in the normal install (`[apple-speech]` extra).
