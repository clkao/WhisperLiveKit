#!/usr/bin/env python3
"""TimestampSource abstraction for the SimulST eval harness.

Two implementations behind one seam:
  - ForcedAlignTimestampSource: post-hoc forced aligner (mlx-qwen3-asr
    ``Qwen3-ForcedAligner-0.6B``) over a closed chunk's audio + text.
  - NativeTokenTimestampSource: native per-token timestamps from a
    streaming transducer (e.g., nemotron-mlx ``AlignedToken.start``).

Both produce ``list[WordTimestamp]`` — per-word acoustic start/end times
that the MT commit-policy frontier reads. They are NOT the hypothesis
``delays`` (which are chunk-boundary audio-processed-time); they feed the
commit policy, not the latency metric.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class WordTimestamp:
    """A single word's acoustic alignment."""
    text: str
    start_time: float  # seconds
    end_time: float    # seconds


@runtime_checkable
class TimestampSource(Protocol):
    """Abstract timestamp source for the commit-policy frontier."""

    def get_word_timestamps(
        self,
        audio: np.ndarray,
        text: str,
        language: str | None = None,
    ) -> list[WordTimestamp]:
        """Return per-word acoustic timestamps for the given audio + text."""
        ...


class ForcedAlignTimestampSource:
    """Post-hoc forced alignment via mlx-qwen3-asr's ForcedAligner.

    Loads ``Qwen/Qwen3-ForcedAligner-0.6B`` (or a local path) once and
    aligns each closed chunk's audio + text to get per-word acoustic
    timestamps. Used by the anchor run (mlx-qwen3-asr + forced aligner).
    """

    def __init__(
        self,
        model_path: str = "Qwen/Qwen3-ForcedAligner-0.6B",
    ):
        self.model_path = model_path
        self._aligner = None

    def _ensure_aligner(self):
        if self._aligner is None:
            from mlx_qwen3_asr.forced_aligner import ForcedAligner
            self._aligner = ForcedAligner(model_path=self.model_path)
        return self._aligner

    def get_word_timestamps(
        self,
        audio: np.ndarray,
        text: str,
        language: str | None = None,
    ) -> list[WordTimestamp]:
        if not text or not text.strip() or audio is None or len(audio) == 0:
            return []
        aligner = self._ensure_aligner()
        aligned = aligner.align(
            audio.astype(np.float32),
            text,
            language or "en",
        )
        return [
            WordTimestamp(
                text=w.text,
                start_time=w.start_time,
                end_time=w.end_time,
            )
            for w in aligned
        ]


class NativeTokenTimestampSource:
    """Native per-token timestamps from a streaming transducer.

    Wraps a list of aligned tokens (each with ``.start`` time) produced
    mid-decode by a transducer ASR (e.g., nemotron-mlx's ``AlignedToken``).
    No post-hoc aligner call needed. Used by the flagship run.
    """

    def __init__(self):
        self._tokens: list[WordTimestamp] = []

    def update(self, aligned_tokens: list) -> None:
        """Feed new aligned tokens from the transducer's mid-decode."""
        for tok in aligned_tokens:
            start = getattr(tok, "start", None) or getattr(tok, "start_time", None)
            text = getattr(tok, "text", "") or getattr(tok, "surface", "")
            if start is not None and text:
                self._tokens.append(
                    WordTimestamp(text=text, start_time=float(start), end_time=float(start))
                )

    def get_word_timestamps(
        self,
        audio: np.ndarray,
        text: str,
        language: str | None = None,
    ) -> list[WordTimestamp]:
        return list(self._tokens)

    def reset(self) -> None:
        self._tokens = []
