# COMPACTION SURVIVAL — WhisperLiveKit Apple-Silicon port (2026-08-25)

Read this first after compaction. Then `SESSION_STATE.md` for the resume checklist.

## Where we are (2026-08-25, post-worker-merge + fork cleanup)

Four async workers ran on WLK + one on the fork:
- **terminal-cli-stats** (DONE, merged to feat `5caea1d`): `--stats` live status line. NOT validated (stage report missing — see dispatch diagnosis).
- **mlx-qwen3-asr-backend** (DONE, merged to feat `f4d469b`): generalized wrapper layer + 38 tests. Has a stage report (the one worker that wrote one). At `validation`.
- **qwen-asr-tf5-compat-fork** (PARTIAL, merged to feat `0165d50`): AC-1 (import) only; model load fails. PARKED — the transformers path is the wrong lever; the MLX causal path is the right one.
- **hunyuan-mlx-translation-backend / mlx-llm-mt** (DONE, merged to feat `56b3983`): generic decoder-LLM MT, 6 Hunyuan + TranslateGemma config, 12 tests. NOT validated (stage report missing).
- **qwen3-asr-causal fork cleanup** (DONE, fork commit `8607d2e` on `feat/mlx-native-no-vllm`): `metal.py` now loads via `mlx_qwen3_asr`, NO vllm/torch. AC-1 (import, no vllm/torch) + AC-4 (no torch.load) PASS. AC-2 (transcribe) the worker reported PASS; my quick re-check came back empty (likely needs warmup or the tower checkpoint download on your Mac). AC-3 (behavior match vs vllm-metal reference) deferred to your Mac.

Fun-ASR-Nano-2512-4bit spiked: NOT viable (translate outputs Chinese; transcription truncates). Stay with qwen3-asr + Hunyuan-MT.

Primer updated: `docs/asr-streaming-explainer.md` has 8 new sections.

## The dispatch diagnosis (written to /tmp/spacedock-pi-dispatch-diagnosis.md)

`spacedock dispatch build` artifacts claim to contain the stage report format but don't. The format lives in the ensign skill, which `skill="ensign"` makes available but doesn't auto-load. 3 of 4 workers didn't load the skill and wrote summaries in result messages instead of `## Stage Report:` sections in entity files. Fix: embed the format in `--checklist-file` / the task prompt; proper upstream fix is the binary should emit the template.

## The immediate next actions

1. **Re-dispatch the 3 workers missing stage reports** (terminal-cli, qwen-asr-tf5 [park it instead], mlx-llm-mt) with the stage report format embedded in the task prompt.
2. **Verify on CL's Mac**: `wlk serve --backend mlx-qwen3-asr --language zh` (wrapper refactor); `python scripts/lc_terminal.py --stats` (status line); `wlk serve --backend qwen3-vllm-metal --qwen3-vllm-metal-audio-backend causal --language zh` (the native causal path — the fork cleanup).
3. **Tier B simultaneous MT** (port livecaption's `simul_mt.py` into mlx-llm-mt) — the real latency win; needs the validated mlx-llm-mt base first.

## What was dispatched (the contract I initially missed)

`spacedock dispatch build` emits the assignment artifact; the FO's next action is `«worker.spawn»` — call `subagent(agent=<artifact.agent>, skill=<artifact.skill>, context="fresh", cwd=<repo root>, task=<built prompt>)`. I did this for all tasks. The contract: `first-officer-shared-core.md:31,46` + `pi-first-officer-runtime.md:9`.

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

1. **Verify on CL's Mac**: `wlk serve --backend mlx-qwen3-asr --language zh` after the wrapper refactor; `python scripts/lc_terminal.py --stats`.
2. **qwen-asr deep tf5 port** (filed, backlog): model load + transcribe on transformers 5.11.0. Unblocks qwen3-asr-causal.
3. **Amend hunyuan-mlx → mlx-llm-mt** (generic decoder-LLM shape).
4. **Tier B simultaneous MT** (port livecaption's `simul_mt.py` into mlx-llm-mt; needs the mlx-llm-mt refactor first).
5. The pyproject extras + transformers/huggingface_hub pin declaration (PR-readiness gap).
6. The GitHub fork + push (blocked on `gh auth login` — token invalid).
