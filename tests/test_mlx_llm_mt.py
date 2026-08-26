"""Tests for the mlx-llm-mt translation backend.

Covers:
  - The config registry has multiple model families with distinct repos
    and prompt templates. A second config loads with a different repo and
    prompt without new code.
  - ``validate_buffer_and_reset`` does not double the output: it returns
    the translation once at a silence boundary, and returns empty when
    there is nothing to flush.

These tests mock ``_translate_text`` so they run without mlx-lm or a model
download — they exercise the buffer and contract logic, not the model.
"""
from __future__ import annotations

import pytest

from whisperlivekit.timed_objects import ASRToken, TimedText, Translation
from whisperlivekit.translation_mlx_llm_mt import (
    MTX_MODEL_CONFIGS,
    MlxLlmMtModelConfig,
    MlxLlmTranslation,
)


# ---------------------------------------------------------------------------
# Config registry: multiple model families from config, not code
# ---------------------------------------------------------------------------

def test_registry_has_multiple_config_families():
    """The registry has at least two config families with distinct repos and
    prompt templates."""
    hy = MTX_MODEL_CONFIGS["hy-mt2-1.8b-8bit"]
    tg = MTX_MODEL_CONFIGS["translategemma-4b-4bit"]
    assert hy.repo != tg.repo, "repos must differ across config families"
    assert hy.prompt_template != tg.prompt_template, "prompts must differ"


def test_second_config_constructs_without_new_code():
    """Constructing the backend with a second config (warmup=False, no model
    download) resolves the right config — different repo and prompt — purely
    from the config dict, with no new code."""
    backend = MlxLlmTranslation(
        model_id="translategemma-4b-4bit", target_language="en", warmup=False
    )
    assert backend._config.repo == "mlx-community/TranslateGemma-4b-4bit"
    assert "Translate the following text" in backend._config.prompt_template
    hy = MlxLlmTranslation(
        model_id="hy-mt2-1.8b-8bit", target_language="en", warmup=False
    )
    assert hy._config.repo == "mlx-community/Hy-MT2-1.8B-8bit"
    assert backend._config.repo != hy._config.repo
    assert backend._config.prompt_template != hy._config.prompt_template


def test_unknown_model_raises():
    """An unknown model id raises a clear error listing available configs."""
    with pytest.raises(ValueError, match="Unknown mlx-llm-mt model"):
        MlxLlmTranslation(model_id="nonexistent-model", warmup=False)


def test_config_is_data_not_code():
    """Adding a new model is a config-dict entry, not a subclass."""
    custom = MlxLlmMtModelConfig(
        repo="mlx-community/some-other-mt-4bit",
        prompt_template="Translate to {target_lang}: {text}",
        eos_token="<|end|>",
    )
    assert custom.repo == "mlx-community/some-other-mt-4bit"
    assert custom.eos_token == "<|end|>"


# ---------------------------------------------------------------------------
# validate_buffer_and_reset does not double the output
# ---------------------------------------------------------------------------

def _make_backend(model_id="hy-mt2-1.8b-8bit"):
    """Create a backend with _translate_text mocked (no model download)."""
    backend = MlxLlmTranslation(model_id=model_id, target_language="en", warmup=False)
    backend._translate_text = lambda text: f"[EN:{text}]"
    return backend


def _token(text, start, end):
    return ASRToken(start=start, end=end, text=text)


def test_process_emits_translation_for_closed_segment():
    """``process()`` translates a punctuation-closed segment and returns it."""
    b = _make_backend()
    b.insert_tokens([_token("你好", 0.0, 0.5), _token("。", 0.5, 0.6)])
    tr, buf = b.process()
    assert tr is not None
    assert tr.text == "[EN:你好。]"
    assert isinstance(tr, Translation)


def test_validate_flushes_open_segment_once():
    """At a silence boundary, ``validate_buffer_and_reset`` flushes the open
    segment and returns the translation once."""
    b = _make_backend()
    b.insert_tokens([_token("你好", 0.0, 0.5)])
    tr, buf = b.validate_buffer_and_reset()
    assert tr.text == "[EN:你好]"
    assert buf.text == "[EN:你好]"


def test_validate_does_not_double_after_process():
    """After ``process()`` has already emitted a translation for a closed
    segment, ``validate_buffer_and_reset`` must not return it again. It
    returns empty, not the stale buffer."""
    b = _make_backend()
    b.insert_tokens([_token("你好", 0.0, 0.5), _token("。", 0.5, 0.6)])
    tr, buf = b.process()
    assert tr is not None
    assert tr.text == "[EN:你好。]"
    tr2, buf2 = b.validate_buffer_and_reset()
    assert not tr2.text, "validate must return empty, not a duplicate"
    assert not buf2.text, "buffer must be empty, not the stale translation"


def test_validate_empty_when_nothing_buffered():
    """``validate_buffer_and_reset`` on a fresh backend returns empty."""
    b = _make_backend()
    tr, buf = b.validate_buffer_and_reset()
    assert not tr.text
    assert not buf.text


def test_process_returns_none_when_no_closed_segment():
    """``process()`` returns (None, buffer) when there is no closed segment.
    The buffer is the running untranslated partial."""
    b = _make_backend()
    b.insert_tokens([_token("你好", 0.0, 0.5)])
    tr, buf = b.process()
    assert tr is None
    assert buf.text == "你好"


def test_insert_silence_noop():
    """``insert_silence`` is a no-op."""
    b = _make_backend()
    b.insert_tokens([_token("测试", 0.0, 0.5)])
    b.insert_silence(1.0)
    tr, buf = b.process()
    assert tr is None
    assert buf.text == "测试"


# ---------------------------------------------------------------------------
# Alias
# ---------------------------------------------------------------------------

def test_hunyuan_mlx_reexports():
    """The ``translation_hunyuan_mlx`` module re-exports the class so existing
    imports keep working."""
    from whisperlivekit.translation_hunyuan_mlx import HunyuanMlxTranslation

    assert HunyuanMlxTranslation is MlxLlmTranslation
