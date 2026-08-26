"""Generic in-process decoder-LLM MT backend for WhisperLiveKit (plain mlx-lm).

This is the generic shape: any decoder-LLM MT model (Hunyuan-MT, TranslateGemma,
Aya, Qwen-MT) runs via mlx-lm in-process on Apple Silicon. The model-specific
parts — the prompt template, the EOS token, and the model registry — are
externalized into a config dict (``MTX_MODEL_CONFIGS``). Hunyuan-MT is one
config, not the backend identity.

The base variant is plain mlx-lm ``stream_generate``, no attention capture,
no simultaneous MT. ``wants_hypothesis_tail = False``. The simultaneous variant
A simultaneous variant (``CapturedAttention`` + commit policy + calibrated
heads) subclasses
this base and adds attention capture; it is a separate upgrade that stays
model-agnostic because the base is generic.

Duck-typed contract (mirrors nllw.OnlineTranslation and AlignAttRemoteEngine):
  - ``insert_tokens(items)``: committed ASRTokens; punctuation closes a segment.
  - ``process()`` -> ``(Translation|None, TimedText buffer)``: translate closed segments.
  - ``validate_buffer_and_reset()`` -> ``(Translation, TimedText)``: flush at silence/speaker-change.
  - ``insert_silence(duration)``: no-op.
  - ``wants_hypothesis_tail = False`` (the base does not draft over the
  unstable tail).

The MT input is raw ASR text (Simplified Chinese in production). OpenCC s2twp is
a display-path concern, NOT this backend's job.

This is a refactor of the earlier ``translation_hunyuan_mlx.py``: the decode loop,
the chat-template application, the sampling params, and the warmup are all
preserved — only the model-specific values are extracted into config.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from whisperlivekit.timed_objects import ASRToken, HypothesisTail, TimedText, Translation

logger = logging.getLogger(__name__)

# Hunyuan-MT's officially recommended prompt (verbatim from the model README).
# Kept here as the canonical Hunyuan config value; the generic backend reads it
# from the config dict, not as a hardcoded class attribute.
HUNYUAN_MT_PROMPT = "把下面的文本翻译成{target_lang}，不要额外解释。\n\n{text}"

# Target-language display names for the prompt. Most decoder-LLM MT prompts
# expect full language names, not ISO codes. Models that use a different
# convention can override via their prompt template.
_TARGET_LANG_NAME = {
    "en": "English",
    "zh": "中文",
    "zh-tw": "繁體中文",
    "zh-cn": "简体中文",
    "ja": "日本語",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}


@dataclass
class MlxLlmMtModelConfig:
    """Per-model config for the generic mlx-llm MT backend.

    A decoder-LLM MT model differs from another only in these values:
    the HF repo, the prompt template, the EOS token, and sampling params.
    Adding a new model is a config-dict entry, not new code.
    """

    repo: str
    #: Prompt template with ``{target_lang}`` (full language name) and ``{text}`` placeholders.
    prompt_template: str
    #: EOS token string to detect/strip from output. ``None`` → read from the tokenizer.
    eos_token: Optional[str] = None
    temp: float = 0.7
    top_p: float = 0.6
    top_k: int = 20
    repetition_penalty: float = 1.05
    max_tokens: int = 512


# Model-config registry (data, not code). Each entry is a short name → config.
# Hunyuan-MT entries:
_HY = dict(
    prompt_template=HUNYUAN_MT_PROMPT,
    eos_token="<|im_end|>",
)

MTX_MODEL_CONFIGS: Dict[str, MlxLlmMtModelConfig] = {
    "hy-mt2-1.8b-8bit": MlxLlmMtModelConfig(
        repo="mlx-community/Hy-MT2-1.8B-8bit", **_HY,
    ),
    "hy-mt2-1.8b-4bit": MlxLlmMtModelConfig(
        repo="mlx-community/Hy-MT2-1.8B-4bit", **_HY,
    ),
    "hy-mt2-7b-4bit": MlxLlmMtModelConfig(
        repo="mlx-community/Hy-MT2-7B-4bit", **_HY,
    ),
    "hy-mt2-7b-8bit": MlxLlmMtModelConfig(
        repo="mlx-community/Hy-MT2-7B-8bit", **_HY,
    ),
    "hunyuan-mt-7b-4bit": MlxLlmMtModelConfig(
        repo="mlx-community/Hunyuan-MT-7B-4bit", **_HY,
    ),
    "hunyuan-mt-7b-8bit": MlxLlmMtModelConfig(
        repo="mlx-community/Hunyuan-MT-7B-8bit", **_HY,
    ),
    # --- Second config family ---------------------------------------
    # A different repo + prompt loads without new code — only the config dict
    # changes. This is a placeholder (not a shipped model); the dry
    # import/construct check (test_mlx_llm_mt_config) verifies it resolves.
    "translategemma-4b-4bit": MlxLlmMtModelConfig(
        repo="mlx-community/TranslateGemma-4b-4bit",
        prompt_template="Translate the following text into {target_lang}. Output only the translation.\n\n{text}",
        eos_token=None,  # read from the tokenizer at load time
    ),
}


class MlxLlmTranslation:
    """Generic in-process decoder-LLM MT backend via mlx-lm (the base variant).

    One shared model instance per repo per process (load is expensive); the
    OnlineTranslation contract is stateless across sessions except for the
    per-instance segment buffer.
    """

    # The base variant does not opt into the unstable ASR tail.
    wants_hypothesis_tail = False

    _MODEL_CACHE: Dict[str, Tuple[Any, Any]] = {}  # repo → (model, tokenizer)

    def __init__(
        self,
        model_id: str = "hy-mt2-1.8b-8bit",
        target_language: str = "en",
        warmup: bool = True,
    ):
        self._model_id = model_id
        config = MTX_MODEL_CONFIGS.get(model_id)
        if config is None:
            available = ", ".join(sorted(MTX_MODEL_CONFIGS))
            raise ValueError(
                f"Unknown mlx-llm-mt model '{model_id}'. "
                f"Available: {available}"
            )
        self._config = config
        self._target_language = target_language
        self._target_name = _TARGET_LANG_NAME.get(target_language, target_language)
        # Per-instance segment state.
        self._buffer_tokens: List[ASRToken] = []
        self._buffer_start: Optional[float] = None
        self._pending_finals: List[Tuple[str, float, float]] = []  # (text, start, end)
        self._last_buffer = TimedText()
        # The unstable ASR tail (HypothesisTail) — accepted (not dropped) when
        # ``wants_hypothesis_tail`` is True. This base does not draft
        # over it; a simultaneous subclass reads ``self._tail.text``
        # to draft ahead and commits only against the committed prefix.
        # Forward-compatible: a subclass overrides ``process`` to use it;
        # this base stores it so the pipeline contract holds either way.
        self._tail: Optional[HypothesisTail] = None
        self._eos_token = config.eos_token  # may be None → resolved at load
        if warmup:
            self._warmup()

    # ------------------------------------------------------------------
    # Model load + decode (generic; config-driven)
    # ------------------------------------------------------------------

    def _warmup(self) -> None:
        """Run one short decode to absorb Metal kernel compilation now, so the
        first real sentence's translation doesn't stall for ~10s."""
        try:
            self._translate_text("warmup。")
        except Exception as exc:  # warmup is non-fatal
            logger.debug("mlx-llm-mt warmup failed (non-fatal): %s", exc)

    @classmethod
    def _ensure_model(cls, config: MlxLlmMtModelConfig):
        repo = config.repo
        if repo not in cls._MODEL_CACHE:
            from mlx_lm import load  # lazy; mlx-lm is an extra
            logger.info("Loading MT model %s ...", repo)
            cls._MODEL_CACHE[repo] = load(repo)  # (model, tokenizer) tuple
        return cls._MODEL_CACHE[repo]

    def _translate_text(self, text: str) -> str:
        from mlx_lm import stream_generate  # lazy import in method scope
        from mlx_lm.sample_utils import make_logits_processors, make_sampler

        model, tokenizer = self._ensure_model(self._config)
        # Resolve the EOS token lazily (may need the tokenizer).
        if self._eos_token is None:
            self._eos_token = getattr(tokenizer, "eos_token", "") or ""
        eos = self._eos_token
        content = self._config.prompt_template.format(
            target_lang=self._target_name, text=text
        )
        # Decoder-LLM MT models are chat models — apply the chat template (a
        # bare prompt hallucinates and rambles past EOS).
        messages = [{"role": "user", "content": content}]
        prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        sampler = make_sampler(
            temp=self._config.temp,
            top_p=self._config.top_p,
            top_k=self._config.top_k,
        )
        processors = make_logits_processors(
            repetition_penalty=self._config.repetition_penalty
        )
        out = ""
        for chunk in stream_generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=self._config.max_tokens,
            sampler=sampler,
            logits_processors=processors,
        ):
            out += chunk.text if hasattr(chunk, "text") else str(chunk)
            if eos and out.endswith(eos):
                break
        if eos:
            out = out.replace(eos, "")
        return out.strip()

    # ------------------------------------------------------------------
    # WLK 5-method contract (model-agnostic; unchanged from the HY version)
    # ------------------------------------------------------------------

    def insert_tokens(self, items: List[Any]) -> None:
        for item in items:
            # Accept the unstable ASR tail (HypothesisTail). This base does not
            # draft over it, but must not drop it — the pipeline sends it when
            # ``wants_hypothesis_tail`` is True, and dropping it breaks the
            # contract. A simultaneous subclass reads ``self._tail`` in ``process``.
            if isinstance(item, HypothesisTail):
                self._tail = item
                continue
            if not isinstance(item, ASRToken):
                continue
            if not item.text or not item.text.strip():
                continue
            if self._buffer_start is None:
                self._buffer_start = item.start
            self._buffer_tokens.append(item)
            # Punctuation closes the segment (mirror AlignAtt's _pending_finals).
            if item.has_punctuation():
                text = "".join(t.text for t in self._buffer_tokens).strip()
                self._pending_finals.append((text, self._buffer_start, item.end))
                self._buffer_tokens = []
                self._buffer_start = None
                self._tail = None

    def process(self) -> Tuple[Optional[Translation], TimedText]:
        # Translate any closed (punctuated) segments; emit the first.
        if self._pending_finals:
            text, start, end = self._pending_finals.pop(0)
            try:
                mt = self._translate_text(text)
            except Exception as exc:
                logger.warning("mlx-llm-mt translate failed: %s", exc)
                return None, self._last_buffer
            tr = Translation(start=start, end=end, text=mt)
            self._last_buffer = TimedText(start=start, end=end, text=mt)
            return tr, self._last_buffer
        # No closed segment: emit the running partial as the buffer (untranslated).
        if self._buffer_tokens:
            text = "".join(t.text for t in self._buffer_tokens).strip()
            start = self._buffer_start or 0.0
            end = self._buffer_tokens[-1].end
            self._last_buffer = TimedText(start=start, end=end, text=text)
        return None, self._last_buffer

    def validate_buffer_and_reset(self) -> Tuple[Translation, TimedText]:
        """Silence / speaker-change boundary: flush the open segment now."""
        if self._buffer_tokens:
            text = "".join(t.text for t in self._buffer_tokens).strip()
            start = self._buffer_start or 0.0
            end = self._buffer_tokens[-1].end
            self._pending_finals.append((text, start, end))
            self._buffer_tokens = []
            self._buffer_start = None
        # The open utterance is closed; the unstable tail no longer applies.
        self._tail = None
        if self._pending_finals:
            text, start, end = self._pending_finals.pop(0)
            try:
                mt = self._translate_text(text)
            except Exception as exc:
                logger.warning("mlx-llm-mt validate translate failed: %s", exc)
                mt = ""
            tr = Translation(start=start, end=end, text=mt)
            self._last_buffer = TimedText(start=start, end=end, text=mt)
            return tr, self._last_buffer
        # Nothing to flush: return empty, NOT the stale _last_buffer (which would
        # duplicate the previous translation when the translation_processor calls
        # validate_buffer_and_reset after process already emitted it).
        return TimedText(), TimedText()

    def insert_silence(self, duration: float = None) -> None:
        pass
