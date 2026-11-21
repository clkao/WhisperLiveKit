---
title: "benchmark: record the update series and report how the provisional text behaves"
status: backlog
score: 0.55
source: adjacent to #477, which scores the translation; this scores the recognition text over time
id: y0dy11789x4m29hbxwyd9awf
---

The suite scores the final text and, after #477, reports when the first translation appeared. It cannot
say what a reader actually saw while the line was provisional: how accurate that text was, how long it
stayed on screen, or whether it changed as appends or as rewrites.

Commit-policy changes move exactly those numbers. Measured on 150 FLEURS clips, holding accuracy fixed,
a persistent-window policy raised the time to final commit by 4.2 s English and 5.2 s Mandarin and turned
50 to 60 % appends into 95 to 97 % rewrites, while prefix-matched accuracy at first-visible was unchanged
inside its interval. A report that shows only the final score cannot distinguish those two products.

## What to record

Per sample, in an optional side file so existing reports keep their shape: each update of the
client-facing text, with its wall clock and its audio position.

## What to report, per language pair

- **prefix-matched accuracy at first-visible** — the text first shown, scored against the corresponding
  prefix of the reference, so a line that is short because speech has not arrived is not scored as wrong;
- **time-weighted error rate** over the lifetime of the provisional line;
- **visible changes per update series** — consecutive identical texts collapsed, split into appends
  (the previous text is a prefix of the new one) and rewrites;
- **clip-complete time** — from clip start to the moment the whole transcript is final, as distinct from
  the moment its first line is final;
- **a same-arm replicate**, so every comparison carries a noise floor.

## Acceptance criteria

- **AC-1.** A run with the side file enabled yields the five numbers per language pair, and each is
  reproducible from the stored series alone. Falsifier: a number that cannot be recomputed without the
  live run.
- **AC-2.** Consecutive identical texts are collapsed before counting, and appends are separated from
  rewrites. Falsifier: a count that equals the raw emission count.
- **AC-3.** A same-arm replicate is reported beside every comparison, and the interval is stated rather
  than a bare point estimate. Falsifier: a comparison with no replicate.

## Not in scope

No new corpus, no new dependency: the existing public manifests carry everything. This does not change
how translation quality is scored, which is #477.
