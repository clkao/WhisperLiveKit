# Order 3 — apple-speech adapter report (WhisperLiveKit → `apple-asr` package)

Status: implemented, verified on this machine (macOS 26.6.2, sandbox), not pushed.

## 1. Branch and commits

Branch `wlk/apple-speech-adapter`, cut from `wlk/integration-2` @ `9d366f9`.

```
9ac8960 chore(asr): one shim source, in one repo — drop the in-tree Swift copy
128f4c0 refactor(asr): register apple-speech from the package's own config and gates
9456417 feat(asr): apple-speech delegates to the apple-asr package
9d366f9 bench: engine/preset passthrough in the CER harness (prior-art engine + mode A/B)
```

Nothing pushed; no PR; no public repo created. The package was installed read-only
(`uv pip install -e /Users/clkao/git/asr/apple-asr`, version 0.1.1 @ `a994b5d`) and its
repo was not modified (`git -C ../apple-asr status` clean).

## 2. Files added / changed / deleted

Added
| file | lines |
|---|---|
| `tests/test_apple_speech_adapter.py` | 269 (new) |

Changed
| file | +/- | what |
|---|---|---|
| `whisperlivekit/asr_apple_speech.py` | 434 → 227 lines (net −177) | rewritten as a thin adapter over `apple_asr.Stream`; no protocol, no timing |
| `whisperlivekit/config.py` | +33/−8 | `apple_speech_mode` replaces `apple_speech_preset`, `apple_speech_spike` dropped, `APPLE_SPEECH_LANGUAGES` / `APPLE_SPEECH_MODES` + FUNASR-style validation |
| `whisperlivekit/core.py` | +20/−4 | Models factory builds the adapter from config; `online_factory` rejects a session language ≠ configured locale; processor name unchanged |
| `whisperlivekit/parse_args.py` | +15/−11 | `--apple-speech-locale`, `--apple-speech-mode` (preset/spike args removed) |
| `whisperlivekit/backend_support.py` | +46 | `apple_speech_backend_available()`, `require_apple_speech_backend()` — delegate to the package's platform/shim gates |
| `whisperlivekit/benchmark/compat.py` | +10/−2 | `BACKEND_LANGUAGES["apple-speech"]` + availability probe |
| `pyproject.toml` | +10 | `[apple-speech]` extra |
| `scripts/lc_terminal.py` | +8/−4 | `--apple-speech-mode` in `_make_engine_kwargs` + banner |

Deleted
| file | lines |
|---|---|
| `_work/sa-spike/spike_speechanalyzer.swift` | 432 (the forked in-tree shim, committed in `6b2112a`) |
| `_work/sa-spike/README.md` | 30 (its build-inside-the-WLK-checkout instructions) |

Kept: `_work/sa-spike/bench_cer.py`, `_work/sa-spike/drive_live.py` (evidence instruments;
`drive_live.py` drives the new adapter unchanged), and the untracked local `sa-spike` binary
(`bench_cer.py --spike` still accepts it; it is the only file-mode shim on this disk).

`git diff --stat 9d366f9..HEAD` → 11 files, 557 insertions, 753 deletions. `git diff --cached`
is empty (nothing staged).

## 3. Verification

### 3.1 Cadence through the ADAPTER vs the golden fixture — the key acceptance

```
$ export APPLE_ASR_CACHE=/tmp/apple_asr_cache   # ~/.cache is not writable in the sandbox
$ .venv/bin/python scripts/lc_terminal.py --backend apple-speech --source file \
    --audio ~/git/asr/_work/zh_long.wav --event-log /tmp/adapter_events.jsonl
[stderr]
OpenCC s2twp on source (auto: source is zh): ASR display -> Taiwan Traditional
ASR: apple-speech (apple-asr package) · zh-TW · streaming
MT: hy-mt2-1.8b-8bit · serial
Simul: available (8 heads, top L9 H5)
VAD: defaults
[shim stderr, inherited]
format=16000.0Hz 1ch int16 vad=off preset=progressive fast=true
control: channel on fd 11
commit[pause]: finalize(through: 3.5s)
commit[pause]: finalize(through: 7.3s)
... 9 more pause commits ...
commit[pause]: finalize(through: 30.35s)
control: close requested
done
[event-log] saved 58 events -> /tmp/adapter_events.jsonl
rc=0
```

Counted from the event log:

| metric | adapter (this run) | `tests/golden/zh_long_ideal.jsonl` | task's expectation |
|---|---|---|---|
| `transcription_final` events | **12** | 12 | 12 |
| first final (`audio_t`) | **3.24 s** | 2.99 s | ≈3.5 s |
| mean gap between finals | **2.675 s** | 2.97 s | ≈2.6 s |
| `translation_final` events | 9 | 9 | — |
| `transcription_provisional` | 37 | 37 | — |

No commits lost, none duplicated: the count matches the golden exactly, and the shim's own
commit trace shows 11 `pause` commits + 1 EOF finalize = 12.

Boundary placement differs slightly from the golden (the golden merges
"在眼科手術中，鐳射用來矯正視力" and ends with one "總之，…" line; this run splits
"在眼科手術中" / "鐳射用來矯正視力" and commits "總之" on its own). Same cadence count, same
phrase scale — this is the real shim's endpointer on this audio, not an adapter mapping
difference (the adapter's tokens come straight from `Final.runs`, asserted token-exactly in
the new test).

Committed source lines from the same run:

```
3.24  我們今天來討論鐳射在醫學上的應用
7.14  鐳射技術可以精確地切除腫瘤組織
10.16 減少對週圍健康組織的傷害
12.01 在眼科手術中
14.28 鐳射用來矯正視力
16.19 治療近視漢遠士          <- ASR mishearing, not an adapter issue
19.63 牙醫也使用鐳射來進行口腔手術
21.90 減少出血汗疼痛。
25.02 皮膚科用鐳射去除斑點和紋身
25.91 總之
30.45 雷射在現代醫學中扮演著越來越重要的角色。
32.67 未來的應用將更加廣泛
```

### 3.2 lc_terminal renders phrase-level committed lines with translations

`/tmp/lc_terminal.out` (stdout of the run above, TuiRenderer frames; the CJK below is mojibake
only when `cat -v`; the file is UTF-8):

```
[18:23:37] 我們今天來討論鐳射在醫學上的應用
We are here today to discuss the applications of lasers in medicine
[18:23:41] 鐳射技術可以精確地切除腫瘤組織
Laser technology can precisely remove tumor tissue
[18:23:47] 減少對週圍健康組織的傷害 在眼科手術中
Reducing damage to surrounding healthy tissues in ophthalmic surgery
[18:23:51] 鐳射用來矯正視力 治療近視漢遠士
Laser is used to correct vision
[18:23:55] 牙醫也使用鐳射來進行口腔手術 減少出血汗疼痛。
To treat myopia, Han Yuan Shi dentists also use laser to perform oral surgeries.
[18:23:59] 皮膚科用鐳射去除斑點和紋身 總之
Skin care with laser removal of spots and tattoos – in short
[18:24:03] 雷射在現代醫學中扮演著越來越重要的角色。
Lasers play an increasingly important role in modern medicine.
[18:24:16] 未來的應用將更加廣泛
Future applications will be more widespread
```

Eight committed source lines, each with its translation — not the one-big-chunk regression.

### 3.3 Tests

```
$ .venv/bin/python -m pytest tests/test_backends.py tests/test_silent_backend_guard.py \
      tests/test_apple_speech_adapter.py -q -p no:cacheprovider
53 passed, 3 warnings in 22.27s
```
(44 pre-existing from the two named files, 9 new; run serially on a loaded machine, no flakes
observed. The new file also passed alone: `9 passed in 7.64s`.)

New test file coverage (all through the package's `tests/fixtures/fake_shim.py`, pointed at via
`APPLE_ASR_CACHE` in a tmp dir — no macOS 26, no Swift, no Speech, no mic):

- `start_silence() returns the pause's final as word tokens` — the load-bearing mapping
  (emulated endpointer; asserts the first commit is collected *inside* the pause window).
- `process_iter maps one token per word run` — scripted scenario; exact
  `(text, start, end)` triples, times on the package session clock, no re-delivery.
- `get_buffer follows the latest partial` (+ the documented nuance that partials reach the
  buffer only after a poll).
- `finish drains the tail` and reports `stream_end`.
- `end_silence advances the stream clock`; `new_speaker` is a no-op returning that cursor.
- `session carries the measured defaults` — `pause_commit == 0.08`, `commit_interval == 0.0` in
  the shim argv, and mode `streaming → preset=progressive/fast` vs `accurate →
  preset=transcription/--no-fast`.
- `sep follows the locale` (zh-TW joins without a space, en-US with one).
- Gates: missing package → `RuntimeError` naming `whisperlivekit[apple-speech]` (asserted *not*
  an ImportError); unsupported host → the package's own `UnsupportedPlatform`.
- Session language ≠ locale → `ValueError` from `online_factory`.

### 3.4 Unsupported-host / missing-package gate

(a) Package uninstalled (`uv pip uninstall apple-asr`, then reinstalled):

```
$ .venv/bin/python scripts/lc_terminal.py --backend apple-speech --source file \
    --audio ~/git/asr/_work/zh_long.wav
  File ".../whisperlivekit/asr_apple_speech.py", line 71, in __init__
    require_apple_speech_backend()
  File ".../whisperlivekit/backend_support.py", line 104, in require_apple_speech_backend
    raise RuntimeError(
RuntimeError: The apple-speech backend needs the `apple-asr` package (macOS 26+):
pip install 'whisperlivekit[apple-speech]'
rc=1
```

(b) Simulated non-macOS-26 host, through the real CLI (`apple_asr.platform.macos_major`
patched to 25; patching `sys.platform` wholesale is not usable here — it makes `soundfile`
try to dlopen `libsndfile.so`):

```
$ .venv/bin/python /tmp/sim_macos25.py     # runpy's scripts/lc_terminal.py, macos_major -> 25
  File ".../apple_asr/platform.py", line 41, in require_supported
apple_asr.errors.UnsupportedPlatform: apple-asr requires macOS 26+ (Apple SpeechAnalyzer);
this system reports macOS 26.6.2.
rc=1
```

Both print the gate's message; neither surfaces an `ImportError`. Gate helpers directly:

```
available on macOS 25: False
UnsupportedPlatform -> apple-asr requires macOS 26+ ...
available without the package: False
RuntimeError -> The apple-speech backend needs the `apple-asr` package (macOS 26+): ...
```

(The "reports macOS 26.6.2" tail is the package's own wording using the real
`platform.mac_ver()`; the simulated major version is what raised.)

### 3.5 Registration smoke checks

```
languages: ['auto','de','en','es','fr','it','ja','ko','pt','yue','zh']  modes: ['accurate','streaming']
ValueError -> Apple SpeechAnalyzer supports only: auto, de, en, es, fr, it, ja, ko, pt, yue, zh.
              Set --language to the locale's language (--apple-speech-locale zh-TW).
ValueError -> apple-speech mode must be one of: accurate, streaming.
ok: zh-TW streaming
compat apple-speech zh: True   cs: False
compat has spike field? False  preset? False
available here: True           detected backends: [... 'voxtral', 'apple-speech']
```
`--apple-speech-locale` / `--apple-speech-mode {streaming,accurate}` appear in
`parse_args()`'s help; `--apple-speech-preset` / `--apple-speech-spike` are gone.

### 3.6 Ruff

```
$ uv run --frozen ruff check whisperlivekit/asr_apple_speech.py whisperlivekit/config.py \
    whisperlivekit/core.py whisperlivekit/parse_args.py whisperlivekit/backend_support.py \
    whisperlivekit/benchmark/compat.py tests/test_apple_speech_adapter.py
All checks passed!

$ uv run --frozen ruff check .            # repo-wide
Found 17 errors.      # all pre-existing, none in a touched file:
                      # _work/capture_attention_golden.py, _work/sa-spike/{analyze,bench_cer,drive_live}.py,
                      # tests/test_voxtral_mlx_compile.py
$ uv run --frozen ruff check scripts/lc_terminal.py    # `scripts` is excluded from the scan
Found 15 errors.      # identical count and rules at 9d366f9 (checked via a worktree of the base commit)
```

## 4. What I could not verify, and why

1. **`uv run ruff check .` (without `--frozen`) no longer resolves in this checkout.** Adding the
   `[apple-speech]` extra makes uv re-lock the whole project, and it fetches the extra's git
   dependency — which does not exist yet:
   ```
   × Failed to download and build `apple-asr @ git+https://github.com/clkao/apple-asr@v0.1.1`
   ╰─▶ remote: Repository not found.
   ```
   This is inherent to "an extra pointing at an unpublished package": any specifier (git URL *or*
   a bare PyPI name) breaks `uv sync` / `uv run` until the package is published. Workarounds used
   here: `uv run --frozen …`, or run `.venv/bin/python` / `.venv/bin/ruff` directly (the backend
   itself only needs the editable install). **Decision needed from CL**: the URL/owner is a guess
   — there is no remote on the `apple-asr` repo and no published home, so I used
   `github.com/clkao/apple-asr@v0.1.1` (matching the WLK fork's namespace) with a TODO saying the
   repo and tag do not exist yet. If the intended home differs, it is a one-line change.
2. **Live mic ja/zh run** (design acceptance item 5) — needs mic TCC, which the sandbox does not
   have. The file path above exercises the same code (`insert_audio_chunk` / `start_silence` /
   `end_silence` / `process_iter`), so the adapter mapping is covered, but the mic + real-VAD
   cadence should still be signed off by CL in Terminal.app:
   ```
   APPLE_ASR_CACHE=~/.cache uv run --extra apple-speech livecaption --source mic \
     --asr-model apple-speech ...    # or: scripts/lc_terminal.py --backend apple-speech --source mic
   ```
3. **`~/.cache/apple_asr` is not writable in this sandbox**, so I built the shim into
   `APPLE_ASR_CACHE=/tmp/apple_asr_cache`. `python -m apple_asr.build` (swiftc present, ~15 s) and
   `apple-asr-shim --list-locales` both work here; on CL's Terminal the default cache works.
4. **The fake shim's endpointer re-arms during a long continuous quiet run** whereas the real
   `PauseCommitter` latches `fired` per quiet run (it only resets on speech). Consequence: the
   emulated scenario emits extra empty-range finals during one pause, so the new test asserts on
   the first commit rather than "exactly one final". Not an adapter bug and not a package bug
   against the real shim; I did not modify the package. Worth a package-side test-double fix
   later (it makes long-pause assertions in `apple-asr`'s own suite weaker than they look).
5. **`uv.lock` is unchanged and now stale** with respect to the new extra: it cannot be
   regenerated until `apple-asr` is fetchable. Whoever publishes it should re-run `uv lock`.
6. `.spacedock/dev/.spacedock-state/speechanalyzer-spike/{spike.md,README.md}` still contain
   "build the shim inside the WLK checkout" lines. Those paths are locally excluded
   (`.git/info/exclude`) and were never committed, so no repo doc points at the deleted shim; I
   left CL's local spike-state archive alone rather than rewriting history notes.
6. `_work/COMPACTION_SURVIVAL.md:89` mentions `_work/sa-spike/ (shim + README)` — untracked
   session notes, stale pointer only, not updated.
7. **`apple-asr`'s own test suite was not run as part of this order** (it was not modified, and
   the package's suite is the package's bar, verified in orders 1-2). The WLK-side adapter is the
   only thing whose behaviour this order changed.

## 5. Design conformance notes

- The adapter is 227 lines (the design estimated ~120): 26 lines of module docstring plus the
  per-path error logging are the difference. It contains **no timing code** — verified:
  `grep -n "preroll|drift|_silence_pump|_stream_time|_frames_written"` finds nothing; the pump,
  pre-roll, drift mapping, and pause-onset collection all live in the package.
- `start_silence()` returns the finals collected in a 0.30 s bounded window (the in-tree
  constant, unchanged) — that is the fix that makes commits land during a pause.
- Measured defaults preserved: `pause_commit=0.08`, `commit_interval=0.0`, `mode="streaming"`
  (asserted through the shim argv in the new test).
- `stderr="inherit"` on `Stream` keeps the shim's commit-decision diagnostics on WLK's stderr,
  matching the prototype it replaces (the package default is `capture`, which would swallow the
  live-latency trace that made this backend debuggable). Explicit and commented in the adapter.
- `apple_asr` is imported lazily (factory-side gate and processor construction only);
  `import whisperlivekit` works with the package uninstalled.
