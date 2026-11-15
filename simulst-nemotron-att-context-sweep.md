---
title: "Nemotron att_context sweep against the NeMo IWSLT 2026 anchor: is the WER gap configuration or model?"
status: backlog
score: 0.7
source: follow-up to the tier-2 two-direction benchmark; the ASR term dominates the chrF gap
id: 1514n3b7z79ms5gp1b2f8sjf
gates:
    version: 1
    records:
        - id: gate:1514n3b7z79ms5gp1b2f8sjf:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:1514n3b7z79ms5gp1b2f8sjf-backlog-1
              briefing:
                id: briefing:1514n3b7z79ms5gp1b2f8sjf:backlog:attempt-1:revision-1
                digest: sha256:2b5bddbaadb8e2792285f34e5ae19e5b3ff7bc0546fc786f34d002c84ec47ac9
                room-ref: '@review/backlog/briefing-1'
---

Direction B in the tier-2 suite scores chrF 12.481 with nemotron and 26.348 with qwen3-asr on the
IWSLT devset. The published IWSLT 2026 anchor for the same direction is chrF 41.01 (NeMo, MCIF dev).
The question this task answers: how much of that gap is our decode configuration rather than our
weights, measured at fixed weights with no download.

## The knob

`--nemotron-mlx-asr-att-context` takes a left/right frame pair at 80 ms per frame. Our tier-2 rows
ran `[56, 6]` (4.48 s left, 0.48 s right). NeMo's IWSLT 2026 table lists `[70, 13]` for
`nemotron-speech-streaming-en` (5.60 s left, 1.04 s right). Both are expressible today on the cached
`mlx-community/nemotron-3.5-asr-streaming-0.6b-8bit`, so the comparison needs no download.

## Anchor, to be verified before it is quoted

The anchor WER for NeMo's nemotron row must be read from their own table, not from a secondary
summary. A first officer read of a jumbled PDF extraction suggested 17.52 %, but the same table also
shows 7.89 % beside the nemotron row and repeats one WER column across all three En→X directions,
which is consistent with WER being a property of the ASR step. The first job of this task is to pin
the exact configuration-to-WER mapping from the paper, and to state it before any of our numbers are
compared to it.

## Acceptance criteria

- **AC-1.** The NeMo anchor is pinned: the paper's WER for `nemotron-speech-streaming-en` at
  `[70, 13]` on En→Zh, quoted with the table or section it came from, and the reading that would
  falsify it stated. Falsifier: an anchor quoted from a secondary summary.
- **AC-2.** The same 919 devset segments run through the cached nemotron weights at three
  configurations, `[56, 6]` as our baseline and `[70, 13]` as the anchor config, plus one intermediate,
  each with WER, RTF, and the wall time recorded, `git_dirty: false`, and no download. Falsifier: a
  row whose configuration is not stated in its own notes.
- **AC-3.** The result states how much of the WER gap the configuration explains, and what remains,
  in one number with its caveat, and does not compare chrF across aggregations without saying so.
  Falsifier: a conclusion that names no residual.
