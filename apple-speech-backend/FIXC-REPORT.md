# CLOCK FIX C — `apple-asr`: the caller's declared pause durations define the session clock

Status: **implemented, committed, tagged, released**. Repo `/Users/clkao/git/asr/apple-asr`
(3 commits on top of `5029088 release: 0.1.2`, tag `v0.1.3` pushed, tree clean).
Machine: macOS 26.6.2 (arm64), real Speech framework present, integration tests **ran** (no skips).
Nothing under `/Users/clkao/git/asr/WhisperLiveKit` was modified except this report.

```
58437c5 clock: the caller's declared pause durations define the session clock
70c008c docs: the clock section describes the declared timeline and the clamp
04de6c9 release: 0.1.3
9f33325 tests: correct the measured consumed total in the repeated-pauses docstring
        (post-tag; the wheel packages only src/apple_asr, so the v0.1.3 asset is unaffected)
```

---

## 0. Result in one paragraph

`Stream.pause_end(d)` now advances the session clock by **exactly `d`**, not by the silence
actually written (`max(synthesized, declared)`), so the clock is the caller's declared timeline:
pushed audio + reported pauses. Since the shim's frame timeline then legitimately diverges (a
live caller holds every VAD pause open while it waits for the transcriber's final — WhisperLiveKit
up to ~0.3 s — so the pump writes more silence than `d`), `pause_end` also **re-anchors the
shim→session mapping unconditionally**, which compresses that over-delivery out of every later
timestamp. Compression is retroactive (the shim's final ranges tile its timeline, so one of those
boundaries can sit inside the compressed region), so the previously-removed **`Final.start` clamp
is back** — clamping only the start, bounded by that one pause's over-delivery — and nothing else
is clamped. Push-only callers are untouched (no divergence, anchor never has to move, mapping is
identity). Version 0.1.3; `SHIM_VERSION`/`PROTOCOL_VERSION` untouched; measured defaults untouched;
`pause_end(d)` keeps its shape.

**One thing had to be added beyond the four numbered bullets, and it is not optional — see §2.2.**
The literal minimal edit (bullet 1 only) does *not* fix the reviewer's bug: the guarded
`SessionClock.anchor()` refuses to move onto a diverging line, so the mapping stays on the
pre-pause line and every later timestamp is *still* ahead by the accumulated over-delivery
(measured: final end 1.75 s against a 1.25 s declared cursor). Bullet 2's own rationale —
"compressing over-delivered silence can otherwise re-order already-published times" — presupposes
compression, so the compression is part of the fixed design; it needed `SessionClock.reanchor()`
to become effective. Evidence for both halves is in §2.2 and §5 (mutation m3).

---

## 1. Changed files

| file | change |
|---|---|
| `src/apple_asr/stream.py` | `pause_end(d)`: `add_session(max(_pause_written, target)/rate)` → `add_session(d)` + `reanchor()`; docstrings (module clock paragraph, `pause_end`, `audio_time`, `_SILENCE_PUMP_RATE` comment, the `pause_start` anchor comment) rewritten to the declared-timeline semantics. Frame-writing behaviour (pre-roll, pump, top-up to `round(d·rate)` frames) **unchanged**. |
| `src/apple_asr/transport.py` | `SessionClock` docstring: declared timeline, the over-held divergence, the retroactive compression, and why the clamp exists. New `SessionClock.reanchor()` (forced anchor). `anchor()` docstring narrowed to what it does now (called from `push()`/`pause_start()`). `Transport._make_final`: `_last_final_end` + the `Final.start` clamp restored with a comment; nothing else clamped. |
| `tests/test_clock_accounting.py` | 5 → 8 tests: module docstring rewritten; the old over-delivered attribution test replaced by the reviewed-case test; 3 new tests (repeated short pauses, over-held pause with a mid-pause final, push-only identity); one renamed (`..._are_exact_without_a_clamp` → `..._stay_exact_and_contiguous`, the clamp is back). |
| `README.md` | "the clock (the subtle part)" rewritten to the new semantics. |
| `pyproject.toml`, `src/apple_asr/__init__.py` | version 0.1.2 → **0.1.3**. |

Public API: unchanged (no signature/name changes on `Stream`/events; `SessionClock` is internal and
gains one method). Measured defaults unchanged: `pause_commit=0.08`, `commit_interval=0.0`,
`mode="streaming"` (asserted by `tests/test_config.py::test_measured_defaults_are_not_improved`,
still green). Shim behaviour/argv untouched; no new dependencies; `ruff` clean.

---

## 2. The clock change and the clamp

### 2.1 `Stream.pause_end(d)` (stream.py)

```python
        # The declared duration is the timeline: advance the session clock by
        # exactly `d` (never by the silence actually written, which is longer for
        # an over-held pause) and re-anchor unconditionally, so the section after
        # the pause runs 1:1 from the caller's cursor and the over-delivered
        # silence is compressed out of every later timestamp (SessionClock).
        self._clock.add_session(float(duration_s))
        self._clock.reanchor()
```

`Stream.audio_time`'s docstring (bullet 4) now reads:

```
        """Seconds on the session clock: your declared timeline, not the shim's.

        Pushed audio plus the pause durations reported so far. Identical to the
        audio the shim has consumed whenever you never hold a pause open past the
        duration you report at `pause_end(d)`; a caller that does over-hold (a
        live VAD waiting for the transcriber's final) sees the shorter declared
        timeline, which is the one every reported timestamp is on.
        """
```

### 2.2 `SessionClock.reanchor()` (transport.py) — the mechanism the compression needed

`anchor()` (called by `push()` and `pause_start()`) moves the anchor **only onto the same 1:1
line**; that guard is what keeps the *pause-onset* anchor in force while a pause is open, and it
was already there. It therefore also refuses the post-pause point whenever the caller over-held
(exactly the case that must now be compressed), so I added a separate, explicit method:

```python
    def reanchor(self) -> None:
        """Move the anchor to the current point whatever line it sits on.

        Used by `Stream.pause_end(d)` once the session clock has advanced by the
        caller's declared `d`: the silence actually written may exceed it (a
        pause held open past its reported duration), and that excess is on the
        shim's timeline but not the caller's. Re-anchoring drops the exhausted
        line, so the mapping runs 1:1 from the caller's declared cursor and no
        later timestamp is ahead by the accumulated over-delivery. When nothing
        was over-delivered the point is already on the anchor's line and this is
        a no-op.
        """
        with self._lock:
            self._anchor = (self._written_frames, self._session_s)
```

Measured before/after (probe: push 0.4 s, hold the pause 0.4 s of wall time, `pause_end(0.1)`,
then push 0.2 s; the shim consumed 1.0 s, the caller's declared cursor is 0.7 s):

```
# minimal edit only (add_session(d), guard still refusing the off-line point)
audio_time 0.5      written 0.8s      anchor (6400, 0.4)   map(0.9)=0.9  map(1.1)=1.1
#   -> the second final's wire range [0.4, 1.0] maps to [0.4, 1.0]: 0.3 s AHEAD of the caller
# with add_session(d) + reanchor()
audio_time 0.5      written 0.8s      anchor (12800, 0.5)  map(0.9)=0.6  map(1.1)=0.8
#   -> the same final maps to where the caller's own audio is
```

The re-anchor is a **no-op** whenever nothing was over-delivered (the point is already on the
line), so only the over-held path changes. It can only move the line *down*, never up: `pause_end`
advances the session clock by `d` while the written frames advance by `max(d, P) ≥ d`. That is why
only an upward clamp of `Final.start` is needed, and why no timestamp can jump forward.

### 2.3 The clamp (transport.py, `Transport._make_final`)

Restored exactly as order 1 had it, with the new justification:

```python
        # `Final.start` is clamped up to the previous final's end (SPEC.md §3.3:
        # ranges never overlap). The clamp is load-bearing, not cosmetic:
        # `Stream.pause_end(d)` advances the session clock by the caller's
        # declared `d`, so the shim's over-delivered pause silence is compressed
        # out of the timeline at that call. The shim's final ranges tile *its*
        # timeline, one of those boundaries can lie inside the over-delivered
        # region, and the final already published mid-pause was mapped on the
        # pre-pause line while the next one is mapped on the post-pause line: that
        # same shim time now maps earlier, i.e. before the end already reported.
        # The re-ordering is bounded by the over-delivery of that one pause (its
        # pre-roll plus the pumped ticks the caller did not declare), and clamping
        # the start is what keeps the published ranges monotone. Only the start is
        # clamped: pulling an end backwards would move audio that has already been
        # attributed. tests/test_clock_accounting.py covers it (the
        # over-held-pause test fails if this clamp is removed).
        ...
        if start < self._last_final_end:
            start = self._last_final_end
        if end < start:  # a wire range narrower than the clamp
            end = start
        self._last_final_end = end
```

Honest note on the requested wording: the parenthetical "(≤ pre-roll + one pump tick)" describes
the *minimum* over-delivery, not the general bound. The clamp's nudge is bounded by **that one
pause's over-delivery**, i.e. by how long the caller held it past `d` (pre-roll + all the pumped
ticks that landed while it waited) — for a live caller that is ~0.1–0.3 s, and the engineered test
below measures a 0.35 s overlap. The comment says that instead of repeating the smaller number;
the parenthetical understates it and I did not want the code to claim a bound I measured to be
false.

`Word` runs are deliberately **not** clamped (instruction: "do not clamp anything else"), so a word
run straddling the compressed boundary can start slightly before the clamped `Final.start`
(same bound). Residual risk, §8.3.

---

## 3. Tests (5 → 8 in `tests/test_clock_accounting.py`)

```
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -v --no-header tests/test_clock_accounting.py
tests/test_clock_accounting.py::test_final_ranges_never_overlap_in_normal_use PASSED [ 12%]
tests/test_clock_accounting.py::test_a_final_that_lands_mid_pause_maps_to_the_shim_range_exactly PASSED [ 25%]
tests/test_clock_accounting.py::test_consecutive_mid_pause_finals_stay_exact_and_contiguous PASSED [ 37%]
tests/test_clock_accounting.py::test_a_push_with_a_pause_open_keeps_the_pause_onset_anchor PASSED [ 50%]
tests/test_clock_accounting.py::test_a_pause_held_past_its_reported_duration_keeps_the_declared_clock PASSED [ 62%]
tests/test_clock_accounting.py::test_repeated_short_pauses_do_not_accumulate_over_delivery PASSED [ 75%]
tests/test_clock_accounting.py::test_an_over_held_pause_with_a_mid_pause_final_stays_monotone PASSED [ 87%]
tests/test_clock_accounting.py::test_push_only_sessions_are_unchanged PASSED [100%]

============================== 8 passed in 5.20s ===============================
```

What each requested test does (and its observed values):

1. **The reviewed case** — `test_a_pause_held_past_its_reported_duration_keeps_the_declared_clock`:
   `push(0.4)` → `pause_start()` → hold 0.5 s (pre-roll + pump already written) → `pause_end(0.1)`.
   `audio_time == 0.5` exactly (the reviewer saw 0.7); after `push(0.2)` + `flush()` it is 0.7
   exactly (0.4 + 0.1 + 0.2 declared) while the shim consumed >0.75 s (asserted, so the test cannot
   be vacuous); finals collected — non-overlapping, monotone, every `end ≤ audio_time`.
2. **Repeated short pauses** — `test_repeated_short_pauses_do_not_accumulate_over_delivery`:
   5 × (`push(0.2)`, `pause_start()`, 0.1 s hold, `pause_end(0.05)`): `audio_time == 1.25`
   exactly (5 × 0.25); the shim consumed 1.75 s (measured; each pause over-delivers ≥ the 0.05 s
   shortfall against the 0.10 s pre-roll, and the test asserts `> 1.65`), so there is no
   accumulation; finals monotone and every `end ≤ 1.25`.
3. **Over-held pause with a mid-pause final** — `test_an_over_held_pause_with_a_mid_pause_final_stays_monotone`
   (scripted): final `mid` published at frames 8000+pre-roll with wire range `[0.0, 0.4]`, then the
   pause is held ~0.4 s and reported as 0.05 s, then `push(0.6)` and a second final `after` with
   wire range `[0.4, 0.8]`. Observed: `mid == [0.0, 0.4]` (unchanged — mapped on the pause-onset
   line), `after.start == mid.end == 0.4` (**the clamp pinned it**), `after.end ≤ audio_time`
   (1.05 declared). Mutation m1 below shows the same test failing with
   `final ranges overlap: 0.4 > 0.05…` when the clamp is removed.
4. **Push-only unchanged** — `test_push_only_sessions_are_unchanged`: no pauses → `audio_time ==
   1.0` for 1.0 s pushed, and every mapped final range equals the shim's wire range byte-for-byte
   (the mapping is identity).

Renamed/kept: `test_consecutive_mid_pause_finals_stay_exact_and_contiguous` (was
`..._are_exact_without_a_clamp`) still asserts `[[0,0.5],[0.5,1.0]]` exactly — a pause that is
*not* over-held leaves the mapping where it was, so no clamp nudge appears.
`test_a_final_that_lands_mid_pause_maps_to_the_shim_range_exactly` and
`test_a_push_with_a_pause_open_keeps_the_pause_onset_anchor` pass unchanged (both are about the
pause-onset anchor, which the guard still protects).

### 3.1 The existing assertion whose semantics changed (honest note)

`test_an_over_delivered_pause_is_attributed_to_the_session_clock` asserted
`audio_time == pytest.approx(consumed_s)` and `audio_time > 1.5` — i.e. the old "the excess is
attributed to the session clock (SPEC §3.3)" semantics. That *is* the behaviour the task reverses,
so the test was replaced by the reviewed-case test above, which asserts the declared timeline
(`audio_time == 0.7`, `< consumed_s`) and additionally checks monotonicity/non-overlap. No other
existing assertion needed changing; `tests/test_pause.py` still passes untouched (the frames
written for a pause are still `round(d·rate)` whenever the caller does not over-hold, and the
top-up is still frame-exact).

---

## 4. Mutation evidence (falsifiability)

Harness `/tmp/probe/mutate.py`: patch one file, run pytest, restore in a `finally`, and verify the
file is byte-identical afterwards (it prints `restored …: md5 <before> == <after>: True`). No
mutation text remains in the tree (`grep -rn "MUTATION" src tests README.md` → nothing;
`git status --short` → empty).

### m1 — remove the `Final.start` clamp (the required one)

`src/apple_asr/transport.py`, replacing the clamp with `# MUTATION: clamp removed`, against the
whole clock file:

```
--- m1-no-clamp: src/apple_asr/transport.py patched ---
finals = [Final(text='mid', start=0.0, end=0.4, words=(), reason='pause'),
          Final(text='after', start=0.050000000000000044, end=0.45000000000000007, reason='pause')]

    def _assert_no_overlap(finals: list[Final]) -> None:
        for previous, following in zip(finals, finals[1:], strict=False):
>           assert following.start >= previous.end - 1e-9, (
                f"final ranges overlap: {previous.end} > {following.start}"
            )
E           AssertionError: final ranges overlap: 0.4 > 0.050000000000000044
E           assert 0.050000000000000044 >= (0.4 - 1e-09)

FAILED tests/test_clock_accounting.py::test_a_pause_held_past_its_reported_duration_keeps_the_declared_clock
FAILED tests/test_clock_accounting.py::test_repeated_short_pauses_do_not_accumulate_over_delivery
FAILED tests/test_clock_accounting.py::test_an_over_held_pause_with_a_mid_pause_final_stays_monotone
3 failed, 4 passed in 5.11s

restored src/apple_asr/transport.py: md5 7bf1d615cd979a0f4a7da9d57210e1b4 == 7bf1d615cd979a0f4a7da9d57210e1b4: True
```

(The 0.4 → 0.05 overlap equals that pause's over-delivery, as designed.)

### m2 — put the old clock rule back (`add_session(max(_pause_written, target)/rate)` + `anchor()`)

```
FAILED tests/test_clock_accounting.py::test_a_pause_held_past_its_reported_duration_keeps_the_declared_clock
FAILED tests/test_clock_accounting.py::test_repeated_short_pauses_do_not_accumulate_over_delivery
FAILED tests/test_clock_accounting.py::test_an_over_held_pause_with_a_mid_pause_final_stays_monotone
3 failed, 4 passed in 4.11s
E       AssertionError: 1.4
E       assert 1.4 == 1.05 ± 1.0e-09      # the reviewed case: 1.4 s consumed vs 1.05 s declared
restored src/apple_asr/stream.py: md5 f26144a9baef72aa851780e8b40a18fa == f26144a9baef72aa851780e8b40a18fa: True
```

### m3 — keep `add_session(d)` but drop `reanchor()` (the §2.2 justification)

```
E       AssertionError: [(0.0, 0.2, 1.25), (0.2, 1.75, 1.25)]
E       assert False
E        +  where False = all(<generator object test_repeated_short_pauses…>)
FAILED tests/test_clock_accounting.py::test_a_pause_held_past_its_reported_duration_keeps_the_declared_clock
FAILED tests/test_clock_accounting.py::test_repeated_short_pauses_do_not_accumulate_over_delivery
2 failed, 5 passed in 4.52s
restored src/apple_asr/stream.py: md5 f26144a9baef72aa851780e8b40a18fa == f26144a9baef72aa851780e8b40a18fa: True
```

i.e. without the re-anchor a final's end is reported at **1.75 s while the caller's declared cursor
is 1.25 s** — exactly the reviewer's "every subsequent token time is reported ahead by the
accumulated over-delivery". This is why the literal bullet-1-only edit was not sufficient.

---

## 5. Full suite, matrix, lint, integration

```
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -q --tb=line -rf
73 passed in 48.69s                      # baseline on this machine was 70 collected (69 passed + the known flake)
$ APPLE_ASR_CACHE=$PWD/.cache .venv/bin/python -m pytest -q --no-header -rs -m integration -s
....
cadence: ours=spans=23 events=145 partials=132 finals=12 wall=31.7s audio=32.0s ended=closed
pauses=11 missed=0 max_pause_latency=0.105s first_commit=3.50s mean_commit_gap=2.59s
golden(finals=12, first=2.99s)
..
6 passed, 66 deselected in 32.51s        # -rs prints no skip summary: the integration tests RAN
$ for v in 3.10 3.11 3.12 3.13; do /tmp/ord2-$v/bin/python -m pytest -q -m "not integration"; done
3.10: 67 passed, 6 deselected in 15.60s
3.11: 67 passed, 6 deselected in 15.45s
3.12: 67 passed, 6 deselected in 15.69s
3.13: 67 passed, 6 deselected in 15.53s
$ .venv/bin/python -m ruff check .
All checks passed!
$ .venv/bin/python -c "import apple_asr; print(apple_asr.__version__, apple_asr.SHIM_VERSION, apple_asr.PROTOCOL_VERSION)"
0.1.3 0.1.0 1
```

Counts: baseline 70 (64 non-integration + 6 integration, from the 0.1.2 tree); now **73** = 70 − 1
replaced + 3 added + 1 push-only = 73 (67 non-integration + 6 integration). The integration cadence
is unchanged from the 0.1.2 record (12 finals vs the golden's 12, 11/11 pauses committed, first
commit 3.50 s vs 2.99 s). `audio=32.0s` equals the clip duration: the replay's pauses are held for
their real duration and topped up, i.e. they do not over-hold, so the declared timeline and the
shim's consumed audio still coincide there — the good case must stay unchanged, and it does.

Pre-existing flake: `tests/test_integration_replay.py::test_every_pause_commit_lands_within_a_third_of_a_second`
failed once on the **unmodified** 0.1.2 baseline during this session (`these pauses never
committed: [(11, 15.89…, 0.22…)]`, load-related; documented in CLOCKFIX-REPORT.md §5b). It passed
in the post-change runs above. Not touched.

---

## 6. Release

```
$ git tag -a v0.1.3 -m "apple-asr 0.1.3"
$ git push origin main && git push origin v0.1.3
   5029088..04de6c9  main -> main
 * [new tag]         v0.1.3 -> v0.1.3
```

* wheel workflow (`macos-26`, arm64): **completed / success**
  https://github.com/clkao/apple-asr/actions/runs/35830969516
* ci (`v0.1.3` and `main`): **completed / success**
  https://github.com/clkao/apple-asr/actions/runs/35830969501 ·
  https://github.com/clkao/apple-asr/actions/runs/35830969094
* **Release URL: https://github.com/clkao/apple-asr/releases/tag/v0.1.3**
* **Wheel asset: `apple_asr-0.1.3-py3-none-macosx_26_0_arm64.whl`** (132,614 bytes)
  `https://github.com/clkao/apple-asr/releases/download/v0.1.3/apple_asr-0.1.3-py3-none-macosx_26_0_arm64.whl`

`git status --short` is empty (nothing staged, nothing modified); `git diff HEAD` is empty.

---

## 7. What this means for the WhisperLiveKit adapter (read-only inspection, nothing modified)

`whisperlivekit/asr_apple_speech.py` holds the pause open for `_PAUSE_COLLECT_S = 0.30` while it
waits for the pause's final, then calls `pause_end(silence_duration)` with WLK's own VAD silence
duration, and tracks its own `_audio_end += silence_duration`. That is precisely the over-holding
caller: before this change the package's `audio_time` and every token timestamp ran ahead of
`_audio_end` by the accumulated hold (up to ~0.3 s per pause), while `online_processor` and
`deepgram_compat` compare event timestamps against their own audio cursor. After this change every
reported timestamp is on the declared timeline, and `Stream.audio_time` equals WLK's `_audio_end`
exactly (both = pushed + Σ reported silence).

Textual caveat in that adapter's module docstring: "Token and buffer times need no remapping —
`apple_asr` already reports a session clock that advances with consumed audio, including the
synthesized pauses." The second clause is now wrong; the first is more true than before. That file
is in the `wlk-apple-speech-adapter` worktree and is out of scope here (I did not touch it) — the
parent may want the sentence amended when the adapter is next rebased onto 0.1.3.

---

## 8. Unresolved / residual risks

1. **SPEC.md now contradicts the code.** `_work/apple-asr-package/SPEC.md` (outside this repo, in
   the parent's state dir) defines the session clock as advancing "with consumed audio (including
   synthesized pauses)" and CLOCKFIX-REPORT.md §2 documents that as a deliberate decision. This
   pass reverses it by design ("the caller's declared durations define the timeline"), so SPEC §3.3
   and the CLOCKFIX report's §2/§3.4 (and README-adjacent docs) need an amendment. I did not edit
   files outside the repo. The in-repo docs (README, module/class docstrings) are consistent with
   the code as shipped.
2. **Partial/word events published *during* a pause are still on the pre-pause line.** While the
   pause is open nothing is compressed yet (by design: that keeps the mid-pause commit on its own
   audio), so a partial that arrives mid-pause maps 1:1 from the pause onset and can read up to the
   over-delivery ahead of the declared cursor until `pause_end` lands; the pause's final (which
   ends at the pause onset) and every later event are on the declared timeline. Volatile by nature,
   and superseded at commit, but a caller that renders tokens live will see that transient.
3. **Word runs are not clamped** (instruction: only `Final.start`). A `Word` straddling a compressed
   boundary can start marginally before the clamped `Final.start` for that same audio; bound = the
   same one-pause over-delivery. `Partial.start/end` likewise unclamped.
4. **The clamp can flatten a final to zero width** (`end < start → end = start`) when a wire range
   is narrower than the nudge, same as order 1's behaviour. Not observed in the suite; no test
   asserts a minimum width.
5. **`SessionClock.drift` is unused** (was already unused before this change); left in place rather
   than widened the diff.
6. **The clamp's bound is the caller's hold length, not "pre-roll + one tick"** (see §2.3). If the
   parent wants the stricter claim, the mechanism to get it would be compressing the pause region
   onto `[pause_onset, pause_onset + d]` (a piecewise map with an extra segment) instead of
   re-anchoring; that is a larger mapping change and I did not do it. What ships is the
   declared-cursor re-anchor with a start clamp, bounded by the over-delivery of one pause.
