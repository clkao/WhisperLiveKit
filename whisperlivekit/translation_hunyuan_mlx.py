"""In-process Hunyuan-MT translation backend for WhisperLiveKit (Tier A: plain mlx-lm).

This is the Apple-Silicon answer to WLK's translation gap: the qwen3 ASR backends
are blocked from in-process NLLB (core.py guard) and the only other built-in
path is the AlignAtt sidecar (vLLM/CUDA). This backend runs Tencent Hy-MT2
(1.8B-8bit default, 7B optional) via mlx-lm in-process on Apple Silicon.

Tier A = plain mlx-lm stream_generate, no attention capture, no simultaneous MT.
wants_hypothesis_tail = False. The simultaneous variant (Tier B: CapturedAttention
+ commit policy + calibrated heads) is a separate upgrade; see the design doc.

Duck-typed contract (mirrors nllw.OnlineTranslation and AlignAttRemoteEngine):
  - insert_tokens(items): committed ASRTokens; punctuation closes a segment.
  - process() -> (Translation|None, TimedText buffer): translate closed segments.
  - validate_buffer_and_reset() -> (Translation, TimedText): flush at silence/speaker-change.
  - insert_silence(duration): no-op.
  - wants_hypothesis_tail = False (Tier A does not draft over the unstable tail).

The MT input is raw ASR text (Simplified Chinese in production). OpenCC s2twp is
a DISPLAY-path concern, NOT this backend's job.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from whisperlivekit.timed_objects import ASRToken, TimedText, Translation

logger = logging.getLogger(__name__)

# Hunyuan-MT's officially recommended prompt (verbatim from the model README).
HUNYUAN_MT_PROMPT = "把下面的文本翻译成{target_lang}，不要额外解释。\n\n{text}"

# Sentence terminators: CJK + Latin. A segment closes when the accumulated
# source text ends with one of these, mirroring how the overlay splits for hold.
_SENT_END = "。！？.!?"

# Target-language display names for the prompt (Hunyuan expects full names).
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

# Model registry (mirrors livecaption/config.py MT_MODELS).
_MODELS = {
    "hy-mt2-1.8b-8bit": "mlx-community/Hy-MT2-1.8B-8bit",
    "hy-mt2-1.8b-4bit": "mlx-community/Hy-MT2-1.8B-4bit",
    "hy-mt2-7b-4bit": "mlx-community/Hy-MT2-7B-4bit",
    "hy-mt2-7b-8bit": "mlx-community/Hy-MT2-7B-8bit",
    "hunyuan-mt-7b-4bit": "mlx-community/Hunyuan-MT-7B-4bit",
    "hunyuan-mt-7b-8bit": "mlx-community/Hunyuan-MT-7B-8bit",
}


class HunyuanMlxTranslation:
    """In-process Hunyuan-MT translation backend (Tier A, plain mlx-lm).

    One shared model instance per process (load is expensive); the OnlineTranslation
    contract is stateless across sessions except for the per-instance segment buffer.
    """

    # Tier A: do not opt into the unstable ASR tail.
    wants_hypothesis_tail = False

    _MODEL = None  # class-level cache: (model, generate) loaded once
    _MODEL_ID = None

    def __init__(self, model_id: str = "hy-mt2-1.8b-8bit", target_language: str = "en"):
        self._model_id = model_id
        self._target_language = target_language
        self._target_name = _TARGET_LANG_NAME.get(target_language, target_language)
        # Per-instance segment state.
        self._buffer_tokens: List[ASRToken] = []
        self._buffer_start: Optional[float] = None
        self._pending_finals: List[Tuple[str, float, float]] = []  # (text, start, end)
        self._last_buffer = TimedText()
        self._warmup()

    def _warmup(self) -> None:
        """Run one short decode to absorb Metal kernel compilation now, so the
        first real sentence's translation doesn't stall for ~10s. Mirrors
        livecaption/translate.py which warms the MT model at load."""
        try:
            self._translate_text("warmup。")
        except Exception as exc:  # warmup is non-fatal
            logger.debug("Hunyuan-MT warmup failed (non-fatal): %s", exc)

    @classmethod
    def _ensure_model(cls, model_id: str):
        if cls._MODEL is None or cls._MODEL_ID != model_id:
            from mlx_lm import load  # lazy; mlx-lm is an extra
            repo = _MODELS.get(model_id, model_id)
            logger.info("Loading Hunyuan-MT model %s (%s)...", model_id, repo)
            cls._MODEL = load(repo)  # (model, tokenizer) tuple
            cls._MODEL_ID = model_id
        return cls._MODEL

    def _translate_text(self, text: str) -> str:
        from mlx_lm import stream_generate  # lazy import in method scope
        from mlx_lm.sample_utils import make_sampler, make_logits_processors
        model, tokenizer = self._ensure_model(self._model_id)
        content = HUNYUAN_MT_PROMPT.format(target_lang=self._target_name, text=text)
        # Hunyuan-MT is a chat model — apply the chat template (a bare prompt
        # hallucinates and rambles past EOS). Mirrors livecaption/translate.py.
        messages = [{"role": "user", "content": content}]
        prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        sampler = make_sampler(temp=0.7, top_p=0.6, top_k=20)
        processors = make_logits_processors(repetition_penalty=1.05)
        out = ""
        for chunk in stream_generate(model, tokenizer, prompt=prompt,
                                     max_tokens=512, sampler=sampler,
                                     logits_processors=processors):
            out += chunk.text if hasattr(chunk, "text") else str(chunk)
            if out.endswith("<|im_end|>"):
                break
        return out.replace("<|im_end|>", "").strip()

    def insert_tokens(self, items: List[Any]) -> None:
        for item in items:
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

    def process(self) -> Tuple[Optional[Translation], TimedText]:
        # Translate any closed (punctuated) segments; emit the first.
        if self._pending_finals:
            text, start, end = self._pending_finals.pop(0)
            try:
                mt = self._translate_text(text)
            except Exception as exc:
                logger.warning("Hunyuan-MT translate failed: %s", exc)
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
        if self._pending_finals:
            text, start, end = self._pending_finals.pop(0)
            try:
                mt = self._translate_text(text)
            except Exception as exc:
                logger.warning("Hunyuan-MT validate translate failed: %s", exc)
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
