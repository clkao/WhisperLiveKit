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
started: 2026-08-27T08:42:04Z
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
