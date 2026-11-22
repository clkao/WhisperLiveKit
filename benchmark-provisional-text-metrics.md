---
title: "benchmark: record the update series and report how the provisional text behaves"
status: backlog
score: 0.55
source: adjacent to #477, which scores the translation; this scores the recognition text over time
id: y0dy11789x4m29hbxwyd9awf
gates:
    version: 1
    records:
        - id: gate:y0dy11789x4m29hbxwyd9awf:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:y0dy11789x4m29hbxwyd9awf-backlog-1
              briefing:
                id: briefing:y0dy11789x4m29hbxwyd9awf:backlog:attempt-1:revision-1
                digest: sha256:253ecc4b735e2038dc2e1191b0682119406f6dee88bf220a3a0f169f0db41406
                room-ref: '@review/backlog/briefing-1'
              withdrawal:
                by: agent:first-officer
                at: "2026-11-22T05:26:49.6748Z"
                reason: Seed amended to require a worked comparison that demonstrates the tradeoff, not only the fields
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
- **AC-4.** The metrics demonstrate a tradeoff rather than merely existing: one run of two commit
  policies side by side, showing accuracy, exposure and the append-versus-rewrite split in a single table.
  Falsifier: a deliverable that reports the fields without one worked comparison.
- **AC-5.** The demonstration states what a reader can conclude and what it cannot, given that the sample
  is single-sentence read speech. Falsifier: a claim about multi-sentence audio that the sample cannot
  support.

## Not in scope

No new corpus, no new dependency: the existing public manifests carry everything. This does not change
how translation quality is scored, which is #477.

#### Cycle 1 — the task must demonstrate, not just report (2026-11-21)

CL asked that this task be able to show its improvement and its tradeoff, so the deliverable is not the
fields alone. Two criteria were added: one worked comparison of two commit policies in a single table
(accuracy, exposure, append-versus-rewrite), and a statement of what that comparison cannot support, since
the sample is single-sentence read speech.

The seed's motivation already carries the measured reason: holding accuracy fixed, a long-window policy
raised time to final commit by 4.2 s English and 5.2 s Mandarin and turned 50 to 60 % appends into 95 to
97 % rewrites, while prefix-matched accuracy at first-visible stayed inside its interval. A report that
shows only the final score cannot tell those two products apart, which is the case for this task.
