"""Testable display-state model for the overlay (no AppKit).

The overlay's caption display logic (hold-drain, provisional→final replacement,
scroll-up-to-history, expiry) is extracted here as a pure state machine that
produces a DOM-like ``DisplayState`` (styled spans per line) from the event
stream (preview/translation). The AppKit ``OverlayRenderer`` is a thin view over
this model: it feeds events in and applies the returned ``DisplayState`` to the
NSTextFields. Tests drive the model with a deterministic event stream and a fake
clock, then assert on ``DisplayState`` — no GUI, no threads.

The model emits WHAT to show; the view's reconciler decides HOW it transitions
(in-place append for text that extends what's shown, hard-replace on rewrite,
word-by-word streaming animation). Keeping the animation in the reconciler keeps
this logic testable without timers/threads.

Display behavior (tuned live, see the overlay commit series):
  - provisional (simul draft): dimmed, replaces in place, never frozen — extends
    update, rewrites hard-replace; persists until the final replaces it (a
    vanishing draft reads as a dropped caption)
  - final: bright; the LAST sentence shows on the current row and the
    SECOND-TO-LAST on the prev row immediately (no slow per-sentence pacing)
  - a new caption scrolls the committed current line up to the prev row; the
    prev row expires on its own timer
  - finals expire after the hold; a provisional whose hold elapsed with nothing
    queued stays (the final is expected to follow)
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple


# Hunyuan placeholder artifact (fullwidth-pipe-delimited token).
_HY_PLACEHOLDER_RE = re.compile(r"<[\|｜][^\|｜]*[｜|]>")

SENT_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")


def strip_placeholder(text: str) -> str:
    """Strip Hunyuan placeholder tokens (display-side defense; the engine strips
    at source now)."""
    if not text:
        return text
    return _HY_PLACEHOLDER_RE.sub("", text).strip()


def split_sentences(text: str) -> List[str]:
    return [s for s in (p.strip() for p in SENT_SPLIT_RE.split(text)) if s]


# Style tags (the "DOM" node kinds). The view maps these to colors; tests assert
# on the tags directly.
PROVISIONAL = "provisional"   # dimmed draft
FINAL = "final"               # bright committed text


@dataclass
class Span:
    """One styled text run in the display DOM."""
    text: str
    style: str


@dataclass
class DisplayState:
    """Snapshot of the overlay's two EN rows as styled spans. Tests assert on this;
    the AppKit view renders it."""
    current: List[Span] = field(default_factory=list)  # active caption line
    prev: List[Span] = field(default_factory=list)     # scrolled-up history line

    def plain(self, which: str = "current") -> str:
        spans = self.current if which == "current" else self.prev
        return "".join(s.text for s in spans)


def _text_spans(text: str, style: str) -> List[Span]:
    """Wrap one caption text as a single styled span (the WLK overlay renders plain
    runs — no inline diff in the GUI)."""
    return [Span(text, style)] if text else []


class OverlayDisplayModel:
    """Pure display-state machine for the overlay's two EN rows.

    Feed it the same events the renderer gets (``preview``/``translation``) and
    call ``tick()`` on the drainer thread to advance the hold timers. ``tick``
    returns the ``DisplayState`` to render, or None when nothing changed (the
    view can skip the render). ``state()`` returns the snapshot without advancing.

    The clock is injectable (``clock`` returns monotonic seconds) so tests are
    deterministic; production passes ``time.monotonic``. Single-threaded by
    construction: the AppKit view serializes access with its own lock.
    """

    def __init__(self, hold_sec: float = 3.5, clock: Callable[[], float] = time.monotonic) -> None:
        self._hold = hold_sec
        self._clock = clock
        # current row
        self._en_plain: str = ""
        self._en_spans: List[Span] = []
        self._en_utt: Optional[tuple] = None   # utterance identity (label, started_at)
        self._en_is_final: bool = False
        self._shown_at: float = -hold_sec      # release the first caption immediately
        # prev (history) row
        self._prev_spans: List[Span] = []
        self._prev_plain: str = ""
        self._prev_at: float = 0.0
        # pending captions waiting for the drainer: (plain, utt, is_final)
        self._queue: List[Tuple[str, Optional[tuple], bool]] = []
        self._last_state: Optional[DisplayState] = None

    # ---- event feed (mirrors the renderer callbacks) ----

    def preview(self, text: str, utt: Optional[tuple]) -> None:
        """Provisional translation (simul draft). Enqueued through the drainer so a
        draft can't flicker over a held final; the queue keeps the newest draft."""
        plain = strip_placeholder(text).strip()
        if plain == self._en_plain:
            return  # unchanged — no churn
        self._enqueue(plain, utt, is_final=False)

    def translation(self, text: str, utt: Optional[tuple]) -> None:
        """Final translation. Shows the LAST sentence on the current row and the
        SECOND-TO-LAST on the prev row immediately — no slow per-sentence pacing
        (4 sentences × 3.5s pacing means the viewer watches sentences cycle instead
        of reading the committed final). A final of the SAME utterance replaces its
        provisional in place (a draft correction, not a new caption)."""
        plain = strip_placeholder(text).strip()
        if not plain:
            return
        same_utt = (utt is not None and self._en_utt is not None
                    and utt == self._en_utt)
        # same-utterance final correcting its own provisional: replace in place —
        # a draft is not a committed caption and must not scroll up to history.
        if same_utt and not self._en_is_final:
            self._en_plain = ""
            self._en_spans = []
        now = self._clock()
        sents = split_sentences(plain)
        if len(sents) >= 2:
            # last sentence on current, second-to-last on prev — immediately
            self._prev_spans = _text_spans(sents[-2], FINAL)
            self._prev_at = now
            self._show(plain, sents[-1], utt, now, True)
        else:
            # single sentence: scroll the old committed caption up to history when a
            # genuinely different caption replaces it (different utterance, or the
            # current line is a final); a same-utterance provisional correction was
            # cleared above and does not scroll.
            if (self._en_plain and plain != self._en_plain
                    and (not same_utt or self._en_is_final)):
                self._prev_spans = list(self._en_spans)
                self._prev_at = now
            self._show(plain, plain, utt, now, is_final=True)

    def tick(self) -> Optional[DisplayState]:
        """Advance the hold timers one step (call from the drainer thread). Returns
        the DisplayState to render if something changed, else None."""
        now = self._clock()
        cur_changed = False
        prev_changed = False
        if self._queue and now - self._shown_at >= self._hold:
            plain, utt, is_final = self._queue.pop(0)
            same_utt = (utt is not None and self._en_utt is not None
                        and utt == self._en_utt)
            # Scroll the current line up to history only when it's a genuinely
            # different caption — a different utterance, OR the current line is a
            # final (a multi-sentence final's own sentences scroll up so the reader
            # sees each in turn). The case that must NOT scroll up: a provisional
            # replaced by its own final (same utterance, in-place correction).
            scroll_up = (self._en_plain and plain != self._en_plain
                         and (not same_utt or self._en_is_final))
            if scroll_up:
                self._prev_spans = list(self._en_spans)
                self._prev_at = now
                prev_changed = True
            self._show(plain, plain, utt, now, is_final)
            cur_changed = True
        else:
            # Current row expires with nothing queued — ONLY for finals. A provisional
            # persists until replaced (a vanishing draft reads as a dropped caption).
            if (self._en_plain and self._en_is_final
                    and now - self._shown_at >= self._hold):
                self._en_plain = ""
                self._en_spans = []
                cur_changed = True
            # The prev row expires on its own timer.
            if self._prev_spans and now - self._prev_at >= self._hold:
                self._prev_spans = []
                prev_changed = True
        if not cur_changed and not prev_changed:
            return None
        state = self.state()
        if self._last_state is not None and state == self._last_state:
            return None
        self._last_state = state
        return state

    def state(self) -> DisplayState:
        """Current display snapshot without advancing the timers."""
        return DisplayState(current=list(self._en_spans), prev=list(self._prev_spans))

    # ---- internals ----

    def _show(self, plain: str, sentence: str, utt: Optional[tuple], now: float,
              is_final: bool) -> None:
        self._en_plain = sentence
        self._en_spans = _text_spans(sentence, FINAL if is_final else PROVISIONAL)
        self._en_utt = utt
        self._en_is_final = is_final
        self._shown_at = now
        self._last_state = None

    def _enqueue(self, plain: str, utt: Optional[tuple], is_final: bool) -> None:
        """Queue a caption for the hold-drain (newest wins; releases immediately)."""
        self._queue.clear()
        self._queue.append((plain, utt, is_final))
        self._shown_at = -self._hold  # release on the next tick
