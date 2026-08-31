"""Pure state machine for the overlay's source reading buffer (no AppKit).

The src row semantics — accumulated committed clauses + rolling tail, with
the float-to-history happening when new words need the line — are extracted
here so they are unit-testable without AppKit. ``OverlayRenderer`` delegates
its src-row bookkeeping to this class; tests drive it directly.
"""
from __future__ import annotations


def _is_cjk(ch: str) -> bool:
    return ("\u4e00" <= ch <= "\u9fff"
            or ch in "\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001\uff09\u300d\u300f\u3011")


def src_join(a: str, b: str) -> str:
    """Join accumulated source clauses: no space across a CJK boundary (zh has
    none), a single space for Latin."""
    if not a:
        return b
    if not b:
        return a
    if a[-1].isspace() or b[:1].isspace():
        return a + b
    if _is_cjk(a[-1]) and _is_cjk(b[0]):
        return a + b
    return a + " " + b


def ends_sentence(text: str) -> bool:
    """True when the text ends a sentence (CJK/Latin/quote-final terminators)."""
    return text.rstrip().endswith(
        ("。", "！", "？", ".", "!", "?", '."', '!"', '?"'))


class SrcReadingBuffer:
    """Src reading buffer: committed clauses accumulate; a sentence-final
    terminator freezes the buffer; the NEXT utterance's words promote it to
    the zh history field. The display is monotonic within a sentence.

    Usage:
        display = buf.tail(text)      # rolling update -> display string
        if buf.consume_promotion():   # a completed sentence floated up
            zh_field = buf.last_promoted
        display = buf.commit(text)    # a clause committed
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._committed = ""          # committed clauses of the current sentence
        self._sentence_complete = False
        self.last_promoted: str | None = None

    @property
    def committed(self) -> str:
        return self._committed

    @property
    def sentence_complete(self) -> bool:
        return self._sentence_complete

    def consume_promotion(self) -> str:
        """Return and clear the sentence promoted to history (or None)."""
        p = self.last_promoted
        self.last_promoted = None
        return p

    def tail(self, text: str) -> str:
        """A rolling update: returns the src row display string. If the buffer
        holds a completed sentence, it promotes — the float happens when new
        words need the line, not at commit."""
        if self._sentence_complete:
            self.last_promoted = self._committed
            self._committed = ""
            self._sentence_complete = False
        # defensive: some backends' rolling buffer still carries the committed
        # prefix — never render it twice
        if self._committed and text.startswith(self._committed):
            return text
        return src_join(self._committed, text)

    def commit(self, text: str) -> str:
        """A committed clause: accumulates into the buffer. A sentence-final
        terminator freezes the buffer (promotable)."""
        self._committed = src_join(self._committed, text)
        if ends_sentence(text):
            self._sentence_complete = True
        return self._committed
