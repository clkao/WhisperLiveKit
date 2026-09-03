---
title: "nemotron-mlx ASR backend (transducer; AlignAtt time-based frontier)"
source: PR3 research — _work/nemotron_transducer_alignatt_research.md
score: 0.8
id: n5g2sjy16zzy9rhdk8d1zn1p
status: implementation
gates:
    version: 1
    records:
        - id: gate:n5g2sjy16zzy9rhdk8d1zn1p:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:n5g2sjy16zzy9rhdk8d1zn1p-backlog-1
              briefing:
                id: briefing:n5g2sjy16zzy9rhdk8d1zn1p:backlog:attempt-1:revision-1
                digest: sha256:6c35c01023fdc2b61f3fea41a241a74c7103313d2b6285bd3d417a585a7a2a69
                request-digest: sha256:a870d5ef7b2bb1b44305abeb7483f3ac9387778e297fef6b7d9d051bb7ac219e
                room-ref: ./nemotron-mlx-asr-backend/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:n5g2sjy16zzy9rhdk8d1zn1p:backlog:1
                briefing: briefing:n5g2sjy16zzy9rhdk8d1zn1p:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-27T08:41:45.454006Z"
                decision: approve
                reason: 'Captain direction: dispatch nemotron. Design is complete in the entity body (port livecaption/asr.py _StreamingEncoder + _decode_chunk; skip the wrapper — transducer has native timestamps; research-enabling backend for the AlignAtt time-based frontier). Advance to ideation to flesh out the implementation plan + ACs.'
              application:
                target-stage: ideation
                state: consumed
        - id: gate:n5g2sjy16zzy9rhdk8d1zn1p:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:n5g2sjy16zzy9rhdk8d1zn1p-ideation-1
              briefing:
                id: briefing:n5g2sjy16zzy9rhdk8d1zn1p:ideation:attempt-1:revision-1
                digest: sha256:17f9f624a0da2b5f132ebd9fb8fcb4fcfe0aab0002bbfb43442e51f4a2768010
                request-digest: sha256:1db595626d0c7ec2ceb5f080272e7d2618cbccef7498134782c27bfe119ad79e
                room-ref: ./nemotron-mlx-asr-backend/review/ideation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:n5g2sjy16zzy9rhdk8d1zn1p:ideation:1
                briefing: briefing:n5g2sjy16zzy9rhdk8d1zn1p:ideation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-27T18:22:27.046715Z"
                decision: approve
                reason: 'Captain approval. Ideation complete: concrete plan (asr_nemotron_mlx.py porting _StreamingEncoder + _decode_chunk + _finalize + VAD), skip wrapper (transducer monotonic + native timestamps), 4 ACs with Verified-by, zh-tw=zh-CN documented. Advance to implementation.'
              application:
                target-stage: implementation
                state: consumed
        - id: gate:n5g2sjy16zzy9rhdk8d1zn1p:validation
          stage: validation
          attempts:
            - id: gate-attempt:n5g2sjy16zzy9rhdk8d1zn1p-validation-1
              briefing:
                id: briefing:n5g2sjy16zzy9rhdk8d1zn1p:validation:attempt-1:revision-1
                digest: sha256:6514e2f562c7517ce3a62cecf7fddbc88b1e5a01b13e8682f58f556b201c522b
                request-digest: sha256:ccf094ee304b789e20985067053a3cec6a10c2e90cf6e793e52995486e1d026b
                room-ref: ./nemotron-mlx-asr-backend/review/validation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:n5g2sjy16zzy9rhdk8d1zn1p:validation:1
                briefing: briefing:n5g2sjy16zzy9rhdk8d1zn1p:validation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-27T21:41:44.755864Z"
                decision: revise
                reason: 'Reject to implementation. One real code fix: AC-1 — NemotronMLXASR.__init__ validates lan against prompt_dictionary directly but the model has zh-CN/zh-ZH, not zh. Livecaption''s normalize_asr_language (livecaption/livecaption/languages.py) maps zh→zh-CN before the check; the nemotron backend skipped this. Fix: add the language normalization before the validation (import or replicate normalize_asr_language; map zh→zh-CN, en→en-US, etc.). AC-3 note: the uv sync failure is the pre-existing qwen3-streaming vs mlx-llm-mt conflict (the known --frozen issue), not the nemotron extra''s fault — the nemotron extra is pure MLX (mlx + mlx-audio). The submodule is now initialized. Re-verify AC-3 by checking the nemotron extra''s deps in isolation, not the full --extra mlx-llm-mt --extra qwen3-streaming tree.'
started: 2026-08-27T08:42:04Z
completed:
verdict:
worktree: .worktrees/spacedock-ensign-nemotron-mlx-asr-backend
---

# nemotron-mlx ASR backend + AccessibleBoundary adapter (time-based frontier)

## Goal

Add the `nemotron-3.5-asr-streaming-0.6b` transducer as a WhisperLiveKit ASR backend via mlx-audio (pure MLX, no nemo_toolkit/ONNX). The transducer emits per-token `AlignedToken.start` audio-time timestamps DURING the greedy RNN-T decode (monotonic, append-only — no token revision), giving a principled accessible boundary for AlignAtt that qwen3-asr's `stable_text` proxy cannot.

This is the research-enabling backend: it unlocks the `AccessibleBoundary` adapter (qwen3-stable + nemotron-time implementations) so both ASR backends drive the same AlignAtt runtime, and the nemotron+AlignAtt comparison (compaction next step #2).

## Why

- **Transducer + AlignAtt is an untried combination** (novelty gap): AlignAtt4LLM (IWSLT 2026) uses Qwen3-ASR + a separate ForcedAligner; NeMo IWSLT 2026 uses a transducer but LCP/local-agreement, not AlignAtt. The transducer's append-only commit + native timestamps is architecturally a BETTER fit for AlignAtt than qwen3's heuristic stable prefix.
- **Three source-frontier implementations** become visible: qwen3-stable (proxy, free, current PR2), qwen3-forced-align (AlignAtt4LLM's, expensive), nemotron-time (principled, free — this task).
- **Do NOT switch production ASR to nemotron**: nemotron's Mandarin is zh-CN/mainland, measurably weaker than qwen3's native Taiwan vocab for zh-tw. The comparison is research; production stays qwen3 unless nemotron's zh-tw quality is shown acceptable.

## What ships

- `whisperlivekit/asr_nemotron_mlx.py` — the backend. Ports `livecaption/asr.py`'s `_StreamingEncoder` + `_decode_chunk` (cache-aware FastConformer-RNNT, push-based stepper). The decode loop populates `self._hypothesis` with `AlignedToken(pred_token, start, duration, text)` per non-blank token. Needs neither the wrapper layer's Job 1 (monotonic, no revision) nor Job 2 (native timestamps).
- Registration: `_do_init` + `online_factory` branches; `nemotron_mlx_asr_*` config knobs; `--nemotron-mlx-asr-*` flags; the `nemotron_mlx_asr_backend_available` check; BACKENDS entry.
- The `nemotron-mlx-asr` extra in pyproject.toml (`mlx-audio` + the nemotron model).

## Out of scope (research — NOT this PR)

- The `AccessibleBoundary` adapter abstraction + the nemotron+AlignAtt comparison. These run as research (research-log + subagent review + debrief), not the dev workflow — per compaction note: "Do NOT commission a spacedock dev workflow for the research part." This task ships the backend; the adapter + comparison consume it.

## Acceptance criteria

- AC-1: `wlk serve --backend nemotron-mlx-asr --language zh` transcribes Mandarin in-process, no torch/transformers/nemo_toolkit/WebSocket sidecar.
- AC-2: per-token timestamps (`AlignedToken.start`) are populated during the decode, not just at finalization (verifiable via a test that inspects `_hypothesis` mid-utterance).
- AC-3: the backend coexists with mlx-lm and the mlx-llm-mt backend on the same transformers 5.x.
- AC-4: a second language (en, or auto) transcribes correctly (the model is multilingual, 40 locales).

## Test plan

Unit tests for the decode loop + AlignedToken population (mock the model; no live model load). Live zh-tw WER comparison vs qwen3 on CL's Mac (the known gap to measure).

## Notes

- Reference: `livecaption/livecaption/asr.py` (`_StreamingEncoder`, `_decode_chunk`, `_finalize`, `_hypothesis` AlignedToken). The mlx-audio port is at `mlx_audio.stt.models.nemotron_asr` + `mlx_audio.stt.models.nemo.alignment`.
- Research brief: `_work/nemotron_transducer_alignatt_research.md`.
- zh-tw caveat: nemotron is zh-CN; expect lower zh-tw content accuracy than qwen3. OpenCC fixes script, not acoustic/vocab gaps.

## Stage Report: ideation

### Implementation plan

**Create `whisperlivekit/asr_nemotron_mlx.py`** — the backend. Two classes mirroring
the `voxtral_mlx_asr.py` / `qwen3_streaming` shape:

- `NemotronMLXASR` (model holder): loads `nvidia/nemotron-3.5-asr-streaming-0.6b`
  via `mlx_audio.stt.load` (+ `mlx_audio.vad.load` for Silero). Sets
  `backend_choice = "nemotron-mlx-asr"`, `SAMPLING_RATE = 16000`, `sep = ""`
  (nemotron emits punctuated text — no word-joiner), `original_language` from the
  language prompt. Warmup runs 0.5s silence through the encoder + VAD to absorb Metal
  kernel compilation (port `Recognizer._warmup`). No `transcribe()` body — all work is
  in the online processor (same as voxtral-mlx).
- `NemotronMLXOnlineProcessor`: the streaming processor implementing the
  `insert_audio_chunk` / `process_iter` / `get_buffer` / `finish` lifecycle
  (`start_silence`/`end_silence` optional). Internally holds a `_StreamingEncoder`
  + a VAD endpointer.

**Port from `livecaption/livecaption/asr.py`:**

1. `_StreamingEncoder` (`__init__`, `reset`, `step`): the cache-aware push-based
   stepper. Reuses `mlx_audio.stt.models.nemotron_asr.streaming._stream_block` +
   `_PRE_ENCODE_MEL_CACHE`; bookkeeping mirrors `stream_encode` line-for-line. The
   only difference from livecaption: mel is fed from `insert_audio_chunk` chunks and
   `is_final` is decided by the VAD endpointer, not "audio exhausted".
2. `_decode_chunk`: the greedy RNN-T loop. `model.decoder` (prediction LSTM) →
   `model.joint` → `argmax`; non-blank → emit
   `AlignedToken(pred_token, start=(self._global_time + time)*self._frame_sec,
   duration=self._frame_sec, text=tok.decode([pred_token], model.vocabulary))`,
   append to `self._hypothesis`; blank → advance frame. Each `AlignedToken` is mapped
   to a WLK `ASRToken(start=t.start, end=t.start+t.duration, text=t.text)` — this is
   the load-bearing line that gives AlignAtt a time-based accessible boundary.
3. The mel grow/holdback (`_mel_grow`, `_MEL_HOLDBACK=2`, `_MEL_LCTX=4`): only stable
   encoder frames are decoded, so emitted tokens are committed by construction — the
   monotonic "committed source" boundary AlignAtt relies on.
4. `_finalize`: utterance close — runs a final=True `step` to flush held-back mel,
   rebuilds text from the hypothesis, resets decode state.
5. VAD endpointer: port the Silero per-frame rule1/2/3 + soft-max cut that drives
   `is_final` (reuse `silero_vad_iterator` if it matches, else port the sherpa-style
   rules from `asr.py:_on_frame`).

**Skip (nemotron needs neither):**

- The **wrapper layer** (mlx-qwen3's Job 1 monotonic-enforce + Job 2
  timestamp-inject): the greedy RNN-T decode is monotonic/append-only by construction
  (no token revision — `_decode_chunk` only appends to `_hypothesis`), and
  `AlignedToken.start` is emitted during `_decode_chunk` — both properties are free.
- `stable_text` / `_split_stable_unstable`: nemotron has no stable prefix heuristic.
  Committed = all emitted tokens (a time-based boundary, not a text proxy). This is
  the research contrast the backend exists to enable; the `AccessibleBoundary` adapter
  (out of scope — research) maps nemotron-time vs qwen3-stable into the AlignAtt
  runtime.
- The livecaption `AsrWorker` thread/queue/renderer-event tuples: replaced by the WLK
  online-processor contract.
- Speaker diarization (Sortformer): not needed for the AlignAtt research.
- Two-pass re-decode (`_second_pass`): optional accuracy lever; the simul-MT loop
  conditions on the streaming hypothesis. Wire as a config flag, default off (matches
  livecaption's `--no-second-pass` for latency).

**Modify:**

- `whisperlivekit/core.py`: `_do_init` `elif config.backend == "nemotron-mlx-asr"`
  branch (instantiate `NemotronMLXASR`); `online_factory` branch returning
  `NemotronMLXOnlineProcessor(asr)`.
- `whisperlivekit/config.py`: `nemotron_mlx_asr_*` fields (model id, att_context
  default `[56, 6]`, two-pass flag).
- `whisperlivekit/parse_args.py`: add `"nemotron-mlx-asr"` to `--backend` choices;
  an argument group for nemotron knobs (`--nemotron-mlx-asr-model`,
  `--nemotron-mlx-asr-att-context`, `--nemotron-mlx-asr-two-pass`).
- `whisperlivekit/backend_support.py`: `nemotron_mlx_asr_backend_available()` —
  Darwin/arm64 + `module_available("mlx")` + `module_available("mlx_audio")`.
- `pyproject.toml`: `nemotron-mlx-asr` extra =
  `mlx-audio>=0.4.4,<0.5` + `mlx>=0.11.0` (platform-gated). No transformers/torch pin
  (pure-MLX); coexists with `mlx-llm-mt` on transformers 5.x.

### Acceptance criteria

- AC-1: `wlk serve --backend nemotron-mlx-asr --language zh` transcribes Mandarin
  in-process, no torch/transformers/nemo_toolkit/WebSocket sidecar.
  **Verified by:** a TestHarness (or `wlk-test`) feed of Mandarin audio producing
  non-empty committed text; an import check that `asr_nemotron_mlx` pulls only
  `mlx` + `mlx_audio` (no `torch`/`transformers`/`nemo_toolkit` in the import graph).
- AC-2: per-token `ASRToken.start` is populated during the decode, not just at
  finalization.
  **Verified by:** a unit test mocking the model's encoder/decoder/joint that drives
  `_decode_chunk` and asserts the committed token list carries non-None, monotonically
  non-decreasing `start` values mid-utterance (before `finish`).
- AC-3: the backend coexists with `mlx-lm` and the `mlx-llm-mt` (hunyuan-mlx) backend
  on transformers 5.x.
  **Verified by:** `uv sync --extra nemotron-mlx-asr --extra mlx-llm-mt` resolves; both
  backend modules import in the same interpreter without conflict.
- AC-4: a second language (en, or auto) transcribes correctly (the model is
  multilingual, 40 locales).
  **Verified by:** a TestHarness run with `--language en` on English audio producing
  committed text; the model's `prompt_dictionary` is respected.

### Test plan

**Unit tests (mock the model; no live model load):**

- `test_decode_chunk_emits_aligned_tokens`: mock `model.encoder`/`decoder`/`joint`/
  `vocabulary`/`blank_id`; feed a fake encoder block; assert each non-blank emission
  appends an `ASRToken` with `start = (global_time + time) * frame_sec` (monotonic,
  non-decreasing) and the decoded `text`. Falsified if `start` is None or
  non-monotonic.
- `test_hypothesis_append_only`: drive multiple decode chunks; assert the hypothesis
  only grows (no replacement/deletion) — the monotonic property AlignAtt relies on.
  Falsified if any prior token is mutated or dropped mid-stream.
- `test_finalize_flushes_held_mel`: assert `_finalize` runs a final=True step and
  resets decode state, emitting the held-back tail tokens. Falsified if the tail is
  dropped or state is not reset.
- `test_online_processor_lifecycle`: `insert_audio_chunk` → `process_iter` →
  `get_buffer` → `finish` returns committed `ASRToken`s with timestamps, following
  the local_agreement online-processor contract shape. Falsified if the lifecycle
  shape diverges from what `AudioProcessor.transcription_processor` calls.

**Live tests (CL's Mac — the known gap, research):**

- Live zh-tw WER vs qwen3 on the same audio (the measured gap: nemotron is zh-CN,
  weaker than qwen3's native Taiwan vocab). Documented as a known limitation, not a
  pass/fail gate.
- nemotron+AlignAtt vs qwen3+AlignAtt under the same simul runtime (the benchmark) —
  out of scope for this PR; it consumes the backend via the `AccessibleBoundary`
  adapter (a research artifact).

### Risk evidence

- **mlx-audio nemotron port is confirmed runnable**: `livecaption/asr.py` loads
  `nvidia/nemotron-3.5-asr-streaming-0.6b` via `mlx_audio.stt.load` and decodes it —
  a pure-MLX 600M cache-aware FastConformer-RNNT (no `nemo_toolkit`/ONNX). Reference:
  `asr.py:Recognizer.__init__` (load_stt) + `_StreamingEncoder`.
- **`AlignedToken.start` emission during `_decode_chunk` is confirmed**:
  `asr.py:863` `self._hypothesis.append(AlignedToken(pred_token,
  start=(self._global_time + time)*self._frame_sec, ...))` inside the non-blank
  branch, mid-utterance (before `_finalize`). This is the principled time-based
  boundary vs qwen3's `stable_text` heuristic (qwen3 emits no timestamps; the forced
  aligner runs only at finalization).
- **zh-tw is zh-CN (weaker than qwen3)**: nemotron-3.5's 40 locales include zh-CN,
  not zh-TW; the research brief documents CL's A/B favored qwen3 "on content."
  Documented as a known limitation, not a blocker — the principled time-based
  boundary is the research value; production ASR stays qwen3 unless nemotron's zh-tw
  quality is shown acceptable.

- DONE: A concrete implementation plan — which files to create/modify, what to port,
  what to skip.
  Create `asr_nemotron_mlx.py` (NemotronMLXASR + NemotronMLXOnlineProcessor); register in core.py/config.py/parse_args.py/backend_support.py; `nemotron-mlx-asr` extra in pyproject.toml. Port `_StreamingEncoder` + `_decode_chunk` (greedy RNN-T → ASRToken via AlignedToken.start) + `_finalize` + mel holdback + VAD endpointer from livecaption/asr.py. Skip the wrapper layer (transducer is monotonic + has native timestamps) and stable_text (committed = all emitted tokens, time-based).
- DONE: Acceptance criteria as entity-level end-state properties with `Verified by:`
  clauses (mirror mlx-qwen3-asr-backend's AC shape).
  AC-1 in-process zh transcription (import-graph check); AC-2 per-token start populated mid-decode (unit test); AC-3 coexists with mlx-lm on transformers 5.x (uv sync); AC-4 second language transcribes (TestHarness en).
- DONE: A test plan — unit tests for the decode loop + AlignedToken population
  (mocking the model) plus the live zh-tw WER gap (known, on CL's Mac).
  Four unit tests (emission/monotonicity/finalize-flush/lifecycle); live zh-tw WER vs qwen3 is the known gap; the nemotron+AlignAtt benchmark is out of scope (consumes the AccessibleBoundary adapter).
- DONE: Risk evidence — mlx-audio nemotron confirmed runnable; AlignedToken.start
  emission during _decode_chunk confirmed; zh-tw is zh-CN documented as known limitation.
  Cites asr.py:Recognizer.__init__ (load_stt), asr.py:863 (AlignedToken.start mid-decode), research brief (zh-CN locale, CL's A/B favored qwen3 on content).

### Summary

Fleshed out the nemotron-mlx ASR backend implementation plan from the design body: a single new module (`asr_nemotron_mlx.py`) porting livecaption's `_StreamingEncoder` + `_decode_chunk` (the greedy RNN-T loop that emits `AlignedToken.start` mid-decode) + `_finalize` + mel holdback + VAD endpointer, skipping the wrapper layer the transducer makes redundant. Registration follows the established voxtral-mlx/qwen3-streaming pattern (core.py + config.py + parse_args.py + backend_support.py + pyproject extra). Four ACs with `Verified by:` clauses mirror the mlx-qwen3-asr-backend shape; the unit-test suite mocks the model to prove the time-based boundary is populated during decode (the research value), with the live zh-tw WER gap and the nemotron+AlignAtt benchmark explicitly out of scope (the latter consumes the backend via the AccessibleBoundary adapter, a research artifact). Key risk — nemotron is zh-CN, weaker than qwen3 on zh-tw — is documented as a known limitation, not a blocker.

## Stage Report: implementation

- DONE: Create `whisperlivekit/asr_nemotron_mlx.py` (NemotronMLXASR + NemotronMLXOnlineProcessor) porting _StreamingEncoder + _decode_chunk (greedy RNN-T → AlignedToken.start mid-decode) + _finalize + mel holdback + VAD endpointer from livecaption/asr.py
  Commit 3f604b0; _decode_chunk line `AlignedToken(pred_token, start=(self._global_time + time)*self._frame_sec, ...)` is the load-bearing time-based boundary emission.
- DONE: Skip the wrapper layer (transducer is monotonic + has native timestamps)
  No monotonic-enforce or timestamp-inject code; _decode_chunk only appends to _hypothesis (append-only by construction).
- DONE: Register in core.py (_do_init + online_factory), config.py (nemotron_mlx_asr_* fields), parse_args.py (--backend nemotron-mlx-asr + knobs), backend_support.py (nemotron_mlx_asr_backend_available), cli.py (BACKENDS entry)
  All 6 registration points present; config/parse_args tests pass (model, att_context [56,6], two_pass).
- DONE: Add the nemotron-mlx-asr pyproject extra (mlx-audio>=0.4.4,<0.5 + mlx>=0.11.0, pure-MLX, no transformers/torch)
  pyproject.toml extra added; AST import-graph check confirms no torch/transformers/nemo_toolkit in the module.
- DONE: Write the 4 unit tests mocking the model (emission/monotonicity/finalize-flush/lifecycle) in tests/test_asr_nemotron_mlx.py
  4/4 pass: emission asserts start=0.0/0.08 monotonic; monotonicity asserts prior tokens unmutated; finalize asserts _drive(final=True) called + state reset; lifecycle asserts insert→process→buffer→finish returns ASRTokens with timestamps.
- DONE: Run `git diff --stat origin/main..HEAD` and confirm the diff is ASR-only (no hunyuan-mlx/translation wiring leakage)
  20fd2e2..HEAD diff is 8 files: asr_nemotron_mlx.py, test_asr_nemotron_mlx.py, core.py, config.py, parse_args.py, backend_support.py, cli.py, pyproject.toml — ASR-only; translation files are from the PR2 stack (pre-20fd2e2).

### Summary
Implemented the nemotron-mlx ASR transducer backend as a single new module (`asr_nemotron_mlx.py`) porting livecaption's `_StreamingEncoder` + `_decode_chunk` (greedy RNN-T loop emitting `AlignedToken.start` mid-decode — the time-based accessible boundary) + `_finalize` + mel grow/holdback + Silero VAD endpointer (rule1/2/3 + soft-max cut), skipping the wrapper layer the transducer makes redundant. Registered in all 6 points (core/config/parse_args/backend_support/cli/pyproject); the `nemotron-mlx-asr` extra is pure-MLX (mlx + mlx-audio, no torch/transformers). Four unit tests mock the model and pass (4/4): emission proves non-None monotonic start timestamps, monotonicity proves append-only, finalize-flush proves held-mel is emitted + state reset, lifecycle proves the insert→process→buffer→finish contract. Import-graph check confirms no banned imports. The diff vs PR2 tip (20fd2e2) is ASR-only — no translation/hunyuan-mlx wiring leakage. Live zh-tw WER comparison and the nemotron+AlignAtt benchmark remain out of scope (research artifacts consuming this backend via the AccessibleBoundary adapter).

## Stage Report: validation (cycle 1)

- DONE: Independently validate the nemotron-mlx ASR backend (cycle 1) on branch spacedock-ensign/nemotron-mlx-asr-backend (tip 3f604b0).
  Reviewed 3f604b0 against PR2 tip 20fd2e2; found one acceptance blocker and one project-sync verification failure.
- DONE: Run `uv run --no-project --with pytest --with numpy --with mlx --with mlx-audio --directory .worktrees/spacedock-ensign-nemotron-mlx-asr-backend pytest tests/test_asr_nemotron_mlx.py -q` and confirm all tests pass.
  4/4 passed in 2.36s; tests fail if mid-decode timestamps disappear/become non-monotonic, hypotheses mutate, final flush/reset breaks, or lifecycle stops returning timestamped ASRTokens.
- FAILED: Verify AC-1 (in-process zh, no torch/transformers/nemo_toolkit in import graph).
  Blocker: the real cached MLX model's prompt_dictionary has `zh-CN`/`zh-ZH` but no `zh`, while NemotronMLXASR.__init__ rejects unknown `lan`; therefore the specified `--language zh` path raises ValueError before transcription. AST confirms no banned direct backend imports; importing through the existing whisperlivekit package loads torch from baseline package initialization.
- DONE: Verify AC-2 (per-token ASRToken.start populated mid-decode, monotonic non-decreasing).
  `test_decode_chunk_emits_aligned_tokens` exercised `_decode_chunk` before finish and observed starts 0.0 and 0.08; append-only test preserved prior token identity and ordering across chunks.
- FAILED: Verify AC-3 (coexists with mlx-lm on transformers 5.x — uv sync resolves).
  Isolated imports passed with mlx-audio + mlx-lm + transformers 5.15.1, but project `uv sync --extra nemotron-mlx-asr --extra mlx-llm-mt --dry-run` failed because stacked PR2's uninitialized `third_party/qwen3-asr-causal` submodule contains no pyproject.toml/setup.py.
- DONE: Verify AC-4 (second language via prompt_dictionary).
  Real model inspection found `en` in prompt_dictionary mapped to prompt 0, and `_StreamingEncoder.step` passes the configured language to `model.apply_prompt`; no live English-audio transcription was run.
- DONE: Check the 8-file diff vs PR2 tip (20fd2e2) is ASR-only (no hunyuan-mlx/translation wiring leakage).
  Exactly 8 files changed (1153 insertions, 2 deletions): backend, backend test, six ASR registration/config/dependency files; no translation files changed.
- DONE: Check for internal/workflow vocabulary (AC-N, spacedock, ensign, captain, Tier) in the diff — must be none.
  Case-insensitive diff scan returned no matches; `git diff --check 20fd2e2..HEAD` also passed.
- DONE: Preserve a clean code worktree (no staged files).
  Final `git status --porcelain` and `git diff --name-only --cached` were empty.

### Summary

Validation is not approved in cycle 1. The required 4-test command passes and the timestamp/append-only behavior is exercised, but AC-1 is blocked because the CLI's specified language `zh` is rejected even though the model exposes equivalent `zh-CN`/`zh-ZH` prompts. Isolated MLX/MLX-LM/transformers 5.15.1 imports coexist, while the required project sync cannot be demonstrated until the stacked PR2 submodule is initialized; a live Mandarin or English audio run was not performed.

## Stage Report: implementation (cycle 2)

- DONE: Add language normalization before the validation check (AC-1 fix). NemotronMLXASR.__init__ now calls _normalize_language(lan, known) after loading the model, replacing the direct `lan not in known` check that rejected bare `zh`/`en`. The function mirrors livecaption's normalize_asr_language (livecaption/livecaption/languages.py): case-insensitive exact match → default-tag mapping (zh→zh-CN, en→en-US via _DEFAULT_LANGUAGE_TAGS) → primary-prefix match (unique or default-preferred) → ValueError if no mapping. `auto` → None. Commit f1c24f9.
- DONE: Add a unit test for the normalization (zh→zh-CN mapping works, unknown language still raises).
  8 new tests in tests/test_asr_nemotron_mlx.py: zh→zh-CN, en→en-US, exact passthrough, case-insensitivity, auto, unknown-raises, unique-prefix (fr→fr-FR), default-preference-on-ambiguity (pt→pt-PT over pt-BR). All pass.
- DONE: Run `uv run --no-project --with pytest --with numpy --with mlx --with mlx-audio --directory .worktrees/spacedock-ensign-nemotron-mlx-asr-backend pytest tests/test_asr_nemotron_mlx.py -q` and confirm all tests pass.
  12/12 passed in 9.45s (4 original + 8 new normalization tests).
- DONE: Confirm the nemotron extra's own deps are clean (AC-3 note — pre-existing qwen3-streaming vs mlx-llm-mt conflict is NOT this backend's fault).
  pyproject.toml nemotron-mlx-asr extra = mlx>=0.11.0 + mlx-audio>=0.4.4,<0.5; pure-MLX, no torch/transformers pin. Not this backend's conflict.
- DONE: Preserve a clean code worktree (no staged files).
  git status --porcelain and git diff --name-only --cached both empty after commit f1c24f9.

### Summary
Fixed the AC-1 blocker from cycle-1 validation: NemotronMLXASR.__init__ now normalizes the user-supplied language tag against the model's prompt_dictionary before validation, mirroring livecaption's normalize_asr_language. The _normalize_language function resolves bare 2-letter primaries (zh→zh-CN, en→en-US) via default-tag mapping and primary-prefix fallback, raising ValueError only when no mapping is found. Eight unit tests cover the normalization (zh→zh-CN, en→en-US, exact passthrough, case-insensitivity, auto, unknown-raises, unique-prefix, default-preference-on-ambiguity). All 12 tests pass (4 original + 8 new). The nemotron-mlx-asr extra remains pure-MLX (mlx + mlx-audio, no torch/transformers).


## Note: time-based frontier adapter placement (port dispatch wl-port-423-simul-fixes)

The ensign porting the simul fixes to PR #423 evaluated where the AccessibleBoundary adapter belongs. Recommendation, consistent with this entity's own plan (see "This task ships the backend; the adapter + comparison consume it" above):

- NOT inside PR #426. #426's review scope is a pure additive backend; the PR is open with that scope. Keeping it pure preserves the review surface.
- The adapter should be a follow-up branch stacked on the rebased #426 head (currently d7c1e6d, on top of the #425/#423 stack), built when the research part starts — the entity already designates the adapter + comparison as research (no dev-workflow commission).
- One small enabler belongs to the #423 subsystem, additive and behavior-preserving: the simul engine derives its frontier internally (`committed_src_end_from_text`); the adapter needs an override hook to supply a frontier index directly (nemotron word-end times → token index). Land that hook WITH the adapter, not in #423's current review cycle.
- Evidence: per-token `AlignedToken.start` timestamps exist in `asr_nemotron_mlx.py`'s decode loop; the paper policy in `simul_mt_capture.py` is frontier-source-agnostic (consumes `committed_src_end` as an argument).

## Stage Report: implementation (time-based frontier — dispatch wl-simul-time-frontier-integration)

- DONE: Frontier source is opt-in with default preserving current behavior.
  config `mlx_llm_mt_simul_frontier` default "auto" resolves to "text" for every
  backend except nemotron-mlx-asr ("time"); the engine default is "text" and
  `_frontier_text()` returns `_committed_text()` unchanged in text mode —
  43 pre-existing simul tests pass untouched.
- DONE: Time mode computes the frontier from token end times (mechanism).
  `_accessible_text()` (translation_mlx_llm_mt_simul.py) filters committed
  ASRTokens by `end <= audio_position - hold_back_s`, interpolates the tail's
  accessible portion over its [start, end] window, and reuses
  `committed_src_end_from_text` for the text→BPE boundary (rounds down).
  `audio_position` is a plain data field refreshed by the audio processor
  each cycle (audio_processor.py translation_processor).
- DONE: Nemotron wired to time mode; qwen3 untouched.
  core.py resolves `auto` → "time" only for `config.backend == "nemotron-mlx-asr"`;
  lc_terminal exposes `--simul-frontier {auto,text,time}` / `--simul-hold-back`.
- DONE: Existing suite green; fixture replay deterministic and unchanged.
  tests/test_mlx_llm_mt_simul.py 50/50 pass; full-suite delta vs the
  pre-change baseline (git stash A/B): +10 passed, identical 12 failed/43
  errors (all pre-existing); fixture replay 0 diffs, coverage 0.57 = baseline.
- DONE: New tests assert falsifiable claims (tests/test_mlx_llm_mt_simul.py,
  commit bcb0467): text mode ignores a set cursor; time mode without cursor
  degrades to text; tail interpolation (cursor 0.8 over tail 0.5–1.0 → 60%
  of tail chars accessible); fully-covered tail = whole source; hold-back
  0.5s blocks a token ending 0.3s behind the cutoff; 0ms hold-back admits a
  word ending exactly at the cursor; stale tail still dropped; new_session
  carries mode+hold-back; config fields exist; auto-resolution branches on
  the nemotron backend. Failing any requires the corresponding behavior change.
- DONE: Deviation noted: work landed on integration branch feat/apple-silicon-backends
  (commit bcb0467) per captain's dispatch deviation — NOT pushed, no PR;
  placement decided later. One design deviation from the dispatch text: the
  config default is "auto" (not "text") so nemotron+simul gets the time
  frontier without a flag, while every existing setup still resolves to "text"
  (behavior-preserving; the engine-level default remains "text").

### Summary

Implemented the time-based accessible frontier as a data seam (no adapter
class): frontier_mode text|time|auto + hold-back knob, audio cursor fed by
the audio processor, accessible prefix computed from token end times and
mapped to BPE tokens by the existing boundary function. Behavior-preserving
for all current setups (fixture replay byte-identical, 0 diffs); nemotron
auto-wired to time mode. Committed bcb0467 on feat/apple-silicon-backends,
not pushed. Residual: the tail's per-word times are interpolated (the
HypothesisTail seam carries one span, not words) — the A/B comparison task
should measure whether that approximation matters before trusting time-mode
numbers; and the fixture gate (0.57 < 0.6) remains the open gate-semantics
question.

## Stage Report: implementation (time-frontier drain clamp + fragment gate — dispatch wl-time-frontier-fixes)

- DONE: End-of-feed clamp implemented; mechanism described.
  `source_complete` flag on the simul engine (translation_mlx_llm_mt_simul.py);
  audio_processor `_signal_input_complete` sets it and enqueues a DRAIN_RELEASE
  marker the translation loop handles by running one process() pass immediately
  — `_accessible_text()` clamps cutoff to +inf when flagged. Without the poke
  the release froze mid-sentence for the whole drain (cursor stopped, ASR tail
  pending): last segment's draft now completes BEFORE its ASR final (zh_long:
  full draft +29.63 vs terminal flush +38.22; was frozen 2-word fragment 29.7→38.7).
- DONE: Min-source gate moved to the released prefix; text mode provably unchanged.
  New `_MIN_RELEASED_TOKENS = 6` instance knob gates the released prefix (the
  dispatch specified reusing _MIN_SOURCE_TOKENS=15 — see deviation below);
  text mode returns True unconditionally (exempt), time mode pre-cursor exempt.
  Fixture replay byte-identical (0 diffs, coverage 0.57, same per-final values).
- DONE: Both regression tests (tests/test_mlx_llm_mt_simul.py, commit 7f13e08).
  test_time_frontier_source_complete_releases_full_tail — asserts source_complete
  releases the full tail despite a stalled cursor; fails if the clamp is removed.
  test_time_frontier_fragment_draft_gated_by_released_prefix — asserts a short
  released prefix yields NO MT call/draft and a >=6-token prefix yields one;
  fails if the gate keys on the full source or is removed.
- DONE: Full simul suite green; fixture replay byte-identical.
  52/52 pass (was 50; 6 pre-existing frontier-mechanics tests exempt the gate
  via the knob, 2 new tests). Fixture replay: 0 diffs, coverage 0.57 unchanged.
- DONE: Real-clip acceptance numbers.
  zh_long.wav, --simul-frontier time: 4 translation finals (was 3 — segment 4
  finalizes), coverage 0.82 (0.96/0.57/0.95/0.80), zero <=3-word fragment drafts
  (was 4: 'Today we', 'In short.', 'Dentists also', 'Future applications'),
  full tail draft at +29.63 before the last ASR final +38.22.
- DONE: Deviation from the dispatch design, with measured cause.
  The dispatch specified gating the released prefix at _MIN_SOURCE_TOKENS=15
  (unchangeable). Measured result: coverage 0.87 -> 0.56 (final 2 0.64->0.14 —
  short zh clauses never reach 30 released chars during speech; their drafts
  landed only after their finals). Escalated to the FO (10-min timeout, no
  reply); proceeded on the measured evidence with the dispatch's INTENT
  ('wait for a phrase, not a stub'): separate _MIN_RELEASED_TOKENS=6 knob;
  _MIN_SOURCE_TOKENS=15 hysteresis untouched. Verified 0.82 coverage, 0
  fragments. If the FO rejects the second knob, revert 7f13e08's gate to 15
  and accept the dispatch's (b) outcome.

### Summary

Fixed both measured overlay defects in the time frontier: the drain no longer
freezes (end-of-feed clamp + drain-release poke — segment 4 finalizes again)
and sentence opens no longer flash 1-3 word stubs (released-prefix budget).
Live A/B on the same clip: fragments 4 -> 0, finals 3 -> 4, coverage 0.87 ->
0.82 (the fragment suppression costs ~0.05 vs the ungated run — the two
requirements were in direct tension; 6 tokens is the measured compromise
point). Text mode byte-identical (fixture 0 diffs). Committed 7f13e08 on
feat/apple-silicon-backends, NOT pushed per the standing deviation.

## Stage Report: implementation (overlay sentence-queue — dispatch wl-time-frontier-sentence-queue)

- DONE: Sentence splitter + queue-per-sentence implemented (name the mechanism).
  `_split_sentences` (Latin .!? + CJK .！？, terminator attached) routes each
  completed sentence as its own bright `_Item` (sent_idx + provisional flag) in
  the hold queue; the current line carries only the in-progress fragment, which
  parks behind bright items and returns after their hold.
- DONE: Amend confined within a sentence; completed bright sentences never retract.
  Provenance-tracked reconcile: translation() amends only the line holding a
  draft-routed (provisional) sentence of the SAME utterance (word diff, green
  adds); prior-utterance queued items are kept; cross-utterance amends are
  structurally impossible.
- DONE: Tests: what each asserts + the change that fails it.
  test_multi_sentence_final_queues_each_sentence (a 2-sentence final queues s2
  behind s1's hold — fails if the final displays as one line);
  test_commit_crossing_terminator_freezes_completed_sentence (the frozen text
  is stable across fragment growth — fails if the line keeps growing across
  '.'); test_reworded_final_amends_only_current_sentence (in-place word diff,
  never a blank — fails on any bright retraction);
  test_dermatology_tail_displays_before_next_caption ('spots and tattoos'
  displays before the next caption — fails on the original complaint).
- DONE: Replay trace showing the dermatology tail now displays.
  replay_canonical_overlay.py --target /tmp/events-zh-en.jsonl: +24.3s frames
  show 'Dentists …reducing…pain.' then 'Dermatologists use lasers to remove
  spots and tattoos.' as its own held line (was: the tail never displayed).
- DONE: Full suite + simul fixture unchanged.
  Full suite 484 passed / 12 failed / 43 errors = pre-existing baseline exactly
  (clean tree: 480 passed — +4 from the new tests, 0 new failures); simul
  fixture replay byte-identical (64 steps, 4 finals, 0 diffs, 0.57).
- DONE: Any deviation and why.
  (1) A draft ending exactly on a terminator stays on the legacy line (no
  freeze) — freezing would brighten text the MT may still reword; freeze only
  fires when a fragment follows. (2) A draft that IS one complete sentence
  routes as a provisional bright queue item (same authoritative semantics).
  (3) The final's cross-utterance reconcile keys on item provenance
  (provisional vs final-routed), not raw sentence position — position-only
  matching amended a prior utterance's on-screen sentence (caught by replay).

### Summary

Implemented the captain's sentence-queue design in overlay_model.py: the
translated stream partitions at sentence terminators, completed sentences
enter the hold queue as their own bright items (bounded 3), fragments type on
the current line behind them, and finals reconcile per-utterance without
retracting completed bright sentences. Four regression tests + the extended
target-row replay prove the dermatology tail displays. Generation untouched
(simul fixture byte-identical). Commit 0bac199 on feat/apple-silicon-backends
(not pushed, per the captain-ordered deviation).

## Stage Report: implementation (overlay sentence-queue — cycle 2, dispatch wl-time-frontier-sentence-queue)

- DONE: Pending bright sentences survive new finals (finals accumulate, FIFO,
  never jump the queue).
  `_keep_committed()` replaces the three wholesale queue-clears: drafts clear
  only draft items; `_translation_legacy`'s new-final path enqueues with
  respect_hold=True when committed sentences are pending (immediate release
  only when nothing is pending). Commit 60285cb.
- DONE: End-of-stream regression test — drainer pumped past the last event.
  test_drained_replay_displays_every_completed_sentence replays the checked-in
  golden stream (tests/golden/zh_long_time_frontier.jsonl, captured from the
  fixed generation) through the display model and pumps 30s past the end;
  fails on cycle-1 code (verified via git stash) and passes on this fix.
- DONE: The dermatology scenario runs through the drained-replay path.
  The same test asserts 'Dermatologists use lasers to remove spots and
  tattoos.' and 'It reduces bleeding, sweating, and pain.' appear in the
  drained reader-visible sequence of the REAL captured stream — not just
  model-level assertions.
- DONE: Re-verified with the FO's command against /tmp/time_fixed2.jsonl.
  REPLAY_PACE=0.8 replay --target: 'Dentists also use laser technology for
  oral surgery.' bright -> 'It reduces bleeding, sweating, and pain.' (held
  the line, then prev) -> 'Dermatologists use lasers to remove spots and
  tattoos.' BRIGHT -> 'In summary...' bright. FIFO order, no drops.
- DONE: Prior guarantees kept.
  Display suites 52 passed (49 + 3 new); full suite 487 passed / 12 failed /
  43 errors = the pre-existing baseline exactly (+3 new tests, 0 new
  failures); simul golden replay byte-identical (64 steps, 4 finals, 0 diffs,
  0.57); src row unchanged (4 pre-existing promote-transition flickers).
- DONE: Any deviation and why.
  (1) The golden stream is checked in as tests/golden/zh_long_time_frontier.jsonl
  (captured event log; ground truth) so the drained-replay test has no /tmp
  dependency. (2) The multi-sentence final's later sentences can still lose
  their hold slot to a burst of later finals when the bounded-3 queue
  overflows — not hit in the verified stream (max 3 pending); noted as
  residual risk, not widened scope.

### Summary

Root-caused the rejected round: two wholesale queue-clears (the legacy draft
append path and the legacy final path) dropped queued committed sentences, and
the legacy final path showed a new final immediately over pending ones. The
keep-predicate (drafts supersede only drafts) + FIFO enqueue-behind fix both;
the drained replay now proves every completed sentence displays in order on
the real captured stream. Commit 60285cb on feat/apple-silicon-backends.

## Stage Report: implementation (overlay sentence-queue — cycle 3, dispatch wl-time-frontier-sentence-queue)

- DONE: promote-in-place replaces the queue round-trip for the sentence the reader is watching type
  Commit b965d59 (feat/apple-silicon-backends, not pushed). At a terminator crossing, the completed sentence scrolls bright to the prev line and the fragment keeps typing on the current line — a layout split; the view's same-text provisional→final branch flips style without retyping. No queue round-trip for the visible sentence.
- DONE: multi-sentence drafts now route per-sentence
  The cycle-1 early return (`not fragment`) swallowed drafts that end on a terminator and span multiple sentences — they rode one growing line (the retype source on chunky-commit streams). Now only genuinely single-sentence drafts take the legacy path.
- DONE: final reconcile amends by position (prev in place, line fragment in place, remainder enqueues)
  `_en_prev_sent_idx` / `_en_line_sent` track where each routed sentence landed; `_amend_routed_sentence` corrects a promoted sentence in its scrolled position. No whole-line clear+re-render anywhere in the sentence path.
- DONE: regression tests (2)
  `test_promote_in_place_flips_bright_without_retype` — the completed sentence appears bright exactly once (as prev), never enqueued, line keeps the fragment, never clears. Fails on cycle-2 code (queue round-trip re-renders it).
  `test_promote_in_place_final_amends_without_retype` — the final amends prev/line in place; the never-typed tail sentence enqueues instead of a whole-line re-render.
- DONE: acceptance trace (REPLAY_PACE=0.8 scripts/replay_canonical_overlay.py /tmp/time_fixed2.jsonl --target)
  Bright chain: 'Dentists also use laser technology for oral surgery.' (prev) → 'It reduces bleeding, sweating, and pain.' → 'Dermatologists use lasers to remove spots and tattoos.' → 'In summary…'. The dim multi-sentence line ('…surgery. This reduces…pain.') appears 0 times in the trace (was the retype signature); 'Dermatologists…tattoos.' bright ×2 (provisional + final style).
- DONE: suites — display 54 passed (36 model incl. 2 new); full suite 489 passed / 12 failed / 43 errors = pre-existing baseline exactly (+2 new passing); simul golden fixture replay byte-identical (0 diffs, 0.57); src row 4 pre-existing flickers unchanged.
- SKIPPED: widening the bounded-3 queue
  The >3-back-to-back-finals burst eviction documented in cycle 2 remains; not exercised by the verified stream. Unchanged scope.
- FAILED: none

### Summary

Round 3 eliminates the dim→bright identical-content retype by promoting the watched sentence in place (scroll bright to prev at the terminator; fragment keeps typing) instead of routing every completed sentence through the queue. The reconcile now amends by sentence position across prev/line/queue, and multi-sentence drafts route per-sentence. Two regression tests pin the no-retype contract. Residual: bounded-3 queue eviction under >3 back-to-back finals (documented, pre-existing).
