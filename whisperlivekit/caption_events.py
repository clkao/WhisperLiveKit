"""Standardized caption event stream — the contract between ASR+MT generation
and the display/test layers.

Parallel tap (spike): the pipeline emits these events alongside building
``FrontData``. ``FrontData`` (the web UI wire protocol) is untouched — it
stays built by ``audio_processor``. The event stream is the testable seam:
it carries the four ASR/MT event types so generation can be tested for
coherence independently of how the display renders it.

Event types:
  - ``asr_draft``  : the unstable ASR tail (rolling hypothesis, not committed)
  - ``asr_final``  : committed ASR tokens (a finalized fragment/segment)
  - ``mt_draft``   : provisional translation (AlignAtt release against
                     committed source; held target is NOT released yet)
  - ``mt_final``   : finalized translation (quality pass at a boundary)

The display layer derives its own events (partial_transcription,
partial_translation, final_translation) from this stream; the web UI keeps
using ``FrontData`` snapshots unchanged.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Protocol


@dataclass
class CaptionEvent:
    """One event in the caption stream."""
    t: float          # wall clock (seconds since stream start)
    audio_t: float    # audio position (seconds)
    type: str         # asr_draft | asr_final | mt_draft | mt_final
    text: str
    # mt_draft only: what AlignAtt released against (committed source)
    committed: str = ""
    # mt_draft only: the full source the MT saw (committed + tail)
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class EventSink(Protocol):
    """Anything that consumes caption events."""
    def emit(self, event: CaptionEvent) -> None: ...


@dataclass
class EventLog:
    """In-memory event log + JSONL save. Use as the sink for capture."""
    events: List[CaptionEvent] = field(default_factory=list)

    def emit(self, event: CaptionEvent) -> None:
        self.events.append(event)

    def save(self, path: str) -> None:
        Path(path).write_text(
            "\n".join(json.dumps(e.to_dict(), ensure_ascii=False) for e in self.events)
            + "\n"
        )

    @classmethod
    def load(cls, path: str) -> "EventLog":
        log = cls()
        for line in Path(path).read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                log.events.append(CaptionEvent(**d))
        return log


class EventTap:
    """Tap attached to the ASR+MT driver loop.

    The driver calls the asr_* / mt_* methods at the points where each event
    is produced; the tap forwards to its sink (if any). Kept stateless so a
    no-op tap (sink=None) is zero-cost and the pipeline runs unchanged.
    """
    def __init__(self, sink: Optional[EventSink] = None, clock=None):
        self._sink = sink
        self._clock = clock  # callable returning wall seconds; None = perf_counter

    def _now(self) -> float:
        if self._clock is not None:
            return self._clock()
        import time
        return time.perf_counter()

    def asr_draft(self, audio_t: float, text: str) -> None:
        if self._sink is None or not text or not text.strip():
            return
        self._sink.emit(CaptionEvent(self._now(), audio_t, "asr_draft", text))

    def asr_final(self, audio_t: float, text: str) -> None:
        if self._sink is None or not text or not text.strip():
            return
        self._sink.emit(CaptionEvent(self._now(), audio_t, "asr_final", text))

    def mt_draft(self, audio_t: float, text: str, committed: str = "", source: str = "") -> None:
        if self._sink is None or not text or not text.strip():
            return
        self._sink.emit(CaptionEvent(self._now(), audio_t, "mt_draft", text, committed, source))

    def mt_final(self, audio_t: float, text: str) -> None:
        if self._sink is None or not text or not text.strip():
            return
        self._sink.emit(CaptionEvent(self._now(), audio_t, "mt_final", text))
