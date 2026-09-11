fix(vibevoice_asr): drop the redundant untied lm_head weight when sanitizing

## Summary

`mlx_audio.convert` fails on the released `VibeVoice-ASR-Streaming`
checkpoints with:

    ValueError: Received 1 parameters not in model: language_model.lm_head.weight.

The checkpoints declare `tie_word_embeddings: true` in `decoder_config`,
but the safetensors still ship a `language_model.lm_head.weight`. It is
byte-identical to `language_model.model.embed_tokens.weight` (verified:
max abs diff 0.0), so the checkpoint is effectively tied and the extra key
is a redundant copy.

## Fix

`Model.sanitize` now drops the lm_head weight when it is byte-identical to
the tied embedding — lossless, and strict weight loading passes. If a
checkpoint ships an lm_head that actually differs from the embedding, the
sanitizer raises a clear error instead, because the tied inference path
(`embed_tokens.as_linear`) cannot represent it.

## Validation

- `mlx_audio.convert --hf-path microsoft/VibeVoice-ASR-Streaming-1.5B
  --model-domain stt --dtype bfloat16` completes (4.2GB bf16 output with
  all tokenizer sidecars) — previously failed at weight loading.
- The converted model streams correctly with the 1.5B streaming interface
  (two 30s clips, zh and en).
- 8-bit re-measure enabled by the fix (canonical `mlx.nn.quantize` with a
  divisibility-guarded predicate on the converted checkpoint): zh whole-file
  RTF 0.369 (bf16: 0.795), en 0.453 (bf16: 1.09-1.44) — both comfortably
  faster than real-time.
