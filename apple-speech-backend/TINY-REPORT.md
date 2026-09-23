# apple-asr tiny order — report

Commit: `8ab4ff7` (single commit, tree clean). Suite: **64 passed in 49.80s**, `ruff check .` clean.

## 1. FLEURS attribution (landed)

Two places, no change to the clip:

**a. `tests/fixtures/audio/README.md` (new)** — full notice:

> `zh_long.wav` — A **31.55 s, 16 kHz mono PCM** clip of spoken Mandarin, derived
> from the `google/fleurs` corpus, which is licensed **CC-BY-4.0**. It is
> redistributed here as test data; content unchanged.
> It is a *cadence fixture* for the integration test suite — the golden fixture
> `tests/golden/zh_long_ideal.jsonl` was produced from exactly this audio, so the
> clip must not be replaced or re-encoded. It is **not** a general-purpose audio
> sample: do not reuse it as a benchmark, demo, or training input.
> Attribution: FLEURS — *FLEURS: Few-shot Learning Evaluation of Universal
> Representations of Speech* (Conneau et al., 2022; Google), CC-BY-4.0.

**b. `README.md`, new `### Fixture attribution` subsection at the end of `## Development`:**

> `tests/fixtures/audio/zh_long.wav` is a 31.55 s / 16 kHz mono clip derived from
> the `google/fleurs` corpus, which is licensed **CC-BY-4.0**; see
> `tests/fixtures/audio/README.md` for the full notice. It is a cadence fixture for
> the golden test (that golden fixture was produced from exactly this audio), not a
> general-purpose audio sample.

## 2. Fake-shim endpointer latch (landed)

`tests/fixtures/fake_shim.py`: added `self.fired`, set `True` when a quiet run commits
(in `run_emulate`) and cleared only when non-quiet audio arrives (in `_consume`); the
arm condition gained `and not self.fired`. Docstrings updated (module `emulate` note,
`self.fired` comment). Real shim path untouched.

Assertions strengthened:

- `tests/test_clock_accounting.py::test_an_over_delivered_pause_is_attributed_to_the_session_clock`
  — the comment that justified the old `assert len(finals) >= 2` ("a long pause makes
  the fake endpointer re-arm and re-publish zero-width finals") is gone; now
  `assert len(finals) == 2` + `assert [f.reason for f in finals] == ["pause", "flush"]`,
  and a new `assert len(state["quiet_commits"]) == 1` — i.e. exactly one commit per
  pause, which the re-arm could previously violate. `_drain_finals`' docstring
  ("can publish several in a pause") corrected.
- `tests/test_pause.py::test_pause_commit_lands_within_pause_commit_plus_epsilon` —
  already asserted `len(state["quiet_commits"]) == 1`, but that was timing-dependent
  under the re-arm; comment now records that the latch makes it exact.
- Already-exact assertions that the latch now makes deterministic rather than lucky
  (left unchanged): `tests/test_replay.py::test_replay_drives_the_pause_pattern_and_measures_latency`
  (`len(result.pause_commits) == 1`) and the tiling/monotonicity checks in
  `test_final_ranges_never_overlap_in_normal_use`.

## 3. Flush race — documented, not chased

Read the `fake_shim.py` loop (~3 min). `run()` calls `poll_commands()` **before**
`run_emulate()` each tick, and the stdin reader is a separate thread, so a `finalize`
with no `through` commits `self.frames` frozen at whatever the reader had consumed —
if the last pushed frames are still in flight, the final lands short of `(0.0, 1.0)`.
No clean one-liner: "drain pending stdin" would have to guess when the writer is done,
which is the same race. Code left alone; README note added (plus a one-line
cross-reference from `## Known limitations`):

> ### Known issues
>
> * **Unresolved flake in the full suite:**
>   `tests/test_control.py::test_flush_without_through_uses_the_cursor` failed once
>   in a full-suite run — it expected an exact shipped range `(0.0, 1.0)` — but
>   never in isolation (3/3 passes) or in the fake-shim subset (4/4). Suspected
>   cause: the fake shim's main loop polls its control fd *before* it reads stdin,
>   so a `finalize` command that arrives while the last pushed frames are still
>   in flight commits `through` the shim's frozen frame count, and the final lands
>   short. Draining stdin before handling a command would be the fix, but it is
>   racy by construction (the frames may not have left the writer yet); the race
>   is **unresolved** and the fake shim is left as-is.

## 4. Verification

- `APPLE_ASR_CACHE="$PWD/.cache" .venv/bin/python -m pytest -q --tb=line -rf` →
  **`64 passed in 49.80s`** (integration included, zero skips; macOS 26.6.2, real shim built).
- `.venv/bin/python -m ruff check .` → `All checks passed!`
- Earlier same-command run without the env var: `59 passed, 5 errors in 17.61s` — the 5
  errors are integration setups hitting `PermissionError` on `~/.cache/apple_asr/...`
  (sandbox blocks writes there, not a code change); re-run with the README-documented
  `APPLE_ASR_CACHE` override gave the clean 64-passed line above. `.cache/` is gitignored.

## Deliberately not done

- Did not replace the clip; did not touch the real shim, public API, measured defaults
  (`pause_commit 0.08`, `commit_interval 0.0`, streaming mode), or the version.
- Did not build a reproduction harness for the flush race; did not loop or re-run the
  suite beyond the two full runs above and one focused subset (22 passed in 11.24s) to
  validate the latch.
- Nothing under `/Users/clkao/git/asr/WhisperLiveKit` was modified.
