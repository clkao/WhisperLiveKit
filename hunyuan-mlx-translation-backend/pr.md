feat: generic mlx-llm-mt translation backend (Hunyuan-MT, TranslateGemma)

## Summary

Add a generic, config-driven in-process translation backend for
WhisperLiveKit that runs decoder-LLM MT models via MLX on Apple Silicon.

The backend is generic: adding a model is a profile entry, not a
subclass. A profile (`MtModelProfile` in `translation_profiles.py`) holds
the prompt mechanism, EOS token, and sampling params. Two prompt
mechanisms are supported:

  - **text template**: a prompt string with `{target_lang}` and `{text}`
    placeholders. Hunyuan-MT ships two templates per its model card —
    ZH<->XX (Chinese instruction, Chinese language names) and XX<->XX
    (English instruction, English names); a resolver picks by
    source/target language.
  - **structured chat**: ISO source/target codes passed via
    `apply_chat_template`; the model chat template maps codes to full
    names. TranslateGemma uses this path.

Models shipped (mlx-community MLX-quantized checkpoints):

  Hunyuan-MT (text template):
    `hy-mt2-1.8b-8bit`   -> `mlx-community/Hy-MT2-1.8B-8bit`
    `hy-mt2-1.8b-4bit`   -> `mlx-community/Hy-MT2-1.8B-4bit`
    `hy-mt2-7b-4bit`     -> `mlx-community/Hy-MT2-7B-4bit`
    `hy-mt2-7b-8bit`     -> `mlx-community/Hy-MT2-7B-8bit`
    `hunyuan-mt-7b-4bit` -> `mlx-community/Hunyuan-MT-7B-4bit`
    `hunyuan-mt-7b-8bit` -> `mlx-community/Hunyuan-MT-7B-8bit`

  TranslateGemma (structured chat):
    `translategemma-4b-it-4bit` -> `mlx-community/translategemma-4b-it-4bit`

The `wlk bench` CLI gains `--translation-backend`, `--target-language`,
`--reference-translation`, and `--simultaneous` flags. The report shows
MT-RTF, first-translation latency, provisional-before-final,
MT-call-count, and translation accuracy (BLEU/chrF when a reference
translation is supplied).

## User impact

New `--translation-backend mlx-llm-mt` option for in-process decoder-LLM
MT on Apple Silicon. The only new dependency is `mlx-lm` (the
`mlx-llm-mt` extra). The existing `nllb` and `alignatt` paths stay
unchanged.

This PR adds a new backend. It does not modify the existing translation
contract or the audio processor. The base `MlxLlmTranslation` is a plain
translate-on-close backend: it translates a segment when punctuation
closes it, the same shape as the existing nllb path.

A separate follow-up PR adds the simultaneous-MT variant. That variant
uses an AlignAtt commit policy to overlap MT with ASR so provisional
translations appear during speech. It subclasses this generic base; it
is not part of this PR.

## Validation

Hardware: Apple M4. ASR backend: `qwen3-vllm-metal` with the causal audio
backend (`--qwen3-vllm-metal-audio-backend causal`) — the append-only KV
streaming path. WER is N/A for these samples (no matching reference
transcript; the runner skips WER when the reference is empty).

| Path | Model | MT-RTF | 1st-translation | Output |
|---|---|---|---|---|
| Hunyuan zh->en | Hy-MT2 1.8B 8bit | 0.22x | 6.9s | correct English |
| Hunyuan en->it | Hy-MT2 1.8B 8bit | 0.56x | 2.7s | correct Italian |
| TranslateGemma en->it | TranslateGemma 4B 4bit | 0.95x | 16.2s | correct Italian |
| TranslateGemma zh->en | TranslateGemma 4B 4bit | 1.07x | - | correct English |
| nllb en->it (comparison) | nllb 600M | N/A | 37.6s | correct Italian |

MT-RTF = translation compute wall-time / audio duration.

Sample outputs:
  Hunyuan zh->en: "Today, we will discuss the applications of laser in
    medicine. Laser technology can precisely remove tumor tissue..."
  Hunyuan en->it: "Concord e tornato nel suo posto tra le tende. Gli
    inglesi inviarono delle cestine piene di fiori ai francesi..."

Tests: `pytest tests/test_mlx_llm_mt.py -q` -> 11 passed.
Static checks: `ruff check` on changed files -> all checks passed.
`uv lock --check` fails on `main` (a pre-existing stale lockfile); this
PR does not touch `uv.lock`.

## Checklist

- [ ] I searched for an existing issue or discussion and linked it when relevant.
- [x] I added or updated tests for behavior changes.
- [ ] I updated documentation for user-facing changes.
- [x] I ran `ruff check .` (on changed files; all passed).
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or private data.
