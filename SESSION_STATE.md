# WhisperLiveKit Apple-Silicon port — session state (NOT durable)

This file captures the state that lives only in this session or the sandbox
venv. The durable artifacts are the code (committed on
`feat/apple-silicon-backends`) and the spacedock workflow (the three task files
in `.spacedock/dev/.spacedock-state/`). Everything below is the resume checklist.

## The one blocker: GitHub auth

The `gh` token is invalid (`gh auth status` fails; `gh api user` returns
"Requires authentication"). The `clkao/WhisperLiveKit` fork does not exist
(404). Nothing can push until CL runs:

```
gh auth login -h github.com
gh repo fork QuentinFuxa/WhisperLiveKit --clone=false   # creates clkao/WhisperLiveKit
```

After the fork exists, push the three things:

```
# 1. the code feature branch (PR target: upstream QuentinFuxa/WhisperLiveKit:main)
cd /Users/clkao/git/asr/WhisperLiveKit
git push fork feat/apple-silicon-backends
gh pr create --repo QuentinFuxa/WhisperLiveKit --head clkao:feat/apple-silicon-backends

# 2. the spacedock spec + state (push to the fork)
cd .spacedock/repo
git push -u origin main
git push -u origin dev-state
```

The remotes are already wired:
- code repo: `origin` = QuentinFuxa/WhisperLiveKit, `fork` = clkao/WhisperLiveKit
- `.spacedock/repo`: `origin` = clkao/WhisperLiveKit

## The working venv (not in git — lives in WhisperLiveKit/.venv)

The `transformers==5.11.0` + `huggingface_hub==1.18.0` + `mlx-lm>=0.31.1` +
`mlx-qwen3-asr>=0.3.5` combo is installed in the sandbox venv but NOT declared in
`pyproject.toml`. The pin is load-bearing:

- `qwen3-asr-causal` pins `transformers==4.57.6` (its `qwen_asr` imports
  `is_offline_mode` from huggingface_hub, removed after 1.18.0).
- `mlx-lm>=0.31.1` wants transformers 5.x.
- transformers 5.15 removed `is_offline_mode` from huggingface_hub, breaking qwen-asr.
- The working combo: transformers 5.11.0 + huggingface_hub 1.18.0 (last hub with
  `is_offline_mode`) coexists with mlx-lm 0.31.3 AND mlx-qwen3-asr 0.3.5.

Action before the PR: add the `mlx-qwen3-asr` and `mlx-lm` extras to
`pyproject.toml` with the right pins. The extras:
```
mlx-qwen3-asr = ["mlx-qwen3-asr>=0.3.5,<0.4"]
hunyuan-mlx = ["mlx-lm>=0.31.1"]
overlay = ["pyobjc-framework-cocoa>=12.2.2", "pyobjc-framework-quartz>=12.2.2"]
```
The transformers/huggingface_hub pin is the cross-cutting part — the PR needs to
document the tested combo or constrain it. The sandbox venv has it; git does not.

## The pyobjc deps (installed, not declared)

`pyobjc-framework-cocoa` and `pyobjc-framework-quartz` are installed in the
sandbox venv for the overlay. They're not in `pyproject.toml`. The `[overlay]`
extra (above) declares them, but `uv sync` from a clean clone won't have them
until the extra lands.

## Known limitations (to fix or document in the PR)

1. **Translation is Tier A (translate-on-close), not streamed mid-utterance.**
   `wants_hypothesis_tail=False`. Translation appears at each utterance
   boundary (silence), not word-by-word. The simultaneous-MT (Tier B:
   CapturedAttention + calibrated heads + commit policy) is a separate task —
   the `hunyuan-mlx-translation-backend` task file's "Out of scope" section.
2. **The ASR live partial still shows rolling-decode repetition mid-utterance**
   until the two-pass text replaces it at the boundary. Display polish, not
   correctness.
3. **`pause_segmentation_seconds` defaults to 5.0 in WLK** — too long; the VAD
   fires short silences (0.1-0.3s). `lc_terminal.py` sets 0.1; the web UI needs
   `--pause-segmentation-seconds 0.1` or the default should change.
4. **The sandbox can't render the overlay window or capture mic.** Run from
   Terminal.app on CL's Mac for `--source mic --overlay`.
5. **No tests.** The PR ships no test suite. The task files' acceptance criteria
   are the validation bar (a fresh-agent review runs them).
6. **`uv.lock` was modified** by the installs. The lockfile in the commit
   reflects the sandbox venv state; a clean `uv sync` may resolve differently
   until the pyproject extras + pins land.

## The three task files (durable, in .spacedock)

- `mlx-qwen3-asr-backend` (id p0) — the ASR backend task
- `hunyuan-mlx-translation-backend` (id bp) — the MT backend task
- `native-overlay-client` (id gz) — the overlay task

All in `backlog`, written in STE, state committed to `dev-state`.

## What was NOT done this session

- The pyproject extras + the transformers/huggingface_hub pin declaration
  (the biggest PR-readiness gap).
- The fork + push (blocked on `gh auth`).
- Tier B simultaneous MT (the `simul_mt.py` port — a separate task).
- The screen-OCR hotword loop (separate; needs the Vision/NaturalLanguage extras).
- Nemotron ASR backend (designed, not built — `/tmp/design_nemotron_wlk_backend.md`).

## Resume commands

```
cd /Users/clkao/git/asr/WhisperLiveKit
# the code is on feat/apple-silicon-backends
git log --oneline -1 feat/apple-silicon-backends

# run it (the venv has the combo installed)
.venv/bin/wlk serve --backend mlx-qwen3-asr --language zh \
  --translation-backend hunyuan-mlx --target-language en

# the spacedock workflow
spacedock status --workflow-dir .spacedock/dev

# the design docs (in /tmp — NOT durable, will be gone after reboot)
ls /tmp/design_nemotron_wlk_backend.md /tmp/design_hunyuan_mlx_wlk_backend.md /tmp/exploration-workflow-proposal.md
```

## Environment notes (verified this session)

- The agent sandbox CAN run mlx/Metal, mlx-lm, mlx-qwen3-asr, and the WLK
  pipeline (GPU is open). It CANNOT render the overlay window or capture mic.
- `~/.cache/huggingface` is read+write from the sandbox; the qwen3-0.6b and
  Hy-MT2-1.8B-8bit models are cached there.
- `uv run` re-syncs from `uv.lock` and can revert manual `uv pip install`
  changes; use `.venv/bin/python` directly to run against the hand-installed
  combo.
