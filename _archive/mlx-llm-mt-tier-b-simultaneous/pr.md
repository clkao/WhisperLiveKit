feat: simultaneous-MT variant for mlx-llm-mt (AlignAtt commit policy)

## Summary

Add a simultaneous-MT variant that overlaps MT with ASR so a provisional
translation appears during speech, before the ASR finalizes the utterance.
The variant (`MlxLlmTranslationSimul`) subclasses the generic
`MlxLlmTranslation` base from the mlx-llm-mt PR; the base is unchanged.

The mechanism: the variant drafts a translation over (committed source +
unstable ASR tail) and commits only the target tokens whose attention
(argmax over the source span) lands on a source token the ASR has
committed. Held target tokens release from cached attention when the ASR
commits more source, without a new MT call.

A hysteresis (a 15-char minimum source delta) prevents a new MT call on
every tail token; the release path re-applies the commit policy on the
cached draft instead.

The attention capture hooks `hunyuan_v1_dense.Attention` with a manual
softmax(QK^T) so the alignment-head attention is capturable for 8
calibrated zh->en head indices (top head L9/H5). The capture is
bit-identical to the original forward (only attention storage is added).

The `--simultaneous` flag selects the variant. `wants_hypothesis_tail`
is set so the audio processor forwards the unstable ASR tail.

## User impact

New `--simultaneous` flag for `--translation-backend mlx-llm-mt`. When
set, a provisional EN translation appears during speech, before the ASR
finalizes the utterance. The final translation still lands at utterance
close (the quality pass).

The `audio_processor` change (6 lines) forwards the provisional
translation buffer when no finalized translation is produced. This is a
general fix: a backend that returns a provisional buffer with no
finalized translation now reaches the display (the buffer was dropped
before). The base `MlxLlmTranslation` is unchanged.

No compatibility risk: the flag defaults to off; the base path is
identical to the mlx-llm-mt PR.

## Validation

Hardware: Apple M4. ASR backend: `faster-whisper` (base) with the
localagreement policy. MT: `mlx-community/Hy-MT2-1.8B-8bit` (Hunyuan-MT
1.8B 8bit). Audio: 31.6s Mandarin, multi-sentence. Speed: 1.0
(real-time).

The metric that matters: when does the first EN translation reach the
user?

| Variant | first EN reaches user | how | MT calls | MT-RTF |
|---|---|---|---|---|
| base (no --simultaneous) | 16.52s | at utterance close (final) | 12 | 0.19x |
| simul (--simultaneous) | 2.44s | during speech (provisional) | 24 | 0.42x |

The simul variant's first EN translation reaches the user 14.08s earlier
(2.44s vs 16.52s) because it drafts over the unstable ASR tail and
commits the aligned prefix during speech.

Trade-off: the simul variant makes more MT calls (24 vs 12). It makes
the same 12 final calls as the base, plus 12 provisional calls (one
per sentence, the first draft after each reset). The release path
(re-applying the commit policy on cached attention when the ASR commits
more source) does NOT increment the call counter — verified by unit
tests. The hysteresis prevents calls on every tail token; the count is a
superset of the base, not a reduction.

Heads log confirms the 8 calibrated heads load and (9,5) is the top
head: `MlxLlmTranslationSimul: alignment heads=[(9, 5), (13, 1), (9, 6),
(12, 11), (14, 2), (14, 0), (4, 12), (1, 10)] top=(9, 5)`.

Tests: `pytest tests/test_mlx_llm_mt.py tests/test_mlx_llm_mt_simul.py -q`
-> 32 passed (11 base + 21 simul).

## Checklist

- [ ] I searched for an existing issue or discussion and linked it when relevant.
- [x] I added or updated tests for behavior changes.
- [ ] I updated documentation for user-facing changes.
- [x] I ran `ruff check .` (on changed files).
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or private data.
