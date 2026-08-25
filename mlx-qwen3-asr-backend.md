---
id: p0f67wa79kd56yh3bs0cca2e
title: mlx-qwen3-asr ASR backend + generalized ASR wrapper layer
status: ideation
source: WhisperLiveKit Apple-Silicon backend work
started:
completed:
verdict:
score:
worktree:
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
                state: pending
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
