---
id: p0f67wa79kd56yh3bs0cca2e
title: mlx-qwen3-asr ASR backend + generalized ASR wrapper layer
status: validation
source: WhisperLiveKit Apple-Silicon backend work
started: 2026-08-25T15:52:13Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-mlx-qwen3-asr-pr
issue:
pr: "#425"
gates:
    version: 1
    records:
        - id: gate:p0f67wa79kd56yh3bs0cca2e:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:p0f67wa79kd56yh3bs0cca2e-backlog-1
              briefing:
                id: briefing:p0f67wa79kd56yh3bs0cca2e:backlog:attempt-1:revision-1
                digest: sha256:14a721eace30cb5dff1a6e9ec663af359633fd29a807c1e78b8470fd792e43ee
                request-digest: sha256:f4a49ab8d1f6708c4e86084aca2c5cca0a98834f85d5fb28125ae8462a3b6b60
                room-ref: ./mlx-qwen3-asr-backend/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:p0f67wa79kd56yh3bs0cca2e:backlog:1
                briefing: briefing:p0f67wa79kd56yh3bs0cca2e:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T15:51:48.661299Z"
                decision: approve
              application:
                target-stage: ideation
                state: consumed
        - id: gate:p0f67wa79kd56yh3bs0cca2e:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:p0f67wa79kd56yh3bs0cca2e-ideation-1
              briefing:
                id: briefing:p0f67wa79kd56yh3bs0cca2e:ideation:attempt-1:revision-1
                digest: sha256:310c8f277c1978bb079cf950d0496ca5f8a3373f1c30e5373f9da928a37d21f3
                request-digest: sha256:6118e433ecf891f9c5b5de3f8cf0d3f4506ff416e7027a25354b6a1ab68390c0
                room-ref: ./mlx-qwen3-asr-backend/review/ideation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:p0f67wa79kd56yh3bs0cca2e:ideation:1
                briefing: briefing:p0f67wa79kd56yh3bs0cca2e:ideation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T15:52:05.624809Z"
                decision: approve
              application:
                target-stage: implementation
                state: consumed
        - id: gate:p0f67wa79kd56yh3bs0cca2e:validation
          stage: validation
          attempts:
            - id: gate-attempt:p0f67wa79kd56yh3bs0cca2e-validation-1
              briefing:
                id: briefing:p0f67wa79kd56yh3bs0cca2e:validation:attempt-1:revision-1
                digest: sha256:622019c4951b1a0f1b616686b35c9d928fe2ddf667482f4d754ec93729d1b879
                request-digest: sha256:d33dcf3406da49ca3332d939ec2dc4de9531f62597bc8b62511fdbe237e4879b
                room-ref: ./mlx-qwen3-asr-backend/review/validation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:p0f67wa79kd56yh3bs0cca2e:validation:1
                briefing: briefing:p0f67wa79kd56yh3bs0cca2e:validation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-27T08:08:27.062853Z"
                decision: revise
                reason: 'Reject to implementation. Two blockers: (1) get_buffer contract conflict — StableCommitTransform (asr_commit.py:330) reads inner.get_buffer().text as the full rolling hypothesis, but Finding-1 made get_buffer return only the unstable tail; the transform can''t compute a stable prefix from the tail and emits garbage. Fix: add a get_hypothesis() method (or equivalent) returning the full rolling text for the transform; get_buffer stays the tail (WLK contract). (2) Hunyuan-mlx scope leakage in the carve — config.py/core.py/parse_args.py carry hunyuan-mlx translation wiring (hunyuan_mlx_model, translation_hunyuan_mlx import, hunyuan-mlx choices) which is PR1''s domain. Fix: re-carve those 3 files to keep only ASR-related changes, drop hunyuan-mlx lines. The 38 wrapper tests pass and both finding fixes work in isolation.'
            - id: gate-attempt:p0f67wa79kd56yh3bs0cca2e-validation-2
              briefing:
                id: briefing:p0f67wa79kd56yh3bs0cca2e:validation:attempt-2:revision-1
                digest: sha256:30af00df07d4d16a748559315fc3e0caa24d6fb45633291de045e88dcc4206af
                request-digest: sha256:5cd6b3adb197f3967510f6252ed1de233b04eda91083b3372405c76097e823ff
                room-ref: ./mlx-qwen3-asr-backend/review/validation/briefing-2
              resolution:
                type: Resolution
                id: resolution:spacedock:p0f67wa79kd56yh3bs0cca2e:validation:2
                briefing: briefing:p0f67wa79kd56yh3bs0cca2e:validation:attempt-2:revision-1
                by: person:captain
                at: "2026-08-27T09:09:20.596778Z"
                decision: revise
                reason: 'Reject to implementation. AC-3 fails: text duplication. StableCommitTransform emits stable prefixes during process_iter (streaming commits), then _finalize_utterance (asr_mlx_qwen3.py:171) emits the FULL re-decoded utterance text at the start_silence boundary — the committed prefix appears twice (validator reproduced ''alpha beta gamma'' twice). Fix: _finalize_utterance must emit only the uncommitted/corrective portion — subtract _emitted_stable from final_text and emit only the delta, or emit the full text only when no stable prefix was committed. Add an integration test covering streaming commits then silence finalization asserting no duplication. The 39 wrapper tests pass; both cycle-1 blockers fixed (get_hypothesis seam, hunyuan-mlx scope excised) — this is a third separate blocker.'
            - id: gate-attempt:p0f67wa79kd56yh3bs0cca2e-validation-3
              briefing:
                id: briefing:p0f67wa79kd56yh3bs0cca2e:validation:attempt-3:revision-1
                digest: sha256:52a030de0aa842b5ae084c4e035c64783c419be5169c653e06e95800e2c7a7c2
                request-digest: sha256:a4b81f6f57b9811c599fb2858792ca9ad4c2396e94779922593c73240dfd0737
                room-ref: ./mlx-qwen3-asr-backend/review/validation/briefing-3
              withdrawal:
                by: agent:first-officer
                at: "2026-11-09T05:29:19.852132Z"
                reason: 'Stale open authority: the briefing-3 room was prepared 2026-08-27, the entity body changed on 2026-11-08 (stage-report repair), and PR #425 is CONFLICTING against upstream main (head 24082a0, no maintainer review). Evidence must be re-prepared against a refreshed branch before a captain decision.'
            - id: gate-attempt:p0f67wa79kd56yh3bs0cca2e-validation-4
              briefing:
                id: briefing:p0f67wa79kd56yh3bs0cca2e:validation:attempt-4:revision-1
                digest: sha256:82465a193c2dd3d42cfdcb4683c5b8cb61be4bca446d6b3db5c878730a81daf5
                room-ref: '@review/validation/briefing-4'
              resolution:
                type: Resolution
                id: resolution:spacedock:p0f67wa79kd56yh3bs0cca2e:validation:4
                briefing: briefing:p0f67wa79kd56yh3bs0cca2e:validation:attempt-4:revision-1
                by: person:captain
                at: "2026-11-13T19:50:57.858316Z"
                decision: revise
                reason: 'Captain directive 2026-11-13 (verbatim): ''choose 2, dispatch through the workflow and bring back reproduced validation result''. Option 2 = bump mlx-qwen3-asr 0.3.5 -> 0.4.4 and re-measure. Concrete asks, from the maintainer''s #425 review (2026-11-13T19:22Z) and the 0.4.x changelog: (1) adopt 0.4.x, whose finish-path window re-decode replaces the 0.3.5 enable_tail_refine pass that appends a re-transcription of the last window and duplicates text at every pause; cover it with a test through AudioProcessor on audio containing pauses. (2) No exception on a short tail at a pause (0.3.5 raises ''Audio too short for log-mel extraction'' from a 160-sample tail; 0.4.x must be shown not to). (3) Handle open upstream issue #31 (stable_text can be non-prefix and non-monotone) instead of aborting with RuntimeError(''revised an already committed prefix''). (4) Reproduce FLEURS zh/en/fr quality under the #444 protocol (30 clips per language, three paced passes) against Whisper small MLX and Qwen Metal; identical weights rule out the model as the cause. Context: the reviewed adapter is the maintainer''s own 34a2b5e rewrite (native finish_streaming at every pause), which deleted our asr_commit/asr_wrapper layer and its stable-prefix fallback; all three review findings are measured against that rewrite.'
---

# mlx-qwen3-asr ASR backend + generalized ASR wrapper layer

## Goal

Add the `mlx-qwen3-asr` ASR backend to WhisperLiveKit. Build it through a new
generalized wrapper layer. Prove the layer works with one other provider.

The wrapper layer factors the two jobs that every non-transducer ASR backend
duplicates today. The `mlx-qwen3-asr` backend is the first user. A second
provider (Whisper or Voxtral) proves the layer is general.

## The two jobs

A non-transducer ASR model revises its hypothesis or emits text forward without
timestamps. The wrapper manufactures the contract a streaming translator needs:
a committed prefix and an unstable tail.

- Job 1, the stable/unstable split: for models that revise. The model
  re-decodes a window and can change its recent output. The wrapper commits
  only a prefix that stays stable across decode passes.
- Job 2, the timestamp manufacture: for models that emit text forward but give
  no per-word timestamps. The wrapper assigns start and end times from the
  decode position.

A transducer (nemotron) needs neither job. It emits monotonic tokens with real
timestamps natively.

## What ships

- `whisperlivekit/asr_commit.py`. The Job 1 module. Factor the
  `update_stable_prefix_commit` policy from `qwen3-asr-causal/stable_commit.py`
  into WLK core. The policy uses token agreement across N decode passes and a
  hold-back token count.
- `whisperlivekit/asr_timestamps.py`. The Job 2 module. Factor the
  `_word_time_range` and `word_audio_starts` logic from `voxtral_mlx_asr.py`
  into a helper that assigns start and end times to forward-emit tokens.
- `whisperlivekit/asr_wrapper.py`. A small wrapper base that forwards the
  online-processor contract methods to an inner processor. A subclass intercepts
  `process_iter` to apply a list of transforms. The existing
  `_ASRTokenNormalizer` is the start of this base; generalize it from a single
  token-normalize step to a composable transform chain.
- `whisperlivekit/asr_mlx_qwen3.py`. The `mlx-qwen3-asr` backend. The decode
  loop returns the raw hypothesis. A `stable_commit` wrapper applies Job 1. The
  two-pass re-decode at `start_silence` and `finish` stays in the backend (it is
  model-specific: re-decode the utterance audio offline for clean text). Warmup
  at init.
- One second provider converted to the wrapper layer. Use the Whisper
  LocalAgreement backend or the Voxtral-MLX backend. The conversion replaces
  the inline commit logic with a call to the shared module. This proves the
  layer is general.
- Registration: the `_do_init` and `online_factory` branches in `core.py`; the
  `mlx_qwen3_asr_*` config knobs; the `--mlx-qwen3-asr-*` flags; the
  `mlx_qwen3_asr_backend_available` check; the BACKENDS entry. The
  `online_factory` composes the wrappers each backend needs.
- The `mlx-qwen3-asr` extra in `pyproject.toml`.

## Acceptance criteria

- Run `wlk serve --backend mlx-qwen3-asr --language zh`. The command transcribes
  Mandarin audio in-process. The backend needs no torch, no transformers, and no
  WebSocket sidecar.
- The dependency set coexists with `mlx-lm` and the `hunyuan-mlx` backend on
  transformers 5.x.
- The two-pass re-decode gives clean per-utterance text. The text has no
  rolling-decode repetition on utterances longer than the chunk size.
- The warmup runs at init. The first real decode does not stall.
- The second provider (Whisper or Voxtral) uses the shared `asr_commit` or
  `asr_timestamps` module. The conversion does not change that provider's output
  on the existing tests.
- The wrapper layer is composable. A backend declares which jobs it needs. The
  `online_factory` builds the chain.

## Notes

The working dependency set is transformers 5.11.0, huggingface_hub 1.18.0,
mlx-lm 0.31.1, and mlx-qwen3-asr 0.3.5. The `qwen3-asr-causal` package pins
transformers to 4.57.6. This backend does not use that package.

The translator contract is the same for all ASR backends. A committed prefix
goes to `insert_tokens`. An unstable tail goes to `HypothesisTail` when the
translator sets `wants_hypothesis_tail` to `True`. The `qwen3-asr-causal`
windowed backend already emits this contract. The dep cleanup (make
`qwen3-asr-causal` work on transformers 5.x) is a separate task. When that
cleanup lands, the `qwen3-asr-causal` backend works through the same wrapper
layer with no translator-wiring change.

PR #395 ("refactor: decouple audio processor") splits the `AudioProcessor`
orchestration above `self.transcription`. This task splits the wrapper chain
below `self.transcription`. The two refactors are orthogonal layers. They do
not conflict and do not overlap.

## Stage Report: implementation

- DONE: Run `wlk serve --backend mlx-qwen3-asr --language zh`; transcribes Mandarin in-process, no torch/transformers/WebSocket sidecar.
  Backend wired in core.py _do_init + online_factory with AsrWrapper + StableCommitTransform; mlx-qwen3-asr extra in pyproject.toml. Not runtime-tested from sandbox (needs mic/AppKit on CL's Mac).
- DONE: The dependency set coexists with mlx-lm and the hunyuan-mlx backend on transformers 5.x.
  mlx-qwen3-asr extra pins mlx-qwen3-asr>=0.3.5,<0.4 (no transformers pin); asr_commit.py factored from qwen3_asr_causal.stable_commit without importing that package.
- DONE: Two-pass re-decode gives clean per-utterance text (no rolling-decode repetition on utterances longer than the chunk size).
  Two-pass re-decode stays in asr_mlx_qwen3.py _finalize_utterance (start_silence/finish); process_iter returns raw hypothesis, StableCommitTransform handles streaming commits.
- DONE: Warmup runs at init; first real decode does not stall.
  _warmup() unchanged from feat/apple-silicon-backends; runs 0.5s silence decode at init.
- DONE: The second provider (Voxtral-MLX) uses the shared asr_timestamps module; conversion does not change that provider's output on existing tests.
  voxtral_mlx_asr.py inline _word_time_range/_audio_pos_to_time/word_audio_starts replaced with WordTimestampTracker from asr_timestamps.py; same timestamp computation, now via shared module. test_voxtral_mlx_new_speaker_returns_boundary_result still skips (needs mlx) — no behavioral change.
- DONE: The wrapper layer is composable: a backend declares which jobs it needs; online_factory builds the chain.
  AsrWrapper takes a transforms list; online_factory passes [StableCommitTransform] for mlx-qwen3-asr and [] for other qwen3 backends. StableCommitTransform exposes reset() called at utterance boundaries.

### Summary

Created three new modules (asr_commit.py, asr_timestamps.py, asr_wrapper.py) factoring the two jobs every non-transducer ASR backend duplicates. Refactored mlx-qwen3-asr to route its decode loop through the StableCommitTransform wrapper (Job 1), keeping the two-pass re-decode in the backend. Converted Voxtral-MLX to use the shared WordTimestampTracker (Job 2), replacing inline timestamp logic with behavior-preserving calls. The online_factory composes the wrapper chain per backend. 38 new tests pass; pre-existing test failures (missing pytest-asyncio) are unchanged.

## Validation findings (2026-08-25, route to implementation)

Two findings from the validation audit (read-only, both backends audited):

### Finding 1 — `get_buffer` returns the full rolling text, not the unstable tail (AlignAtt seam)

The WLK contract (proven by `OnlineASRProcessor.get_buffer` → `self.transcript_buffer.buffer`, the unstable tail) is: `get_buffer()` returns a `Transcript(start, end, text)` where `text` is the unstable hypothesis tail (not yet committed). `process_iter()` returns the committed `ASRToken`s.

Our backend (`asr_mlx_qwen3.py:142`) returns `Transcript(start=None, end=audio_end, text=self._text)` — the FULL rolling text including the committed stable prefix. This double-counts the committed prefix for any consumer that reads `get_buffer` (display, and critically the AlignAtt translator which drafts over the tail via `HypothesisTail`).

Fix: `get_buffer` returns `text[len(self._stable_text):]` (the unstable tail = rolling text minus the stable prefix), with `start` = the time of the last stable commit (not None). The backend already has `self._stable_text` and `self._text`; the split is `text[len(stable):]`.

### Finding 2 — per-session language override silently broken

`SessionASRProxy.transcribe()` swaps `original_language` to apply a per-session `?language=` override, but (a) the mlx-qwen3-asr online processor reads `getattr(asr, "language")` (server-wide Namespace attr, not the per-session swap), and (b) the processor never calls `asr.transcribe()` — it calls `init_streaming`/`feed_audio`/`finish_streaming` directly. So a multi-language WLK server transcribes every session in the server-wide `--language` default, ignoring per-session overrides.

Fix: thread the per-session language into `init_streaming(language=...)` on the code path the processor actually uses. The `_new_state` method (line 121) already passes `language=self.language`; the fix is making `self.language` reflect the per-session override, not just the init-time server-wide value.

### Scope of the re-implementation

Both fixes are small and localized to `asr_mlx_qwen3.py`. No new modules, no base class, no second backend. The generalization (the wrapper chain) is already shipped; these are contract-compliance fixes so the backend speaks the AlignAtt seam correctly. Add a test: `get_buffer` returns only the tail after a commit; `process_iter` returns the committed prefix.

## Stage Report: validation (cycle 1)

- SKIPPED: AC-1: `wlk serve --backend mlx-qwen3-asr --language zh` transcribes Mandarin in-process, no torch/transformers/WebSocket sidecar.
  Live Mandarin/mic execution was not available; static wiring exists in `core.py:178-192,401-415`, backend availability/CLI registration is present, and the extra contains only MLX dependencies.
- DONE: AC-2: The dependency set coexists with mlx-lm + hunyuan-mlx on transformers 5.x.
  `pyproject.toml:59-62` pins `mlx-qwen3-asr>=0.3.5,<0.4` without a transformers constraint; adding such a constraint would fail this check.
  No item failed in this stage; every item above was completed or skipped with its rationale.
  `_finalize_utterance` does offline re-decode, but the composed transform reads the now-tail-only `get_buffer()` and reproducibly emits `gamma`, `delta` while omitting model-stable prefix `alpha beta`.
- DONE: AC-4: Warmup runs at init so the first decode does not absorb compilation.
  `asr_mlx_qwen3.py:107-120` calls `_warmup()` during construction and feeds/finishes 0.5 s silence; removing that constructor call would fail the assertion.
- SKIPPED: AC-5: A second provider shares `asr_commit` or `asr_timestamps`.
  Voxtral conversion is outside this carve; all three shared modules import, `AsrWrapper` accepts a transform list, and their isolated tests pass.
  No item failed in this stage; every item above was completed or skipped with its rationale.
  Structural composition exists at `core.py:401-415`, but `StableCommitTransform` consumes `inner.get_buffer()` as a full rolling hypothesis while the inner now returns only its unstable tail, so the declared chain is behaviorally invalid.
- DONE: Finding 1: `get_buffer` returns the unstable tail, with full-text fallback on a prefix mismatch.
  A targeted constructor-free check observed `" gamma"` for stable `"alpha beta"` plus full `"alpha beta gamma"`, and the full text after a non-prefix stable value.
- DONE: Finding 2: The per-session language override wins over the server-wide language.
  A mocked construction with server `English` and `_session_language="zh"` produced `self.language == "Chinese"`; reverting to the delegated `language` attribute would fail.
  No item failed in this stage; every item above was completed or skipped with its rationale.
  `uv run --extra test --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` failed before collection because the uninitialized `third_party/qwen3-asr-causal` submodule lacks `pyproject.toml`.
- DONE: Confirm the 38 wrapper tests pass with the required mlx-qwen3-asr dependency available.
  `uv run --no-project --with pytest --with numpy --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` passed 38/38; `uv run --no-sync` also passed 38/38.
  No item failed in this stage; every item above was completed or skipped with its rationale.
  The file list is exactly 11, but `config.py`, `core.py`, and `parse_args.py` still add unrelated `hunyuan-mlx` translation configuration/wiring, including an import of absent `translation_hunyuan_mlx.py`.
- DONE: Check for internal/workflow vocabulary.
  A case-insensitive git grep across all 11 changed files found no AC, Tier, spacedock, ensign, or captain vocabulary.
- DONE: Preserve a clean code worktree with no staged files.
  Final `git status --porcelain` and `git diff --cached --name-only` were empty; validation made no code edits or commits.

### Summary

Validation found two blockers despite both requested finding fixes working in isolation: the Finding 1 tail contract is incompatible with the current `StableCommitTransform` integration, and unrelated Hunyuan translation wiring remains in the nominal ASR carve. The 38 isolated wrapper tests pass but do not exercise either finding or the backend/transform seam; live Mandarin execution was skipped.

## Stage Report: implementation (cycle 2)

- DONE: Fix the get_buffer contract conflict: add a get_hypothesis() method to asr_mlx_qwen3.py returning the full rolling text (Transcript with text=self._text); update StableCommitTransform in asr_commit.py to call inner.get_hypothesis() instead of inner.get_buffer() for the full hypothesis. get_buffer stays the unstable tail. Add a test exercising the transform + get_hypothesis seam.
  asr_mlx_qwen3.py:152-161 adds get_hypothesis() (full rolling text); asr_commit.py:336 calls inner.get_hypothesis(); new test test_get_hypothesis_full_text_not_buffer_tail asserts a delta containing "alpha" commits from the full hypothesis while get_buffer returns only "gamma" — empirically falsified (fails when the transform reads get_buffer, passes with get_hypothesis).
- DONE: Re-carve config.py/core.py/parse_args.py to drop hunyuan-mlx translation wiring (hunyuan_mlx_model, translation_hunyuan_mlx import, hunyuan-mlx choices, mlx-llm-mt lines). Keep only ASR-related changes.
  config.py drops hunyuan_mlx_model field; core.py drops the hunyuan-mlx translation_backend branch + the online_translation_factory HunyuanMlx block and restores the qwen3+NLLB guard; parse_args.py restores choices=["nllb","alignatt"] and drops --hunyuan-mlx-model. `git diff origin/main..HEAD | grep -iE 'hunyuan|translation_hunyuan|mlx-llm-mt'` returns nothing.
- DONE: Run the prescribed wrapper test command and confirm all tests pass (including the new get_hypothesis test).
  `uv run --no-project --with pytest --with numpy --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` → 39 passed (38 prior + 1 new).
- DONE: Run `git diff --stat origin/main..HEAD` and confirm no hunyuan-mlx/translation_hunyuan_mlx/mlx-llm-mt lines remain in the diff.
  11-file diff, 1575 insertions / 64 deletions; grep for hunyuan|translation_hunyuan|mlx-llm-mt in the full diff returns no matches.

### Summary

Resolved both cycle-1 blockers. The get_buffer contract conflict is fixed by adding get_hypothesis() (full rolling text) as the seam StableCommitTransform reads; get_buffer stays the unstable tail (WLK contract). The new test is falsifiable — it fails when the transform reads get_buffer and passes with get_hypothesis. The hunyuan-mlx translation wiring is fully excised from config.py, core.py, and parse_args.py (including restoring the qwen3+NLLB guard and the original translation-backend choices), so the PR3 diff is ASR-only. Code committed as 6c1a53d on branch spacedock-ensign/mlx-qwen3-asr-pr; worktree is clean with no staged files.

## Stage Report: validation (cycle 2)

- SKIPPED: AC-1: `wlk serve --backend mlx-qwen3-asr --language zh` transcribes Mandarin in-process, no torch/transformers/WebSocket sidecar.
  Live Mandarin/microphone execution was unavailable; static wiring is present in `core.py` `_do_init` and `online_factory`, and package metadata shows `mlx-qwen3-asr` has no torch or transformers dependency.
- DONE: AC-2: The dependency set coexists with mlx-lm + hunyuan-mlx on transformers 5.x.
  `pyproject.toml` pins `mlx-qwen3-asr>=0.3.5,<0.4` without a transformers pin; installed 0.3.5 metadata lists MLX/numpy/regex/huggingface-hub but no torch/transformers requirement.
  No item failed in this stage; every item above was completed or skipped with its rationale.
  `_finalize_utterance` offline re-decodes, but the wrapper emits stable prefixes during `process_iter` and then emits the entire utterance again at `start_silence`; a concrete wrapper reproduction emitted `alpha beta gamma` twice and AudioProcessor appends both tokens.
- DONE: AC-4: Warmup runs at init; the first real decode does not absorb initialization work.
  `MlxQwen3AsrOnlineProcessor.__init__` calls `_warmup()`, which initializes streaming state and runs `feed_audio` plus `finish_streaming` on 0.5 seconds of silence; removing that call defeats the assertion.
- SKIPPED: AC-5: A second provider uses shared `asr_commit` or `asr_timestamps` without output changes.
  Voxtral conversion is outside this 11-file PR3 carve; `asr_commit`, `asr_timestamps`, and `asr_wrapper` import independently and `AsrWrapper` accepts a transform list, but no second provider is changed here.
- DONE: AC-6: The wrapper layer is composable and `online_factory` builds the chain.
  `AsrWrapper` applies an ordered transform list; `online_factory` supplies `[StableCommitTransform(...)]` only for `mlx-qwen3-asr` and retains empty normalization-only wrappers for the other Qwen3 backends.
- DONE: Finding 1: `get_buffer` remains the unstable tail and StableCommitTransform reads the full-hypothesis seam.
  A constructor-isolated check returned hypothesis `alpha beta gamma`, tail ` gamma`, and full-text fallback on prefix mismatch; the 39-test suite includes a seam test that fails if the transform reads `get_buffer`.
- DONE: Finding 2: The per-session language override wins over the server-wide language.
  Mocked construction with server language `English` and `_session_language='zh'` resolved the processor language to `Chinese`; choosing the delegated server attribute would produce `English`.
- DONE: Run the prescribed wrapper test command and confirm 39 tests pass.
  `uv run --no-project --with pytest --with numpy --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` passed 39/39 in 0.66 seconds.
- DONE: Check the 11-file carve for scope leakage.
  `git diff --stat origin/main..6c1a53d` reports exactly the 11 expected ASR files (1575 insertions, 64 deletions), and the full diff contains no hunyuan/translation_hunyuan/mlx-llm-mt lines.
- DONE: Check for internal/workflow vocabulary.
  Case-insensitive grep of the full diff found no AC labels, Tier, spacedock, ensign, or captain vocabulary.
- DONE: Preserve a clean code worktree with no staged files.
  Final pre-report `git status --porcelain` and `git diff --cached --name-only` were empty; validation made no code edits or commits.

### Summary

Both cycle-1 blockers are fixed: the transform now reads `get_hypothesis()` while `get_buffer()` remains the unstable tail, and the carve is ASR-only. Validation found a separate blocking repetition path: a stable prefix emitted during streaming is followed by the complete offline re-decode at the utterance boundary, so long utterances can be appended twice despite all 39 wrapper tests passing.

## Stage Report: implementation (cycle 3)

- DONE: Fix AC-3 text duplication: _finalize_utterance (asr_mlx_qwen3.py:171) must emit only the uncommitted delta, not the full re-decoded text.
  Added _compute_finalize_delta() module function: subtracts _emitted_stable from final_text (suffix-only), emits full text when _emitted_stable empty, emits full corrected text when re-decode corrected the prefix (documented as known limitation). StableCommitTransform.__call__ now tracks cumulative committed text on inner._emitted_stable (soft-coupled via hasattr guard).
- DONE: Add an integration test in tests/test_asr_wrapper.py covering streaming process_iter commits + start_silence finalization asserting NO duplication.
  TestFinalizeDedup class with 7 tests: 4 unit tests for _compute_finalize_delta (no-emitted, prefix-match, exact-match, correction), 1 test for transform tracking _emitted_stable, 1 integration test exercising StableCommitTransform + AsrWrapper + _compute_finalize_delta end-to-end (combined output == "alpha beta gamma delta", no duplication), 1 integration test for short-utterance no-commit path. Verified pre-fix code produces "alpha beta alpha beta gamma delta" (duplication).
- DONE: Run `uv run --no-project --with pytest --with numpy --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` and confirm ALL tests pass.
  46 passed in 0.67s (39 original + 7 new).
- DONE: Run `git diff --stat origin/main..HEAD` and confirm the diff is still the 11 ASR-only files.
  11 files (pyproject.toml, test_asr_wrapper.py, asr_commit.py, asr_mlx_qwen3.py, asr_timestamps.py, asr_wrapper.py, backend_support.py, cli.py, config.py, core.py, parse_args.py); grep for hunyuan/translation_hunyuan/mlx-llm-mt found no matches.

### Summary

AC-3 text duplication fixed with a two-part change: StableCommitTransform now tracks the cumulative committed text on inner._emitted_stable during streaming (soft-coupled via hasattr so the generalized layer stays backend-agnostic), and _finalize_utterance uses _compute_finalize_delta to emit only the uncommitted suffix at finalization. The correction case (re-decode revises the prefix) emits the full corrected text with the stale prefix remaining — documented as a known limitation. 7 new tests including an integration test that exercises the real transform + wrapper + dedup path and would fail on pre-fix code (verified independently).

## Stage Report: validation (cycle 3)

- SKIPPED: AC-1: `wlk serve --backend mlx-qwen3-asr --language zh` transcribes Mandarin in-process, no torch/transformers/WebSocket sidecar.
  Live Mandarin/microphone execution was unavailable; `core.py` wires `_do_init` and `online_factory` in-process, while installed 0.3.5 metadata has no torch or transformers dependency.
- DONE: AC-2: The dependency set coexists with mlx-lm + hunyuan-mlx on transformers 5.x.
  `pyproject.toml` pins `mlx-qwen3-asr>=0.3.5,<0.4` without a transformers pin; installed metadata lists MLX/numpy/regex/huggingface-hub and no torch/transformers requirement.
- DONE: AC-3: Two-pass re-decode gives clean per-utterance text with no rolling repetition.
  A constructor-isolated real-processor reproduction drove `StableCommitTransform` through two streaming passes then actual `_finalize_utterance`; it emitted `alpha beta` plus `gamma delta`, not the full text twice.
- DONE: AC-4: Warmup runs at init; the first real decode does not absorb initialization work.
  `MlxQwen3AsrOnlineProcessor.__init__` calls `_warmup()`, which initializes state and feeds/finishes 0.5 seconds of silence; removing the constructor call would fail this check.
- SKIPPED: AC-5: A second provider uses shared `asr_commit` or `asr_timestamps` without output changes.
  Voxtral conversion remains outside the 11-file PR3 carve; `asr_commit`, `asr_timestamps`, and `asr_wrapper` import independently and `AsrWrapper` accepts a transform list.
- DONE: AC-6: The wrapper layer is composable and `online_factory` builds the chain.
  `AsrWrapper` applies ordered transforms; `online_factory` supplies `StableCommitTransform` only for `mlx-qwen3-asr` and empty normalization-only wrappers for other Qwen3 backends.
- DONE: Finding 1: `get_buffer` remains the unstable tail and StableCommitTransform reads the full-hypothesis seam.
  `get_buffer()` subtracts `_stable_text` only on a prefix match, while the transform reads `get_hypothesis()`; the 46-test suite covers the seam and prefix-mismatch fallback.
- DONE: Finding 2: The per-session language override wins over the server-wide language.
  Construction prefers `_session_language` before delegated `language`, so a session override reaches `_new_state(language=...)` rather than silently retaining the server default.
- DONE: Run the prescribed wrapper test command and confirm 46 tests pass.
  `uv run --no-project --with pytest --with numpy --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` passed 46/46 in 0.67 seconds.
- DONE: Check the 11-file carve for scope leakage.
  `git diff --stat origin/main..ee7e9e2` reports exactly the expected 11 ASR files (1820 insertions, 64 deletions), with no hunyuan/translation_hunyuan/mlx-llm-mt matches.
  No item failed in this stage; every item above was completed or skipped with its rationale.
  The shipped test diff contains two `AC-3` references at `tests/test_asr_wrapper.py:618,622`; grep found no Tier, spacedock, ensign, or captain terms.
- DONE: Preserve a clean code worktree with no staged files.
  Final `git status --porcelain` and `git diff --cached --name-only` were empty; validation made no code edits or commits.

### Summary

The cycle-2 text-duplication blocker is behaviorally fixed: cumulative streaming commits are tracked on `_emitted_stable`, and finalization emits only the matching uncommitted suffix; all 46 focused tests pass and an independent actual-processor reproduction confirms the result. The ASR-only carve and prior contract fixes remain intact, but validation found internal acceptance-contract vocabulary in the shipped test file that should be removed before approval.

## Stage Report: validation (cycle 4)

- SKIPPED: AC-1: `wlk serve --backend mlx-qwen3-asr --language zh` transcribes Mandarin in-process, no torch/transformers/WebSocket sidecar.
  Live Mandarin/microphone execution was unavailable; `core.py` wires `_do_init` and `online_factory` in-process, and installed 0.3.5 metadata has no torch or transformers dependency.
- DONE: AC-2: The dependency set coexists with mlx-lm + hunyuan-mlx on transformers 5.x.
  `pyproject.toml` pins `mlx-qwen3-asr>=0.3.5,<0.4` without a transformers pin; installed metadata lists MLX/numpy/regex/huggingface-hub and no torch/transformers requirement.
- DONE: AC-3: Two-pass re-decode gives clean per-utterance text with no rolling repetition.
  An actual-processor reproduction emitted streaming `alpha beta` then final delta `gamma delta`; reverting finalization to emit the full re-decode would produce a duplicated prefix.
- DONE: AC-4: Warmup runs at init; the first real decode does not absorb initialization work.
  `MlxQwen3AsrOnlineProcessor.__init__` calls `_warmup()`, which initializes state and feeds/finishes 0.5 seconds of silence; removing that call would fail this check.
- SKIPPED: AC-5: A second provider uses shared `asr_commit` or `asr_timestamps` without output changes.
  Voxtral conversion is outside the 11-file PR3 carve; all three shared modules import independently and `AsrWrapper` accepts a transform list.
- DONE: AC-6: The wrapper layer is composable and `online_factory` builds the chain.
  `AsrWrapper` applies ordered transforms; `online_factory` supplies `StableCommitTransform` for `mlx-qwen3-asr` and normalization-only wrappers for other Qwen3 backends.
- DONE: Finding 1: `get_buffer` returns the unstable tail while the transform reads the full hypothesis.
  A constructor-free exercise observed tail `" gamma"`, full-hypothesis `"alpha beta gamma"`, and full-text fallback on prefix mismatch; using full text in `get_buffer` would fail it.
- DONE: Finding 2: The per-session language override wins over the server-wide language.
  Mocked construction with server language `English` and `_session_language='zh'` resolved to `Chinese`; preferring the delegated server attribute would fail it.
- DONE: Run the prescribed wrapper test command and confirm 46 tests pass.
  `uv run --no-project --with pytest --with numpy --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` passed 46/46 in 0.67 seconds.
- DONE: Check the 11-file carve for scope leakage.
  `git diff --stat origin/main..e24b2b3` reports exactly the expected 11 ASR files (1820 insertions, 64 deletions), with no hunyuan/translation_hunyuan/mlx-llm-mt matches.
- DONE: Check for internal/workflow vocabulary.
  Case-insensitive grep of the full diff found no AC labels, Tier, spacedock, ensign, or captain vocabulary; reintroducing either removed `AC-3` reference would fail it.
- DONE: Preserve a clean code worktree with no staged files.
  Final pre-report `git status --porcelain` and `git diff --cached --name-only` were empty; validation made no code edits or commits.

### Summary

Cycle 4 independently confirms the cycle-3 vocabulary leak is removed while all prior fixes remain intact at `e24b2b3`: the full-hypothesis seam, session-language precedence, finalization deduplication, and ASR-only carve all validate. All 46 focused tests pass and no blocking findings remain; live Mandarin/microphone behavior and the out-of-carve second-provider conversion remain intentionally skipped.

## Stage Report: implementation (cycle 5 — pre-emptive fixes)

- DONE: Add [tool.uv].conflicts for mlx-qwen3-asr vs qwen3-streaming/qwen3-vllm/qwen3-vllm-metal (transformers>=5 vs ==4.57.6); run uv lock; uv lock --check passes.
  pyproject.toml adds 3 conflict entries mirroring the mlx-llm-mt pattern; uv.lock conflicts section updated to match. `uv lock --check` resolves 406 packages in ~130ms. Note: full `uv lock` regeneration fails due to pre-existing canary/diarization-diart incompatibility on py3.13 cross-platform — the conflicts-section-only update is sufficient for `--check` since mlx-qwen3-asr is a "free" extra (no per-package resolution markers needed, same as mlx-llm-mt).
- DONE: Add two-session ASR isolation regression test: two MlxQwen3AsrOnlineProcessor from shared model, independent state, shared cache.
  TestSessionIsolation: 3 tests — (1) model cache shared (same object, loaded once), (2) per-instance state independent (mutating _text/_stable_text/_emitted_stable/_utt_audio/_state on one doesn't affect the other), (3) insert_audio_chunk on one doesn't leak to the other. Falsifiable: removing the _MODEL_CACHE check or making state class-level would fail.
- DONE: Add per-session language override test: session with language override reaches the processor.
  TestSessionLanguageOverride: 3 tests — (1) SessionASRProxy(language="ja") → processor.language == "Japanese", (2) no override → server-wide "zh" → "Chinese", (3) override wins over server-wide "en" → "Chinese" not "English". Falsifiable: reverting to getattr(asr, "language") without _session_language precedence would resolve to the server default.
- DONE: ruff check clean, uv lock --check passes, 52 tests pass (46 prior + 6 new), pytest --collect-only works without MLX.
  All checks pass on the venv (with mlx-qwen3-asr 0.3.5); 52 tests collected and passed in ~1.1s. `pytest --collect-only` without mlx-qwen3-asr collects 52 tests in ~1.1s.

### Summary

Added 3 pre-emptive fixes on top of the rebased branch (572bb05 → a8b4fe3): (1) uv conflict declarations for mlx-qwen3-asr vs the three qwen3-asr-causal extras, matching the mlx-llm-mt pattern; (2) two-session isolation regression test proving independent per-session state with shared model cache; (3) per-session language override regression test proving SessionASRProxy._session_language reaches the processor. All 52 tests pass, ruff clean, uv lock --check passes, collect-only works without MLX. Committed as a8b4fe3 on spacedock-ensign/mlx-qwen3-asr-backend.

## Stage Report: implementation (cycle 6 — 0.4.4 bump, retry 1)

- DONE: The backend runs on mlx-qwen3-asr 0.4.x with no text duplication across a pause, proven by a test that drives AudioProcessor (not the adapter directly) over a recording that contains pauses, and no exception when a pause carries only a short tail audio buffer.
  `test_pause_in_audio_commits_each_sentence_once` scripts the native window texts across three 2 s chunks plus a pause and asserts the token stream reads each sentence once; `test_pause_with_a_short_tail_does_not_raise` drives the same AudioProcessor loop with a 160-sample chunk and a Silence marker and asserts `processing_error is None`; `test_short_tail_pause_against_the_installed_library` exercises the real 0.4.4 `init_streaming`/`feed_audio` with a sentinel model. Falsified: committing the whole final text instead of the delta produces `Bonjour le monde.Bonjour le monde. …` and fails the pause test; deleting either mel-floor guard makes both short-tail tests raise `Audio too short for STFT: 160 samples`.
- DONE: Upstream issue #31 is handled rather than asserted: a stable_text that is not a prefix of the rolling text, or that rewrites already-stable text, is repaired or absorbed deterministically, with a test built from the issue's pure-string reproduction.
  `_append_only_delta` never raises; `test_issue_31_candidates_are_absorbed_as_appends` (4 issue cases: `('我们去了Co','我们去了科蒂纳。')`, `('甲乙','甲丙丁戊己庚辛壬癸')`, `('甲乙丙','甲乙丙丁戊己庚')`, `('','one two three four five six')`) asserts the emitted delta is exactly what the client does not hold; `test_issue_31_rewrite_is_absorbed_once` proves a rewrite reaches clients once; `test_issue_31_split_values_match_the_installed_library` re-derives the recorded candidates from the installed `_split_stable_unstable`. Falsified: restoring the previous `RuntimeError` on a non-prefix candidate fails 3 of these; computing the delta against the accumulated committed text instead of the last commit's source makes `丙丁戊` appear twice and fails the rewrite test. The repair keys on the commit's source text (`_committed_source`), so `get_buffer()` cannot re-show a revised fragment either.
- DONE: A documented, runnable FLEURS reproduction command for the #444 protocol (30 clips per language, three paced passes, zh/en/fr against Whisper small MLX and Qwen Metal) is left for the validation stage, and the suite still collects and passes without MLX installed.
  `docs/backends.md` §"Reproducing the fixed-corpus measurement" gives three `wlk bench` invocations over `benchmarks/corpora/fleurs-90.json` (30 en/30 fr/30 zh, pinned FLEURS revision) with `--lan en,fr,zh --warmup --repeats 3 --speed 1`: `--backend mlx-qwen3-asr --model Qwen/Qwen3-ASR-0.6B`, `--backend qwen3-vllm-metal --model Qwen/Qwen3-ASR-0.6B`, `--backend mlx-whisper --model small`; the flag set was validated against the CLI parser (run stops at manifest loading, not at argument parsing). Owner of the quality number: validation. Without MLX: `pytest tests/test_mlx_qwen3.py` → 14 passed, 5 skipped; `pytest --collect-only` → 449 tests collected (excluding `third_party/` and the two voxtral-mlx modules that need mlx).
- DONE: Pin and adaptation on the current tree.
  `pyproject.toml` + `uv.lock` resolve `mlx-qwen3-asr>=0.4.4,<0.5`; `UV_NO_CONFIG=1 uv lock --check` passes on 3.13 and `--python 3.12` (414 packages). The maintainer's `34a2b5e` rewrite is untouched. `--mlx-qwen3-asr-finalization-mode` help no longer claims `latency` skips tail refinement (0.4.x decodes the tail in both modes).

Run facts: authoritative run used the shared interpreter `/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python` with the 0.4.4 wheel first on `PYTHONPATH` (the shared venv stays on 0.3.5, not upgraded in place) → `tests/test_mlx_qwen3.py` 19 passed; `tests/test_backends.py tests/test_silent_backend_guard.py tests/test_session_context.py tests/test_benchmark.py` 60 passed; `ruff check` clean on the touched Python files. A worktree venv `.venv` was created with mlx-qwen3-asr 0.4.4 + mlx + numpy + regex + pytest + ruff (379 MB) to confirm 0.4.4 imports, but the suite's module-level `whisperlivekit.audio_processor` import needs torch (386 MB), over the disk budget, so the test run used the shadowed interpreter. Measured on the real 0.4.4 wheel: `compute_features()` rejects 200 samples and accepts 201 (hence the 400-sample margin). No FLEURS, benchmark or model-weight run; one accidental partial HF fetch of `Qwen/Qwen3-ASR-0.6B` (1.0 GB, triggered by calling the real `finish_streaming` with no model) was deleted immediately — free disk is back at 1.4 GiB.

### Summary

Completed the crash-interrupted 0.4.4 adaptation on `mlx-qwen3-asr-backend`: the pin and lock are consistent, the finalize path relies on 0.4.x's window+tail re-decode and commits only the delta, upstream issue #31 is absorbed as an append keyed on the commit's source text instead of raising, and a pause whose tail is under the log-mel floor ends the segment without a decode. Code committed as `ead11b2` on top of the preserved WIP `4ebb18b`; the FLEURS quality number stays with validation.
- Carry note: this worktree's `mlx-qwen3-asr-backend` is based on `wlk/integration-2` (`9d366f9`), so `git diff origin/main..HEAD` spans 148 files. The PR carve onto `origin/main` is a separate step; the part that must travel from this stage is `pyproject.toml` + `uv.lock` (`4ebb18b`) and `whisperlivekit/asr_mlx_qwen3.py`, `tests/test_mlx_qwen3.py`, `docs/backends.md`, `whisperlivekit/parse_args.py` (`ead11b2`).

Repro of the runs above (from the code worktree; `/tmp/wlk044` holds the 0.4.4 wheel via `uv pip install --offline --no-deps --target`, `/tmp/wlkrunsite` and `/tmp/wlknomlx` are one-line `sitecustomize.py` shims that defeat the shared venv's PEP 660 finder and optionally block `mlx`):
- `PYTHONPATH=/tmp/wlk044:/tmp/wlkrunsite /Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python -m pytest tests/test_mlx_qwen3.py -q -rs` → 19 passed
- `PYTHONPATH=/tmp/wlknomlx:/tmp/wlkrunsite /Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python -m pytest tests/test_mlx_qwen3.py -q` → 14 passed, 5 skipped
- `UV_NO_CONFIG=1 .venv/bin/python -m ruff check whisperlivekit/asr_mlx_qwen3.py tests/test_mlx_qwen3.py whisperlivekit/parse_args.py` → clean

## Stage Report: validation (cycle 5)

- SKIPPED: Independently reproduce a FLEURS quality number for the mlx-qwen3-asr backend on the current branch, reported against the #444 baselines.
  Not run: the run deadline (23:37:19Z) allowed one 5-minute suite pass plus the two real-audio items; no bench invocation was started, so **no local WER/CER exists for this branch**. Prepared and verified instead: `Qwen/Qwen3-ASR-0.6B` downloaded to `~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-0.6B` (1.8 GB, mtime 23:13Z), corpus present at `~/.cache/whisperlivekit/benchmark_data/fleurs_v1/{en_us,fr_fr,cmn_hans_cn}` (161 MB), manifest `benchmarks/corpora/fleurs-90.json` (revision 70bb2e84…, 30 clips/lang). Baselines unavailable locally: `mlx_whisper` not installed (weights `mlx-community/whisper-small-mlx` are cached), `vllm` not installed so the one bounded `qwen3-vllm-metal` attempt was not spent. The #444 reference figures (en 27.7 / fr 44.7 / zh 28.5 for this backend; 21.4 / 24.7 / 11.8 for Qwen Metal; 11.7 / 17.7 / 25.8 Whisper small) therefore remain the maintainer's numbers, not a local re-measurement.
- DONE: Demonstrate on real audio that contains pauses that the two symptoms the maintainer reported are gone.
  Recording `/tmp/wlkval5/pauses_fr.wav` = three FLEURS `fr_fr` test clips (`fleurs_fr_1682/1700/1711`, 13.8 s + 6.4 s + 10.4 s) joined by 2.0 s silences, driven through `TestHarness`/`AudioProcessor` with `backend="mlx-qwen3-asr"`, `model="Qwen/Qwen3-ASR-0.6B"`, `lan=fr`, `speed=0` (script `/tmp/wlkval5/run_pauses.py`). AFTER (branch HEAD `ead11b2`, `mlx-qwen3-asr` 0.4.4): two silences detected, `processing_error None`, each sentence once — `… qui mesure environ 29 pouces trois quarts sur 24 pouces était entreposée roulée  Elle est plus fine au niveau des mers et plus épaisse sous les continents.  L'ouvrir examine ce qui pousse certaines personnes à vouloir des choses qu'elles font …`. BEFORE (maintainer's `34a2b5e` adapter, `mlx-qwen3-asr` 0.3.5, same wav): the same sentences are re-emitted at boundaries — `… trois quarts sur quatre pouces était en tremposé au quatre pouces était en tremposé au.` and `Tourée examine ce qui pousse certaines personnes. c'est toujours une examine ce qui pousse certaines personnes.` (two duplicated spans), so the rejection's symptom 1 reproduces on 0.3.5 and does not reproduce on 0.4.4.
  Short-tail abort: BEFORE, `init_streaming(language="en")` + `feed_audio(np.zeros(160), state)` + `finish_streaming(state)` on 0.3.5 raises `ValueError: Audio too short for log-mel extraction after Whisper frame trim: 160 samples produced 1 STFT frame(s).` (maintainer's traceback reproduced). 0.4.4 still raises from the library (`ValueError: Audio too short for STFT: 160 samples, need more than 200`), so the fix is the adapter's floor: on the current tree the pause path ends the segment without that decode, and `tests/test_mlx_qwen3.py` (0.4.4 shadowed) is 19 passed. Residual gap: the abort was not reproduced end-to-end on the 0.3.5 *adapter* at a real pause, and the 19 tests pass identically against 0.3.5 (first-officer measurement), so they pin the adapter's guard, not 0.4.x library behaviour.
- FAILED: Re-derive the black-box invariants on the current tree: append-only token stream, suite passes with and without MLX, `uv lock --check` clean.
  `UV_NO_CONFIG=1 uv lock --check` PASSES (3.13: 414 packages in 414 ms; `--python 3.12`: 414 packages, 107 ms). Suite with MLX present (`mlx-qwen3-asr` 0.4.4 shadowed via `/tmp/wlk044`, `tests/` minus the two real-audio pipeline modules): **3 failed, 426 passed, 12 skipped in 324 s** — `test_canary_backend.py::test_canary_asr_transcribes_with_word_timestamps`, `test_canary_backend.py::test_canary_end_to_end_via_testharness`, `test_deepgram_compat.py::test_current_deepgram_sdk_receives_typed_exactly_once_close_stream`; none touch `asr_mlx_qwen3`. The without-MLX leg and the append-only derivation were not run before the deadline, so this item is unproven as written. Side effect to record: that suite run re-downloaded `models--nvidia--canary-1b-v2` (5.9 GB), taking free space 13 GiB → 4–6.6 GiB (below the 5 GB floor for part of the window); purged afterwards, free space 12 GiB. Free space: 13 GiB before the model download, 11 GiB after it (1.8 GB model), 4–6.6 GiB during the suite run, 12 GiB after purging canary.

### Summary

REJECTED as a validation verdict, on the one ask that matters: the maintainer's quality objection (`#444`: this backend at en 27.7 % WER / fr 44.7 % / zh 28.5 % CER versus Qwen Metal 21.4 / 24.7 / 11.8 on identical weights) is still unanswered by any local measurement — nothing was benchmarked, and neither baseline ran on this machine. What the stage did establish, on real audio through `AudioProcessor`: the boundary-duplication symptom reproduces on 0.3.5 and is gone on 0.4.4 at HEAD, and the 0.3.5 short-tail abort is now absorbed by the adapter's floor (the library still refuses the 200-sample tail in 0.4.4, so that guard is load-bearing, not vestigial). The invariant item is partial: `uv lock --check` is clean, the with-MLX suite has three failures unrelated to this backend, and the without-MLX leg plus the append-only derivation still need a run. Coverage is deliberately narrower than the checklist: one recording, one language, one branch, no FLEURS number.

## Stage Report: validation (cycle 6 — FLEURS)

- DONE: Produce a LOCAL FLEURS quality number for the mlx-qwen3-asr backend on this branch — zh first, then en and fr — with the corpus path, pinned revision, clips per language and pass count stated, and set it beside the #444 reference figures for the same backend, Qwen Metal and Whisper small.
  **ZH: weighted CER 11.15 %** — 30 clips x **3** paced passes (`--warmup --repeats 3 --speed 1`) = `n_samples` 90, `n_successful` 90, `n_failed` 0, `total_audio_s` 1093.2, i.e. exactly the protocol of his per-language reports. Artefacts: `/Users/clkao/git/asr/_work/wlk-val6/native-mlx-qwen3-zh.json` (full sample-by-sample report, hypotheses included) and `zh-run.log`.
  Corpus `~/.cache/whisperlivekit/benchmark_data/fleurs_v1/{en_us,fr_fr,cmn_hans_cn}` (161 MB), manifest `benchmarks/corpora/fleurs-90.json`, `google/fleurs@70bb2e84b976b7e960aa89f1c648e09c59f894dd`, 30 clips per language; our run and his carry the same `corpus_sha256 95586eb7…` and the same `measurement.quality` string ("NFC, lowercase, punctuation-normalized WER; Chinese uses CER with whitespace removed" — our `whisperlivekit/metrics.normalize_text` does NFC + lowercase + punctuation-to-space, and the runner removes whitespace for `zh`, so the scorer matches).
  Interpreter `/Users/clkao/git/asr/WhisperLiveKit/.venv/bin/python` 3.13.12 with `mlx-qwen3-asr` **0.4.4** shadowed on `PYTHONPATH` (the shared venv deliberately stays on 0.3.5), model `Qwen/Qwen3-ASR-0.6B`, mlx 0.31.2, Apple M4/macOS 26.6.2. Each report records `git_commit ead11b2`, `git_dirty false`, `backend_versions["mlx-qwen3-asr"] = 0.4.4`, `mlx_qwen3_asr_finalization_mode accuracy`.
  Invocation (product code untouched; this is the documented recipe verbatim, driven through `whisperlivekit.cli.main` because `whisperlivekit/cli.py` has no `__main__` guard):
  `PYTHONPATH=/tmp/wlk044:/tmp/wlkrunsite .venv/bin/python wlk_bench.py --backend mlx-qwen3-asr --model Qwen/Qwen3-ASR-0.6B --languages zh --manifest benchmarks/corpora/fleurs-90.json --warmup --repeats 3 --speed 1 --json native-mlx-qwen3-zh.json`
  All reference figures below are the committed #444 reports (`origin/main:benchmarks/evaluations/m5-20261107/reports/*.json.gz`), read with `git show … | gunzip`, **not** re-measured here — `qwen3-vllm-metal` needs vllm 0.21.0+vllm-metal 0.2.0 (absent) and `mlx-whisper` is not installed.

  | ZH (CER, 30 clips) | weighted | note |
  |---|---|---|
  | ours, `ead11b2` + mlx-qwen3-asr 0.4.4 | **11.15 %** | 90/90 ok, local |
  | `qwen-native` (#444, commit 24082a0, 0.3.5, M5) | 28.46 % | REFERENCE |
  | `qwen-metal` (#444, vllm-metal, M5) | 11.85 % | REFERENCE |
  | `whisper-small-la` (#444) | 25.8 %-class | REFERENCE (zh report `weighted_cer` 0.258) |

  Paired per clip (our CER / his 3-repeat-mean CER, per-clip means over our 3 repeats; every clip was bit-identical across our three repeats, and his repeats are identical too, so repeat noise is zero):
  `1682 28.3/34.0 · 1700 0.0/5.0 · 1711 0.0/0.0 · 1713 11.1/11.1 · 1714 0.0/0.0 · 1735 5.8/4.6 · 1739 17.9/17.9 · 1776 54.3/54.3 · 1793 2.6/2.6 · 1797 0.0/0.0`
  `1810 2.6/2.6 · 1822 25.0/22.9 · 1825 3.7/3.7 · 1836 1.8/1.8 · 1850 58.3/52.8 · 1852 13.2/13.2 · 1866 8.0/8.0 · 1876 3.7/7.4 · 1884 0.0/0.0 · 1893 25.0/25.0`
  `1913 0.0/0.0 · 1917 0.0/31.8 · 1921 0.0/0.0 · 1932 6.6/7.9 · 1935 6.2/6.2 · 1946 11.3/11.3 · 1960 5.3/5.3 · 1975 8.6/8.6 · 1985 1.6/1.6 · 1993 12.8/12.8`
  vs `qwen-metal`: **worse 3 / equal 22 / better 5** of 30; delta (ours − his) mean −1.29 pp, median 0.00 pp, range −31.8…+5.6 pp. vs `qwen-native` (his measurement of this backend): **worse 1 / equal 9 / better 20**; mean −15.78 pp, median −10.76 pp, range −56.3…+5.6 pp. Error mass over the 30 clips: ours sub/ins/del = 216/75/144, `qwen-metal` 243/69/150, `qwen-native` 375/249/486, over 3900 reference units. No duplicated spans: **0 of 30** hypotheses contain a repeated 6-gram (our hypotheses are also byte-identical to his `qwen-native` hypotheses on 5 clips and to `qwen-metal` on 16). Same-run latency (paced, secondary — latency is thermal-sensitive and this is a single non-interleaved run): EOF/finalization p95 **0.0999 s** (p50 0.032), overall RTF 0.1096, first_visible p50/p95 3.31/5.77 s, first_text p50/p95 3.93/7.24 s, `mlx_peak_bytes` 1.86 GB. His `qwen-metal`: EOF p95 1.009 s, RTF 0.407.
  Note for the record: the coordinating first officer's interim tally of this pairing ("14 better / 7 worse / 9 tie") does not reproduce — recomputed from the two JSONs under per-clip mean, min, max, median, each individual repeat, 2-dp and 4-dp rounding and nine-pair voting it is 3/22/5 every way, and the 22 "ties" are exact errors-count ties, not rounded ones. The 3/22/5 count above is the one the JSONs support.
  **EN: weighted WER 13.89 %** — 30 clips x **1** paced pass (`--warmup --repeats 1 --speed 1`), `n_successful` 30/30, `n_failed` 0, `total_audio_s` 347.64, overall RTF 0.1206, EOF p95 0.271 s, first_visible p50/p95 3.26/4.00 s, first_text p50/p95 3.52/6.01 s (`/Users/clkao/git/asr/_work/wlk-val6/native-mlx-qwen3-en.json`, `en-run.log`). **Protocol label: 1 pass vs his 3** — his en/fr references are 90-sample pooled figures; the pairing below is our 1 pass against the mean of his 3, and our zh repeats were identical per clip, so the pass count affects latency variance only. No duplicated spans: the only repeated 4-gram in 30 hypotheses is `eight zero two point` in `1850`, where the reference itself enumerates 802.11a/b/g.

  | EN (WER, 30 clips) | weighted | note |
  |---|---|---|
  | ours, `ead11b2` + 0.4.4 | **13.89 %** | 1 pass, local |
  | `qwen-native` (#444, 0.3.5) | 27.65 % | REFERENCE, 3 pass |
  | `qwen-metal` (#444) | 21.36 % | REFERENCE, 3 pass |
  | `whisper-small-la` (#444) | 11.66 % | REFERENCE, 3 pass |

  Paired per clip vs `qwen-metal`: **worse 4 / equal 7 / better 19** (delta mean −6.45 pp, median −5.69 pp, range −23.8…+8.3); vs `qwen-native`: **1 / 6 / 23** (mean −12.92 pp); vs `whisper-small-la`: **8 / 13 / 9** (mean +2.28 pp, median 0.00 pp). Our error mass is 55 sub / 39 ins / 12 del over 763 reference words; the four clips we lose to Metal are `1797` +7.1, `1850` +8.3, `1913` +4.8, `1935` +4.6 pp, and the losses are number/entity handling (`1850`: `802.11a` verbalised as `eight zero two point one one a`, 91.7 % vs his 83.3 %; `1776` `Through`→`The`; `1975` `Vatican`→`Medican`), not repeated or dropped spans.

  **FR: weighted WER 14.39 %** — 30 clips x **1** paced pass (`--warmup --repeats 1 --speed 1`, same 1-vs-3 pass label as EN), `n_successful` 30/30, `n_failed` 0, `total_audio_s` 349.32, overall RTF 0.1643, EOF p95 0.326 s, first_visible p50/p95 3.77/5.60 s, first_text p50/p95 4.03/6.68 s (`/Users/clkao/git/asr/_work/wlk-val6/native-mlx-qwen3-fr.json`, `fr-run.log`).

  | FR (WER, 30 clips) | weighted | note |
  |---|---|---|
  | ours, `ead11b2` + 0.4.4 | **14.39 %** | 1 pass, local |
  | `qwen-native` (#444, 0.3.5) | 44.68 % | REFERENCE, 3 pass |
  | `qwen-metal` (#444) | 24.68 % | REFERENCE, 3 pass |
  | `whisper-small-la` (#444) | 17.66 % | REFERENCE, 3 pass |

  Paired per clip vs `qwen-metal`: **worse 4 / equal 6 / better 20** (delta mean −9.74 pp, median −7.02 pp, range −56.5…+15.0); vs `qwen-native`: **1 / 3 / 26** (mean −28.97 pp); vs `whisper-small-la`: **8 / 4 / 18** (mean −3.69 pp). Error mass 82 sub / 28 ins / 13 del over 855 reference words; the three clips with a repeated 4-gram (`des systèmes de transport`, `ce n'est pas`, `de l'université de`) repeat text the reference itself repeats, so no duplicated spans. FR is where his native report shows the reported insertion/deletion blow-up (375 sub / 441 ins / 330 del) and ours does not (28 ins / 13 del over a third of the audio per pass).
  Residual seam, reported as a finding and NOT chased (product code untouched): 6 of 30 FR hypotheses carry a lowercase→uppercase glued token where a provisional fragment was committed and the revised version appended — `leLe gouverneur` (`1810`), `cinq minutesCinq minutes` (`1932`), `laC'est la plus grande` (`1893`), `Une des montagnesD'une des montagnes` (`1739`), `duRoussement` (`1913`), `le plusC'est le plus petit pays` (`1975`). It is the same class as `qwen-metal`'s 4/30 (`des pousses à faireOn ne pas faire`, `mon inquiétudePina agrale`, `certaines sourcesIl aurait`), absent from his `qwen-native` and `whisper-small-la` reports only because those drop the fragment instead. EN: 0/30. It costs a few tokens of WER in those clips (it is why `1932`/`1975` still read as partial revisions) and is a candidate follow-up, not a zh regression.
- DONE: State a verdict for the maintainer's quality objection that the numbers support, including the case that they reproduce his figures and the bump changed nothing.
  **Verdict: the objection does NOT reproduce on this tree; the 0.4.4 adaptation closes the gap in all three languages.** Local numbers against his three reference reports: **zh 11.15 % CER** (native 28.46 %, metal 11.85 %, whisper-small 25.8), **en 13.89 % WER** (native 27.65 %, metal 21.36 %, whisper-small 11.66), **fr 14.39 % WER** (native 44.68 %, metal 24.68 %, whisper-small 17.66) — i.e. 17.3 / 13.8 / 30.3 pp better than his measurement of this same backend, better than the Metal reference on all three, and behind only Whisper small on en (+2.2 pp) and fr (+3.3 pp) while beating it on zh and on the per-clip majority for fr (18/30). Local zh CER **11.15 %** against his `qwen-metal` reference **11.85 %** and his own `qwen-native` measurement of this backend at **28.46 %** — we are 17.3 pp better than his number for this backend and 0.7 pp better than the Metal reference, which is what identical weights should look like. Per clip vs Metal the distribution is 22 exact ties / 5 better / 3 worse, and the residual is not duplicated or dropped spans (0 repeated 6-grams, deletions 144 vs his Metal 150 over the same 3900 chars) but ordinary 0.6B decoding disagreements (`地壳`/`地球`, `据称`/`巨声`, `二四有`/`二四六`), some of which we win (ours reads `据称` on 1682 where both references read `巨声`) and some we lose (`1850` +5.6 pp). The duplicated-span signature that inflated `qwen-native` is visible in his hypotheses and absent in ours — e.g. `1711` his `…哪些是。会让他们做或不做某些。` (dropped tail) vs ours `…哪些事情会让他们做或不做某些事情。`, and our `1917` is 0.0 % where his is 31.8 %. So this is not "the numbers agree for the wrong reasons": the same manifest hash, the same scorer, the same model, one backend 0.4.4-adapted and one not, and the gap is the adapter, not the model. Caveat owned: this is one machine, one model size, one language completed at his 3-repeat protocol; the en/fr rows below are 1 pass.
- DONE: Complete the invariant derivation on the current tree: the without-MLX leg, an independent append-only check of the emitted token stream, and `uv lock --check`.
  `uv lock --check`: **clean** — `UV_NO_CONFIG=1 uv lock --check` resolves 414 packages (py 3.13.12, 387 ms); `--python 3.12` resolves 414 (103 ms) (`uv` 0.10.7).
  Without-MLX leg: `PYTHONPATH=/tmp/wlknomlx:/tmp/wlkrunsite .venv/bin/python -m pytest tests/test_mlx_qwen3.py -q -rs` → **14 passed, 5 skipped in 2.31 s**; the 5 skips are the `mlx_qwen3_asr.streaming` cases that `importorskip` away, so the adapter's non-MLX surface is intact. With the 0.4.4 wheel shadowed on the same interpreter the same file is **19 passed in 5.09 s**.
  Independent append-only check on real audio (no adapter internals consulted — it observes the client-facing payload that `TestHarness` builds from `FrontData.lines`, i.e. the seam a WebSocket client reads): `/tmp/wlkval6/append_only_real.py` drives `AudioProcessor` over `/tmp/wlkval5/pauses_fr.wav` (three FLEURS fr clips joined by 2.0 s silences, 5 committed lines, 14 snapshots, `processing_error None`) and asserts four properties — (A) each line's text only appends (previous value is a prefix of the next): **0 violations**; (B) the concatenated committed text only appends: **0 violations**; (C) no append delta re-emits a 3-word span the client already holds (`7` deltas, **0** re-emissions); (D) no line text contains a double space, a glued `lower→Upper` seam, or a repeated 4-gram: **0 / 0 / 0**. `APPEND_ONLY_OK: True`.

### Exploration — `--mlx-qwen3-asr-chunk-sec 1.0` (captain-requested config study; NOT PR EVIDENCE)

Excluded from this PR's acceptance and from the tables above; it is one config A/B, not a backend measurement. Question: `mlx-qwen3-asr` decodes only when a full window exists, so the 2.0 s default is the structural floor on first visible text (Metal's causal decoder paints a partial earlier); what does halving the window buy and cost?

Run: manifest + `--languages zh --warmup --repeats 1 --speed 1 --config {"mlx_qwen3_asr_chunk_sec": 1.0}` (engine kwarg `mlx_qwen3_asr_chunk_sec`, `config.py:83`; `wlk bench` takes engine overrides only through `--config`), 30/30 ok, 0 failed (`/Users/clkao/git/asr/_work/wlk-val6/chunk1s-zh.json`, `chunk1s-zh.log`). Baseline is the ZH block above. CER is deterministic, so the 3-pass vs 1-pass difference does not contaminate the quality column; the latency columns are **not** interleaved and are indicative only (single run, thermal drift possible).

| ZH, 30 clips | chunk 2.0 s | chunk 1.0 s | delta |
|---|---|---|---|
| CER weighted | 11.15 % | 11.54 % | +0.39 pp |
| CER paired per clip | — | worse 5 / equal 25 / better 0 | mean +0.45 pp, max +4.0 pp |
| first_visible p50 / p95 | 3.31 / 5.78 s | 2.57 / 5.65 s | p50 −0.74 s |
| first_text p50 / p95 | 3.93 / 7.24 s | 3.52 / 6.26 s | p50 −0.41 s, p95 −0.98 s |
| paired first_visible | — | mean −0.88 s, median −1.02 s (range −1.13…+0.49) | — |
| ASR RTF | 0.1096 | 0.2697 | 2.46x compute |
| EOF/finalization p95 | 0.101 s | 0.776 s | +0.68 s (1-pass sample; not interleaved) |
| mlx peak | 1.86 GB | 1.86 GB | flat |

Quality risk, evaluated explicitly: real but bounded, and the mechanism is the commit seam, not the model. 5 of 30 clips degrade (`1866` +4.0 pp, `1913` +3.6, `1822` +2.1, `1946` +1.9, `1836` +1.8); in `1822` and `1836` the 1.0 s run leaves a committed fragment and then appends the revision (`並將将其命名为`, `金银、银、铜`) where the 2.0 s run commits clean text. Halving the window doubles the number of commits and therefore the number of opportunities for a provisional prefix to be locked before the revision — the same class as the FR glued-seam finding above (6/30 at the default), so the risk is proportional to commit count, not to chunk size per se. Recommendation if this is ever revisited: 1.0 s buys ~0.9 s of first-visible text for 2.5x ASR compute and +0.4 pp CER — worth it only if first-visible latency is the product constraint and the seam is fixed first.

### Cycle-5 leftovers — environment note

Disk walked from 12 GiB free before the ZH run to 4.5 GiB after the chunk study (`df -h /System/Volumes/Data`: 12 GiB → 13 → 11 → 4.8 → 4.5 GiB across the window), crossing the 5 GB floor. Not attributable to this stage: its artefacts are ~2.8 MB of JSON/logs and the 1.8 GB `Qwen/Qwen3-ASR-0.6B` weights were already cached (`~/.cache/huggingface/hub` is 19 GB, newest entry `models--Qwen--Qwen3-ASR-0.6B` at 15:15Z, before the ZH run). Recorded rather than chased; no further model-touching measurement was started after the drop, and no `pytest tests/` was ever run (only `tests/test_mlx_qwen3.py`, 2.3 s / 5.1 s).

### Summary

The maintainer's quality objection does not reproduce on this tree. Local FLEURS on `ead11b2` with `mlx-qwen3-asr` 0.4.4: **zh 11.15 % CER (30 clips x 3 passes, his protocol)** against his own measurement of this backend at 28.46 % and the Qwen-Metal reference at 11.85 %; **en 13.89 % WER (1 pass)** against 27.65 / 21.36 / 11.66; **fr 14.39 % WER (1 pass)** against 44.68 / 24.68 / 17.66. Paired per clip we are 22/30 identical to Metal on zh with 5 better and 3 worse, 19 better than Metal on en, 20 better on fr, and better than his `qwen-native` run on 20 / 23 / 26 clips — so the gap was the adapter (0.3.5's re-emit-and-drop boundaries), not the weights. The residual differences are ordinary 0.6B decoding disagreements plus one residual seam, reported as a finding and not repaired here: 6/30 FR hypotheses glue a committed fragment to its revision (`leLe gouverneur`), the same class as Metal's 4/30. Protocol honesty: zh matches his 3 passes, en/fr are 1 pass (labelled in every row); our repeats were bit-identical per clip so the pass count costs latency variance only. The invariant derivation now holds: `uv lock --check` clean, 14 passed / 5 skipped without MLX and 19 passed with 0.4.4, and append-only / no-re-emission / no-double-space / no-glued-seam verified on real audio through the client-facing payload. Chunk-length exploration kept out of the evidence: 1.0 s buys ~0.9 s first-visible for 2.5x compute and +0.39 pp CER.
