---
title: "Tier 2: two labelled directions — product zh→en on FLEURS, comparison en→zh on the IWSLT devset, scored by XCOMET-XL"
status: backlog
score: 0.8
source: inherits the tier-2 scope of simulst-eval-harness (8z), whose tier 1 is approved for delivery
id: 1mvkhny3ke6wcza27p8x5v8j
gates:
    version: 1
    records:
        - id: gate:1mvkhny3ke6wcza27p8x5v8j:backlog
          stage: backlog
          attempts:
            - id: gate-attempt:1mvkhny3ke6wcza27p8x5v8j-backlog-1
              briefing:
                id: briefing:1mvkhny3ke6wcza27p8x5v8j:backlog:attempt-1:revision-1
                digest: sha256:441a6fdaa2edaef2b055f0792c7fba9ab7b5554d0bd02d8f12c50ba00ffcc600
                room-ref: '@review/backlog/briefing-1'
---

Tier 1 shipped the benchmark suite that scores a translation. This task produces the two measured
numbers the project actually needs, and keeps them apart.

## The two directions

**Direction A, the product direction: Mandarin to English.** FLEURS Chinese rows, with the English
reference taken from the same `sentence_id` join tier 1 built. No new corpus and no download. This is
the direction the project exists for: Mandarin speech, English captions.

**Direction B, the comparison direction: English to Chinese.** The IWSLT 2026 devset, 21 wav files
and 919 segments, with `ref/en.txt` and `ref/zh.txt` on disk. This number can be placed beside the
published anchors; direction A cannot.

Never put the two numbers in one table. Each report and each note names its direction.

## Why direction B is the real work

The devset references are per segment, and segment boundaries live in `audio-segments.yaml` as
offset and duration pairs. The tier-1 harness samples one file at a time, so direction B needs a
segment-level emitter: cut each segment, run the cascade on it, and carry the segment's own source
and reference through to the report. That is the build this task owns.

## Scoring

chrF and the latency fields come from the harness locally. XCOMET-XL runs on `asr-xcomet.exe.xyz`,
which holds the 13.94 GB checkpoint in a warm cache; the recipe, its two pins and its 27.9 GB RSS
requirement are in `_work/eval_env_runbook.md` section 2a. Only text crosses the wire.

## Acceptance criteria

- **AC-1.** Direction A produces a checked-in report labelled product, covering at least 10 FLEURS
  Chinese rows, carrying chrF, `first_translation_time_s` and `final_translation_time_s`, plus a
  system XCOMET-XL score from one VM run whose request and response are both recorded. Falsifier: a
  row without a direction label, or an XCOMET score with no recorded request.
- **AC-2.** Direction B's emitter converts `audio-segments.yaml` plus the two reference files into
  per-segment samples and carries at least one whole wav file's segments end to end, with each
  segment's source, reference and hypothesis traceable to its segment index. Falsifier: a segment
  whose reference cannot be traced to its index in `ref/zh.txt`.
- **AC-3.** The run stays inside its limits: no download, cached models only, free disk on this Mac
  never below 1.5 GiB, and the VM paused between runs. Falsifier: a cache write or a disk reading
  below the floor.
