# CLOCK FIX REPORT — `apple-asr`: exact session-clock mapping, `Final.start` clamp removed

Status: **implemented, committed, tree clean** (`a994b5d`, one commit).
Repo: `/Users/clkao/git/asr/apple-asr` (parent `8d433aa`).
Machine: macOS 26.6.2 (arm64), Speech framework present; CPython 3.12.9 (`/tmp/ord2venv`)
plus the 3.10–3.13 matrix venvs. `APPLE_ASR_CACHE=$PWD/.cache` for the runs that build
/resolve the real shim (the sandbox cannot write `~/.cache`, the documented escape hatch).
Nothing under `/Users/clkao/git/asr/WhisperLiveKit` was modified except this report.

---

## 0. Result in one paragraph

The single global `drift = session_consumed − frames_written` is gone. `SessionClock`
now keeps an **anchor pair `(shim_frame, session_s)` refreshed at every input boundary**
(`push`, `pause_start`, `pause_end`) and maps a shim time `t` as
`anchor_session + (t·rate − anchor_frame)/rate`, 1:1 from the anchor. The anchor moves
only when the new boundary point sits on the **same 1:1 line**, so while a pause is open
the **pause-onset anchor stays in force** and a final published mid-pause maps onto its own
audio instead of being pulled back by synthesized silence already written but not yet
reported. The mapping is monotone and 1:1, and the shim's final ranges tile its timeline,
so mapped finals are contiguous **by construction**: the `Final.start` clamp — and its
`_last_final_end` bookkeeping — is **removed** (no more up-to-drift nudge). One thing had
to be decided and is documented below: when a caller holds a pause open *past* the duration
it reports, that excess is attributed to the **session clock** (it is consumed audio, which
is how SPEC §3.3 defines the clock), because the alternative framing produces a *provable*
overlap — I found that overlap with a test before settling the semantics (§2).

---

## 1. What changed

| file | change |
|---|---|
| `src/apple_asr/transport.py` | `SessionClock`: replaced the global drift with the anchor pair + `anchor()`; `map()` is `anchor_session + (t·rate − anchor_frame)/rate` (negative clamp kept). `Transport._make_final`: **clamp removed**, `self._last_final_end` removed; the only remaining guard is `if end < start: end = start` for a malformed wire range. Docstrings now state the mechanism, the excess attribution, and why no clamp is needed. |
| `src/apple_asr/stream.py` | `push()` calls `clock.anchor()` after advancing both clocks; `pause_start()` calls `clock.anchor()` **before** the pre-roll (the pause onset, not the synthesized silence); `pause_end(d)` advances the session clock by the silence **actually written** (`max(_pause_written, target)/rate`, i.e. `d` exactly whenever the pause is not over-held) and then calls `clock.anchor()`. Docstrings + the `_SILENCE_PUMP_RATE` comment updated. |
| `tests/test_clock_accounting.py` | rewritten around exactness instead of the clamp: 5 tests (§4). |
| `README.md` | the "clock (the subtle part)" section rewritten: anchor mapping, no clamp, the excess attribution. |
| `pyproject.toml`, `src/apple_asr/__init__.py` | package version `0.1.0` → **`0.1.1`**; `__version__` is now spelled out (it used to alias `SHIM_VERSION`). **`SHIM_VERSION` is untouched (`0.1.0`)** and so is the Swift shim. |

Public API unchanged: no signature or name changes on `Stream`/events; `SessionClock` is
internal (`transport.py` says so) and gains one method (`anchor()`). The measured defaults
(`pause_commit 0.08`, `commit_interval 0.0`, `mode streaming`) are untouched — asserted on
this run by `tests/test_config.py::test_measured_defaults_are_not_improved`.
No new dependencies.

---

## 2. The attribution decision (requirement 2), and the counterexample that forced it

Two candidate semantics for a **pause held open past the reported `d`** (the pump has
already written `P > d` of silence by the time `pause_end(d)` lands):

1. **Session clock = pushed audio + Σ reported `d`** (order 2's model; `add_session(d)`),
   with the excess somehow folded into the mapping.
2. **Session clock = consumed audio** (SPEC §3.3 verbatim), i.e. the excess is attributed to
   the session clock too.

I implemented (1) first, as an anchored *piecewise* mapping that compressed the over-delivered
pause onto `[pause_onset, pause_onset + d]`, and **my own test found a real overlap** on the
second run of it:

```
E   AssertionError: final ranges overlap: 0.512 > 0.5057142857142857
E    +  where 0.5057142857142857 = Final(text='final-8192-32800', start=0.5057142857142857, ...).start
E    +  and   0.512 = Final(text='final-8192-8192', start=0.512, end=0.512, ...).reason='pause').end
```

Mechanism (not a fake-shim artifact): the shim's own final ranges **tile its timeline**, and
one of those boundaries (shim 8192) lies *inside* the over-delivered pause region. While the
pause is open those shim times map 1:1 (0.512, as requirement 1 demands); at `pause_end` the
compression re-defines that same shim time to a **smaller** value (0.5057). Any compression of
an interval that is shorter than the shim's pause region is therefore **retroactive**: an
event already mapped during the pause can overlap the first event mapped after it. The mapping
cannot be a fixed function while the pause is open under model (1), because `P` is only known
at `pause_end` — and the order forbids re-introducing a clamp.

Model (2) removes the problem at the root: the session clock advances by the silence
**actually written**, so every boundary lands back on the same 1:1 line, the pause-onset
anchor never needs to be re-defined, and the mapping is one fixed monotone function. This is
exactly SPEC §3.3 ("a session clock that starts at 0 and advances with consumed audio
(including synthesized pauses)") and is what the old `pause_end` docstring already claimed
("the session clock advances by exactly what you fed").

**Decision: model (2).** Consequences, documented in code + README:

* The "total synthesized silence for a pause equals the reported duration" guarantee is
  unchanged: the frames written for a pause are still `round(d·rate)` whenever the caller does
  not hold it past `d` (still asserted by `test_pause.py`, which passes untouched).
* `Stream.audio_time` now follows the **consumed audio** rather than `pushed + Σd`: for an
  over-held pause it gains the real elapsed silence. `[pre-roll]=0.10 s` means a reported
  `d < 0.10 s` also counts 0.10 s (the pre-roll is written regardless) — previously it
  counted `d`. Stated in the README.
* No timestamp can be pulled backwards, so the §3.3 "no overlap" invariant holds for every
  caller behaviour, not just well-behaved ones.

One honest caveat on requirement 1's suggested mutation: with model (2) the **`pause_end`
anchor refresh is numerically a no-op** (the point is already back on the 1:1 line), so
dropping it does not fail any test (mutation m1 below, reported as such). The *load-bearing*
anchor property is the pause-**onset** anchor and its "move only on the same 1:1 line" guard —
both are covered by failing mutations m5/m2 below and by the new push-with-a-pause-open test.

---

## 3. Verification (commands + observed output)

All from `/Users/clkao/git/asr/apple-asr`, post-commit (`a994b5d`), `pytest` = `/tmp/ord2venv/bin/python -m pytest`.

### 3.1 Full suite, fake shim **and** the macOS-26 integration tests running (no skips)

```
$ APPLE_ASR_CACHE=$PWD/.cache /tmp/ord2venv/bin/python -m pytest -q -rs
................................................................         [100%]
64 passed in 54.40s
```

`-rs` prints no skip summary: the 6 integration tests genuinely ran against the real shim.
(Green full-suite runs: `64 passed in 46.66s`, `46.47s`, `65.18s`, `56.61s`, `56.88s`,
`54.40s` — 6 consecutive, plus one failing run under a load-average of ~245; see §5b.)

**Count note:** the order expected 61; the suite is now **64** because this change adds
regression tests — one replaced (the clamp test) and three added (mid-pause exactness; the
pause-onset anchor under a push with a pause open; the over-delivered pause). Fake-shim subset
is 58, integration 6.

### 3.2 Golden cadence (the integration tests, real shim)

```
$ APPLE_ASR_CACHE=$PWD/.cache /tmp/ord2venv/bin/python -m pytest -q -m integration -s -rs
....
cadence: ours=spans=23 events=145 partials=132 finals=12 wall=31.3s audio=32.0s ended=closed
pauses=11 missed=0 max_pause_latency=0.140s first_commit=3.50s mean_commit_gap=2.59s
golden(finals=12, first=2.99s)
..
6 passed, 58 deselected in 34.02s
```

**12 finals vs the golden's 12**, 11/11 pauses committed, first commit 3.50 s vs golden 2.99 s
(asserted within ±1.5 s) — unchanged from order 2.

### 3.3 The clock tests alone (the required `tests/test_clock_accounting.py`, no clamp)

```
$ APPLE_ASR_CACHE=$PWD/.cache /tmp/ord2venv/bin/python -m pytest -v tests/test_clock_accounting.py
tests/test_clock_accounting.py::test_final_ranges_never_overlap_in_normal_use PASSED
tests/test_clock_accounting.py::test_a_final_that_lands_mid_pause_maps_to_the_shim_range_exactly PASSED
tests/test_clock_accounting.py::test_consecutive_mid_pause_finals_are_exact_without_a_clamp PASSED
tests/test_clock_accounting.py::test_a_push_with_a_pause_open_keeps_the_pause_onset_anchor PASSED
tests/test_clock_accounting.py::test_an_over_delivered_pause_is_attributed_to_the_session_clock PASSED
5 passed in 5.09s
```

This includes order 2's engineered **drift-divergence** case (two finals whose arrival-instant
drifts differ) — it passes without the clamp, and the mapped ranges are now the shim's own
ranges rather than a clamp-produced touch.

### 3.4 Direct timestamp sanity check (scripted fake shim, final emitted mid-pause)

`test_a_final_that_lands_mid_pause_maps_to_the_shim_range_exactly` runs a scripted scenario
that emits one final (wire range `[0.0, 0.5]`) **while the pause is open** — the shim has
consumed 9600 frames (0.6 s: push + the 0.10 s pre-roll) while the session clock still reads
0.5 s. Observed, with the assertion temporarily instrumented (test file restored, md5
`6c5d1c646eec3cf4842f010592293861` before and after):

```
OBS mid-pause final=Final(text='mid', start=0.0, end=0.5, words=(), reason='pause')
OBS wire={'type': 'final', 'text': 'mid', 'range': [0.0, 0.5], 'runs': []}
OBS consecutive mapped=[[0.0, 0.5], [0.5, 1.0]]
OBS wire=[[0.0, 0.5], [0.5, 1.0]]
OBS over-delivered: audio_time=2.05 consumed=2.05 reported_d=0.5
     finals=[(0.0, 0.5), (0.5, 0.5) ×9, (0.4999999999999998, 2.05)]
```

The mapped range equals the shim's own range **exactly** (no nudge), the two finals of the
engineered case tile `[0, 0.5]`/`[0.5, 1.0]`, and the over-delivered pause (reported 0.5 s,
1.55 s actually written) leaves `audio_time == consumed == 2.05` with every final still
mapped to its wire range and contiguous.

### 3.5 Fake-shim matrix + lint

```
$ /tmp/ord2venv/bin/python -m pytest -q -m "not integration"
58 passed, 6 deselected in 21.69s

$ for v in 3.10 3.11 3.12 3.13; do /tmp/ord2-$v/bin/python -m pytest -q -m "not integration"; done
3.10: Python 3.10.19   58 passed, 6 deselected in 31.07s
3.11: Python 3.11.14   58 passed, 6 deselected in 29.58s
3.12: Python 3.12.9    58 passed, 6 deselected in 33.54s
3.13: Python 3.13.12   58 passed, 6 deselected in 16.31s

$ /tmp/ord2venv/bin/python -m ruff check .
All checks passed!
```

### 3.6 Version

```
$ /tmp/ord2venv/bin/python -c "import sys; sys.path.insert(0,'src'); import apple_asr; \
    print(apple_asr.__version__, apple_asr.SHIM_VERSION)"
0.1.1 0.1.0
```

---

## 4. The five clock tests (what each one guards)

| test | guards |
|---|---|
| `test_final_ranges_never_overlap_in_normal_use` | the §3.3 invariant + `audio_time == 3.5` exactly on an ordinary push/pause/pause_end cycle (unchanged from order 2, still green with the clamp gone). |
| `test_a_final_that_lands_mid_pause_maps_to_the_shim_range_exactly` | requirement 1: a mid-pause final maps to the shim's wire range *exactly* (this is the "no nudge" sanity check of §3.4). |
| `test_consecutive_mid_pause_finals_are_exact_without_a_clamp` | the engineered drift-divergence case: `[[0,0.5],[0.5,1.0]]` exactly, second start == first end == the shim's own boundary. |
| `test_a_push_with_a_pause_open_keeps_the_pause_onset_anchor` | the anchor's "move only on the same 1:1 line" guard: a `push()` with unreported pumped silence behind it must not move the anchor. (The only path where that guard is observable — see mutation m5.) |
| `test_an_over_delivered_pause_is_attributed_to_the_session_clock` | requirement 2: `audio_time == consumed audio` exactly, every final maps to its wire range, no overlap. |

---

## 5. Mutation evidence (falsifiability)

Harness `/tmp/mutate_clock.py`: apply one edit, run one test (`-x`), print the failure, restore
the file in a `finally` and assert it is byte-identical afterwards (`git status` clean, no
`MUTATION` text anywhere in the tree).

**m2 — map with the arrival drift while a pause is open** (`transport.py`, the *old* global
drift), against `test_a_final_that_lands_mid_pause_maps_to_the_shim_range_exactly`:

```
E   AssertionError: (Final(text='mid', start=0.0, end=0.4, words=(), reason='pause'),
                     {'type': 'final', 'text': 'mid', 'range': [0.0, 0.5], 'runs': []})
E   assert [0.0, 0.4] == [0.0, 0.5]
1 failed in 0.42s
```

**m5 — the anchor follows every boundary unconditionally** (`transport.py`), against
`test_a_push_with_a_pause_open_keeps_the_pause_onset_anchor`:

```
E   AssertionError: Final(text='resumed', start=0.0, end=0.19999999999999996, words=(), reason='pause')
E   assert [0.0, 0.19999999999999996] == [0.0, 0.5]
1 failed in 0.67s
```

**m3 — `pause_end` advances the session clock by the reported `d` only** (the model-(1)
semantics; `stream.py`), against `test_an_over_delivered_pause_is_attributed_to_the_session_clock`:

```
E   assert 1.5 == 2.05 ± 1.0e-09
E     comparison failed
E     Obtained: 1.5
E     Expected: 2.05 ± 1.0e-09
1 failed in 2.38s
```

**m1 — drop the `pause_end` anchor refresh** (the mutation the order suggested; `stream.py`):
**does not fail. `5 passed in 4.70s`.** Reason: under the chosen attribution, `pause_end` has
already put the point back on the 1:1 line, so refreshing the anchor there is numerically a
no-op (§2, last caveat). Reported as a no-op rather than dressed up.

**m4 — take the pause anchor *after* the pre-roll** (`stream.py`): **does not fail**
(`1 passed`). Reason: the guard in `anchor()` refuses to move onto a line with a different
offset, which is exactly the property the fix needs — so this mutation is absorbed by the
guard rather than by the assertion.

Both no-op mutations were reverted; the tree is clean (`git status --short` empty) and
`git diff HEAD` contains no mutation text.

---

## 5b. Pre-existing flakiness disclosure (not introduced by this change)

Under heavy machine load (load average was **95–245** during this session; the box is running
other agents) `tests/test_integration_replay.py::test_every_pause_commit_lands_within_a_third_of_a_second`
intermittently fails with `these pauses never committed: [...]` — the replay's pause window is
the true pause duration (0.22–0.28 s) and the real shim's pause→commit latency is load
sensitive. I verified this is **pre-existing**: a clean `git worktree` at `HEAD` (i.e. *without*
this change) failed the same test in **4/4** integration runs, with the same message
(`these pauses never committed: [(3, 7.12, 0.28), (5, 10.10, 0.24), (7, 11.85, 0.28),
(9, 13.93, 0.28), (11, 15.93, 0.22)]`). This change cannot affect it: commit timing is driven
by the audio bytes the client writes, and the pump/pre-roll/shim path is untouched — only the
client-side mapping changed. Together with §3.1 (6 consecutive green full-suite runs at
moderate load) I treat the replay pause-commit test as a pre-existing environmental flake; it
is out of scope here and I did not touch it.

---

## 6. Spec/doc updates

* **README.md** — "the clock (the subtle part)" rewritten: anchor pair + mapping formula,
  pause-onset anchor while a pause is open, "no clamp and no nudged timestamp", and the
  over-delivery attribution (`audio_time` follows consumed audio, not the sum of reported
  durations, with the reason).
* **Code docs** — `SessionClock` class docstring (mechanism + attribution + why no clamp),
  `SessionClock.anchor()`, `SessionClock.drift` (now "the offset in force at the current
  point"), `Transport._make_final` (why the clamp is gone and what order 1 measured),
  `Stream.pause_end` docstring, `Stream` module docstring clock paragraph, the
  `_SILENCE_PUMP_RATE` comment (`stream.py`).
* **`_work/apple-asr-package/SPEC.md` is untouched** (read-only): it already says the session
  clock "advances with consumed audio (including synthesized pauses)", which is the semantics
  the fix now honors; its §5 "drift term ... becomes zero and the mapping is identity" line is
  satisfied by the anchor formulation (the anchor is only ever needed while a pause is open).
* `tests/fixtures/fake_shim.py` untouched (its "tiles the timeline" emulation is exactly the
  worst case this fix has to survive; note the emulation's `quiet_start` is **chunk-granular**,
  which the tests now account for where they compare against the wire).

---

## 7. Residual risks / open questions

1. `Stream.audio_time` semantics in the over-held-pause case (and for `d < 0.10 s`) now follow
   consumed audio. This is SPEC §3.3 and is tested/documented, but a caller that models its
   own timeline as `pushed + Σd` will see a divergence — the only case where that matters is a
   caller holding a pause open longer than it reports.
2. Requirement 1's suggested "drop the `pause_end` anchor" mutation is a no-op under the
   chosen attribution (m1). The anchor is still required (and tested) at the pause **onset**.
   If the parent prefers the anchor to be load-bearing at `pause_end` too, that implies model
   (1), whose overlap counterexample is in §2 — I'd want a decision before going back.
3. `push()` while a pause is open *and no `pause_end` ever follows* leaves the pumped silence
   off the session clock (pre-existing ambiguity; unchanged by this fix, no test covers it).
4. The integration replay pause-commit latency test is environmentally flaky (§5b, pre-existing).
