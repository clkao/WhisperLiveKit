# COMPACTION SURVIVAL — WhisperLiveKit Apple-Silicon port (2026-08-25)

Read this first after compaction. Then `SESSION_STATE.md` for the resume checklist.

## Where we are (one paragraph)

Built and committed three WLK backends on `feat/apple-silicon-backends` (4 commits): `asr_mlx_qwen3.py` (pure-MLX Qwen3-ASR), `translation_hunyuan_mlx.py` (in-process Hunyuan-MT via mlx-lm), `overlay.py` + `lc_terminal.py` (native macOS overlay). All work end-to-end zh→en in-process (verified via `wlk serve` + test_client). A detached split-root spacedock workflow is set up at `.spacedock/` (VALID), three tasks filed in backlog, the `mlx-qwen3-asr-backend` task amended to build through a generalized ASR wrapper layer (prove with a second provider) and advanced to `implementation` with a worktree stamped at `.worktrees/spacedock-ensign-mlx-qwen3-asr-backend` (branch `ensign/mlx-qwen3-asr-backend`).

## The immediate next action (the one I missed)

The `mlx-qwen3-asr-backend` task is at `implementation`, worktree stamped, but **`«worker.spawn»` has NOT run** — I stopped at `dispatch build --stamp` and wrongly said "the worker isn't auto-launched." The contract (`first-officer-shared-core.md:31,46` + `pi-first-officer-runtime.md:9`) is explicit: `dispatch build` emits the assignment artifact; the FO's next action is to call `subagent(agent=<artifact.agent>, skill=<artifact.skill>, context="fresh", cwd=<repo root>, task=<built prompt>)`. Do that to launch the ensign. CL corrected me on this; do not repeat the miss.

To resume the dispatch:
```
cd /Users/clkao/git/asr/WhisperLiveKit
spacedock dispatch build --workflow-dir .spacedock/dev --host pi \
  --entity-path "$(realpath .spacedock/dev/.spacedock-state/mlx-qwen3-asr-backend.md)" \
  --stage implementation --checklist-file <checklist> --stamp
# read the artifact's agent/skill fields, then:
subagent(agent=..., skill=..., context="fresh", cwd=<repo>, task=<built prompt>)
subagent_wait({id, nonBlocking: true})  # async wake pattern
```

## The active track CL is steering toward

After I built the generalized-wrapper design + the asr-streaming-explainer, CL asked: **"for our prototype, can we try the dep cleanup (fork `-causal` if needed) + Hy-MT's AlignAtt?"**

Two interpretations of "Hy-MT's AlignAtt":
- **Option A (assumed intent): port livecaption's `simul_mt.py` into WLK as an in-process translation backend** (Tier B simultaneous MT — `CapturedAttention` + calibrated zh→en heads + commit policy, `wants_hypothesis_tail=True`). This is the MLX in-process AlignAtt, the ~1.4s latency win we measured in livecaption. No server, no WebSocket. CONFIRM this is the intent before building.
- Option B: run the actual AlignAtt4LLM `alignatt-mt-server` (CUDA/vLLM) as a sidecar — not viable on Apple Silicon.

The dep cleanup (fork `qwen3-asr-causal`) is independent and worth doing regardless. Verified blockers (just ONE, not two):
- `is_offline_mode` IS available in huggingface_hub 1.18.0 (our combo has it) — NOT a blocker.
- The real blocker: `@check_model_inputs()` decorator in `qwen_asr/core/transformers_backend/modeling_qwen3_asr.py:986` — signature changed in transformers 5.x (`TypeError: check_model_inputs() missing 1 required positional argument: 'func'`). A surgical fork patch (the decorator signature) unblocks `qwen3-streaming` on transformers 5.x.

## Load-bearing facts (do not re-derive)

- **The working dep combo**: `transformers==5.11.0`, `huggingface_hub==1.18.0`, `mlx-lm>=0.31.1` (install with `--no-deps` — its metadata demands transformers 5.x but runs on 5.11.0), `mlx-qwen3-asr>=0.3.5,<0.4`. Coexist on one venv. The `qwen3-asr-causal` transformers 4.57.6 pin is the thing we avoid.
- **`uv run` re-syncs from `uv.lock`** and reverts manual `uv pip install` changes; run via `.venv/bin/python` directly against the hand-installed combo. The pyproject extras + pins are NOT yet declared (the biggest PR-readiness gap, in `SESSION_STATE.md`).
- **The translator contract is the same for all ASR backends**: committed `ASRToken`s via `process_iter`/`start_silence` → `insert_tokens`; unstable tail via `get_buffer()` → `Transcript(text=unstable)` → `HypothesisTail` (when `wants_hypothesis_tail=True`). `qwen3-asr-causal` windowed already emits this; the dep cleanup (not a wiring change) is all it needs.
- **The wrapper layer design** (the amended task): two jobs — Job 1 stable/unstable split (factor `stable_commit.py` from qwen3-asr-causal into WLK core), Job 2 timestamp manufacture (factor from `voxtral_mlx_asr.py`). Five backends today duplicate these (Whisper/LocalAgreement, Voxtral-MLX, Voxtral-HF, Qwen3-causal, mlx-qwen3-asr); only `stable_commit.py` is factored. PR #395 (open) refactors the orchestration *above* `self.transcription`; our wrapper layer is *below* — orthogonal, no conflict.
- **`pause_segmentation_seconds` default 5.0 is too long** — VAD fires short silences (0.1-0.3s); set 0.1 or utterances merge into one growing line. `lc_terminal.py` sets 0.1.
- **`[lat]` stderr spam** in overlay was fixed (gate behind `show_mem`, commit fb5f2ad).
- **Sandbox CAN run mlx/Metal/mlx-lm/mlx-qwen3-asr/WLK pipeline; CANNOT render overlay or capture mic** (use Terminal.app).

## The files that matter

- `SESSION_STATE.md` — resume checklist, the dep-combo pin, known limitations.
- `docs/asr-streaming-explainer.md` — transducer vs encoder-decoder, wrapper simulation, Tier A/B, dep-cleanup lever.
- `docs/design-nemotron-wlk-backend.md`, `docs/design-hunyuan-mlx-wlk-backend.md` — the backend designs.
- `.spacedock/dev/.spacedock-state/mlx-qwen3-asr-backend.md` — the amended task (build through generalized wrapper).
- `.worktrees/spacedock-ensign-mlx-qwen3-asr-backend/` — the worktree (branch `ensign/mlx-qwen3-asr-backend`).
- `livecaption/livecaption/simul_mt.py` — the Tier B simultaneous MT to port (Option A above).
- `_work/SIMUL_MT_CONSOLIDATED.md` (asr workspace) — the simul-MT record + measurements.

## What is NOT done

1. `«worker.spawn»` for the mlx-qwen3-asr task (the immediate next action above).
2. The pyproject extras + transformers/huggingface_hub pin declaration (PR-readiness gap).
3. The GitHub fork + push (blocked on `gh auth login` — token invalid).
4. The dep cleanup fork of `qwen3-asr-causal` (the `check_model_inputs` decorator patch).
5. Tier B simultaneous MT port (Option A — confirm intent first).
6. The generalized wrapper layer (the amended task's scope).
7. Second provider conversion to prove the wrapper (part of the amended task).
