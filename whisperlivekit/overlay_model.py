"""Testable display-state model for the overlay (no AppKit).

The overlay's caption display logic (the hold-drain + provisional→final
replacement + scrollback) is extracted here as a pure state machine that
produces a DOM-like ``DisplayState`` (a list of styled spans per line) from
the event stream (preview/translation/partial/final). The AppKit
``OverlayRenderer`` is a thin view over this model; tests drive the model
with a deterministic event stream and a fake clock, then assert on the
``DisplayState`` without touching the GUI.

Styling (the "DOM"):
  - provisional: dimmed (a draft — clearly not the final word)
  - final same:  bright (unchanged from the provisional)
  - final add:   green (the correction / new words)
  - del spans are OMITTED from the final display (strikethrough is hard to
    read in an overlay; the old words simply vanish, the green adds show
    what changed). The provisional is shown dimmed first, so the reader sees
    the draft, then the bright final with green corrections replaces it.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# Hunyuan placeholder artifact (fullwidth-pipe-delimited token).
_HY_PLACEHOLDER_RE = re.compile(r"<[\|｜][^\|｜]*[\|｜]>")


def _strip_hy_placeholder(text: str) -> str:
    if not text:
        return text
    return _HY_PLACEHOLDER_RE.sub("", text)


def _strip_hy_placeholder_preserve_ws(text: str) -> str:
    """Strip the Hunyuan placeholder but PRESERVE leading/trailing whitespace (the
    diff spans bake their spacing into each span — stripping it would collapse
    ' we are' to 'we are' and break word separation)."""
    if not text:
        return text
    return _HY_PLACEHOLDER_RE.sub("", text)


# Style tags (the "DOM" node kinds). The overlay view maps these to colors;
# tests assert on the tags directly.
PROVISIONAL = "provisional"   # dimmed draft
FINAL_SAME = "same"           # bright, unchanged from provisional
FINAL_ADD = "add"             # green correction
# NOTE: no "del" style — deletions are omitted from the final display.


@dataclass
class Span:
    """One styled text run in the display DOM."""
    text: str
    style: str


@dataclass
class DisplayState:
    """A snapshot of the overlay's two EN lines + the source partial, as styled spans.
    Tests assert on this; the AppKit view renders it."""
    current: List[Span] = field(default_factory=list)   # the active caption line
    prev: List[Span] = field(default_factory=list)      # the scrolled-up history line
    partial: str = ""                                    # the ASR source partial (plain)


def _segments_plain(segments: list) -> str:
    """Flatten (speaker, text[, diff]) segments to plain text (for comparison)."""
    parts = []
    for seg in segments:
        speaker, text = seg[0], _strip_hy_placeholder(seg[1])
        parts.append(f"[S{speaker + 1}] {text}" if speaker is not None else text)
    return "  ".join(parts)


def _segments_to_spans(segments: list, is_final: bool) -> List[Span]:
    """Build the styled-span DOM for one caption.

    Provisional (is_final=False): one dimmed span per segment (the whole text is a
    draft). Final (is_final=True): render the diff spans — "same" bright, "add" green,
    "del" OMITTED (the old words just disappear; the green adds show the correction).
    2-tuple segments (no diff) render as one bright span.
    """
    spans: List[Span] = []
    for i, seg in enumerate(segments):
        if i:
            spans.append(Span("  ", FINAL_SAME if is_final else PROVISIONAL))
        speaker = seg[0]
        if speaker is not None:
            tag = FINAL_SAME if is_final else PROVISIONAL
            spans.append(Span(f"[S{speaker + 1}] ", tag))
        if len(seg) > 2 and seg[2]:
            for kind, words in seg[2]:
                words = _strip_hy_placeholder_preserve_ws(words)
                if not words.strip():
                    continue
                if is_final:
                    if kind == "add":
                        spans.append(Span(words, FINAL_ADD))
                    elif kind == "same":
                        spans.append(Span(words, FINAL_SAME))
                    # "del" spans are omitted — the old words vanish from the final.
                else:
                    # provisional: the whole text is a draft; render plain dimmed
                    spans.append(Span(words, PROVISIONAL))
        else:
            text = _strip_hy_placeholder(seg[1])
            tag = FINAL_SAME if is_final else PROVISIONAL
            spans.append(Span(text, tag))
    return spans


class _noop:
    def __enter__(self): return self
    def __exit__(self, *a): pass


class OverlayDisplayModel:
    """Pure display-state state machine for the overlay's EN lines.

    Feed it the same events the renderer gets (preview/translation/partial/final) and
    call ``tick(now)`` to advance the hold-drain. ``tick`` returns the ``DisplayState``
    to render (or None if nothing changed since the last tick — the view can skip).

    The clock is injectable (``clock`` returns monotonic seconds) so tests are
    deterministic; production passes ``time.monotonic``.
    """

    def __init__(self, hold_sec: float, clock=time.monotonic) -> None:
        self._hold = hold_sec
        self._clock = clock
        self._lock_held = False  # (the AppKit view adds its own threading.Lock; the model is single-threaded by construction)
        # current line
        self._en_plain: str = ""
        self._en_spans: List[Span] = []
        self._en_utt: Optional[float] = None
        self._en_is_final: bool = False
        self._en_shown_at: float = -hold_sec
        # prev (history) line
        self._en_prev_plain: str = ""
        self._en_prev_spans: List[Span] = []
        self._en_prev_at: float = 0.0
        # pending (the most recent enqueue, waiting for the drainer to show it)
        self._queue: List[Tuple[List[Span], str, Optional[float], bool]] = []
        # source partial
        self._partial: str = ""
        self._last_partial: str = ""  # for change detection
        # last emitted state (for change detection)
        self._last_state: Optional[DisplayState] = None

    # ---- event feed (mirrors OverlayRenderer callbacks) ----

    def set_partial(self, text: str) -> None:
        self._partial = text or ""

    def clear_partial(self) -> None:
        self._partial = ""

    def preview(self, segments: list, started_at) -> None:
        """Provisional translation. If the new provisional extends the shown text, stream
        the delta (smooth growth). If it rewrites (different prefix), hard-replace to the
        latest (no animation, but stays current — not frozen). Skip if unchanged."""
        plain = _segments_plain(segments)
        shown = self._en_plain
        if plain == shown:
            return  # skip (unchanged)
        if shown and plain.startswith(shown):
            # extends: stream the delta (enqueue the full new text; the drainer shows it)
            spans = _segments_to_spans(segments, is_final=False)
            self._enqueue(spans, plain, started_at, is_final=False)
        else:
            # rewrite or first: hard-replace to the latest provisional
            spans = _segments_to_spans(segments, is_final=False)
            self._enqueue(spans, plain, started_at, is_final=False)

    def translation(self, segments: list, started_at) -> None:
        """Final translation. Only AMEND — don't retype what's already shown. Keep the
        shown prefix (flip to final style), only enqueue the delta (new suffix)."""
        plain = _segments_plain(segments)
        shown = self._en_plain
        if shown:
            # common-prefix diff: keep the shown prefix, only show the delta
            cpl = 0
            n = min(len(shown), len(plain))
            while cpl < n and shown[cpl] == plain[cpl]:
                cpl += 1
            if cpl < len(shown):
                cpl = shown.rfind(" ", 0, cpl) + 1 if " " in shown[:cpl] else 0
            committed = plain[:cpl]  # already shown — keep, flip to final
            delta = plain[cpl:]       # new content
            # if there's no common prefix (committed=""), the old content scrolls up
            # to history (it's a genuinely different caption).
            if not committed and shown:
                # Only scroll up if this is NOT a same-utterance provisional→final
                # correction (a draft correction replaces in place, not a new caption).
                utt_t = started_at.timestamp() if started_at else None
                same_utt = (utt_t is not None
                            and self._en_utt == utt_t
                            and not self._en_is_final)
                if not same_utt:
                    self._en_prev_plain = shown
                    self._en_prev_spans = self._en_spans
                    self._en_prev_at = self._clock()
            # the committed prefix stays as the current line (now final style)
            self._en_plain = committed
            self._en_spans = _segments_to_spans([(None, committed, None)], is_final=True) if committed else []
            self._en_is_final = True
            self._en_shown_at = -self._hold  # release delta immediately on next tick
            self._en_utt = started_at.timestamp() if started_at else None
            # only enqueue the delta sentences
            if delta.strip():
                import re as _re
                sents = [s.strip() for s in _re.split(r'(?<=[.!?])\s+', delta) if s.strip()]
                for s in sents:
                    s_spans = _segments_to_spans([(None, s, None)], is_final=True)
                    self._queue.append((s_spans, s, self._en_utt, True))
            return
        # no shown provisional: full enqueue
        spans = _segments_to_spans(segments, is_final=True)
        self._enqueue(spans, plain, started_at, is_final=True)

    def _enqueue(self, spans: List[Span], plain: str, started_at, is_final: bool) -> None:
        utt_t = started_at.timestamp() if started_at is not None else None
        # If this final corrects a provisional of the same utterance currently on screen,
        # replace in place: drop the provisional so the drainer won't scroll it up.
        if (is_final and utt_t is not None
                and self._en_utt == utt_t and not self._en_is_final):
            self._en_plain = ""
            self._en_spans = []
        self._queue.clear()
        self._queue.append((spans, plain, utt_t, is_final))
        self._en_shown_at = -self._hold  # release immediately on the next tick

    # ---- the drainer (advance the hold timers) ----

    def tick(self) -> Optional[DisplayState]:
        """Advance the drainer one step. Returns the DisplayState to render if something
        changed, or None if the display is unchanged (the view can skip)."""
        now = self._clock()
        cur_changed = False
        prev_changed = False
        if self._queue and now - self._en_shown_at >= self._hold:
            spans, plain, utt_t, is_final = self._queue.pop(0)
            same_utt = utt_t is not None and utt_t == self._en_utt
            scroll_up = (self._en_plain and plain != self._en_plain
                         and (not same_utt or self._en_is_final))
            if scroll_up:
                self._en_prev_plain = self._en_plain
                self._en_prev_spans = self._en_spans
                self._en_prev_at = now
                prev_changed = True
            self._en_plain = plain
            self._en_spans = spans
            self._en_utt = utt_t
            self._en_is_final = is_final
            self._en_shown_at = now
            cur_changed = True
        else:
            # expire the current line if its hold elapsed with nothing queued — but
            # ONLY for finals. A provisional is a draft the viewer expects to be
            # followed by the committed/final; it must persist until replaced, not
            # vanish after the hold (a vanishing draft reads as a dropped caption).
            if (self._en_plain and self._en_is_final
                    and now - self._en_shown_at >= self._hold):
                self._en_plain = ""
                self._en_spans = []
                cur_changed = True
            # expire the prev line on its own timer
            if self._en_prev_plain and now - self._en_prev_at >= self._hold:
                self._en_prev_plain = ""
                self._en_prev_spans = []
                prev_changed = True
        if not cur_changed and not prev_changed and self._partial == self._last_partial:
            return None
        self._last_partial = self._partial
        state = DisplayState(
            current=list(self._en_spans),
            prev=list(self._en_prev_spans),
            partial=self._partial,
        )
        # change detection includes partial (set_partial may have changed it)
        if self._last_state is not None and state == self._last_state:
            return None
        self._last_state = state
        return state

    def _partial_changed(self) -> bool:
        return False  # handled in tick via _last_partial

    def state(self) -> DisplayState:
        """Return the current display state (snapshot) without advancing."""
        return DisplayState(
            current=list(self._en_spans),
            prev=list(self._en_prev_spans),
            partial=self._partial,
        )
