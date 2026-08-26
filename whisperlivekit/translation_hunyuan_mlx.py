"""Re-exports the MLX translation backend class under its original name."""
from __future__ import annotations

from whisperlivekit.translation_mlx_llm_mt import (
    HUNYUAN_MT_PROMPT,
    MlxLlmTranslation,
)

HunyuanMlxTranslation = MlxLlmTranslation

__all__ = ["HunyuanMlxTranslation", "MlxLlmTranslation", "HUNYUAN_MT_PROMPT"]
