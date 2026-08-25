---
title: "qwen-asr transformers 5.x compatibility fork"
status: implementation
source: dep cleanup — unblocks qwen3-asr-causal on our Apple-Silicon prototype
score: 0.9
id: zyarn2ybkarvajyz0dd46m1r
gates:
    version: 1
    records:
        - id: gate:zyarn2ybkarvajyz0dd46m1r:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:zyarn2ybkarvajyz0dd46m1r-backlog-1
              briefing:
                id: briefing:zyarn2ybkarvajyz0dd46m1r:backlog:attempt-1:revision-1
                digest: sha256:d71b77f9a57e84c1ff3386da4dc169e200e43b17078fce5d6af6bd31c63c7f4c
                request-digest: sha256:69ee3b3fc12324e03b0e916f804f3d0c140c9a905e7ab49945ef028128a4ebce
                room-ref: ./qwen-asr-tf5-compat-fork/review/backlog/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:zyarn2ybkarvajyz0dd46m1r:backlog:1
                briefing: briefing:zyarn2ybkarvajyz0dd46m1r:backlog:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T16:55:48.567447Z"
                decision: approve
              application:
                target-stage: ideation
                state: consumed
        - id: gate:zyarn2ybkarvajyz0dd46m1r:ideation
          stage: ideation
          attempts:
            - id: gate-attempt:zyarn2ybkarvajyz0dd46m1r-ideation-1
              briefing:
                id: briefing:zyarn2ybkarvajyz0dd46m1r:ideation:attempt-1:revision-1
                digest: sha256:1a60f871591c407965cdcda8e4c2dadb95f7684d1feac88fa043c6360c76ec2f
                request-digest: sha256:d678d56522856f9cda829c448d660b8b5967c97bd268ab2ff02da3ba65c202c7
                room-ref: ./qwen-asr-tf5-compat-fork/review/ideation/briefing-1
              resolution:
                type: Resolution
                id: resolution:spacedock:zyarn2ybkarvajyz0dd46m1r:ideation:1
                briefing: briefing:zyarn2ybkarvajyz0dd46m1r:ideation:attempt-1:revision-1
                by: person:captain
                at: "2026-08-25T16:55:51.593875Z"
                decision: approve
              application:
                target-stage: implementation
                state: consumed
started: 2026-08-25T16:56:14Z
worktree: .worktrees/spacedock-ensign-qwen-asr-tf5-compat-fork
---

The qwen3-asr-causal backend uses a stronger commit policy (LocalAgreement via stable_commit) than mlx-qwen3-asr. It gives more accurate ASR text for our zh-tw prototype. But qwen3-asr-causal depends on the qwen_asr package, which fails to import on transformers 5.x.

## The blocker

One import-time error, verified in our venv (transformers 5.11.0, huggingface_hub 1.18.0):

qwen_asr/core/transformers_backend/modeling_qwen3_asr.py:986
@check_model_inputs()
TypeError: check_model_inputs() missing 1 required positional argument: 'func'

The check_model_inputs decorator signature changed in transformers 5.x. Note: is_offline_mode is NOT a blocker (present in huggingface_hub 1.18.0).

## Proposed approach

Fork qwen-asr. Patch the check_model_inputs call at modeling_qwen3_asr.py:986 to match the transformers 5.x signature. Pin the fork in our prototype install. Do not upstream — this is a local prototype dep.

## Acceptance criteria

- AC-1: qwen_asr imports on transformers 5.11.0. Verified by: python -c "import qwen_asr" exits 0.
- AC-2: qwen3-streaming backend loads and transcribes. Verified by: wlk serve --backend qwen3-streaming --language zh starts without import error.
- AC-3: stable_commit is active. Verified by: backend log shows the stable_commit flush path.

## Out of scope

- Upstreaming the fork. The vllm-metal loader swap. Any change to the decorator itself.

## Implementation summary (implementation stage)

Forked qwen-asr 0.0.6 into `third_party/qwen-asr` (editable, pinned via
`[tool.uv.sources] qwen-asr = { path = "third_party/qwen-asr", editable = true }`)
and applied three transformers-5.x compatibility patches in the forked source.

Patches (all in `src/qwen_asr/core/transformers_backend/`):
1. `modeling_qwen3_asr.py:998` — `@check_model_inputs()` -> `@check_model_inputs`.
   Transformers 5.x made the decorator take `func` directly (no longer
   parametrized); the call form raised `TypeError: ... missing 1 required
   positional argument: 'func'`. This is the named import-time blocker.
2. `configuration_qwen3_asr.py` — `Qwen3ASRConfig.__init__` sets
   `self.thinker_config` BEFORE `super().__init__()`; transformers 5.x runs
   huggingface_hub strict validation (`validate_token_ids` -> `get_text_config`
   -> `self.thinker_config`) during `super().__init__`, which previously
   raised `AttributeError: 'Qwen3ASRConfig' object has no attribute 'thinker_config'`.
3. `modeling_qwen3_asr.py` — `Qwen3ASRThinkerTextRotaryEmbedding` falls back to
   the plain `inv_freq` formula when `rope_type` ('default') is absent from
   `ROPE_INIT_FUNCTIONS` (transformers 5.x pruned the 'default' entry; only
   scaled variants remain, and config moved from `rope_scaling` to `rope_parameters`).

Dependency: `transformers` relaxed from upstream hard pin `==4.57.6` to `>=4.57`
so the fork imports on both 4.57 and 5.x.

### Acceptance results
- AC-1 SATISFIED: `python -c "import qwen_asr"` exits 0 on transformers 5.11.0
  (editable fork installed; the check_model_inputs TypeError is gone).
- AC-2 PARTIAL: the import-time error is resolved —
  `from whisperlivekit.qwen3_streaming import Qwen3StreamingASR` imports
  cleanly, and `wlk serve --backend qwen3-streaming --language zh` no longer
  fails on the import error. However full model LOAD is NOT achieved: startup
  now fails at a further transformers-5.x incompatibility —
  `AttributeError: 'Qwen3ASRThinkerConfig' object has no attribute 'pad_token_id'`
  at modeling line 1101 — with "Application startup failed." More such 5.x
  runtime incompatibilities are likely to follow.
- AC-3 NOT SATISFIED: the stable_commit flush path is not reached because the
  model never loads on transformers 5.x.

### Discovery / scope note
The spec identified a single import-time error (verified by importing). In
reality qwen_asr 0.0.6 has MULTIPLE transformers-5.x incompatibilities across
its modeling/config layer (decorator call form, config validation ordering,
RoPE init registry, config attribute presence, ...). The three patches above
are correct, minimal, non-regressing 5.x-compat shims that fix the import and
advance the load path, but completing model load + transcription (AC-2
"loads and transcribes", AC-3 stable_commit flush) requires a deeper
transformers-5.x modeling/config port — out of scope for this stage.

### Recommended next step
Spin a follow-up stage: "qwen-asr transformers-5.x runtime port" — continue
the fork patch surface (config attribute access via getattr-with-default for
`pad_token_id`/token ids, rope_scaling vs rope_parameters in forward paths,
`merge_with_config_defaults`/auto_docstring cache_position docstring
warnings, attention/SDPA path) until `wlk serve --backend qwen3-streaming`
loads the model and the e2e smoke test (`tests/data/e2e_smoke.wav`) emits the
`[qwen3-streaming] finish: flushed N words` stable_commit log line (AC-3).

### Verification commands run
- `python -c "import qwen_asr"` -> exit 0 (AC-1)
- `python -c "from whisperlivekit.qwen3_streaming import Qwen3StreamingASR"` -> OK
- `wlk serve --backend qwen3-streaming --language zh` -> past import, fails at
  model load (`pad_token_id` AttributeError)
- e2e runner (`tests/data/e2e_smoke.wav`, Qwen/Qwen3-ASR-0.6B + causal tower)
  -> fails at model load, same point.

Code commit: spacedock-ensign/qwen-asr-tf5-compat-fork @ 2604338
