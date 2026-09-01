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
    partial_committed_len: int = 0                        # chars of `partial` that are committed
                                                          # (the split the view styles: stable vs tail)


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


def _truncate_spans(spans, n: int) -> list:
    """Spans covering the first n characters (the boundary span is split)."""
    out = []
    used = 0
    for sp in spans:
        if used + len(sp.text) <= n:
            out.append(sp)
            used += len(sp.text)
        elif used < n:
            out.append(Span(sp.text[:n - used], sp.style))
            used = n
            break
        else:
            break
    return out


def _spans_after(spans, n: int) -> list:
    """Spans covering everything beyond the first n characters."""
    out = []
    used = 0
    for sp in spans:
        t = sp.text
        if used + len(t) <= n:
            used += len(t)
            continue
        if used < n:
            t = t[n - used:]
            used = n
        out.append(Span(t, sp.style))
    return out


def _common_prefix_len(a: str, b: str) -> int:
    """Char common prefix, backtracked to a word boundary of `a` (CJK chars
    are their own words — no backtrack needed there)."""
    n = 0
    m = min(len(a), len(b))
    while n < m and a[n] == b[n]:
        n += 1
    if n < len(a) and n > 0:
        # backtrack to the last space so the kept prefix ends on a word edge
        cut = a.rfind(" ", 0, n + 1)
        if cut > 0:
            n = cut + 1
    return n


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
        self._partial_shown_at = clock()
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
        self._partial_committed_len: int = 0
        self._last_partial_committed_len: int = 0
        self._last_state: Optional[DisplayState] = None
        # set by in-place updates (append effect) so tick() emits the new state
        self._dirty = False

    # ---- event feed (mirrors OverlayRenderer callbacks) ----

    def set_partial(self, text: str, committed_len: int = 0) -> None:
        text = text or ""
        # monotonic display: with the same committed split, ANY shorter text is
        # a streaming-hypothesis regression (a prefix shrink, or a re-decode
        # rewording that retracts words) — hold the longer text until a commit
        # resolves it. Rendering the retraction is the "prefix flicker" CL
        # sees: words vanish, then re-appear a moment later. Legitimate resets
        # (a commit or a new sentence after a promote) change committed_len
        # and pass through.
        cur, cur_cl = self._partial, self._partial_committed_len
        if (text and cur and committed_len == cur_cl
                and len(text) < len(cur)):
            return
        self._partial = text
        self._partial_committed_len = max(0, min(committed_len, len(text)))
        self._partial_shown_at = self._clock()

    def clear_partial(self) -> None:
        self._partial = ""
        self._partial_committed_len = 0

    def preview(self, segments: list, started_at) -> None:
        """Provisional translation with the append effect.

        - extends the shown draft  -> APPEND in place: the line grows on screen,
          no scroll-up, no retype, no hold. The new words just appear at the
          end of the existing draft (the view streams the delta word-by-word).
        - rewrites the draft       -> replace IN PLACE: the stale draft is
          discarded (not scrolled to history — it was wrong, it is not
          history-worthy), the new draft shows after the hold.
        - unchanged                -> skip.

        Utterance identity is structural (provisional vs final state), NOT the
        started_at timestamp: callers pass datetime.now() per update, so
        timestamp equality cannot detect same-utterance transitions.
        """
        plain = _segments_plain(segments)
        shown = self._en_plain
        if plain == shown:
            return  # skip (unchanged)
        if shown and not self._en_is_final and plain.startswith(shown):
            # append effect: the draft grew — extend the line in place.
            # No scroll-up, no retype, no hold: the new words appear at the end
            # and the view streams the delta word-by-word.
            self._en_plain = plain
            self._en_spans = _segments_to_spans(segments, is_final=False)
            self._en_is_final = False
            # keep the next final immediately releasable
            self._en_shown_at = self._clock() - self._hold
            self._queue.clear()  # a queued item is stale — the line shows the latest
            self._dirty = True
            return
        if shown and not self._en_is_final:
            # draft rewrite: the MT self-corrected mid-draft. Keep the common
            # prefix on screen (word-aligned) and enqueue only the divergent
            # suffix as an AMEND — the correction types out instead of the
            # whole line flashing (CL: non-appending provisional). A rewrite
            # is never scrolled to history (it was wrong; history shows finals).
            cpl = _common_prefix_len(shown, plain)
            if cpl > 0:
                self._en_plain = shown[:cpl]
                self._en_spans = _truncate_spans(self._en_spans, cpl)
                spans = _segments_to_spans(segments, is_final=False)
                delta_spans = _spans_after(spans, cpl)
                self._enqueue(delta_spans, plain[cpl:], started_at,
                              is_final=False, amend=True)
                self._en_shown_at = self._clock() - self._hold
                self._dirty = True
                return
            self._en_plain = ""
            self._en_spans = []
        spans = _segments_to_spans(segments, is_final=False)
        # A draft queues behind a shown final's hold — the reader keeps the
        # polished sentence. With endpointing-owned segment closure the
        # inter-final gaps (~5s+) exceed the hold, so queued drafts pop and
        # display (the old starvation came from 2s fragment finals, fixed
        # generation-side). The draft covers the same content plus the new
        # clause, so a late release loses nothing.
        self._enqueue(spans, plain, started_at, is_final=False,
                      respect_hold=shown and self._en_is_final)

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
            # if there's no common prefix (committed=""), this is a genuinely
            # different caption — the next utterance's final. If the shown line
            # is a final still inside its hold, QUEUE behind it instead of
            # flashing it away: back-to-back finals (e.g. dermatology -> in-short
            # 0.37s apart on zh->ja) replaced each other instantly and the
            # reader never got the hold (CL).
            if not committed and shown:
                if self._en_is_final:
                    self._enqueue(_segments_to_spans(segments, is_final=True),
                                  plain, started_at, is_final=True,
                                  respect_hold=True)
                    return
            if committed:
                # the committed prefix stays as the current line (now final
                # style) and the whole final text amends it in place — the line
                # stays one coherent caption (same-utterance correction).
                self._en_plain = plain
                self._en_spans = _segments_to_spans(segments, is_final=True)
                self._en_is_final = True
                self._en_shown_at = self._clock()
                # the final supersedes anything queued (e.g. its own still-pending
                # draft): leaving it queued would pop a stale dim draft over this
                # bright final if the speaker pauses past the hold.
                self._queue.clear()
                self._dirty = True
                return
            # shown draft, no common prefix: discard the draft in place and
            # enqueue the final (falls through to the enqueue below)
            self._en_plain = ""
            self._en_spans = []
        # no shown provisional: full enqueue
        spans = _segments_to_spans(segments, is_final=True)
        self._enqueue(spans, plain, started_at, is_final=True)

    def _enqueue(self, spans: List[Span], plain: str, started_at, is_final: bool,
                 respect_hold: bool = False, amend: bool = False) -> None:
        utt_t = started_at.timestamp() if started_at is not None else None
        # If this final corrects a provisional of the same utterance currently on screen,
        # replace in place: drop the provisional so the drainer won't scroll it up.
        if (is_final and utt_t is not None
                and self._en_utt == utt_t and not self._en_is_final):
            self._en_plain = ""
            self._en_spans = []
        if is_final:
            # FINALS ACCUMULATE — a queued final is committed content and must
            # display; clearing the queue (the draft rule) dropped finals that
            # landed back-to-back (CL: 'not queueing translated strings if
            # they happen immediately after the last'). Drafts supersede.
            self._queue.append((spans, plain, utt_t, is_final, amend))
            del self._queue[:-3]
        else:
            self._queue.clear()
            self._queue.append((spans, plain, utt_t, is_final, amend))
        if not respect_hold:
            self._en_shown_at = -self._hold  # release immediately on the next tick
        # else: the queued item waits for the shown caption's hold to elapse

    # ---- the drainer (advance the hold timers) ----

    def tick(self) -> Optional[DisplayState]:
        """Advance the drainer one step. Returns the DisplayState to render if something
        changed, or None if the display is unchanged (the view can skip)."""
        now = self._clock()
        # A queued item waits MIN_SHOW (half the hold) once a FINAL is shown —
        # back-to-back finals each get a readable minimum instead of flashing
        # (CL: the dermatology final was replaced 0.37s after landing). With
        # nothing queued, the shown final holds for the full hold before expiry.
        min_show = max(1.0, self._hold / 2)
        cur_changed = False
        prev_changed = False
        if self._queue and now - self._en_shown_at >= min(self._hold, min_show):
            item = self._queue.pop(0)
            if len(item) == 5:
                spans, plain, utt_t, is_final, amend = item
            else:
                spans, plain, utt_t, is_final = item
                amend = False
            if amend:
                # Append-flagged delta sentence: grow the current line (it
                # already holds the committed prefix). No scroll — the line
                # stays one coherent caption.
                joiner = "" if (not self._en_plain or plain[:1].isspace()
                                or self._en_plain[-1:].isspace()) else " "
                if joiner:
                    self._en_spans.append(Span(joiner, FINAL_SAME))
                self._en_plain += joiner + plain
                self._en_spans = self._en_spans + list(spans)
                self._en_utt = utt_t
                self._en_is_final = is_final
                self._en_shown_at = now
                cur_changed = True
            else:
                same_utt = utt_t is not None and utt_t == self._en_utt
                # Scroll only FINALS into history. Drafts (provisionals) are never
                # history-worthy: growth appends in place, rewrites replace in
                # place — the reader sees one growing line, not churn.
                scroll_up = (self._en_plain and plain != self._en_plain
                             and self._en_is_final)
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
            # expire the src row after the hold with no ASR activity (mic silence):
            # a stale reading buffer that never clears reads as a stuck caption.
            # The buffer itself keeps its committed text — speech resumes it.
            if (self._partial and now - self._partial_shown_at >= self._hold):
                self._partial = ""
                self._partial_committed_len = 0
                cur_changed = True
            # expire the prev line on its own timer
            if self._en_prev_plain and now - self._en_prev_at >= self._hold:
                self._en_prev_plain = ""
                self._en_prev_spans = []
                prev_changed = True
        if self._dirty:
            cur_changed = True
            self._dirty = False
        if (not cur_changed and not prev_changed
                and self._partial == self._last_partial
                and self._partial_committed_len == self._last_partial_committed_len):
            return None
        self._last_partial = self._partial
        self._last_partial_committed_len = self._partial_committed_len
        state = DisplayState(
            current=list(self._en_spans),
            prev=list(self._en_prev_spans),
            partial=self._partial,
            partial_committed_len=self._partial_committed_len,
        )
        # change detection includes partial (set_partial may have changed it)
        if self._last_state is not None and state == self._last_state:
            return None
        self._last_state = state
        return state


    def state(self) -> DisplayState:
        """Return the current display state (snapshot) without advancing."""
        return DisplayState(
            current=list(self._en_spans),
            prev=list(self._en_prev_spans),
            partial=self._partial,
            partial_committed_len=self._partial_committed_len,
        )
