---
title: "mlx-qwen3-asr: expose the decode-granularity control (long window, revision budget)"
status: backlog
score: 0.6
source: measured on 150 FLEURS clips per language while evaluating #425; the switches were cut from that PR
id: anjv5dgtjrmh17ypd2dsfv3t
---

Decode granularity is the dominant quality lever we found in the mlx-qwen3-asr adapter, worth more than
any other switch. The adapter finalises at every VAD pause, so a 10 to 15 s clip becomes two or three
separate decodes. Exposing one window across pauses, and the library's revision budget, recovers most of
the gap between the shipped behaviour and whole-clip decoding.

## The measured case

150 FLEURS test clips per language, `Qwen3-ASR-0.6B`, `mlx-qwen3-asr` 0.4.4, one normalizer:

| configuration | English WER | Mandarin CER |
|---|---|---|
| shipped: finalise at every pause | 9.96 % | 11.08 % |
| one window across pauses, with 100 ms at deleted-audio splices | **7.20 %** | **9.63 %** |

Intervals exclude zero (English [−4.08, −1.64], Mandarin [−2.29, −0.78]); the largest single clip holds
14 % and 21 % of the net errors; a same-arm replicate moved 0 of 643 errors. The mechanism is granularity:
deferring finalisation until silence exceeds a threshold recovers 0.88 of the 1.45-point gap at 0.5 s and
1.02 at 1.0 s, then flattens, and at 2.0 s the transcripts are byte-identical to the long-window
configuration on 150 of 150 clips.

## The trade

First visible text is unchanged. First **committed** text moves 5.77 → 9.98 s English and 6.23 → 11.45 s
Mandarin. Provisional accuracy at first-visible does not degrade (prefix-matched intervals span zero), but
visible changes go from about half appends to **95 to 97 % rewrites**. Accuracy improves while the line
stops growing and starts being replaced.

## The caveat that decides it

Every measurement is FLEURS read speech: single sentences, where "one window across pauses" and "one decode
per clip" coincide. On multi-sentence presentation audio the window would carry text across sentence
boundaries, and that is unmeasured. The honest first experiment is long-form audio with references.

## Acceptance criteria

- **AC-1.** The two switches exist behind defaults that leave today's numbers reproducible, with a test
  showing an unset revision budget keeps the library's own default. Falsifier: a default that moves an
  existing measurement.
- **AC-2.** The improvement is demonstrated on 150 clips per language against the shipped behaviour, with
  intervals and a same-arm replicate. Falsifier: a claim with no replicate.
- **AC-3.** The trade is demonstrated in the same table: first-visible, first-committed, exposure, and the
  append-versus-rewrite split. Falsifier: a comparison that reports accuracy alone.
- **AC-4.** The long-form caveat is stated wherever the flags are documented, and the long-form measurement
  is either run or named as not run with the reason.
