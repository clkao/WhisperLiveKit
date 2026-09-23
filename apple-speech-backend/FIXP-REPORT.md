# Pass P — apple-asr 0.1.4: word-run clamp, handshake-failure leak, dead `drift`; released

Repo: `/Users/clkao/git/asr/apple-asr` (WhisperLiveKit untouched — no file outside this repo
was read or written except this report).
Base: `9f33325 tests: correct the measured consumed total in the repeated-pauses docstring`
(HEAD at start, tree clean, version 0.1.3). Final: `73f0d31 release: 0.1.4`, tree clean,
tag `v0.1.4` → `73f0d31`.

```
$ git log --oneline -5
73f0d31 release: 0.1.4
c65cebe transport: drop the unused SessionClock.drift
6e31fc4 transport: clamp word-run starts like Final.start
e2a0309 transport: kill the child when the handshake is rejected
9f33325 tests: correct the measured consumed total in the repeated-pauses docstring

$ git status --porcelain          # (empty)
$ git diff --stat 9f33325..HEAD
 README.md                      |   8 +--
 pyproject.toml                 |   2 +-
 src/apple_asr/__init__.py      |   2 +-
 src/apple_asr/transport.py     | 120 +++++++++++++++++++++++++++++------------
 tests/fixtures/fake_shim.py    |  20 +++++++
 tests/support.py               |  50 +++++++++++++++++
 tests/test_clock_accounting.py |  94 ++++++++++++++++++++++++++++++++-
 tests/test_handshake.py        |  57 +++++++++++++++++++++++++-
 8 files changed, 310 insertions(+), 43 deletions(-)
```

`e2a0309` and `6e31fc4` were each checked out into a scratch worktree and tested on their own
(bisectable, not just the tip): 70 passed / 6 deselected at `e2a0309`, 71 passed / 6 deselected
at `6e31fc4` (`pytest -q -m "not integration"`, py3.13).

---

## FIX 1 — clamp `Word` starts like `Final.start`

**Change.** `src/apple_asr/transport.py`:

* `_make_words(obj, floor=0.0)` now clamps every run's mapped `start` up to `floor`, and keeps
  `end >= start` (`if end < start: end = start`, i.e. a wire run narrower than the clamp
  collapses onto the boundary). Only starts move; no end is ever pulled backwards.
* `_make_final` captures the boundary *before* it updates it (`boundary = self._last_final_end`)
  and uses it both for its own `Final.start` clamp and as `_make_words(obj, floor=boundary)` —
  the same boundary, exactly as specified. `_make_partial` keeps the default `floor=0.0`
  (partials have no such boundary), so partial word mapping is byte-identical to before.
* The bound is stated in the code as **one pause's over-delivery** (that pause's pre-roll plus
  the pumped ticks the caller did not declare) — the same bound as the `Final.start` clamp; the
  smaller "pre-roll + one tick" figure is *not* claimed anywhere.
* `SessionClock`'s docstring and the README paragraph that said "nothing else is clamped / no
  timestamp is ever pulled backwards" were corrected to name the word-run clamp too.

**Regression test.** `tests/test_clock_accounting.py::test_a_word_run_straddling_a_compressed_boundary_is_clamped`.
The scenario mirrors the measured defect: a final is published mid-pause on the pause-onset
anchor (`mid`, exact `[0.0, 0.4]` with its run `["a",0.0,0.4]`), the pause is then closed with
`pause_end(0.0)` — so *everything* written for it (the 0.10 s pre-roll, plus at least one pump
tick) is over-delivery and is compressed out — and a second final `[0.4, 0.8]` with runs
`[["b",0.4,0.75],["c",0.75,0.8]]` is emitted after a `prepare` command, i.e. strictly after the
resume push and its clock update (trigger `on: "cmd"`, so the emission can never race into the
pump). Its raw `range[0]` is the shim time `mid.end` came from, so the mapped raw start lands
*before* the boundary: run `b` straddles it. Non-vacuity is structural, not timing-dependent —
the pre-roll alone guarantees over-delivery ≥ 0.10 s, so the mapped first-run start is always
behind the boundary.

```
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -q tests/test_clock_accounting.py
.........                                                                [100%]
9 passed in 5.45s
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -q tests/test_handshake.py
.........                                                                [100%]
9 passed in 1.25s
```

(test functions on disk: clock 8 → 9, handshake 6 → 7; the handshake file collects 9 tests
because the new one is parametrized 3 ways.)

**Mutation evidence** (clamp disabled: `if start < floor: start = floor` → `if False: ...`,
patch reverted afterwards; only the new test fails):

```
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -q --tb=line -rf tests/test_clock_accounting.py
.......F.                                                                [100%]
E   AssertionError: (Word(text='b', start=0.30000000000000004, end=0.65, confidence=None),
                     Final(text='mid', start=0.0, end=0.4, words=(Word(text='a', start=0.0, end=0.4, confidence=None),), reason='pause'))
    assert 0.30000000000000004 == 0.4
     +  where 0.30000000000000004 = Word(text='b', start=0.30000000000000004, end=0.65, confidence=None).start
     +  and   0.4 = Final(text='mid', start=0.0, end=0.4, words=(Word(text='a', start=0.0, end=0.4, confidence=None),), reason='pause').end
tests/test_clock_accounting.py:472: AssertionError
FAILED tests/test_clock_accounting.py::test_a_word_run_straddling_a_compressed_boundary_is_clamped
1 failed, 8 passed in 5.26s
```

That is exactly the measured defect reproduced deterministically: the final's own start is
clamped to `0.4` (the previous final's end) while its first word starts at `0.30` — it *leads*
its own final by the pause's over-delivery (0.10 s here; −0.17 … −0.25 s measured on real
WhisperLiveKit audio).

Constraint check: the v0.1.3 clock semantics are untouched — declared timeline, `pause_end`
re-anchor, `Final.start` clamp all unchanged in behaviour (`test_an_over_held_pause_with_a_mid_pause_final_stays_monotone`,
`test_a_pause_held_past_its_reported_duration_keeps_the_declared_clock`,
`test_repeated_short_pauses_do_not_accumulate_over_delivery`, `test_push_only_sessions_are_unchanged`
still pass, unmodified). Only starts of word runs move, and only for runs that would otherwise
start before their own final.

---

## FIX 2 — kill the shim child when the handshake fails

**Change.** `src/apple_asr/transport.py`: the post-spawn startup (starting the stderr pump,
`_read_and_validate_hello`, starting the reader) is now wrapped in `try/except BaseException`;
on failure it calls the new `Transport._abort_startup()` and re-raises the original exception
untouched. `_abort_startup` is best-effort and never raises: close the control-channel write end,
close the child's stdin, `_kill()` the child (SIGKILL + reap), then join the stderr/reader
threads (5 s each).

Note on placement: the leak is in `Transport.__init__`, which is where the spawn *and* the
`hello` validation live, so that is where the teardown belongs — `Stream.__init__` cannot reach
it (the constructor raised, so the caller has no object to `close()`). The paragraph-silence
pump thread is started by `Stream` *after* the transport is constructed, so it cannot exist on
this path; the regression test asserts on *any* thread created by the call, which covers the
stderr pump, a reader thread and the pump thread alike.

**Regression test.** `tests/test_handshake.py::test_a_rejected_handshake_kills_the_child_it_spawned`,
parametrized over all three rejection paths (`protocol-mismatch`, `first-line-not-hello`,
`format-mismatch`). It asserts the exception is raised, then that the child is gone and that no
thread outlives the failed construction. The child writes its own pid before `hello`
(`APPLE_ASR_FAKE_PID`), because a SIGKILL leaves no state dump *and* `/bin/ps` is denied to the
sandboxed test process (`/bin/ps: Operation not permitted`) — liveness is probed with
`os.kill(pid, 0)` (`support.process_alive`). The scenario adds `ignore_eof: true` so the child's
lifetime depends only on being killed, not on whether a garbage-collected pipe happens to close
its stdin.

Fake-shim extension (test double only, wire protocol untouched): `FakeShim.dump_pid()` writes
`os.getpid()` to `$APPLE_ASR_FAKE_PID` at the top of `run()`, described in the module docstring.
No invalid-handshake capability was needed — the existing `first_line` / `protocol` / `format`
scenario knobs already express all three rejections.

**Mutation evidence** (`self._abort_startup()` → `pass`, patch reverted afterwards):

```
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -q --tb=line -rf tests/test_handshake.py
E   AssertionError: the shim child (pid 27640) outlived the failed handshake
E   AssertionError: the shim child (pid 29332) outlived the failed handshake
E   AssertionError: the shim child (pid 31067) outlived the failed handshake
FAILED tests/test_handshake.py::test_a_rejected_handshake_kills_the_child_it_spawned[protocol-mismatch]
FAILED tests/test_handshake.py::test_a_rejected_handshake_kills_the_child_it_spawned[first-line-not-hello]
FAILED tests/test_handshake.py::test_a_rejected_handshake_kills_the_child_it_spawned[format-mismatch]
3 failed, 6 passed in 16.35s
```

All three parametrizations fail, each naming the still-live child pid (which also proves the
liveness probe is real, not a vacuous assertion). The stderr-capture thread also survived the
mutation — it pins the `Popen`, and with it the child's stdin pipe, which is why the child never
even saw EOF.

---

## FIX 3 — `SessionClock.drift`: removed

Removed (`src/apple_asr/transport.py`, commit `c65cebe`). `grep -rn "drift" src/ tests/` now
returns **0** code hits — the only remaining mentions are prose about order 1's *old* global
`drift = session - written` term in `stream.py`/`README.md`/test docstrings, which is a
historical note about what the boundary-anchored anchor replaced, not an API.
Why remove rather than document: nothing read it, it is not in `__all__` (transport is
documented as internal), and `session - written` is exactly the transiently-stale quantity the
anchor-based mapping replaced mid-pause — keeping it as a "documented" property would invite a
future caller to reintroduce that staleness. `session_s` is the cursor callers actually need and
is retained.

---

## Verification

**Full suite, macOS 26.6.2 (the integration tests must RUN, not skip — `-rs` reports no skips):**

```
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -q --tb=line -rf -rs
........................................................................ [ 93%]
.....                                                                    [100%]
77 passed in 48.96s

$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -m integration -v
collected 77 items / 71 deselected / 6 selected
tests/test_integration_file.py::test_file_mode_commits_with_word_runs PASSED              [ 16%]
tests/test_integration_file.py::test_file_mode_timestamps_are_monotonic_and_never_overlap PASSED [ 33%]
tests/test_integration_replay.py::test_every_pause_commit_lands_within_a_third_of_a_second PASSED [ 50%]
tests/test_integration_replay.py::test_replay_produces_a_full_transcript_with_word_runs PASSED [ 66%]
tests/test_integration_replay.py::test_cadence_matches_the_wlk_golden_fixture PASSED      [ 83%]
tests/test_integration_replay.py::test_load_wav_matches_the_session_contract PASSED       [100%]
====================== 6 passed, 71 deselected in 32.36s ======================
```

(73 tests before → 77 after: +1 clock regression, +3 parametrized handshake regressions. No
existing test was weakened, skipped, deselected or edited except the module/README docstrings
that had become false.)

**3.10–3.13 fake-shim matrix** (locally, the same selection CI uses; the integration marker is
deselected exactly as in `ci.yml`):

```
=== py3.10: Python 3.10.19 ===  71 passed, 6 deselected in 16.01s
=== py3.11: Python 3.11.14 ===  71 passed, 6 deselected in 16.13s
=== py3.12: Python 3.12.9  ===  71 passed, 6 deselected in 16.11s
=== py3.13: Python 3.13.12 ===  71 passed, 6 deselected in 16.25s
```

**Lint / version:**

```
$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/python -c "import apple_asr; print(apple_asr.__version__, apple_asr.SHIM_VERSION, apple_asr.PROTOCOL_VERSION)"
0.1.4 0.1.0 1
```

Public API signatures, measured defaults (`pause_commit=0.08`, `commit_interval=0.0`,
`mode="streaming"`) and `SHIM_VERSION` / `PROTOCOL_VERSION` are unchanged.

---

## Release

* **Release URL:** https://github.com/clkao/apple-asr/releases/tag/v0.1.4
* **Wheel asset:** `apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl` (133,474 bytes)
  https://github.com/clkao/apple-asr/releases/download/v0.1.4/apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl
  (downloaded back: HTTP 200, `Version: 0.1.4`, bundles `apple_asr/shim/apple-asr-shim`)
* Tag `v0.1.4` → `73f0d31`; `git push origin main` then `git push origin v0.1.4`.

**CI:**

```
35835189293  ci     v0.1.4  push  completed/success   (fake-shim tests: py3.10, 3.11, 3.12, 3.13 all ✓)
35835189038  wheel  v0.1.4  push  completed/success   (platform wheel (macos-26, arm64); artifact apple-asr-wheel-macosx_26_0_arm64)
35835184753  ci     main    push  completed/success   (fake-shim tests: py3.10, 3.11, 3.12, 3.13 all ✓)
```

### Release-path incident (report it; it is a real, reproducible flake)

The first wheel run reported success, but my `gh release view v0.1.4` / `releases/tags/v0.1.4`
showed `assets: []`, so I concluded the upload had not happened. It *had*: the
`releases/<id>/assets` endpoint returned 1 asset the whole time — the `.assets` array on the
tag/`gh release view` response was stale. Acting on that, I re-ran the wheel run, which then
failed with:

```
HTTP 422: Validation Failed (https://uploads.github.com/repos/clkao/apple-asr/releases/394426006/assets?label=&name=apple_asr-0.1.4-py3-none-macosx_26_0_arm64.whl)
ReleaseAsset.name already exists
##[error]Process completed with exit code 1.
```

i.e. `gh release upload --clobber` did **not** clobber an existing asset on that release — a
rerun of the wheel workflow for an already-published tag is *not* idempotent. To get to a clean
state I deleted and recreated the release (`gh release delete v0.1.4 --yes`, tag preserved) and
re-ran the wheel run, which created the release and uploaded the wheel cleanly. Net effect: the
release id changed (394426006 → 394429135) while the tag (`v0.1.4` → `73f0d31`) and the asset
name/contents are exactly what the workflow produces. Both the delete+recreate and the rerun are
public actions on this repo beyond the push+tag, and are disclosed for that reason.

Residual: the `--clobber` non-idempotency is in `.github/workflows/wheel.yml` and was *not*
fixed (out of scope for this pass; it only bites a rerun for an existing tag).

---

## Unresolved / residual risks

1. `gh release upload --clobber` is not idempotent on a rerun for an existing tag (422 above).
   A future pass could add a `gh release delete-asset ... || true` before the upload, or drop
   `--clobber` semantics in favour of an explicit delete step.
2. The word-run clamp only moves *starts*. A run whose mapped range lies entirely behind the
   compressed boundary collapses to zero width at the boundary (`end = start`). That is the
   specified behaviour ("keep `end >= start`", "only the start is clamped") and is bounded by one
   pause's over-delivery, but it is worth knowing that a word can be time-degenerate in that
   case — the downstream time-based alignment path sees a zero-width word rather than a
   backdated one.
3. The handshake teardown is scoped to `Transport.__init__` (spawn + hello validation). A future
   failure *after* `Transport` succeeds (e.g. `Thread.start()` raising in `Stream.__init__`) would
   still leak the transport; today no such failure path exists, so no guard was added.
4. No real-audio re-measurement of the word-start lead was done in this pass (the sandbox has no
   mic and this is a package-side fix); the defect magnitude quoted (−0.17 … −0.25 s) is the one
   from the WhisperLiveKit adapter review, and the fix bounds the lead to 0 by construction.
