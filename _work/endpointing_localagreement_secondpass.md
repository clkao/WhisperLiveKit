# Endpointing + LocalAgreement + second-pass: event trace and design

**Measured 2026-08-29** on zh_long.wav (31.6s continuous Mandarin, no pauses),
zh→en, qwen3-asr + Hy-MT2-1.8B simul-MT (mass policy). On the integration
branch after the CJK commit fix (`bbb70c1`) and token-based MT hysteresis
(`bf383db`).

## Correction: AlignAtt DOES take the provisional (unstable tail) into the MT

`_translate_simul(source, committed)` builds the prompt from
`source = committed + tail` — the full rolling source. The MT generates a
translation draft over ALL of it (committed AND unstable tail). Then
`apply_commit_policy` releases only the target prefix whose attention aligns
to the committed portion. The tail INFORMS the draft (the MT sees it and
translates ahead over it); the target tokens aligning to the tail are HELD
(not released) until the ASR commits the tail.

This is the AlignAtt design: MT drafts ahead over uncommitted source, but
only releases target it can justify against committed source. The held
target releases later WITHOUT a new MT call when the ASR commits the tail
(the release-without-call path re-applies the policy on the cached attention).

## Actual event trace (zh->en, rule3 endpointing at 20s)

```
[ 2s] ASR: stable_text grows -> "我们今天来讨论镭射。" (committed)
[ 6s] ASR commit delta -> committed source = "我们今天来讨论镭射。在医学上的应用..."
[ 8s] ASR commit delta -> committed grows
 ...
[16s] MT draft call: source=70ch(committed+tail), committed=65ch
       AlignAtt releases: "" (attention not aligned enough to committed yet)
[20s] RULE3 fires -> validate_buffer_and_reset -> quality pass FINAL:
      "Today we will discuss laser. Its applications in medicine, lasers..."
      (full base-class translation of the committed utterance — clean)
[22s] MT draft call: source=10ch, committed=5ch "减少出现。皮肤科用。"
       AlignAtt releases: "Reduced occurrence. For" (fragment — committed is
       a fragment because the model's 。 landed mid-clause)
[24s] release (no call): "Reduced occurrence. For dermatology use."
[28s] MT draft call: source=43ch, committed=38ch
       AlignAtt releases: "Reduced occurrence. Used in dermatology."
[30s] ... 
[end]  FINAL: remaining utterance quality pass
```

### The component flow

```
ASR stream ─▶ StableCommitTransform ─▶ committed ASRTokens (stable prefix)
   │              (native stable_text)         │
   │                                         ▼
   │                                   insert_tokens → MT _committed_simul
   │                                         │
   └─▶ get_buffer() = unstable tail ──▶ HypothesisTail → MT _tail
                                             │
                                             ▼
                                    MT _translate_simul(source=committed+tail)
                                       │  draft over FULL source
                                       ▼
                                    apply_commit_policy (AlignAtt)
                                       │  release target aligned to committed
                                       ▼
                                    provisional (TimedText, not finalized)
                                       │
                             [rule3 20s] validate_buffer_and_reset
                                       │  flush committed as pending final
                                       ▼
                                    _translate_text (base class, quality pass)
                                       │  no commit policy, full translation
                                       ▼
                                    FINAL (Translation, committed to display)
```

## Two distinct problems observed

### Problem 1: MT finalizes on has_punctuation() alone -> fragment finals
Without endpointing, the MT layer queues a final whenever an ASR token
has `。`/`.`/`?`. On continuous speech the model emits `。` mid-clause
(probabilistically valid — a period after "讨论镭射" is grammatically
plausible), so finals fire on fragments: 7-12 fragment finals instead of
clean sentences. This is language-agnostic (en->zh shows the same).

FIX (prototype): rule3 endpointing (force-cut at 20s) + disable
has_punctuation-triggered finals. Result: 1 clean final at 20s (quality
pass) + 1 at end, instead of 12 fragments. The final uses the full
committed utterance, not a punct-delimited fragment.

### Problem 2: provisional fragments (bounded by committed source)
The provisional ("Reduced occurrence. For") is a correct translation of the
*committed* source, but the committed source is a fragment because the
model's `。` lands mid-clause. AlignAtt correctly releases only target
aligned to committed — the fragment is not an AlignAtt bug, it's a
commit-boundary problem. The committed boundary is the model's `。`, which
fragments on continuous speech.

NOT FIXED by:
- mass_threshold tuning (tested 0.5→0.05: no change — the release is
  bounded by attention alignment to committed, not threshold)
- LocalAgreement LCP commit (tested: commits a DIFFERENT fragment, not a
  better one — both native and LCP derive from the same rolling decode
  that hallucinates `。` mid-clause)

The provisional is correctly partial (simul-MT contract: provisionals are
partial, finals are complete). The final corrects it.

## --no-second-pass and the final quality

The clean final ("Today, we will discuss the applications of laser
technology in medicine...") comes from the ASR two-pass re-decode at the
20s boundary, which re-decodes the whole utterance offline and produces
clean sentence boundaries. The streaming source (what provisionals and
no-second-pass finals use) carries the hallucinated `。` fragmentation.

| final source | text | quality |
|---|---|---|
| two-pass re-decode (second-pass) | 我们今天来讨论镭射在医学上的应用。镭射技术可以精确的切除肿瘤组织... | clean |
| streaming (no-second-pass) | 我们今天来讨论镭射。在医学上的应用，镭射。技术可以精确的切除。肿瘤组织... | fragmented |

With `--no-second-pass`, the rule3 final uses the streaming source → the
final's quality degrades to the fragmented text. The ~0.5-1.5s/sentence
latency saving of `--no-second-pass` (per AGENTS.md) costs the final's
clean-sentence structure. For a caption overlay, second-pass is the right
default (clean finals matter more); `--no-second-pass` is for the
latency-critical path where fragmentary finals are acceptable.

## Desirable state (if none of these problems)

For zh_long.wav (6-7 natural sentences, ~4-5s each), the ideal:

```
[ ~2s] ASR commit: "我们今天来讨论镭射在医学上的应用。"  (first sentence, clean)
[ ~3s] MT provisional: "Today we will discuss the applications of laser in medicine."
       (full first sentence — committed source = the whole sentence)
[ ~5s] ASR commit: "我们今天来讨论镭射在医学上的应用。镭射技术可以精确的切除肿瘤组织..."
[ ~6s] MT provisional: "...Laser technology can precisely remove tumor tissue..."
[ ~6s] FINAL #1: "Today, we will discuss the applications of laser technology
       in medicine."  (quality pass at the first sentence boundary)
[ ~8s] MT provisional: "...reducing damage to surrounding healthy tissue."
[~10s] FINAL #2: "Laser technology can precisely remove tumor tissue, reducing
       damage to surrounding healthy tissue."
... ~6-7 finals, one per natural sentence, provisionals filling each gap
```

What the ideal requires (what's missing on continuous speech):
1. **Reliable sentence boundaries in committed source.** The model's
   `stable_text` must end on real sentence boundaries, not hallucinated
   mid-clause `。`. Without silence/prosody, the model guesses — and on
   continuous speech it guesses mid-clause. This is the root of both
   fragment finals and fragment provisionals.
2. **Endpointing that fires at sentence boundaries, not punctuation alone.**
   livecaption's rule2 (punct modifies silence threshold, never triggers
   alone) needs a silence signal. The benchmark has no VAD on continuous
   speech → rule2 can't fire → rule3 (force-cut at 20s) is the only
   working rule, and it cuts at a fixed length, not at sentence boundaries.
3. **Second-pass re-decode for the final.** The re-decode fixes the
   fragmented streaming source at the utterance boundary. Without it
   (`--no-second-pass`), the final inherits the fragmentation.

The desirable state needs all three. The benchmark has #2 (rule3) and #3
(second-pass) working; #1 (reliable sentence boundaries mid-utterance) is
the model-quality limit on continuous speech without VAD/silence. In
livecaption production, VAD provides the silence signal that lets rule2
fire at real sentence boundaries — which is why livecaption's zh->en
provisionals flow as clean sentences in the live demo, not fragments.

## Scope

- rule3 endpointing prototype: `scripts/spike_endpointing.py` (not landed —
  prototype only; the real endpointing belongs in the audio_processor /
  VAD layer, not the MT layer).
- The MT `has_punctuation()`-triggers-final behavior: #423 scope (the simul
  layer). Disabling it + adding endpointing is a #423 follow-up.
- `--no-second-pass` final quality: documented tradeoff, not a bug.
- Provisional fragmentation on continuous speech: model-quality limit,
  not fixable in the commit/endpointing layer without a silence signal.
