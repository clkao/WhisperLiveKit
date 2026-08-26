"""Backend detection and language compatibility matrix."""

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Language support per backend.
# None means all Whisper-supported languages.
# A set means only those languages are supported.
BACKEND_LANGUAGES: Dict[str, Optional[Set[str]]] = {
    "whisper": None,
    "faster-whisper": None,
    "mlx-whisper": None,
    "voxtral-mlx": None,
    "voxtral": None,
    "qwen3-streaming": None,
    # Pure-MLX Qwen3-ASR (mlx-qwen3-asr package): multilingual, same
    # language coverage as the qwen3 ASR model family.
    "mlx-qwen3-asr": None,
    # vllm-metal Qwen3-ASR with the LibriSpeech tower checkpoint: the
    # checkpoint is English-only (verified on the tower training data).
    "qwen3-vllm-metal": {"en"},
}


def backend_supports_language(backend: str, language: str) -> bool:
    """Check if a backend supports a given language code."""
    langs = BACKEND_LANGUAGES.get(backend)
    if langs is None:
        return True
    return language in langs


def detect_available_backends() -> List[str]:
    """Probe which ASR backends are importable."""
    backends = []

    try:
        import whisper  # noqa: F401
        backends.append("whisper")
    except ImportError:
        pass

    try:
        import faster_whisper  # noqa: F401
        backends.append("faster-whisper")
    except ImportError:
        pass

    try:
        import mlx_whisper  # noqa: F401
        backends.append("mlx-whisper")
    except ImportError:
        pass

    try:
        import mlx.core  # noqa: F401

        from whisperlivekit.voxtral_mlx.loader import load_voxtral_model  # noqa: F401
        backends.append("voxtral-mlx")
    except ImportError:
        pass

    try:
        from transformers import VoxtralRealtimeForConditionalGeneration  # noqa: F401
        backends.append("voxtral")
    except ImportError:
        pass

    try:
        import mlx_qwen3_asr  # noqa: F401
        backends.append("mlx-qwen3-asr")
    except ImportError:
        pass

    try:
        import mlx.core  # noqa: F401

        from whisperlivekit.qwen3_vllm_metal_asr import Qwen3VLLMMetalASR  # noqa: F401
        backends.append("qwen3-vllm-metal")
    except ImportError:
        pass

    return backends


def resolve_backend(backend: str) -> str:
    """Resolve 'auto' to the best available backend."""
    if backend != "auto":
        return backend

    available = detect_available_backends()
    if not available:
        raise RuntimeError(
            "No ASR backend available. Install at least one: "
            "pip install openai-whisper, faster-whisper, or mlx-whisper"
        )

    # Priority order
    priority = [
        "faster-whisper", "mlx-whisper", "voxtral-mlx", "voxtral",
        "whisper", "mlx-qwen3-asr", "qwen3-vllm-metal",
    ]
    for p in priority:
        if p in available:
            return p
    return available[0]
