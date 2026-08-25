"""Backward-compat shim: the Hunyuan-specific translation backend name.

The implementation now lives in ``translation_mlx_llm_mt.py`` as the generic
``MlxLlmTranslation`` base. Hunyuan-MT is one config entry, not the backend
identity. This module re-exports the old names so existing imports
(``from whisperlivekit.translation_hunyuan_mlx import HunyuanMlxTranslation``)
and the ``isinstance`` check in ``core.online_translation_factory`` keep
working without changes.
"""
from __future__ import annotations

from whisperlivekit.translation_mlx_llm_mt import (
    HUNYUAN_MT_PROMPT,
    MlxLlmTranslation,
)

# Backward-compat alias: the old Hunyuan-specific class name.
HunyuanMlxTranslation = MlxLlmTranslation

__all__ = ["HunyuanMlxTranslation", "MlxLlmTranslation", "HUNYUAN_MT_PROMPT"]
