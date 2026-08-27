#!/usr/bin/env python3
"""SimulST hypothesis emitter.

Drives the MLX cascade (mlx-qwen3-asr or nemotron-mlx + PR2 simul-MT)
over one devset audio, hooks per-word emission, timestamps each word
(audio-processed-time + wallclock), and writes ``hypothesis.jsonl`` +
``manifest.json`` into a run output directory.

Two modes:
  - ``asr-only``: prediction = source-language transcription.
  - ``asr-mt``:   prediction = target-language translation (via PR2 simul-MT).

Key semantics (SimulEval / LongYAAL):
  - ``delays[i]`` = chunk-boundary audio-processed time (ms) at which
    the system emitted word i — NOT the acoustic position.
  - ``elapsed[i]`` = wallclock (ms) at that chunk's finish, normalized
    to CA-compatible incremental form via
    ``normalize_computation_aware_timestamps``.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

import numpy as np

from alignatt4llm.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    HYPOTHESIS_ELAPSED_SEMANTICS_CA_COMPATIBLE,
    HYPOTHESIS_FILENAME,
    MANIFEST_FILENAME,
    ensure_output_dir,
    normalize_computation_aware_timestamps,
    utc_now_isoformat,
    write_json,
    write_jsonl,
)
from alignatt4llm.emission import register_translation_timestamps, register_translation_words
from alignatt4llm.text_surface import prediction_text_from_target_surface

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


# ---------------------------------------------------------------------------
# Audio loading
# ---------------------------------------------------------------------------

def load_audio_mono_16khz(path: str | Path) -> np.ndarray:
    """Load an audio file as 16 kHz mono float32."""
    p = Path(path)
    if p.suffix.lower() == ".wav":
        import wave
        with wave.open(str(p), "rb") as wf:
            sr = wf.getframerate()
            sw = wf.getsampwidth()
            nch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        if sw == 2:
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sw == 4:
            audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width {sw} for {p}")
        if nch > 1:
            audio = audio.reshape(-1, nch).mean(axis=1)
    else:
        import soundfile as sf
        audio, sr = sf.read(str(p), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            duration = len(audio) / sr
            new_len = int(round(duration * SAMPLE_RATE))
            old_t = np.linspace(0, duration, len(audio), endpoint=False)
            new_t = np.linspace(0, duration, new_len, endpoint=False)
            audio = np.interp(new_t, old_t, audio).astype(np.float32)
    # Resample if needed (WAV path may have non-16kHz)
    if p.suffix.lower() == ".wav":
        import wave
        with wave.open(str(p), "rb") as wf:
            sr = wf.getframerate()
        if sr != SAMPLE_RATE:
            duration = len(audio) / sr
            new_len = int(round(duration * SAMPLE_RATE))
            old_t = np.linspace(0, duration, len(audio), endpoint=False)
            new_t = np.linspace(0, duration, new_len, endpoint=False)
            audio = np.interp(new_t, old_t, audio).astype(np.float32)
    return audio.astype(np.float32)


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

class HypothesisEmitter:
    """Emit a hypothesis.jsonl record for one devset audio.

    Parameters
    ----------
    audio_path : str
        Path to the wav file.
    mode : str
        ``"asr-only"`` or ``"asr-mt"``.
    asr_backend : str
        ``"mlx-qwen3-asr"`` (anchor) or ``"nemotron-mlx"`` (flagship).
    target_lang_code : str
        Target language code (``"en"`` for ASR-only, ``"zh"`` for en→zh MT).
    source_lang_code : str
        Source language code (default ``"en"``).
    chunk_sec : float
        Audio chunk size in seconds (default 2.0).
    asr_model_id : str | None
        Override the ASR model ID.
    mt_model_id : str | None
        Override the MT model ID (for asr-mt mode).
    """

    def __init__(
        self,
        audio_path: str,
        *,
        mode: str = "asr-only",
        asr_backend: str = "mlx-qwen3-asr",
        target_lang_code: str = "en",
        source_lang_code: str = "en",
        chunk_sec: float = 2.0,
        asr_model_id: str | None = None,
        mt_model_id: str | None = None,
        second_pass: bool = True,
    ):
        self.audio_path = str(audio_path)
        self.wav_name = Path(audio_path).name
        self.mode = mode
        self.asr_backend = asr_backend
        self.target_lang_code = target_lang_code
        self.source_lang_code = source_lang_code
        self.chunk_sec = chunk_sec
        self.asr_model_id = asr_model_id or "mlx-community/Qwen3-ASR-0.6B-8bit"
        self.mt_model_id = mt_model_id or "hy-mt2-1.8b-8bit"
        self.second_pass = second_pass

    def emit(self, output_dir: str | Path) -> dict[str, str]:
        """Run the cascade over the audio and write artifacts.

        Returns a dict of output file paths.
        """
        output_path = ensure_output_dir(output_dir)

        audio = load_audio_mono_16khz(self.audio_path)
        audio_duration_ms = len(audio) * 1000.0 / SAMPLE_RATE

        if self.mode == "asr-only":
            record = self._run_asr_only(audio, audio_duration_ms)
        elif self.mode == "asr-mt":
            record = self._run_asr_mt(audio, audio_duration_ms)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        manifest = self._build_manifest(audio_duration_ms)

        hyp_path = output_path / HYPOTHESIS_FILENAME
        write_jsonl(hyp_path, [record])
        write_json(output_path / MANIFEST_FILENAME, manifest)

        logger.info(
            "Emitted %s: prediction=%d chars, %d delay units",
            self.wav_name,
            len(record["prediction"]),
            len(record["delays"]),
        )
        return {
            "hypothesis": str(hyp_path),
            "manifest": str(output_path / MANIFEST_FILENAME),
        }

    # ------------------------------------------------------------------
    # ASR-only mode
    # ------------------------------------------------------------------

    def _run_asr_only(
        self,
        audio: np.ndarray,
        audio_duration_ms: float,
    ) -> dict[str, Any]:
        """Run ASR only; prediction = source-language transcription."""
        from mlx_qwen3_asr import load_model
        from mlx_qwen3_asr.streaming import (
            feed_audio,
            finish_streaming,
            init_streaming,
        )

        model, _cfg = load_model(self.asr_model_id)
        language = _lang_code_to_name(self.source_lang_code)

        state = init_streaming(
            model=self.asr_model_id,
            chunk_size_sec=self.chunk_sec,
            max_context_sec=30.0,
            language=language,
            finalization_mode="latency",
        )

        chunk_size = int(SAMPLE_RATE * self.chunk_sec)
        word_delays: list[float] = []
        word_elapsed: list[float] = []
        prev_text = ""
        start = perf_counter()

        for start_sample in range(0, len(audio), chunk_size):
            chunk = audio[start_sample : start_sample + chunk_size]
            state = feed_audio(chunk, state, model=model)

            current_text = (getattr(state, "stable_text", "") or "").strip()
            audio_processed_ms = min(start_sample + chunk_size, len(audio)) * 1000.0 / SAMPLE_RATE
            wallclock_ms = (perf_counter() - start) * 1000.0

            if current_text != prev_text:
                register_translation_words(
                    prev_text, current_text,
                    audio_processed_ms, word_delays,
                    target_lang_code=self.target_lang_code,
                )
                register_translation_timestamps(
                    prev_text, current_text,
                    wallclock_ms, word_elapsed,
                    target_lang_code=self.target_lang_code,
                )
                prev_text = current_text

        # Finalize streaming (may fail on very short trailing buffer)
        try:
            state = finish_streaming(state, model=model)
            final_text = (getattr(state, "stable_text", "") or "").strip()
            if not final_text:
                final_text = (getattr(state, "text", "") or "").strip()
        except Exception as exc:
            logger.warning("finish_streaming failed (%s); using last stable_text", exc)
            final_text = prev_text
        final_wallclock_ms = (perf_counter() - start) * 1000.0

        if final_text != prev_text:
            register_translation_words(
                prev_text, final_text,
                audio_duration_ms, word_delays,
                target_lang_code=self.target_lang_code,
            )
            register_translation_timestamps(
                prev_text, final_text,
                final_wallclock_ms, word_elapsed,
                target_lang_code=self.target_lang_code,
            )

        normalized_elapsed = normalize_computation_aware_timestamps(word_delays, word_elapsed)
        prediction = prediction_text_from_target_surface(
            final_text, target_lang_code=self.target_lang_code,
        )

        return {
            "source": [self.wav_name],
            "source_length": audio_duration_ms,
            "prediction": prediction,
            "delays": word_delays,
            "elapsed": normalized_elapsed,
            "elapsed_wallclock_ms": word_elapsed,
            "elapsed_semantics": HYPOTHESIS_ELAPSED_SEMANTICS_CA_COMPATIBLE,
        }

    # ------------------------------------------------------------------
    # ASR + MT mode
    # ------------------------------------------------------------------

    def _run_asr_mt(
        self,
        audio: np.ndarray,
        audio_duration_ms: float,
    ) -> dict[str, Any]:
        """Run ASR + MT; prediction = target-language translation."""
        from mlx_qwen3_asr import load_model, transcribe
        from mlx_qwen3_asr.streaming import (
            feed_audio,
            finish_streaming,
            init_streaming,
        )
        from mlx_lm import stream_generate
        from mlx_lm.tokenizers_utils import load_tokenizer
        from mlx_lm.utils import load

        # --- ASR setup ---
        asr_model, _cfg = load_model(self.asr_model_id)
        asr_language = _lang_code_to_name(self.source_lang_code)

        # --- MT setup (PR2 simul-MT) ---
        from whisperlivekit.translation_mlx_llm_mt_simul import MlxLlmTranslationSimul
        mt = MlxLlmTranslationSimul(
            model_id=self.mt_model_id,
            target_language=self.target_lang_code,
            warmup=True,
        )

        from whisperlivekit.timed_objects import ASRToken, HypothesisTail

        state = init_streaming(
            model=self.asr_model_id,
            chunk_size_sec=self.chunk_sec,
            max_context_sec=30.0,
            language=asr_language,
            finalization_mode="latency",
        )

        chunk_size = int(SAMPLE_RATE * self.chunk_sec)
        word_delays: list[float] = []
        word_elapsed: list[float] = []
        prev_mt_text = ""
        prev_stable = ""
        start = perf_counter()

        for start_sample in range(0, len(audio), chunk_size):
            chunk = audio[start_sample : start_sample + chunk_size]
            state = feed_audio(chunk, state, model=asr_model)

            stable_text = (getattr(state, "stable_text", "") or "").strip()
            rolling_text = (getattr(state, "text", "") or "").strip()
            audio_processed_ms = min(start_sample + chunk_size, len(audio)) * 1000.0 / SAMPLE_RATE
            wallclock_ms = (perf_counter() - start) * 1000.0

            # Feed committed ASR tokens to MT
            if stable_text and stable_text != prev_stable:
                # Build ASRToken for the newly committed text
                new_text = stable_text[len(prev_stable):].strip()
                if new_text:
                    tok = ASRToken(
                        start=audio_processed_ms / 1000.0,
                        end=audio_processed_ms / 1000.0,
                        text=new_text,
                        speaker=-1,
                    )
                    mt.insert_tokens([tok])
                prev_stable = stable_text

            # Feed unstable tail
            tail_text = rolling_text[len(stable_text):].strip() if rolling_text else ""
            if tail_text:
                mt.insert_tokens([HypothesisTail(
                    start=audio_processed_ms / 1000.0,
                    end=audio_processed_ms / 1000.0,
                    text=tail_text,
                )])

            # Run MT
            translation, buffer = mt.process()
            current_mt = ""
            if buffer and buffer.text:
                current_mt = buffer.text.strip()
            elif translation and translation.text:
                current_mt = translation.text.strip()

            if current_mt and current_mt != prev_mt_text:
                register_translation_words(
                    prev_mt_text, current_mt,
                    audio_processed_ms, word_delays,
                    target_lang_code=self.target_lang_code,
                )
                register_translation_timestamps(
                    prev_mt_text, current_mt,
                    wallclock_ms, word_elapsed,
                    target_lang_code=self.target_lang_code,
                )
                prev_mt_text = current_mt

        # Finalize ASR
        state = finish_streaming(state, model=asr_model)
        final_stable = (getattr(state, "stable_text", "") or "").strip()
        if not final_stable:
            final_stable = (getattr(state, "text", "") or "").strip()

        # Feed final ASR text to MT and flush
        if final_stable and final_stable != prev_stable:
            new_text = final_stable[len(prev_stable):].strip()
            if new_text:
                tok = ASRToken(
                    start=audio_duration_ms / 1000.0,
                    end=audio_duration_ms / 1000.0,
                    text=new_text,
                    speaker=-1,
                )
                mt.insert_tokens([tok])

        # Flush MT
        final_translation, _ = mt.validate_buffer_and_reset()
        final_mt_text = ""
        if final_translation and final_translation.text:
            final_mt_text = final_translation.text.strip()

        # Also check for any pending finals
        tr, _ = mt.process()
        if tr and tr.text:
            final_mt_text = (final_mt_text + " " + tr.text).strip()

        final_wallclock_ms = (perf_counter() - start) * 1000.0

        if final_mt_text and final_mt_text != prev_mt_text:
            register_translation_words(
                prev_mt_text, final_mt_text,
                audio_duration_ms, word_delays,
                target_lang_code=self.target_lang_code,
            )
            register_translation_timestamps(
                prev_mt_text, final_mt_text,
                final_wallclock_ms, word_elapsed,
                target_lang_code=self.target_lang_code,
            )

        normalized_elapsed = normalize_computation_aware_timestamps(word_delays, word_elapsed)
        prediction = prediction_text_from_target_surface(
            final_mt_text, target_lang_code=self.target_lang_code,
        )

        return {
            "source": [self.wav_name],
            "source_length": audio_duration_ms,
            "prediction": prediction,
            "delays": word_delays,
            "elapsed": normalized_elapsed,
            "elapsed_wallclock_ms": word_elapsed,
            "elapsed_semantics": HYPOTHESIS_ELAPSED_SEMANTICS_CA_COMPATIBLE,
        }

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _build_manifest(self, audio_duration_ms: float) -> dict[str, Any]:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "generated_at_utc": utc_now_isoformat(),
            "kind": "inference",
            "wav_path": self.audio_path,
            "chunk_ms": int(self.chunk_sec * 1000),
            "translation_variant": None,
            "source_language": self.source_lang_code,
            "target_language": self.target_lang_code,
            "source_language_code": self.source_lang_code,
            "target_language_code": self.target_lang_code,
            "latency_unit": "char" if self.target_lang_code in ("zh", "ja") else "word",
            "audio_duration_ms": audio_duration_ms,
            "files": {
                "hypothesis_jsonl": HYPOTHESIS_FILENAME,
            },
            "runtime_config": {
                "hypothesis_elapsed_semantics": HYPOTHESIS_ELAPSED_SEMANTICS_CA_COMPATIBLE,
                "stream_update_elapsed_semantics": "wallclock_elapsed_since_run_start",
                "mode": self.mode,
                "asr_backend": self.asr_backend,
                "asr_model_id": self.asr_model_id,
                "mt_model_id": self.mt_model_id if self.mode == "asr-mt" else None,
                "chunk_sec": self.chunk_sec,
                "second_pass": self.second_pass,
            },
            "run_provenance": {},
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LANG_NAMES = {
    "en": "English", "zh": "Chinese", "zh-cn": "Chinese",
    "zh-hans": "Chinese", "zh-tw": "Chinese",
    "ja": "Japanese", "ko": "Korean",
    "de": "German", "fr": "French", "es": "Spanish",
}


def _lang_code_to_name(code: str | None) -> str | None:
    if not code:
        return None
    key = code.strip().lower()
    return _LANG_NAMES.get(key, code.strip().title())
