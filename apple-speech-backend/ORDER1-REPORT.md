# ORDER 1 REPORT — `apple-asr` package

Status: **implemented and verified on this machine (macOS 26.6.2, arm64).**
Repo: `/Users/clkao/git/asr/apple-asr` (new, `git init`, one commit `3901c94`, working tree clean).
Contract: `_work/apple-asr-package/SPEC.md` §3–§8; scope = §11 order 1, minus the instruments/replay/CER port and any test suite (per the task).

---

## 0. Environment note (affects how you re-run the commands)

The agent-safehouse sandbox **cannot create directories directly under `~/.cache`**
(`mkdir: /Users/clkao/.cache/zztest: Operation not permitted`), which is where
SPEC §6 puts the shim cache. The default is implemented exactly as specified
(`~/.cache/apple_asr/<version>/apple-asr-shim`); every command below additionally
sets the documented escape hatch:

```bash
export APPLE_ASR_CACHE=/Users/clkao/git/asr/apple-asr/.cache
```

and the venv used throughout is `/tmp/apple-asr-venv` (uv, CPython 3.12.9).
Outside the sandbox the default path works and `APPLE_ASR_CACHE` is unnecessary.

---

## 1. Files created

`git ls-files` in `/Users/clkao/git/asr/apple-asr`:

```
.github/workflows/ci.yml
.gitignore
LICENSE
README.md
pyproject.toml
src/apple_asr/__init__.py
src/apple_asr/build.py
src/apple_asr/cli.py
src/apple_asr/errors.py
src/apple_asr/events.py
src/apple_asr/platform.py
src/apple_asr/protocol.py
src/apple_asr/shim.py
src/apple_asr/shim/speechanalyzer.swift
src/apple_asr/stream.py
src/apple_asr/transport.py
```

What each is:

| file | content |
|---|---|
| `pyproject.toml` | hatchling; dist `apple-asr`, import `apple_asr`, MIT, `requires-python >=3.10`, runtime dep **numpy only**, console script `apple-asr-shim = apple_asr.cli:main`, `[dev]` extra (ruff+pytest), ruff config |
| `src/apple_asr/shim/speechanalyzer.swift` | the shim: copied from `_work/sa-spike/spike_speechanalyzer.swift`, extended (hello/commit/error/ended, fd-3 command channel, `--list-locales`, `--ensure-installed`, `--no-confidence`, attributeOptions), binary name `apple-asr-shim` |
| `src/apple_asr/stream.py` | `Stream` — §3.2 API, push/pause synthesis + silence pump, clock accounting, consumer-mixing guard |
| `src/apple_asr/transport.py` | §5 transport: subprocess mgr, stdout reader thread, bounded drop-oldest queue, commit acks, stderr capture, `SessionClock`, wire→dataclass mapping |
| `src/apple_asr/events.py` | `Word/Partial/Final/Ended/Error/Event/Stats/Locales/ShimInfo` (§3.3) |
| `src/apple_asr/errors.py` | §3.1 exception hierarchy, actionable messages |
| `src/apple_asr/protocol.py` | `PROTOCOL_VERSION=1`, `SHIM_VERSION="0.1.0"`, negotiated format, known types/commands/capabilities |
| `src/apple_asr/shim.py` | §6 resolution order, build, `shim_info`, `list_locales`, `ensure_installed` |
| `src/apple_asr/build.py` | `python -m apple_asr.build` |
| `src/apple_asr/cli.py` | the `apple-asr-shim` console script (resolve/build → `execv`) |
| `src/apple_asr/platform.py` | §8 gating (`require_supported`, monkeypatchable for order 2) |
| `README.md` | stub: install, quickstart, the clock-ownership section §5 demands, limitations, dev |
| `LICENSE` | MIT |
| `.github/workflows/ci.yml` | ubuntu matrix 3.10–3.13 placeholder job for the future fake-shim tests (install + import + ruff + `pytest` if `tests/` exists) |
| `.gitignore` | `__pycache__`, `.venv`, `dist/`, `.cache/`, … |

The WhisperLiveKit tree was **not** modified by this order (only this report is written there).
Note: `git status` in `WhisperLiveKit` shows pre-existing/concurrent edits
(`_work/sa-spike/bench_cer.py`, `whisperlivekit/asr_apple_speech.py`, …) that
predate this run — no file there was touched by me.

---

## 2. Verification

### 2.1 `swiftc` builds the shim; console script emits a valid `hello` as the first stdout line

```
$ cd /Users/clkao/git/asr/apple-asr && export APPLE_ASR_CACHE=/Users/clkao/git/asr/apple-asr/.cache
$ /tmp/apple-asr-venv/bin/python -m apple_asr.build --force
building shim: /usr/bin/swiftc -O -parse-as-library /Users/clkao/git/asr/apple-asr/src/apple_asr/shim/speechanalyzer.swift -o /Users/clkao/git/asr/apple-asr/.cache/apple_asr/0.1.0/apple-asr-shim.tmp
shim ready: /Users/clkao/git/asr/apple-asr/.cache/apple_asr/0.1.0/apple-asr-shim
/Users/clkao/git/asr/apple-asr/.cache/apple_asr/0.1.0/apple-asr-shim

$ /tmp/apple-asr-venv/bin/apple-asr-shim --stdin < /dev/null | head -1
{"preset":"progressive","capabilities":["volatile","word_runs","pause_commit","flush","context"],"shim_version":"0.1.0","type":"hello","protocol":1,"locale":"en-US","reporting_options":["volatileResults","fastResults"],"format":{"channels":1,"common_format":"int16","sample_rate":16000}}

$ /tmp/apple-asr-venv/bin/apple-asr-shim --stdin < /dev/null > /dev/null 2>/tmp/cli.err; echo "exit=$?"; tail -2 /tmp/cli.err
exit=0
format=16000.0Hz 1ch int16 vad=off preset=progressive fast=true
done
```

Raw cached binary, stdin closed (exit 0), first three stdout lines:

```
$ /tmp/apple-asr-venv/bin/apple-asr-shim --stdin < /dev/null 2>/dev/null | head -3
{"type":"hello","protocol":1,"shim_version":"0.1.0","locale":"en-US","preset":"progressive","format":{"channels":1,"common_format":"int16","sample_rate":16000},"capabilities":["volatile","word_runs","pause_commit","flush","context"],"reporting_options":["volatileResults","fastResults"]}
{"type":"commit","through":0,"reason":"eof","wall":0.11583292484283447}
{"type":"ended","reason":"eof"}
```

Build repeats are cache hits (validated by re-reading `hello`, not by mtime), and
`--force` rebuilds. A stale/broken cache entry is rebuilt (the validation is the
acceptance test).

### 2.2 End-to-end: `_work/zh_long.wav` pushed as float32 16 kHz

Script: `/tmp/aasr/e2e.py` (full text in appendix A).

```
$ cd /Users/clkao/git/asr/apple-asr && export APPLE_ASR_CACHE=/Users/clkao/git/asr/apple-asr/.cache
$ /tmp/apple-asr-venv/bin/python /tmp/aasr/e2e.py
# wav=/Users/clkao/git/asr/_work/zh_long.wav 31.55s sr=16000 ch=1
# hello: {'protocol': 1, 'shim_version': '0.1.0', 'locale': 'zh-TW', 'preset': 'progressive',
          'format': {'sample_rate': 16000, 'channels': 1, 'common_format': 'int16'},
          'capabilities': ['volatile', 'word_runs', 'pause_commit', 'flush', 'context']}
# pushed 31.55s in 0.09s
# after push: 126 partials, 1 finals, audio_time=31.55
# flush -> commits += 1
# finals with reason=flush: 0
# tail types: ['Partial', 'Partial', 'Partial', 'Partial', 'Final', 'Ended']
# TOTAL 133 events: 130 partials, 2 finals, 2 finals with words
  FINAL[pause] 0.00-19.20 words=78 '我們今天來討論鐳射在醫學上的應用雷射技術可以精確地切除腫瘤組織減少對週圍健康組織的傷害在眼科手術中雷射用來矯正視力治療近'
  FINAL[eof] 19.20-31.55 words=51 '減少出血汗疼痛皮膚科用雷射去除斑點汗紋身總之雷射在現代醫學中扮演著越來越重要的角色未來的應用將更加廣泛'
  first final words: [('我', 0.0, 0.24), ('們', 0.24, 0.36), ('今', 0.36, 0.54), ('天', 0.54, 0.72), ('來', 0.72, 1.02), ('討', 1.02, 1.2), ('論', 1.2, 1.38), ('鐳', 1.38, 1.68)]
# stats: Stats(partials=130, finals=2, words=259, dropped=0, bytes=2019320)
# ASSERTIONS OK  finals=2 partials=130 reasons=['eof', 'pause'] ended_reason=closed
$ echo $?
0
```

Asserts (all in the script): ≥1 `Final`; ≥1 `Final` carrying words (259 word runs total);
well-formed ranges; **final ranges never overlap and only advance**; word runs ordered and
inside their final; partials over one range only grow; `flush()` produced **exactly one**
commit acknowledgement (`commits += 1`); `close()` produced `Ended` (`reason='closed'`).

`flush()` produced no additional *final* here (the transcriber had nothing pending after the
pause commit) — §9 test 4's "finals carry reason='flush'" is a fake-shim (order 2) property;
the flush acknowledgement itself is verified by the commit count. The pause-mode run below
does show a real `FINAL[flush]`.

### 2.3 Pause mode: `pause_start`/`pause_end` → commit lands ≤0.3 s after the pause starts

Script: `/tmp/aasr/pause_mode.py` (pattern copied from `_work/sa-spike/drive_live.py`; full text in appendix B).

```
$ /tmp/apple-asr-venv/bin/python /tmp/aasr/pause_mode.py
# /Users/clkao/git/asr/_work/zh_long.wav 31.6s; 11 pauses
  [  3.63s] --- PAUSE 0.22s at 3.51s -> FINAL[pause] landed +0.119s  range 0.00-3.25 words=16
  [  7.63s] --- PAUSE 0.28s at 7.50s -> FINAL[pause] landed +0.136s  range 3.25-6.87 words=15
  [ 10.77s] --- PAUSE 0.24s at 10.62s -> FINAL[pause] landed +0.147s  range 6.90-9.90 words=12
  [ 12.54s] --- PAUSE 0.28s at 12.44s -> FINAL[pause] landed +0.108s  range 9.94-11.59 words=6
  [ 14.72s] --- PAUSE 0.28s at 14.62s -> FINAL[pause] landed +0.103s  range 11.62-13.67 words=8
  [ 16.81s] --- PAUSE 0.22s at 16.69s -> FINAL[pause] landed +0.120s  range 13.70-15.65 words=7
  [ 20.36s] --- PAUSE 0.28s at 20.26s -> FINAL[pause] landed +0.104s  range 15.65-18.97 words=14
  [ 22.51s] --- PAUSE 0.22s at 22.42s -> FINAL[pause] landed +0.091s  range 18.97-20.95 words=8
  [ 25.91s] --- PAUSE 0.24s at 25.79s -> FINAL[pause] landed +0.118s  range 20.95-24.12 words=14
  [ 26.80s] --- PAUSE 0.28s at 26.68s -> FINAL[pause] landed +0.119s  range 24.16-24.96 words=2
  [ 31.08s] --- PAUSE 0.28s at 31.04s -> FINAL[pause] landed +0.047s  range 24.99-29.14 words=20
# tail: ['Partial', 'Partial', 'Final', 'Ended']
# stats: Stats(partials=132, finals=12, words=264, dropped=0, bytes=2034040)
# pause->Final latencies: [0.119, 0.136, 0.147, 0.108, 0.103, 0.12, 0.104, 0.091, 0.118, 0.119, 0.047]
# final ranges contiguous: [(0.0, 3.25), (3.25, 6.87), (6.9, 9.9), (9.94, 11.59), (11.62, 13.67), (13.7, 15.65), (15.65, 18.97), (18.97, 20.95), (20.95, 24.12), (24.16, 24.96), (24.99, 29.14)]
# OK: max latency 0.147s <= 0.30s
$ echo $?
0
```

11/11 pauses committed **during** the pause; max latency 0.147 s. Every final carries word
runs; final ranges are contiguous and non-negative. A `FINAL[flush]` also appeared in the
preceding run of the same script (e.g. `FINAL[flush] (flush) 29.17-31.52`), confirming
`Final.reason` propagation from the `commit` acknowledgement for the flush path.

The silence-pump finding is load-bearing and is recorded in the code comments: writing only a
pre-roll at `pause_start()` does **not** make the shim publish the final (the transcriber
needs continued input), so the measured latency then was ~1.2 s+ and the final only landed at
resume. Delivering silence at the audio rate while the pause is open (the reference driver's
`_silence_pump` mechanism) is what makes the commit land in ~0.05–0.2 s.

### 2.4 Failure paths

Script: `/tmp/aasr/failpaths.py`; fake shims in `/tmp/aasr/fake/`.

```
$ /tmp/apple-asr-venv/bin/python /tmp/aasr/failpaths.py
# ProtocolMismatch OK: shim protocol 999 != client protocol 1; rebuild the shim: python -m apple_asr.build --force
# BackendError OK: shim exited with status 3 while the session was open; stderr tail:
crash.py: exploding mid-session
crash.py: boom traceback tail
# stderr tail carried OK
# DONE
$ echo $?
0
```

- Protocol-mismatch shim (`protocol: 999`) → `ProtocolMismatch` naming **both** versions.
- A shim that exits 3 mid-session → `BackendError` whose message carries the **stderr tail**.
- Also verified: malformed/unknown lines are warnings, not crashes (`misc.py`, §2.6);
  a format-field mismatch raises `BackendError`; a silent shim currently raises nothing
  (see deviation D7).

### 2.5 `ruff check .` clean; fresh venv install; console script runs

```
$ cd /Users/clkao/git/asr/apple-asr && /tmp/apple-asr-venv/bin/ruff check .
All checks passed!

$ rm -rf /tmp/aasr/venv313 && uv venv --python 3.13 /tmp/aasr/venv313
$ VIRTUAL_ENV=/tmp/aasr/venv313 uv pip install -e .
Installed 2 packages in 30ms
 + apple-asr==0.1.0 (from file:///Users/clkao/git/asr/apple-asr)
 + numpy==2.5.3

$ /tmp/aasr/venv313/bin/apple-asr-shim --stdin < /dev/null 2>/dev/null | head -1
{"shim_version":"0.1.0","format":{"channels":1,"sample_rate":16000,"common_format":"int16"},"protocol":1,"capabilities":["volatile","word_runs","pause_commit","flush","context"],"preset":"progressive","reporting_options":["volatileResults","fastResults"],"type":"hello","locale":"en-US"}
$ echo $?
0

$ /tmp/aasr/venv310/bin/python -c "import apple_asr, sys; print(sys.version.split()[0], apple_asr.__version__)"
3.10.19 0.1.0
```

`py3.10` import verified in a separate venv (the `>=3.10` floor). Wheel build check
(`uv build --wheel`) contains the Swift source and the entry point:

```
apple_asr/__init__.py … apple_asr/transport.py
apple_asr/shim/speechanalyzer.swift
apple_asr-0.1.0.dist-info/entry_points.txt
```

Resolution order (§6) spot checks:

```
# step 4: a real binary on PATH (cache empty)
$ APPLE_ASR_CACHE=/tmp/aasr/emptycache PATH=/tmp/aasr/pathbin:$PATH python -c "from apple_asr import shim_info; print(shim_info())"
ShimInfo(path='/private/tmp/aasr/pathbin/apple-asr-shim', version='0.1.0', protocol=1, build='2026-09-22T21:50:54+00:00')

# step 5: only this package's own console script on PATH -> skipped, build-on-demand fires
$ APPLE_ASR_CACHE=/tmp/aasr/freshcache PATH=/tmp/apple-asr-venv/bin:/usr/bin:/bin python -c "from apple_asr import shim_info; print(shim_info())"
building shim: /usr/bin/swiftc -O -parse-as-library … -o /tmp/aasr/freshcache/apple_asr/0.1.0/apple-asr-shim.tmp
ShimInfo(path='/tmp/aasr/freshcache/apple_asr/0.1.0/apple-asr-shim', version='0.1.0', protocol=1, build='2026-09-22T21:51:00+00:00')

$ python -c "... list_locales() ..."
# supported: 30 installed: 12
# zh-TW supported: True  installed: True
# en-US installed: True
$ python -c "... ensure_installed('zh-TW') ..."
# ensure_installed(zh-TW): OK
```

### 2.6 Extra checks (transport semantics beyond the required list)

`/tmp/aasr/misc.py`:

```
# burst: got 4 events, dropped=172, warnings=1
# warning text: event queue full; dropping oldest events (raise queue_size to keep up)
# backpressure OK
# events() iterator: 185 events, last is Ended
# events() OK
# mixing guard OK: Stream consumers must not be mixed: already iterating via 'poll', now 'events'
# aevents(): 197 events
# aevents() OK
```

`/tmp/aasr/cmd_channel.py` (every fd-3 command against the real shim):

```
# hello capabilities: ('context', 'flush', 'pause_commit', 'volatile', 'word_runs')
# events after commands: ['Partial', 'Partial', 'Partial', 'Final']
# finalize commits: 1
# ended: ['Ended'] stats: Stats(partials=3, finals=1, words=4, dropped=0, bytes=80000)
# ALL FD-3 COMMANDS OK
```

`--file` mode kept intact (and now carries word runs + confidence):

```
$ apple-asr-shim --locale zh-TW --file /Users/clkao/git/asr/_work/zh_long.wav
counts: {'hello': 1, 'partial': 131, 'final': 2, 'ended': 1}
final range [0, 25.2] runs 100 reason eof
  first runs: [['我', 0, 0.24, 0.999], ['們', 0.24, 0.36, 0.999], ['今', 0.36, 0.54, 1]]
final range [25.2, 31.551875] runs 29 reason eof
```

`--mic` is unchanged code and untested here (the sandbox has no mic TCC); it needs
CL's Terminal.app.

---

## 3. Spec deviations and interpretation notes

1. **Internal shim flags beyond §4's list.** `--list-locales`, `--ensure-installed <locale>`
   (needed to implement §3.1's `list_locales`/`ensure_installed`) and `--no-confidence`
   (needed for `Stream(confidence=False)`). By default `.audioTimeRange` **and**
   `.transcriptionConfidence` are inserted into the preset's `attributeOptions`; without that,
   results carry no per-run timings at all (verified: `--fast` alone produced 0 word runs).
2. **Wire extension: optional 4th element in `runs`.** With confidence requested the shim emits
   `[word, start, end, confidence]`; the client accepts both 3- and 4-element runs
   (`Word.confidence` is `None` for the 3-element form). §5's example shows 3 elements.
3. **`Ended.reason` includes `"eof"`.** §3.3's Literal lists only `closed|shim_exit|protocol_error`
   but §9 test 5 requires `reason="eof"` for stdin EOF; `eof` is added to the type.
4. **`flush()` blocks** until its `commit` acknowledgement arrives (bounded, 15 s, else
   `BackendError`). The spec only says each `finalize` produces exactly one `commit`;
   blocking makes `flush()` a usable barrier and the acknowledgement checkable.
5. **Session clock = caller-reported time; drift term implemented, not clamped.**
   `session = push durations + pause_end(d)`; shim clock = frames written; `map(t) = t + drift`,
   floored at 0. Over-delivered silence is absorbed into the drift (reference behaviour).
   Because drift can shift by a few ms mid-pause, the transport additionally **enforces
   final-range contiguity** (`Final.start` is clamped to the previous final's `end`), which is
   the only way to keep §3.3's "finals never overlap" invariant exactly true in
   synthesized-pause mode. A global monotonic clamp was tried and reverted: it wrongly pins a
   late-arriving final (whose range covers earlier audio) to the newest partial's end. This is
   what produced the first bogus `range [31.55, 31.55]` result and was fixed.
6. **Pause silence is delivered at 0.8× the audio rate** while a pause is open, plus a 0.10 s
   pre-roll at onset, topped up at `pause_end(d)` so the synthesized silence for a pause totals
   exactly `d` for a well-behaved caller. §3.2 says "at the audio rate"; under 1.0 was chosen so
   the top-up is exact and over-delivery (which shifts the drift and would let consecutive final
   ranges overlap) cannot occur. A caller that keeps the pause open longer than the reported `d`
   adds that excess silence to the timeline — documented in `Stream`.
7. **Silent-backend guard (§9 test 6) NOT implemented.** It is part of order 2's test bar, and
   a naive wall-clock guard would false-fire on the legitimate offline/burst feed (the
   transcriber can legitimately be silent for seconds while it chews a fast-fed burst). Marked
   as an order-2 design item, not silently skipped.
8. **`prepare()` is fire-and-forget.** The protocol defines no ack for `prepare`; the shim also
   warms at startup (`prepareToAnalyze`), so `Stream.prepare()` sends `{"cmd":"prepare"}`
   without waiting.
9. **Live `context` update exists on the wire but is not in the public API.** §3 lists no
   setter; `{"cmd":"context"}` is implemented in the shim and reachable through the transport,
   and construction-time context goes through `--context`.
10. **Console script is a resolver, not the binary.** `apple-asr-shim` (the console script)
    resolves/builds and `execv`s the native shim; the PATH resolution step skips this package's
    own console script to avoid recursion (verified).
11. **`shim_info().build` = binary mtime (ISO-8601 UTC)**; the spec does not define the field.
12. **`stats.dropped` warning is emitted once per Stream**, per §9's "one warning".
13. **Measured defaults preserved** as required: `pause_commit 0.08`, `commit_interval 0.0`
    (pause-only), `preset "progressive"`, `locale "en-US"` default. Nothing was "improved".

---

## 4. Open questions (for the captain / order 2)

1. §12 decisions still open: package name/home/license (used `apple-asr`, MIT, standalone repo),
   prebuilt wheels vs build-on-demand, whether order 3 (the WLK adapter) happens at all.
2. Keep the 4-element `runs` confidence extension, or move confidence to a separate field /
   drop it from the wire?
3. Silent-backend guard design for order 2: what is the right "no output after N seconds of
   audio" signal given fast-fed bursts are legitimate? (Suggest: wall-clock since the last
   shim event *while audio is being fed slower than real time*, plus an explicit
   `silent_timeout` knob.)
4. `--fast` remains a no-op flag in the shim (it was already a no-op in the spike; §4 lists it,
   so it is accepted for compatibility). Worth documenting or removing in order 2?
5. Should `apple-asr-shim --help` bypass build-on-demand (currently it resolves/builds first,
   so `--help` on a machine without a shim builds one)? Cheap to special-case.

---

## Appendix A — `/tmp/aasr/e2e.py`

```python
import os, sys, time, wave
os.environ["APPLE_ASR_CACHE"] = "/Users/clkao/git/asr/apple-asr/.cache"
import numpy as np
from apple_asr import Stream, Partial, Final, Ended, Error

path = "/Users/clkao/git/asr/_work/zh_long.wav"
with wave.open(path) as w:
    sr, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
print(f"# wav={path} {len(audio)/sr:.2f}s sr={sr} ch={ch}")

events = []
with Stream(locale="zh-TW", preset="progressive") as st:
    h = st._transport.hello
    print("# hello:", {k: h.get(k) for k in ("protocol","shim_version","locale","preset","format","capabilities")})
    st.prepare()
    step = int(0.5 * sr)
    t0 = time.monotonic()
    for i in range(0, len(audio), step):
        st.push(audio[i:i+step])
    print(f"# pushed {len(audio)/sr:.2f}s in {time.monotonic()-t0:.2f}s")

    idle = 0
    while idle < 4:
        got = st.poll(0.5)
        if got:
            events.extend(got); idle = 0
        else:
            idle += 1
    n_part = sum(isinstance(e, Partial) for e in events)
    n_fin = sum(isinstance(e, Final) for e in events)
    print(f"# after push: {n_part} partials, {n_fin} finals, audio_time={st.audio_time:.2f}")

    c0 = st._transport.commit_count()
    st.flush()
    c1 = st._transport.commit_count()
    print(f"# flush -> commits += {c1-c0}")
    time.sleep(0.5)
    events.extend(st.poll(1.0))
    n_fin_flush = sum(isinstance(e, Final) and e.reason == "flush" for e in events)
    print(f"# finals with reason=flush: {n_fin_flush}")

    st.close()
    tail = st.poll(3.0)
    events.extend(tail)
    print("# tail types:", [type(e).__name__ for e in tail])

finals = [e for e in events if isinstance(e, Final)]
with_words = [f for f in finals if f.words]
print(f"# TOTAL {len(events)} events: {sum(isinstance(e,Partial) for e in events)} partials, {len(finals)} finals, {len(with_words)} finals with words")
for f in finals[:6]:
    print(f"  FINAL[{f.reason}] {f.start:.2f}-{f.end:.2f} words={len(f.words)} {f.text[:60]!r}")
if finals:
    f = finals[0]
    print("  first final words:", [(w.text, round(w.start,2), round(w.end,2)) for w in f.words[:8]])
print("# stats:", st.stats)

# --- assertions ---
def check(evs):
    fins = [e for e in evs if isinstance(e, Final)]
    parts = [e for e in evs if isinstance(e, Partial)]
    # 1) every range is well-formed
    for e in evs:
        if isinstance(e, (Partial, Final)):
            if e.start is not None and e.end is not None:
                assert e.start <= e.end + 1e-9, f"bad range {e}"
        for w in getattr(e, "words", ()):
            assert w.start <= w.end + 1e-9, f"bad word range {w}"
            assert w.confidence is None or 0.0 <= w.confidence <= 1.0, f"bad confidence {w}"
    # 2) final ranges never overlap and only advance
    for a, b in zip(fins, fins[1:]):
        assert a.end <= b.start + 1e-6, f"final overlap {a.end} > {b.start}"
    # 3) words inside a final are ordered and inside its range
    for f in fins:
        ws = [w for w in f.words]
        for a, b in zip(ws, ws[1:]):
            assert a.end <= b.start + 1e-6, f"word order {a} {b}"
        if ws:
            assert ws[0].start >= f.start - 0.5 and ws[-1].end <= f.end + 0.5, f"words outside final {f}"
    # 4) partials over one range only grow (later supersedes, never shrinks)
    by_start = {}
    for p_ in parts:
        by_start.setdefault(None if p_.start is None else round(p_.start, 1), []).append(p_)
    for _, ps in by_start.items():
        for a, b in zip(ps, ps[1:]):
            assert (b.end or 0) >= (a.end or 0) - 1e-6, f"partial shrank {a.end} -> {b.end}"
    return fins, parts

fins, parts = check(events)
assert len(fins) >= 1, "no Final"
assert any(f.words for f in fins), "no Final carrying words"
assert any(isinstance(e, Ended) for e in events), "no Ended"
ended = [e for e in events if isinstance(e, Ended)][-1]
print(f"# ASSERTIONS OK  finals={len(fins)} partials={len(parts)} "
      f"reasons={sorted({f.reason for f in fins})} ended_reason={ended.reason}")
```

## Appendix B — `/tmp/aasr/pause_mode.py`

Full text preserved at `/tmp/aasr/pause_mode.py` for the duration of this session; the script
is the reference `_work/sa-spike/drive_live.py` pattern with `proc.insert_audio_chunk` →
`Stream.push`, `proc.start_silence()` → `Stream.pause_start()`, and
`proc.end_silence(d, 0)` → `Stream.pause_end(d)`, plus the latency/contiguity assertions
printed in §2.3. Key structure:

```python
for kind, s, e in spans:
    if kind == "speech":
        # push 0.1 s chunks with real-time pacing, poll(0.0) after each
    else:
        t_pause = time.monotonic(); st.pause_start()
        while time.monotonic() - t_pause < (e - s):   # observe the commit during the pause
            for ev in st.poll(0.02):
                if isinstance(ev, Final) and landed is None:
                    landed = time.monotonic() - t_pause   # <- the measured latency
        st.pause_end(e - s)
```

## Appendix C — spec confirmation list (§3–§8, as implemented)

- §3.1 module surface: `Stream, Partial, Final, Word, Ended, Error, list_locales,
  ensure_installed, shim_info, PROTOCOL_VERSION` + the seven exceptions — all exported
  (`__all__` printed in §2.5).
- §3.2: `locale/preset/context/pause_commit/commit_interval/confidence/shim/stderr/queue_size`
  ctor; `prepare/close/__enter__/__exit__/push/pause_start/pause_end/flush/audio_time/
  events/aevents/poll/stats`; int16 accepted (clamp-and-scale); mixing assert present.
- §3.3: frozen dataclasses; `Final.reason` propagated from the `commit` acknowledgement;
  timestamps seconds, monotonic, session clock from 0.
- §4: all three modes; `--stdin` is the package's mode; nonzero exit → `BackendError` + tail.
- §5: hello first, protocol/format refusal, `partial/final/commit/error/ended`, fd-3
  `prepare/finalize/context/close`, unknown types warned not crashed.
- §6: resolution order 1→6 all implemented, cache keyed by `shim_version`, source shipped,
  binary not committed, `python -m apple_asr.build` compiles+validates+prints the path.
- §7: capability table honoured (including `finalize(through:)`, `AssetInventory`,
  `contextualStrings`; `SpeechDetector` exposed but inert; module composition/CMTime not exposed).
- §8: `UnsupportedPlatform` on non-darwin/older; every message names the fix command.

---

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "New repo /Users/clkao/git/asr/apple-asr only (git ls-files: 16 files; 1 commit 3901c94; clean tree). No file under WhisperLiveKit was written except this report. No tests/replay/CER tools created; no test suite docs beyond inline docstrings."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Every required verification item was executed and its observed output is pasted in sections 2.1-2.6 (swiftc build + hello first line; e2e zh_long.wav with word runs/commit-count/Ended; pause-mode 11/11 finals <=0.147s; ProtocolMismatch naming both versions; BackendError with stderr tail; ruff clean; fresh-venv install + console script)."
    }
  ],
  "changedFiles": [
    "apple-asr/.github/workflows/ci.yml",
    "apple-asr/.gitignore",
    "apple-asr/LICENSE",
    "apple-asr/README.md",
    "apple-asr/pyproject.toml",
    "apple-asr/src/apple_asr/__init__.py",
    "apple-asr/src/apple_asr/build.py",
    "apple-asr/src/apple_asr/cli.py",
    "apple-asr/src/apple_asr/errors.py",
    "apple-asr/src/apple_asr/events.py",
    "apple-asr/src/apple_asr/platform.py",
    "apple-asr/src/apple_asr/protocol.py",
    "apple-asr/src/apple_asr/shim.py",
    "apple-asr/src/apple_asr/shim/speechanalyzer.swift",
    "apple-asr/src/apple_asr/stream.py",
    "apple-asr/src/apple_asr/transport.py",
    "WhisperLiveKit/_work/apple-asr-package/ORDER1-REPORT.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {"command": "/tmp/apple-asr-venv/bin/python -m apple_asr.build --force", "result": "passed", "summary": "swiftc -O -parse-as-library compiled the shim; hello validated; path printed"},
    {"command": "/tmp/apple-asr-venv/bin/apple-asr-shim --stdin < /dev/null | head -1", "result": "passed", "summary": "valid hello is the first stdout line; exit 0"},
    {"command": "/tmp/apple-asr-venv/bin/python /tmp/aasr/e2e.py", "result": "passed", "summary": "133 events, 2 finals with 78+51 word runs, flush commits += 1, Ended(closed), ranges monotone/non-overlapping"},
    {"command": "/tmp/apple-asr-venv/bin/python /tmp/aasr/pause_mode.py", "result": "passed", "summary": "11/11 pause-committed finals, max latency 0.147s <= 0.30s, contiguous final ranges"},
    {"command": "/tmp/apple-asr-venv/bin/python /tmp/aasr/failpaths.py", "result": "passed", "summary": "ProtocolMismatch names 999 vs 1; BackendError(status 3) carries stderr tail"},
    {"command": "/tmp/apple-asr-venv/bin/python /tmp/aasr/misc.py", "result": "passed", "summary": "drop-oldest backpressure (dropped=172, 1 warning), events()/aevents()/mixing guard all OK"},
    {"command": "/tmp/apple-asr-venv/bin/python /tmp/aasr/cmd_channel.py", "result": "passed", "summary": "fd-3 prepare/context/finalize/close all work against the real shim"},
    {"command": "/tmp/apple-asr-venv/bin/ruff check .", "result": "passed", "summary": "All checks passed!"},
    {"command": "uv venv --python 3.13 + uv pip install -e .", "result": "passed", "summary": "fresh venv installs; console script emits hello"},
    {"command": "uv venv --python 3.10 + import apple_asr", "result": "passed", "summary": "py3.10.19 imports the package"},
    {"command": "uv build --wheel", "result": "passed", "summary": "wheel contains apple_asr/shim/speechanalyzer.swift and the apple-asr-shim entry point"},
    {"command": "apple-asr-shim --locale zh-TW --file _work/zh_long.wav", "result": "passed", "summary": "--file mode intact: 2 finals, 100+29 word runs with confidence, reason eof"}
  ],
  "validationOutput": [
    "hello: {\"type\":\"hello\",\"protocol\":1,\"shim_version\":\"0.1.0\",\"locale\":\"en-US\",\"preset\":\"progressive\",\"format\":{\"sample_rate\":16000,\"channels\":1,\"common_format\":\"int16\"},\"capabilities\":[\"volatile\",\"word_runs\",\"pause_commit\",\"flush\",\"context\"],\"reporting_options\":[\"volatileResults\",\"fastResults\"]}",
    "e2e: TOTAL 133 events: 130 partials, 2 finals, 2 finals with words; stats Stats(partials=130, finals=2, words=259, dropped=0, bytes=2019320); ASSERTIONS OK reasons=['eof','pause'] ended_reason=closed",
    "pause: latencies [0.119,0.136,0.147,0.108,0.103,0.12,0.104,0.091,0.118,0.119,0.047]; max 0.147s <= 0.30s; finals contiguous",
    "failure: ProtocolMismatch('shim protocol 999 != client protocol 1; rebuild the shim: python -m apple_asr.build --force'); BackendError('shim exited with status 3 while the session was open; stderr tail:\\ncrash.py: exploding mid-session\\ncrash.py: boom traceback tail')",
    "ruff: All checks passed!"
  ],
  "residualRisks": [
    "Silent-backend guard (SPEC §9 test 6) is not implemented in order 1; deferred with an explicit note (naive wall-clock guards false-fire on legitimate fast-fed bursts).",
    "Final-range contiguity is enforced client-side by clamping Final.start to the previous final's end (few-ms drift shifts from synthesized pause silence); this satisfies §3.3 'finals never overlap' but means a final's start can be nudged by up to one pump tick.",
    "Pause synthesis delivers silence at 0.8x the audio rate + exact top-up; a caller that keeps a pause open longer than its reported d adds that excess to the timeline (documented in Stream).",
    "Wire extension: runs entries may carry a 4th (confidence) element; §5 shows 3. Client accepts both.",
    "~/.cache/apple_asr is not creatable from the agent-safehouse, so all runs used APPLE_ASR_CACHE; the spec default path is untested here (it is a plain mkdir on a normal machine).",
    "--mic mode is unchanged code but untested (no mic TCC in the sandbox).",
    "WhisperLiveKit git status shows pre-existing/concurrent edits (bench_cer.py, asr_apple_speech.py) not made by this order."
  ],
  "noStagedFiles": true,
  "diffSummary": "New standalone MIT repo apple-asr: hatchling packaging (numpy-only runtime, console script apple-asr-shim), Swift shim extended from the spike with hello/commit/error/ended + fd-3 command channel + attributeOptions word/confidence runs, python package implementing the §3 API over the §5 transport (subprocess mgr, reader thread, bounded drop-oldest queue, commit acks, session-clock drift mapping), §6 resolution/build helper, §8 platform gating, README and CI placeholder.",
  "reviewFindings": [
    "no blockers"
  ],
  "manualNotes": "The load-bearing discovery: a pre-roll alone at pause_start() does NOT make the transcriber publish the final (latency was >1.2s and the final only landed at resume); the reference's silence-pump mechanism is required, now implemented, and pause commits land in 0.05-0.15s. A global monotonic clamp in the clock mapping was tried and reverted (it pinned late-arriving finals with earlier ranges to the newest partial's end, producing bogus range [31.55, 31.55]); contiguity is instead enforced on finals only. Also fixed: the shim crashed with an uncaught NSFileHandleOperationException on EPIPE (now a POSIX write loop), and one finalize can drain several finals so the shim's final reason is sticky rather than consumed."
}
```
