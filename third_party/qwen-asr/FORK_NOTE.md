# Fork note: qwen-asr tf5-compat

This is a local fork of upstream `qwen-asr` 0.0.6 (https://github.com/Qwen/Qwen3-ASR),
vendored for the WhisperLiveKit prototype. It exists solely to fix one import-time
incompatibility with transformers 5.x.

## The patch

`src/qwen_asr/core/transformers_backend/modeling_qwen3_asr.py:986`

In transformers 5.x, `check_model_inputs` is no longer a parametrized decorator — it
takes `func` directly (see `transformers/utils/generic.py`). The upstream call
`@check_model_inputs()` therefore raises `TypeError: check_model_inputs() missing 1
required positional argument: 'func'`. The fork changes it to `@check_model_inputs`.

The `transformers` dependency is relaxed from the upstream hard pin `==4.57.6` to
`>=4.57` so the fork imports on both 4.57 and 5.x.

This is a local prototype dependency; do not upstream.
