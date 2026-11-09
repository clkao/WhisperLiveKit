"""Caption display model: a pure state machine from caption events to
display state.

``CaptionDisplay`` is the display-semantics layer, and it is a consumer of
the caption event stream (``caption_events.py``): ``emit()`` is the
``EventSink`` entry point, so the model attaches to the pipeline's
``EventTap`` like any other sink. It produces ``DisplayState``: styled
spans for the active caption line, the scrolled-up line above it, and the
ASR source partial, with the hold-drain, provisional-to-final replacement,
sentence-partitioning and monotonic-source rules.

Views are thin consumers: they map span tags to colours, render
``DisplayState``, and call ``tick()`` on their own frame clock. The event
payload carries plain text only — no segments, speaker markers or diff
spans — so the model derives its own styling:

Styling:
  - provisional: dimmed (a draft, clearly not the final word)
  - final same:  bright (unchanged from the provisional)
  - final add:   green (the correction or the new words)
  - deletions are omitted from the final display: the old words simply
    vanish, the green additions show what changed. The provisional is
    shown dimmed first, so the reader sees the draft, then the bright
    final with green corrections replaces it.

Threading contract: events are produced inside the pipeline's asyncio
tasks (the ASR and translation loops) and forwarded by the tap
synchronously on the event loop thread. ``CaptionDisplay`` is
single-threaded: call ``emit()`` or the feed methods only from that loop
thread. A view that renders on another thread (a native GUI loop) must
marshal state across to its own thread; ``DisplayState`` is plain data and
safe to hand off.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from whisperlivekit.caption_events import CaptionEvent

# Hunyuan placeholder artifact (fullwidth-pipe-delimited token). The MT backend
# emits its template marker into the text for some prompts; it is model
# plumbing, never caption content, so it is stripped before a view sees it.
_HY_PLACEHOLDER_RE = re.compile(r"<[\|｜][^\|｜]*[\|｜]>")


def _strip_hy_placeholder(text: str) -> str:
    if not text:
        return text
    return _HY_PLACEHOLDER_RE.sub("", text)


# Style tags (the "DOM" node kinds). Views map these to colors;
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
    """A snapshot of the two target lines + the source partial, as styled spans.
    Tests assert on this; views render it."""
    current: List[Span] = field(default_factory=list)   # the active caption line
    prev: List[Span] = field(default_factory=list)      # the scrolled-up history line
    partial: str = ""                                    # the ASR source partial (plain)


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


def _suffix_span(text: str, n: int, style: str) -> List[Span]:
    """The single span covering `text` beyond its first n characters."""
    return [Span(text[n:], style)] if len(text) > n else []


@dataclass
class _Item:
    """One hold-queue entry (a caption to show when its hold elapses).

    sent_idx: position of this sentence within the utterance's sentence
    stream (-1 = whole-line item, the pre-sentence-queue shape). The
    translation() reconcile uses it to amend/replace routed sentences
    without touching what is already scrolled into history.
    provisional: routed from the running draft (not yet confirmed by a
    final) — translation() replaces these with authoritative sentences.
    """
    spans: List[Span]
    plain: str
    is_final: bool
    amend: bool = False
    sent_idx: int = -1
    provisional: bool = False


def _diff_spans(old: str, new: str) -> List[Span]:
    """Word-level diff spans old->new: unchanged words bright (FINAL_SAME),
    changed/added words green (FINAL_ADD); deletions omitted — the same
    styling the caller-provided diff spans use for whole-line amends."""
    import difflib
    ow, nw = old.split(), new.split()
    spans: List[Span] = []
    sm = difflib.SequenceMatcher(a=ow, b=nw, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        words = ow[i1:i2] if op == "equal" else nw[j1:j2]
        if not words:
            continue
        style = FINAL_SAME if op == "equal" else FINAL_ADD
        # CJK has no spaces (each char is its own word) — rejoin tightly;
        # Latin words rejoin with single spaces
        if all(len(w) <= 1 for w in words) and not any(ch.isspace() for ch in words):
            text = "".join(words)
        else:
            text = " ".join(words)
        if spans:
            text = " " + text
        spans.append(Span(text, style))
    return spans


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


# Sentence terminators for the caption sentence queue: Latin and CJK.
_SENTENCE_TERMINATORS = set(".!?。！？")


def _split_sentences(text: str) -> Tuple[List[str], str]:
    """Split a caption text at sentence terminators.

    Returns (complete_sentences, trailing_fragment). Each sentence keeps its
    terminator attached; the trailing run without a terminator is the
    in-progress fragment ('' when the text ends on a terminator). The split is
    deliberately naive (no abbreviation handling) — same policy as the
    generation-side sentence pacing; a false split mid-abbreviation costs one
    early line break, not a content change.
    """
    sentences: List[str] = []
    start = 0
    for i, ch in enumerate(text):
        if ch in _SENTENCE_TERMINATORS:
            sentences.append(text[start:i + 1].lstrip())
            start = i + 1
    return sentences, text[start:].lstrip()


class CaptionDisplay:
    """Pure display-policy state machine for the caption target lines.

    Feed it the caption event stream via ``emit()`` (the ``EventSink``
    contract) and call ``tick()`` to advance the hold-drain. ``tick`` returns
    the ``DisplayState`` to render (or None if nothing changed since the last
    tick — the view can skip).

    The clock is injectable (``clock`` returns monotonic seconds) so tests are
    deterministic; production passes ``time.monotonic``.
    """

    def __init__(self, hold_sec: float, clock=time.monotonic) -> None:
        self._hold = hold_sec
        self._clock = clock
        self._partial_shown_at = clock()
        # current line
        self._en_plain: str = ""
        self._en_spans: List[Span] = []
        self._en_is_final: bool = False
        self._en_shown_at: float = -hold_sec
        # prev (history) line
        self._en_prev_plain: str = ""
        self._en_prev_spans: List[Span] = []
        self._en_prev_at: float = 0.0
        # pending (the reader's backlog: content not on the line yet). NOT
        # capped — every completed caption in it must display, so evicting the
        # oldest drops a caption the reader never saw. The drainer releases one
        # item per min(hold, max(1.0, hold / 2)) seconds; a producer that
        # outruns the drainer deepens the backlog instead of losing captions.
        # The only superseded content is a DRAFT (the newest in-progress
        # fragment wins: see _keep_committed).
        self._queue: List = []
        # sentence-partitioned state: the translated stream is routed per
        # sentence — a completed sentence (draft crossed a terminator, or a
        # final) becomes its own bright hold-queue item; the current line
        # carries only the in-progress sentence's fragment.
        self._en_draft_full: str = ""   # cumulative draft text seen this utterance
        self._en_sent_texts: List[str] = []  # routed sentence texts, in order
        self._en_current_sent: int = -1  # sentence index on the current line (-1 = fragment/none)
        self._en_line_prov: bool = False  # the line holds a DRAFT-routed sentence of this utterance
        self._en_frag: str = ""         # the fragment text currently on the line
        self._queued_draft: Optional[_Item] = None  # in-progress fragment waiting behind bright sentences
        # in-place promotion (round 3): the sentence the reader is watching type
        # promotes at its terminator WITHOUT a queue round-trip — it scrolls
        # bright to the prev line and the fragment keeps typing. These track
        # where each routed sentence landed so the final's reconcile amends
        # the right surface instead of clearing and re-rendering (the retype).
        self._en_prev_sent_idx: int = -1   # sentence scrolled to prev (draft-routed)
        self._en_line_sent: int = -1       # sentence the current line's fragment belongs to
        # source partial
        self._partial: str = ""
        self._last_partial: str = ""  # for change detection
        self._last_state: Optional[DisplayState] = None
        # set by in-place updates (append effect) so tick() emits the new state
        self._dirty = False

    # ---- event feed (the EventSink contract — how the pipeline drives this) ----

    def emit(self, event: CaptionEvent) -> None:
        """Consume one caption event (the ``EventSink`` entry point).

        The event's ``type`` selects the display rule:

          transcription_provisional -> the rolling ASR tail (``set_partial``)
          transcription_final       -> the commit; the tail it absorbed is
                                       dropped (``clear_partial``) and the
                                       source line then times out on its own
          translation_provisional   -> a dim draft (``preview``)
          translation_final         -> committed caption text (``translation``)

        The provisional columns ``committed``/``source``/``fresh`` describe what
        the MT drafted against and whether it cost a forward pass; the display
        renders ``text`` and leaves those to metrics consumers. An unknown kind
        is not a display event: ignored.
        """
        kind = event.type
        if kind == "transcription_provisional":
            self.set_partial(event.text)
        elif kind == "transcription_final":
            self.clear_partial()
        elif kind == "translation_provisional":
            self.preview(event.text)
        elif kind == "translation_final":
            self.translation(event.text)

    # ---- feed methods (what emit() calls; tests drive them directly) ----

    def set_partial(self, text: str) -> None:
        """Set the source partial (the rolling, uncommitted ASR tail).

        Monotonic source display: ANY shorter text is a streaming-hypothesis
        regression (a prefix shrink, or a re-decode that retracts words) — hold
        the longer text until a commit resolves it. Rendering the retraction is
        the prefix flicker CL sees: words vanish, then re-appear a moment
        later. The commit arrives as its own ``transcription_final`` event,
        which clears the partial, so a post-commit reset is not a shrink
        against a shown line.
        """
        text = _strip_hy_placeholder(text or "")
        cur = self._partial
        if text and cur and len(text) < len(cur):
            return
        self._partial = text
        self._partial_shown_at = self._clock()

    def clear_partial(self) -> None:
        self._partial = ""

    def preview(self, text: str) -> None:
        """Provisional translation with the append effect.

        Sentence-partitioned: when the running draft crosses a sentence
        terminator, the completed sentence becomes its own bright hold-queue
        item and the line carries only the in-progress fragment. Before the
        first terminator the legacy single-line draft behavior applies
        (append effect / rewrite / enqueue).
        """
        plain = _strip_hy_placeholder(text or "")
        if plain == self._en_draft_full:
            return  # skip (unchanged)
        appended = bool(self._en_draft_full) and plain.startswith(self._en_draft_full)
        prev_draft = self._en_draft_full
        completed, fragment = _split_sentences(plain)

        if not self._en_sent_texts and len(completed) == 0:
            # No sentence boundary crossed yet: legacy one-line draft behavior.
            self._en_draft_full = plain
            self._preview_legacy(plain)
            return
        if not self._en_sent_texts and not fragment and len(completed) <= 1:
            # The draft ends exactly on a terminator: still a single caption —
            # the legacy path holds it (the final re-words it anyway). Freezing
            # here would brighten a draft the MT may still reword. A draft that
            # already spans MULTIPLE sentences routes below instead: those
            # sentences must not ride one growing line (round 1).
            self._en_draft_full = plain
            self._preview_legacy(plain)
            return

        # ---- sentence-aware routing ----
        # Route newly completed sentences (positional match: the committed
        # draft grows append-only; a rewrite re-derives per position below).
        # Round 3: the sentence the reader is WATCHING type (the line is a
        # draft that starts with it) promotes IN PLACE — it scrolls bright to
        # the prev line and the fragment keeps typing. No queue round-trip, no
        # re-render of identical text. The queue is reserved for genuinely
        # backlogged content (sentences that complete while a different
        # caption holds the line, multi-crossing updates, final-only
        # sentences).
        prev_texts = self._en_sent_texts
        new_completed = [(i, s) for i, s in enumerate(completed)
                         if i >= len(prev_texts)]
        # Promote IN PLACE every completing sentence the line already carries
        # (the reader watched it type): each scrolls bright to the prev line,
        # the line keeps the remainder. Content the line never showed queues
        # instead — an unseen sentence must not pop onto history untyped.
        remaining = self._en_plain if (not self._en_is_final and self._en_plain) else None
        for i, s in enumerate(completed):
            if i < len(prev_texts):
                if s != prev_texts[i]:
                    self._amend_routed_sentence(i, s)
                continue
            if (i < len(prev_texts) + len(new_completed) and remaining
                    and (remaining.startswith(s) or s.startswith(remaining))):
                # scroll the just-completed sentence bright to the prev line;
                # the line continues with what it still holds of the draft
                self._en_prev_plain = s
                self._en_prev_spans = [Span(s, FINAL_SAME)]
                self._en_prev_at = self._clock()
                self._en_prev_sent_idx = i
                remaining = remaining[len(s):].lstrip() if remaining.startswith(s) else ""
            else:
                self._enqueue_sentence(s, i, authoritative=False)
        self._en_sent_texts = completed
        self._en_draft_full = plain
        if self._en_prev_sent_idx >= 0 and remaining is not None:
            # the line keeps only the in-progress fragment. When the line held
            # the promoted sentence's tail, the remainder is already consumed
            # by the promotion; when the line was mid-sentence (a strict
            # prefix of it), the untyped tail pops in on the prev line and the
            # line takes the new draft's fragment. Either way this is a layout
            # split, not a re-render of typed content.
            self._en_plain = fragment
            self._en_spans = [Span(fragment, PROVISIONAL)] if fragment else []
            self._en_frag = fragment
            self._en_is_final = False
            self._en_current_sent = -1
            self._en_line_prov = False
            self._en_line_sent = len(completed) if fragment else -1
            self._en_shown_at = self._clock() - self._hold  # fragments don't hold
            self._dirty = True
        else:
            self._en_line_sent = len(completed) if fragment else -1
            self._update_fragment(fragment, plain, appended, prev_draft)
        self._dirty = True

    def _keep_committed(self) -> None:
        """Drop queued DRAFT items, keep queued COMMITTED (final) sentences.

        'Drafts supersede' was written for draft-routed items; applied
        wholesale it dropped queued completed sentences (bright, committed
        content the reader has not seen yet) the moment the next utterance's
        draft arrived. A draft may only supersede other drafts — never a
        completed sentence (round-2: the dentist-final backlog was wiped by
        the next segment's 'In short.' draft).
        """
        if any(not getattr(it, "is_final", False) for it in self._queue):
            self._queue = [it for it in self._queue if getattr(it, "is_final", False)]

    def _preview_legacy(self, plain: str) -> None:
        """Pre-sentence-queue draft behavior (no boundary crossed yet)."""
        shown = self._en_plain
        if shown and not self._en_is_final and plain.startswith(shown):
            # append effect: the draft grew — extend the line in place.
            # No scroll-up, no retype, no hold: the new words appear at the end
            # and the view streams the delta word-by-word.
            self._en_plain = plain
            self._en_spans = [Span(plain, PROVISIONAL)]
            self._en_is_final = False
            # keep the next final immediately releasable
            self._en_shown_at = self._clock() - self._hold
            self._keep_committed()  # drafts supersede drafts, never completed sentences
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
                delta_spans = _suffix_span(plain, cpl, PROVISIONAL)
                self._enqueue_item(_Item(delta_spans, plain[cpl:], is_final=False, amend=True))
                self._en_shown_at = self._clock() - self._hold
                self._dirty = True
                return
            self._en_plain = ""
            self._en_spans = []
        spans = [Span(plain, PROVISIONAL)]
        # A draft queues behind a shown final's hold — the reader keeps the
        # polished sentence. With endpointing-owned segment closure the
        # inter-final gaps (~5s+) exceed the hold, so queued drafts pop and
        # display (the old starvation came from 2s fragment finals, fixed
        # generation-side). The draft covers the same content plus the new
        # clause, so a late release loses nothing.
        self._enqueue_item(_Item(spans, plain, is_final=False),
                      respect_hold=shown and self._en_is_final)

    def _enqueue_sentence(self, text: str, sent_idx: int,
                          authoritative: bool = False) -> None:
        """Route a completed sentence as its own bright hold-queue item.

        Inserted BEFORE any queued fragment draft (the sentence is older
        content than the in-progress sentence); the queued draft always stays
        last so the reader sees sentences in order. ``sent_idx`` is the
        utterance-local sentence position; ``provisional`` marks items routed
        from the draft stream (the final's reconcile replaces them with the
        authoritative wording). The insert is uncapped: the sentence waits in
        the backlog until the drainer shows it, so no enqueue may evict an
        older unshown caption.
        """
        item = _Item([Span(text, FINAL_SAME)], text,
                     is_final=True, sent_idx=sent_idx,
                     provisional=not authoritative)
        # insertion point: before a trailing queued draft (the fragment),
        # after any earlier queued sentences
        cut = len(self._queue)
        while cut > 0 and self._queue[cut - 1] is self._queued_draft:
            cut -= 1
        self._queue.insert(cut, item)

    def _amend_routed_sentence(self, idx: int, text: str) -> None:
        """A re-route (reword) of an already-routed sentence.

        - on the current line: amend in place (word diff, green adds)
        - still queued       -> replace the queued item
        - already history    -> leave (the next sentence scrolls in soon)
        """
        if idx == self._en_prev_sent_idx and self._en_prev_plain:
            # the sentence already scrolled to history: correct it there
            self._en_prev_plain = text
            self._en_prev_spans = [Span(text, FINAL_SAME)]
            self._dirty = True
            return
        if idx == self._en_current_sent and self._en_plain:
            self._en_spans = _diff_spans(self._en_plain, text)
            self._en_plain = text
            self._en_shown_at = self._clock()
            self._dirty = True
            return
        for q in self._queue:
            if getattr(q, "sent_idx", -1) == idx and getattr(q, "provisional", False):
                q.plain = text
                q.spans = [Span(text, FINAL_SAME)]
                return
        # in history (or nowhere): leave — the next sentence scrolls in soon

    def _update_fragment(self, fragment: str, plain: str,
                         appended: bool, prev_draft: str) -> None:
        """Show/queue the in-progress sentence's fragment.

        - bright sentence on the line -> the fragment waits in _queued_draft
          (updated in place; drafts supersede, bright items are never dropped)
        - fragment on the line        -> append effect within the sentence,
          or a word-aligned rewrite (reword) that types the correction
        """
        if fragment == self._en_frag and not self._queued_draft:
            return
        if self._en_current_sent >= 0:
            # a bright sentence holds the line — park the fragment behind it
            if fragment:
                self._queued_draft = _Item([Span(fragment, PROVISIONAL)], fragment,
                                           is_final=False)
            else:
                self._queued_draft = None
            return
        shown = self._en_plain
        if shown and self._en_frag and appended and fragment.startswith(self._en_frag):
            # append effect within the sentence (the delta types on); the draft
            # grew by exactly the delta beyond the previous full draft
            delta = _suffix_span(plain, len(prev_draft), PROVISIONAL)
            self._en_plain = fragment
            self._en_spans = self._en_spans + delta
            self._en_frag = fragment
            self._en_is_final = False
            self._en_shown_at = self._clock() - self._hold
            self._dirty = True
            return
        if shown and self._en_frag:
            # rewrite within the sentence: keep the common prefix, enqueue the
            # divergent suffix as an amend (the correction types out)
            cpl = _common_prefix_len(self._en_frag, fragment)
            if cpl > 0:
                self._en_plain = self._en_frag[:cpl]
                self._en_spans = _truncate_spans(self._en_spans, cpl)
                delta = _Item([Span(fragment[cpl:], PROVISIONAL)], fragment[cpl:],
                              is_final=False, amend=True)
                self._enqueue_item(delta, respect_hold=False)
                self._en_frag = fragment
                self._en_shown_at = self._clock() - self._hold
                self._dirty = True
                return
        # fresh fragment line (a new sentence started on the current line)
        self._en_plain = fragment
        self._en_spans = [Span(fragment, PROVISIONAL)] if fragment else []
        self._en_frag = fragment
        self._en_current_sent = -1
        self._en_is_final = False
        self._en_shown_at = self._clock() - self._hold
        self._dirty = True

    def translation(self, text: str) -> None:
        """Final translation, partitioned by sentence.

        The final is AUTHORITATIVE for its own utterance: it replaces the
        draft-routed sentence items (reworded ones amend the line/queue; new
        ones enqueue), while completed sentences from EARLIER utterances still
        queued or on screen are left untouched. Each sentence is its own
        display item and earns its own hold.
        """
        plain = _strip_hy_placeholder(text or "")
        sents, fragment = _split_sentences(plain)
        if not sents and fragment:
            sents, fragment = [fragment], ""
        # pending committed sentences from PRIOR utterances survive (finals
        # accumulate); this utterance's draft-routed queued items are replaced
        # by the authoritative sentences below
        kept = [it for it in self._queue if not getattr(it, "provisional", False)]
        if len(sents) <= 1 and not self._en_sent_texts:
            # single-sentence utterance with no draft-routed sentences: the
            # legacy whole-line path (unchanged semantics)
            self._translation_legacy(plain)
            self._en_draft_full = plain
            self._en_frag = ""
            self._queued_draft = None
            return

        # prev line: this utterance's draft-promoted sentence — the final is
        # authoritative; reword it in place (the history line corrects, no
        # re-render of a different sentence)
        if 0 <= self._en_prev_sent_idx < len(sents):
            auth = sents[self._en_prev_sent_idx]
            if auth != self._en_prev_plain:
                self._en_prev_plain = auth
                self._en_prev_spans = [Span(auth, FINAL_SAME)]
                self._dirty = True
        # the line: a dim draft fragment of a known sentence is superseded IN
        # PLACE by that sentence's authoritative text (the delta types out) —
        # clearing it and queueing the sentence instead re-rendered content
        # the reader had just watched type (round-3: the dentist retype).
        line_j = -1
        if self._en_plain and not self._en_is_final and 0 <= self._en_line_sent:
            line_j = min(self._en_line_sent, len(sents) - 1)
        cur_i = self._en_current_sent if (self._en_is_final and self._en_line_prov) else -1
        start = 0
        if line_j >= 0:
            auth = sents[line_j]
            self._en_spans = _diff_spans(self._en_plain, auth)
            self._en_plain = auth
            self._en_is_final = True
            self._en_line_prov = True
            self._en_current_sent = line_j
            self._en_frag = ""
            self._en_shown_at = self._clock()
            self._dirty = True
            start = line_j + 1
        elif cur_i is not None and cur_i >= 0 and cur_i < len(sents):
            # the sentence on the line amends in place when reworded
            if sents[cur_i] != self._en_plain:
                self._en_spans = _diff_spans(self._en_plain, sents[cur_i])
                self._en_plain = sents[cur_i]
                self._en_is_final = True
                self._en_shown_at = self._clock()
                self._dirty = True
            start = cur_i + 1
        elif self._en_plain and self._en_is_final:
            # a whole-line final (legacy shape) holds the line: all of this
            # final's sentences queue behind it (back-to-back pacing)
            start = 0
        new_items = [
            _Item([Span(s, FINAL_SAME)], s, is_final=True, sent_idx=i)
            for i, s in enumerate(sents) if i >= start
        ]
        # the reader's backlog keeps every completed sentence: a later final
        # must never evict one that has not displayed yet (F-1)
        self._queue = kept + new_items
        if not self._en_plain and self._queue:
            self._en_shown_at = -self._hold  # first item releases immediately
        # authoritative baseline for the next draft cycle; the draft routing
        # is per-utterance (the next utterance's sentences start fresh at 0)
        self._en_sent_texts = []
        self._en_prev_sent_idx = -1
        self._en_line_sent = -1
        self._en_draft_full = plain
        self._en_frag = fragment
        self._dirty = True

    def _translation_legacy(self, plain: str) -> None:
        """Pre-sentence-queue final path (single-sentence captions)."""
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
            # plain[cpl:] is the new content; if there's no common prefix (committed=""), this is a genuinely
            # different caption — the next utterance's final. If the shown line
            # is a final still inside its hold, QUEUE behind it instead of
            # flashing it away: back-to-back finals (e.g. dermatology -> in-short
            # 0.37s apart on zh->ja) replaced each other instantly and the
            # reader never got the hold (CL).
            if not committed and shown:
                if self._en_is_final:
                    self._enqueue([Span(plain, FINAL_SAME)], plain, is_final=True,
                                  respect_hold=True)
                    return
            if committed:
                # the committed prefix stays as the current line (now final
                # style) and the whole final text amends it in place — the line
                # stays one coherent caption (same-utterance correction).
                self._en_plain = plain
                self._en_spans = [Span(plain, FINAL_SAME)]
                self._en_is_final = True
                self._en_shown_at = self._clock()
                # the final supersedes queued DRAFTS (e.g. its own still-pending
                # draft): leaving it queued would pop a stale dim draft over this
                # bright final if the speaker pauses past the hold. Committed
                # sentences from PRIOR finals stay queued — finals accumulate.
                self._keep_committed()
                self._dirty = True
                return
            # shown draft, no common prefix: discard the draft in place and
            # enqueue the final (falls through to the enqueue below)
            self._en_plain = ""
            self._en_spans = []
        # no shown provisional: full enqueue. FIFO behind pending committed
        # sentences: a new final must never jump the queue ahead of completed
        # sentences the reader has not seen yet (round-2: 'In summary' jumped
        # the dentist final's queued sentences). Immediate release only when
        # nothing committed is pending.
        spans = [Span(plain, FINAL_SAME)]
        respect = any(getattr(it, "is_final", False) for it in self._queue)
        self._enqueue(spans, plain, is_final=True, respect_hold=respect)

    def _enqueue(self, spans: List[Span], plain: str, is_final: bool,
                 respect_hold: bool = False, amend: bool = False, sent_idx: int = -1) -> None:
        self._enqueue_item(_Item(spans, plain, is_final,
                                 amend=amend, sent_idx=sent_idx),
                           respect_hold=respect_hold)

    def _enqueue_item(self, item: _Item, respect_hold: bool = False) -> None:
        # A final supersedes a provisional on the line: drop the provisional so
        # the drainer does not scroll a draft up as if it were history.
        if item.is_final and self._en_plain and not self._en_is_final:
            self._en_plain = ""
            self._en_spans = []
        if item.is_final:
            # FINALS ACCUMULATE — a queued final is committed content and must
            # display; clearing the queue (the draft rule) dropped finals that
            # landed back-to-back (CL: 'not queueing translated strings if
            # they happen immediately after the last'). Drafts supersede.
            self._queue.append(item)  # uncapped — see __init__: never evicted
        else:
            # a draft supersedes queued DRAFTS — never committed sentences:
            # a queued final is content the reader has not seen yet; dropping
            # it lost the tail sentences of a multi-sentence final whenever the
            # next utterance's draft arrived (round-2: dermatology regression).
            self._keep_committed()
            self._queue.append(item)
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
            spans, plain = item.spans, item.plain
            is_final, amend = item.is_final, item.amend
            self._en_current_sent = item.sent_idx
            # provenance: only a DRAFT-routed sentence (provisional, this
            # utterance) may be amended by this utterance's final; a final-
            # routed or legacy line is a previous utterance's caption
            self._en_line_prov = bool(getattr(item, "provisional", False)
                                      and getattr(item, "sent_idx", -1) >= 0)
            self._en_frag = ""
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
                self._en_is_final = is_final
                self._en_shown_at = now
                cur_changed = True
            else:
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
                self._en_is_final = is_final
                self._en_shown_at = now
                cur_changed = True
        else:
            # the parked fragment draft returns after the bright sentence's
            # full hold — the sentence earns its hold BEFORE the in-progress
            # line resumes typing (a draft never preempts committed content)
            if (self._queued_draft and self._en_is_final
                    and now - self._en_shown_at >= self._hold):
                d = self._queued_draft
                self._queued_draft = None
                self._en_plain = d.plain
                self._en_spans = list(d.spans)
                self._en_is_final = False
                self._en_current_sent = -1
                self._en_frag = d.plain
                self._en_shown_at = now - self._hold  # drafts don't hold
                cur_changed = True
            # expire the current line if its hold elapsed with nothing queued — but
            # ONLY for finals. A provisional is a draft the viewer expects to be
            # followed by the committed/final; it must persist until replaced, not
            # vanish after the hold (a vanishing draft reads as a dropped caption).
            elif (self._en_plain and self._en_is_final
                    and now - self._en_shown_at >= self._hold):
                self._en_plain = ""
                self._en_spans = []
                self._en_is_final = False
                self._en_current_sent = -1
                cur_changed = True
            # expire the src row after the hold with no ASR activity (mic silence):
            # a stale reading buffer that never clears reads as a stuck caption.
            # The buffer itself keeps its committed text — speech resumes it.
            if (self._partial and now - self._partial_shown_at >= self._hold):
                self._partial = ""
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
                and self._partial == self._last_partial):
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

    def state(self) -> DisplayState:
        """Return the current display state (snapshot) without advancing."""
        return DisplayState(
            current=list(self._en_spans),
            prev=list(self._en_prev_spans),
            partial=self._partial,
        )


def load_caption_events(path) -> List[CaptionEvent]:
    """Read a recorded caption event stream back into events.

    ``EventLog`` is a write-only sink (it appends one JSONL line per event as
    the pipeline runs), so replay reads its output here: the events in the
    order they were emitted. Used by the replay instrument and the
    golden-stream regression tests.
    """
    return [
        CaptionEvent(**json.loads(line))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
