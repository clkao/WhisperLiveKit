"""Display adapter — derives display events from a caption event stream.

The display layer (overlay, TUI) consumes ``CaptionEvent``s and derives what
to render: a rolling partial (ASR draft + provisional translation) and
finalized lines (translation_final). This is the layer we test independently of
generation: feed a golden event sequence, assert the rendered state.

The shipped web UI keeps using ``FrontData`` snapshots; this adapter is for
the overlay/TUI paths (our code), which currently read ``TestState`` fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from whisperlivekit.caption_events import CaptionEvent


@dataclass
class DisplayState:
    """What the display should show at any point in the stream."""
    partial_transcription: str = ""   # current rolling ASR (transcription_provisional)
    partial_translation: str = ""     # current provisional MT (translation_provisional)
    final_lines: List[str] = field(default_factory=list)  # committed translation_finals
    # bookkeeping
    _last_final: str = ""

    def render_summary(self) -> str:
        """Human-readable one-line state, for tests/debug."""
        parts = []
        if self.final_lines:
            parts.append(f"finals={len(self.final_lines)}")
        if self.partial_translation:
            parts.append(f"prov={self.partial_translation!r}")
        if self.partial_transcription:
            parts.append(f"asr={self.partial_transcription!r}")
        return " | ".join(parts) or "(empty)"


class DisplayAdapter:
    """Stateful reducer: feed CaptionEvents, read DisplayState.

    Rules:
      - transcription_provisional   -> set partial_transcription (overwrites; it's rolling)
      - transcription_final   -> clear partial_transcription (the draft is now committed)
      - translation_provisional    -> set partial_translation (overwrites; it's provisional)
      - translation_final    -> append to final_lines, clear partial_translation
    """

    def __init__(self) -> None:
        self.state = DisplayState()

    def feed(self, event: CaptionEvent) -> DisplayState:
        t = event.type
        if t == "transcription_provisional":
            self.state.partial_transcription = event.text
        elif t == "transcription_final":
            self.state.partial_transcription = ""  # committed; draft no longer rolling
        elif t == "translation_provisional":
            self.state.partial_translation = event.text
        elif t == "translation_final":
            if event.text and event.text != self.state._last_final:
                self.state.final_lines.append(event.text)
                self.state._last_final = event.text
            self.state.partial_translation = ""  # final replaces the provisional
        return self.state
