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
pr:
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
- FAILED: AC-3: Two-pass re-decode gives clean per-utterance text and StableCommitTransform handles streaming commits.
  `_finalize_utterance` does offline re-decode, but the composed transform reads the now-tail-only `get_buffer()` and reproducibly emits `gamma`, `delta` while omitting model-stable prefix `alpha beta`.
- DONE: AC-4: Warmup runs at init so the first decode does not absorb compilation.
  `asr_mlx_qwen3.py:107-120` calls `_warmup()` during construction and feeds/finishes 0.5 s silence; removing that constructor call would fail the assertion.
- SKIPPED: AC-5: A second provider shares `asr_commit` or `asr_timestamps`.
  Voxtral conversion is outside this carve; all three shared modules import, `AsrWrapper` accepts a transform list, and their isolated tests pass.
- FAILED: AC-6: The wrapper layer is composable and `online_factory` builds the chain.
  Structural composition exists at `core.py:401-415`, but `StableCommitTransform` consumes `inner.get_buffer()` as a full rolling hypothesis while the inner now returns only its unstable tail, so the declared chain is behaviorally invalid.
- DONE: Finding 1: `get_buffer` returns the unstable tail, with full-text fallback on a prefix mismatch.
  A targeted constructor-free check observed `" gamma"` for stable `"alpha beta"` plus full `"alpha beta gamma"`, and the full text after a non-prefix stable value.
- DONE: Finding 2: The per-session language override wins over the server-wide language.
  A mocked construction with server `English` and `_session_language="zh"` produced `self.language == "Chinese"`; reverting to the delegated `language` attribute would fail.
- FAILED: Run the prescribed project-resolving wrapper test command.
  `uv run --extra test --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` failed before collection because the uninitialized `third_party/qwen3-asr-causal` submodule lacks `pyproject.toml`.
- DONE: Confirm the 38 wrapper tests pass with the required mlx-qwen3-asr dependency available.
  `uv run --no-project --with pytest --with numpy --with 'mlx-qwen3-asr>=0.3.5' pytest tests/test_asr_wrapper.py -q` passed 38/38; `uv run --no-sync` also passed 38/38.
- FAILED: Check the 11-file carve for scope leakage.
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
