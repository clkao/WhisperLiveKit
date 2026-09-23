# Pass B2 — apple-speech cadence (finding 7's pull point), the pause hold, the timestamp edge cases, and the test-double gaps

Branch `apple-speech-backend`, worktree `/Users/clkao/git/asr/WhisperLiveKit/.worktrees/apple-speech-backend`.
Base `origin/main` @ `363e4f6`; tip after B1 `022411a`; **tip after B2 `b303f79`**.
No push, no PR, no tags, no repo creation. The apple-asr package was not modified; no other branch or
worktree was touched. Package re-pin (v0.1.3, lock `0.1.3#04de6c94`) is untouched by this pass.

```
$ git diff --name-only origin/main..HEAD
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
```

Same 15 files as after B1 — the file set stayed apple-speech-only. B2 changed four of them
(+1888/−9 is the whole branch; B2's own diff is +278/−42 across those four):

| file | change |
|---|---|
| `whisperlivekit/audio_processor.py` | the silence pull point (capability-gated), the post-`end_silence()` drain, `_SILENCE_POLL_INTERVAL_S` / `_IDLE_POLL` |
| `whisperlivekit/asr_apple_speech.py` | declares `commits_during_silence`; `_PAUSE_COLLECT_S` 0.30 → 0.12; the volatile-buffer clamp; docstrings |
| `tests/fixtures/apple_speech_fake_shim.py` | mode-honest partials, close ordering, `pause_commit` from argv, unused emulation deleted |
| `tests/test_apple_speech_adapter.py` | late-final regression test, accurate-mode behavioural test, close-drain test, de-circularized defaults assertion, processor-construction cleanup |

---

## FIX 1 — a pull point during silence (finding 7)

### What changed

`whisperlivekit/audio_processor.py`, `transcription_processor()`:

- A backend declares the capability with a class attribute; the loop reads it once:
  `poll_commits_during_silence = bool(getattr(self.transcription, "commits_during_silence", False))`.
  This is the narrowest gate available without touching any other backend's code path: the attribute
  exists on exactly one class in the tree.
- The loop tracks whether a VAD pause is open from the queue's own markers (`silence_open = True` on a
  `Silence(is_starting=True)` item, `False` on `has_ended`). Only that backend gets the short idle
  timeout (`_SILENCE_POLL_INTERVAL_S = 0.1`) while the pause is open.
- On such a timeout the iteration no longer `continue`s: it sets `item = _IDLE_POLL` and falls through
  the normal path, where a new `elif item is _IDLE_POLL:` branch calls
  `_run_counted_process_iter()`. The returned tokens flow into the **same** `new_tokens` list, so they
  are committed to `state.tokens`, queued for translation (`_queue_tokens_for_translation`), and
  rendered by `results_formatter` exactly like a chunk-driven commit.
- `has_ended` now also drains once (`if poll_commits_during_silence: … _run_counted_process_iter()`),
  because `pause_end`'s top-up silence can itself provoke the commit; without it that commit would wait
  for the next audio chunk (an utterance away).

Why this gating and not something broader: a duck-typed capability is the same mechanism B1 already
used for teardown (`getattr(self.transcription, "close", None)`), it is self-describing at the
declaration site, and it leaves every other backend's path literally unchanged — the timeout stays
`0.5`, and the timeout branch still just refreshes `get_buffer()` and `continue`s.

The alternative considered and rejected: polling `process_iter()` on *every* idle timeout for the
apple backend (not only during a pause). It would also catch a commit that lands just after
`pause_end`, but it changes apple's behaviour in ordinary non-speech gaps for no measured benefit, and
the task scoped the pull point to silence. The `has_ended` drain covers the post-pause case.

### Other-backend guarantee (verified)

```
$ python - <<'PY'   # AST scan of whisperlivekit/ for the declaring class
classes scanned: 26
declaring commits_during_silence: [('whisperlivekit/asr_apple_speech.py',
                                    'AppleSpeechOnlineProcessor')]
PY
```

`grep -rn "commits_during_silence" whisperlivekit/` → the declaration, its one read, the `_IDLE_POLL`
branch, and the docs. Every other online processor (`OnlineASRProcessor`,
`SimulStreamingOnlineProcessor`, `FunASROnlineASRProcessor`, `Voxtral*OnlineProcessor`,
`_ASRTokenNormalizer`, …) lacks the attribute, so `getattr(..., False)` is `False` and the loop takes
the original code path. Backend suites pass unmodified:

```
$ pytest -q tests/test_backends.py tests/test_silent_backend_guard.py
44 passed, 3 warnings in 2.54s
$ pytest -q tests/
338 passed, 15 skipped, 17 warnings, 17 errors in 18.59s
# the 17 errors are all pre-existing network failures, not this branch:
#   RuntimeError: Failed to download any test samples
#   WARNING test_data: Failed to download LibriSpeech samples: 401 Client Error
#   (tests/test_pipeline.py[whisper] ×13, tests/test_asr_coalescing_pipeline.py ×4)
# no test file was modified for them and they fail identically on origin/main.
```

### Regression test + mutation

`tests/test_apple_speech_adapter.py::test_a_late_final_commits_during_the_pause_via_the_pull_point`
drives a real `AudioProcessor` (the `_audio_processor` helper, `tests/test_silent_backend_guard.py`
pattern) around the real adapter against the vendored fake shim in **scripted** mode. The final is
emitted only once the shim has consumed 12000 frames — 8000 speech + the 1600-frame pre-roll + enough
pump to pass the 0.12 s onset window — so `start_silence()` cannot see it. The test then asserts the
token is in `orchestrator.state.tokens` **while the pause is still open and before any further audio is
pushed**.

Mutation A — disable the capability (adapter declares `False`):

```
$ sed -i '' 's/^    commits_during_silence = True$/    commits_during_silence = False/' whisperlivekit/asr_apple_speech.py
$ pytest -q tests/test_apple_speech_adapter.py::test_a_late_final_commits_during_the_pause_via_the_pull_point
E  AssertionError: the late final never committed while the pause was open
FAILED tests/test_apple_speech_adapter.py::test_a_late_final_commits_during_the_pause_via_the_pull_point
1 failed in 4.05s
$ cp /tmp/b2_adapter.bak whisperlivekit/asr_apple_speech.py     # restored, md5 verified
```

Mutation B — remove the core fall-through (`if not (…): continue` → `if True: continue`), i.e. mutate
the shared-core half rather than the flag:

```
$ pytest -q tests/test_apple_speech_adapter.py::test_a_late_final_commits_during_the_pause_via_the_pull_point
tests/test_apple_speech_adapter.py:623: AssertionError
FAILED … 1 failed in 3.89s
$ cp /tmp/b2_ap.bak whisperlivekit/audio_processor.py
```

Restored: `grep -c MUTATION whisperlivekit/{asr_apple_speech,audio_processor}.py` → 0, and
`pytest -q tests/test_apple_speech_adapter.py` → **24 passed** (run 3× for flake checking: 24 passed
each time).

---

## FIX 2 — the collection hold, re-tuned

### What changed

`_PAUSE_COLLECT_S`: **0.30 → 0.12**. The package's pre-roll is
`_PAUSE_PREROLL_MIN_S = 0.10` at `pause_commit = 0.08`, so 0.12 s covers the common case (the final is
published ~0.05–0.2 s in) while cutting how long the pause is held open waiting for a final it may
never produce. `pause_commit = 0.08`, `commit_interval = 0.0` and `mode = "streaming"` are unchanged —
the measurement below did not justify touching them.

### Measured before / after (real shim, real audio, repo's own harness)

Harness: `/tmp/b2_measure.py` — `whisperlivekit.test_harness.TestHarness(backend="apple-speech",
lan="zh", apple_speech_locale="zh-TW", mode="streaming")`, `feed("~/git/asr/_work/zh_long.wav",
speed=1.0)`, with the adapter's `start_silence` / `end_silence` / `process_iter` / `finish` /
`get_buffer` / `_tokens_from_final` instrumented. "before" = `_PAUSE_COLLECT_S = 0.30` **and** the pull
point disabled (the pre-B2 behaviour); "after" = this commit. Each row is a separate process; the shim
is the one built from the pinned v0.1.3 package (`swiftc` via the package resolver, real Speech).

| metric (11 pauses, 31.55 s audio) | before (×4 runs) | after (×6 runs) | golden |
|---|---|---|---|
| `transcription_final` count | 12 / 12 / 12 / 12 | 12 / 12 / 12 / 12 / 12 / 12 | **12** |
| first commit (audio time) | 3.24 s (×3), 3.24 s | 3.24 s (×5), 3.14 s | 2.99 s |
| mean commit gap (audio) | 2.57 s | 2.57–2.58 s | 2.97 s |
| pause-commit latency, mean | 0.303 / 0.303 / 0.304 / 0.302 | **0.127 / 0.126 / 0.127** | — |
| pause-commit latency, max | 0.31 / 0.308 / 0.307 / 0.306 | **0.13 / 0.13 / 0.13** | — |
| over-delivery per pause, mean | 0.117 s | **0.028 / 0.028 / 0.031 / 0.033** | — |
| over-delivery per pause, max | 0.246 s | 0.222 s | — |

`pause-commit latency` = wall time from the pause onset (the loop's `start_silence` call) to the pause's
final being returned by the adapter (the onset call, or the pull-point poll that drains it).
`over-delivery` = `Stream._pause_written` at `pause_end` minus `round(d·16000)` — the synthesized
silence beyond the caller's declared `d`, i.e. exactly the quantity the package compresses out at
`pause_end` and therefore the size of the mid-pause transient.

Reading: the mean pause commit went **0.303 s → 0.127 s** (the fixed wait was the floor before) and the
per-pause over-delivery **0.117 s → 0.028 s**, so the clamp nudge and the mid-pause transient shrink
with it — which is the whole point of FIX 2. The acceptance does not regress: still **12 finals vs the
golden's 12** in every run, first commit 3.24 s before / 3.14–3.24 s after vs the golden's 2.99 s, mean
gap 2.57 vs 2.97 (the same off-by-a-little the rebase report recorded, and unchanged by this pass).

Two honest caveats on the numbers:

1. **The bound is met warm, not cold.** One fresh-process run (`after1`, first run after the shim was
   built) showed a single pause whose final landed after the onset window and was committed 0.50 s
   after onset, on the *audio chunk* that resumed speech. That pause was `d = 0.054 s` of declared
   silence and the shim simply published its final ~0.38 s after `pause_end`; the pre-B2 code would
   have hidden it only in a lucky run (its `before` runs returned it at 0.303 s because the shim
   happened to be faster there). It is the recognizer's cold-start latency, not the adapter's hold:
   in the six warm runs the pull point never had to fire (`n_pauses_committed_by_pull = 0`).
2. `_SILENCE_POLL_INTERVAL_S = 0.1` was chosen so that worst-case onset-window miss + poll ≈ 0.22 s,
   inside the ~0.3 s budget. The measured warm max is 0.13 s because the onset window catches every
   pause in practice.

---

## FIX 3 — the timestamp edge cases B1 left

All three are FIXC §8.2/8.3/8.4. Re-measured with the same instrumented real-shim runs (values are the
unclamped package values, so they are comparable before/after).

### §8.2 a partial published mid-pause can read ahead of the declared cursor — **fixed (bounded)**

`get_buffer()` now clamps the volatile partial's `start`/`end` to `self._audio_end` (the caller's
declared cursor, which the package's session clock is on):

```python
start = min(self._partial.start, self._audio_end)
end   = min(self._partial.end,   self._audio_end)
return Transcript(start=start, end=max(start, end), text=self._partial.text)
```

Measured raw overrun (partial end − `_audio_end`, before the clamp could act):
**−0.084 … +0.144 s** after FIX 2 (six runs), vs ≤ **−0.056 s** in the before runs. The bound is one
pause's over-delivery (0.222 s measured max). The clamp is bounded and cannot re-open the overlap
problem: it touches only the volatile buffer (display and the hypothesis-tail hint to MT), never a
committed token, and it is a no-op during speech because a partial's mapped end never exceeds the
pushed audio there (`test_process_iter_maps_one_word_run_per_token` still asserts the un-clamped
values 0.0/0.25 unchanged).

### §8.3 `Word` runs are not clamped — **documented, measured; package-side fix reported**

`word.start − Final.start` measured over the golden runs: **−0.172 … −0.222 s** after FIX 2 (was
−0.246 s before) — the first word of a final can start before its own (clamped) `Final.start` by up to
that pause's over-delivery. `word.end − Final.end ≤ 0.000 s` always (the mapping is affine, so only
the start can move).

I did **not** re-clamp committed word times in the adapter. Doing so would move audio attribution the
package deliberately placed on its own clock (FIXC chose to clamp only `Final.start`, "do not clamp
anything else"), and a consumer-side clamp could itself create zero-width words when the final was
flattened. The clean fix is package-side — `_make_words` clamping each run's start up to
`_last_final_end` exactly as `_make_final` does — which this order forbids touching. **Reported for the
package order**, with the bound above.

### §8.4 the clamp can flatten a final to zero width — **documented, not observed**

`zero_width_finals = 0` over **12 finals × 4 after runs and 12 × 2 before runs**. The bound is the
clamp nudge, i.e. one pause's over-delivery (≤ 0.246 s measured). No adapter test asserts a minimum
width; that is package-side behaviour (`end < start → end = start`).

---

## FIX 4 — the test-double gaps from the audit

| audit item | disposition |
|---|---|
| Fake handles `close` before queued stdin is consumed | **Fixed.** `handle_command` now sets `_close_requested` (+ timestamp) instead of finishing; `run()` finalizes only once `stdin_eof` is observed, with a bounded `CLOSE_DRAIN_S = 1.0` grace so a client that sends `close` without closing stdin cannot hang the double. `transport.shutdown()` always closes stdin right after the command, so the EOF path is the normal one. |
| Accurate mode only checked via argv/state | **Fixed + behavioural test.** `emit_partials` now derives from the argv (`--no-fast`), and the hello advertises `["volatileResults"]` without `fastResults`. `test_volatile_partials_follow_the_configured_mode` runs the same 0.5 s push in both modes and asserts streaming gets partials (buffer text + `partial` events in the state dump) while accurate gets **none**, plus `fast_results` in the dump. |
| Fixture forces `pause_commit=0.08`, so the "resolved defaults" assertion can't fail | **Fixed.** The fixture no longer defaults `pause_commit`, the fake's scenario override for it is deleted (it takes the value from the adapter's argv only), and the test asserts `state["pause_commit"] == _PAUSE_COMMIT_S` **and** `== 0.08` — i.e. what the shim received equals what the adapter was configured with, and that value is the measured default. |
| A test constructs a processor without finishing it | **Fixed.** `test_sep_follows_the_configured_locale` no longer builds an `AppleSpeechOnlineProcessor` (which spawned a shim); it uses `AppleSpeechASR` only. |
| Unused emulator behaviour left as apparent proof | **Trimmed.** Deleted: the `silent` mode (now a fatal unknown mode), the `repeat` step option, the `emit_partials` / `final_text` / `protocol` / `shim_version` / `locale` / `preset` / `format` / `capabilities` / `reporting_options` scenario overrides, and the `pause_commit` scenario override. Kept deliberately: the `finalize`/`close` command handling and the `commit`/`ended` events, which are wire-protocol fidelity the audit confirmed as the double's value. Net effect is a *smaller* simulation surface (fewer behaviours, no mode-agnostic partials); the file grew slightly because the close-ordering fix and the mode-honesty comments add more than the deletions remove. |

The audit's `close`-race item is fixed on code-path grounds (the reader is a separate thread, so
`finish()` reading `self.frames` before EOF is unsound), but I could not reproduce the pre-fix failure
by mutation on this machine — see "unresolved" below. The new
`test_close_finalizes_only_after_queued_audio_is_consumed` asserts the invariant (`frames` == pushed
frames, exit final covers all audio) and guards the fix.

---

## Verification commands (all run, in this worktree)

```
$ APPLE_ASR_CACHE=/tmp/b2_cache pytest -q tests/test_apple_speech_adapter.py -rs
24 passed in 13.27s                       # 0 skips; 21 before B2 → 24 (three new tests)
$ APPLE_ASR_CACHE=/tmp/b2_cache pytest -q tests/test_backends.py tests/test_silent_backend_guard.py
44 passed, 3 warnings in 2.54s
$ APPLE_ASR_CACHE=/tmp/b2_cache pytest -q tests/
338 passed, 15 skipped, 17 warnings, 17 errors in 18.59s
# 17 errors = pre-existing HuggingFace 401 sample downloads (test_pipeline[whisper] ×13,
# test_asr_coalescing_pipeline ×4); reported separately, as B1 did.
$ UV_NO_CONFIG=1 uv lock --check
Resolved 407 packages in 272ms            # exit 0
$ ruff check .
All checks passed!
$ git diff --name-only origin/main..HEAD   # 15 files, apple-speech-only (list above)
$ git status --short                       # clean; nothing staged
```

Golden cadence through the repo's own harness (FIX 2 acceptance; `lc_terminal.py` is not on this base,
so `TestHarness` as the rebase order did) — the after rows are
`/tmp/b2_result_final_after.json`:

```
label final_after  collect_s 0.12  pull_point true
n_finals 12 (golden 12)   first_commit_audio 3.24s (golden 2.99s)   mean_gap 2.57s (golden 2.97s)
n_pauses 11   committed_at_onset 11   committed_by_pull 0
pause_commit_latency mean 0.127s max 0.13s
over_delivery mean 0.028s max 0.222s
zero_width_finals 0 / 12   partial_over_max -0.0879s   word_start_deficit_min -0.172s
committed_chars 131
```

---

## Unresolved / residual risks (with measured bounds)

1. **Word-run starts (FIXC §8.3) — package-side fix.** Bounded by one pause's over-delivery; measured
   −0.222 s (after) / −0.246 s (before) on the golden audio. Fix belongs in `apple_asr`'s
   `Transport._make_words` (clamp run starts like `_make_final` does). Not done here: the order forbids
   modifying the package, and re-clamping committed times in the adapter would be a consumer-side
   re-architecture of the clock.
2. **Zero-width finals (FIXC §8.4) — package-side.** Bound = the clamp nudge (one pause's
   over-delivery); not observed in 6 runs (0/72 finals).
3. **Cold-start pause-commit outlier.** One pause in one fresh-process run committed 0.50 s after
   onset; every warm run is ≤ 0.144 s (mean 0.127 s). This is SpeechAnalyzer's own first-pause latency,
   which no adapter hold can remove — the pre-B2 fixed 0.30 s wait only sometimes happened to cover it.
4. **The fake's close-ordering race could not be reproduced by mutation.** With the pre-fix ordering
   restored (and even with the reader slowed to `READ_BYTES = 8`, and after shrinking the test's write
   below the pipe capacity) the test still passed 15/15 + 3/3: the reader drains a sub-capacity write
   faster than the double's 5 ms command poll. The fix stands on the code path (a threaded reader makes
   `finish()` before EOF unsound) and is covered by the invariant test; it is not demonstrated by a
   failing mutation.
5. **Package-side residuals outside this order's scope**, unchanged from B1/FIXC: the SPEC/CLOCKFIX
   clock wording contradiction (FIXC §8.1), `SessionClock.drift` unused (FIXC §8.5), and the
   handshake-failure child leak in `apple_asr/transport.py` (B1 residual).

No new risks in the shared core: the pull point is dormant for every backend that does not declare the
capability, and its only effect on the apple backend is extra `process_iter()` calls while a pause is
open (they are counted in `metrics.n_transcription_calls`, as the existing periodic-drain pattern
already was).
