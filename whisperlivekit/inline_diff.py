"""CJK-aware inline diff for streaming text display (terminal + testable).

Extracted from livecaption (asr.py) for the TUI's provisional→final correction
rendering: struck-out gray old words + bold green new words, inline in the
final line — the same rendering as the ASR two-pass diff.

Tokens are CJK-aware (each Chinese char is a token, Latin runs stay whole
words), so punctuation/casing-only corrections don't produce spans. Token text
keeps its leading whitespace and a span is the verbatim concatenation of its
tokens, so the renderer joins spans with no separator — correct for Latin
spacing and spaceless CJK alike.
"""
from __future__ import annotations

import difflib
import re

# Edge punctuation ignored when comparing words for the inline diff (ASCII plus the
# curly quotes/dashes/ellipsis the model emits); inner apostrophes ("don't") survive.
_DIFF_TRIM = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~“”‘’„‛…—–"

# CJK / fullwidth codepoint ranges. Each such character is its own diff token: Chinese has no
# word boundaries, so a word-level split() would make a whole sentence one token and render
# any correction as a single del+add of the entire line. Latin/digit runs stay whole "words".
# Tokens keep their leading whitespace so "".join(tokens) reproduces the text verbatim -- the
# renderer then concatenates diff spans with no separator, keeping the spacing correct for
# Latin words and spaceless CJK alike.
_CJK = "　-〿㐀-䶿一-鿿豈-﫿＀-￯"
_DIFF_TOKEN_RE = re.compile(rf"\s*(?:[{_CJK}]|[^\s{_CJK}]+)")


def _diff_key(word: str) -> str:
    """Comparison key: casefold + strip edge punctuation. Corrections are mostly
    punctuation/casing touch-ups ("America" -> "America,"); rendering each as a del+add
    pair doubles the words and drowns the line in red/green noise, so those compare as
    equal and only true word changes show up as corrections (the final text still carries
    the corrected form -- "same" spans render the new words)."""
    # also strip whitespace: tokens keep a leading space for verbatim span text, but the
    # comparison key must treat " word" and "word" (segment-initial) as equal.
    return word.strip().strip(_DIFF_TRIM).casefold()


def _diff_tokenize(text: str) -> list[str]:
    return _DIFF_TOKEN_RE.findall(text)


def inline_diff(old: str, segs: list[str]) -> list[list[tuple[str, str]] | None]:
    """Whole-sentence diff sliced by final segments, for the terminal to render the
    correction effect inline within each final line.

    Returns a list the same length as segs; each item is [(kind, text)] spans
    (kind: same/del/add), or None if that segment has no correction. A deleted token
    is anchored to the segment that owns its position in the new text.
    """
    a = _diff_tokenize(old)
    seg_words = [_diff_tokenize(s) for s in segs]
    b = [w for ws in seg_words for w in ws]
    ops = difflib.SequenceMatcher(
        a=[_diff_key(w) for w in a], b=[_diff_key(w) for w in b], autojunk=False
    ).get_opcodes()
    out: list[list[tuple[str, str]] | None] = []
    lo = 0
    for si, ws in enumerate(seg_words):
        hi = lo + len(ws)
        last = si == len(seg_words) - 1
        spans: list[tuple[str, str]] = []
        for op, i1, i2, j1, j2 in ops:
            if op == "equal":
                jl, jh = max(j1, lo), min(j2, hi)
                if jl < jh:
                    spans.append(("same", "".join(b[jl:jh])))
                continue
            if i1 < i2 and (lo <= j1 < hi or (last and j1 >= hi)):
                spans.append(("del", "".join(a[i1:i2])))
            jl, jh = max(j1, lo), min(j2, hi)
            if jl < jh:
                spans.append(("add", "".join(b[jl:jh])))
        out.append(spans if any(k != "same" for k, _ in spans) else None)
        lo = hi
    return out
