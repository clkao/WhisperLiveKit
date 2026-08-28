"""AccessibleBoundary adapter: nemotron-mlx time-based frontier → AlignAtt commit policy.

The nemotron transducer emits per-token `AlignedToken.start` timestamps
mid-decode into `_hypothesis`. The simul-MT commit policy currently uses
`committed_src_end_from_text` (a text-prefix match) to find the committed
source boundary — this works but ignores the timestamps.

This adapter provides a time-based boundary: source tokens whose `start`
time is <= the current audio-processed time are "committed" (accessible to
the MT commit policy); tokens with later timestamps are the unstable tail.

The adapter is a small function that, given nemotron's `_hypothesis` (list of
AlignedToken with .start and .text) and the current audio-processed time,
returns (committed_text, tail_text) — the same seam `_committed_text()` and
`_tail` use, but sourced from timestamps instead of the stable_text heuristic.

This is the "no-timestamp adapter" (compaction next-step #2): qwen3 uses the
stable_text proxy (no timestamps); nemotron uses this time-based adapter.
Both feed the same AlignAtt runtime.
"""
from __future__ import annotations
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class AlignedTokenLike:
    """Minimal shape of nemotron's AlignedToken (duck-typed)."""
    text: str
    start: Optional[float] = None


def time_based_boundary(
    hypothesis: List[AlignedTokenLike],
    audio_processed_s: float,
) -> Tuple[str, str]:
    """Split nemotron's hypothesis into (committed, tail) by audio time.

    Tokens with start <= audio_processed_s are committed; the rest are tail.
    Returns (committed_text, tail_text) — concatenated, stripped.

    This is the time-based accessible boundary. The simul-MT commit policy
    reads committed_text via `_committed_text()` and drafts over committed+tail
    via `_source_text()`. With this adapter, the boundary is principled (the
    ASR has actually decoded these tokens at these audio times) rather than
    the text-prefix heuristic.
    """
    if not hypothesis:
        return "", ""
    committed_parts: List[str] = []
    tail_parts: List[str] = []
    for tok in hypothesis:
        if tok.start is None:
            # No timestamp: treat as tail (conservative).
            tail_parts.append(tok.text)
        elif tok.start <= audio_processed_s:
            committed_parts.append(tok.text)
        else:
            tail_parts.append(tok.text)
    return "".join(committed_parts).strip(), "".join(tail_parts).strip()


def committed_src_end_from_time(
    hypothesis: List[AlignedTokenLike],
    audio_processed_s: float,
) -> int:
    """Count of source tokens committed by audio time (for the commit policy).

    Returns the number of hypothesis tokens whose start <= audio_processed_s.
    This replaces `committed_src_end_from_text`'s text-prefix match with a
    direct timestamp count — the principled boundary.
    """
    count = 0
    for tok in hypothesis:
        if tok.start is not None and tok.start <= audio_processed_s:
            count += 1
        else:
            break  # monotonic: once a token is in the future, the rest are too
    return count
