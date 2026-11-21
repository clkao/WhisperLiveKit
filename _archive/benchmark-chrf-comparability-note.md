---
title: "benchmark README: say that chrF is a punctuation-stripped variant, not sacrebleu chrF"
status: backlog
score: 0.4
source: follow-up from simulst-eval-harness validation cycle 2, finding 1
id: ebbnkt7fwn907mjbf3n3ny7m
archived: 2026-11-21T19:26:27Z
---

`benchmarks/README.md`'s chrF bullet and the report's `measurement.chrf` note say both sides get the WER normalization and lose whitespace. They do not say how far that moves the number or what it means for the reader.

Measured on the tier-1 reports: the score is 0.28 to 2.64 points below `sacrebleu 2.6.0` on the same text, -4.7 % to -20.1 % relative, lower on every row, because punctuation is deleted before scoring. The arithmetic itself matches sacrebleu exactly.

One sentence closes it: state that the score is a punctuation-stripped, case-folded variant and is not comparable with published chrF numbers. It belongs in the same delivery as the harness, before the pull request opens.
