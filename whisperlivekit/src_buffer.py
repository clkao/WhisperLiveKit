"""The source-row sentence test the terminal driver needs (no AppKit).

``ends_sentence`` is a text predicate, not display policy: ``TerminalSink`` uses
it to tell a landed sentence from the in-flight tail of the cumulative source
line it is printing.

The overlay's source reading buffer (accumulate committed clauses, freeze at a
terminator, promote at the next sentence, monotonic within a sentence) is gone:
``CaptionDisplay.set_partial`` owns the monotonic hold and ``clear_partial``
owns the commit, and the window renders the model's ``DisplayState.partial``
directly (``overlay.layout``), so a second copy of that rule had no reader left.
"""
from __future__ import annotations


def ends_sentence(text: str) -> bool:
    """True when the text ends a sentence (CJK/Latin/quote-final terminators)."""
    return text.rstrip().endswith(
        ("。", "！", "？", ".", "!", "?", '."', '!"', '?"'))
