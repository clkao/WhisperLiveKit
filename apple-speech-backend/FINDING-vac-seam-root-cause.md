# Finding: exact zeros inside an utterance become a hard segment boundary

**Status:** the root cause is known. No fix exists yet.
**Affects:** `apple-asr` 0.1.4 and earlier, for callers that remove silence.
**Impact:** the en WER doubles under the default WhisperLiveKit pipeline. The zh output does not
change.

## Root cause

`apple_asr.Stream._write_silence()` writes exact digital zeros. It writes them for the pre-roll, for
the pump ticks, and for the top-up of each pause. The code is:

```python
zeros = np.zeros(frames, dtype=np.float32)
self._transport.write_audio(zeros.tobytes())
```

Apple SpeechAnalyzer treats exact zeros inside an utterance as a hard segment boundary. The decoder
finishes the segment before the gap. Then it starts a new segment after the gap. It writes the seam
as a run of dots and dashes. It also removes words near the seam.

The WhisperLiveKit VAC removes silence from the feed. This package then makes the silence again.
`pause_start()` writes the pre-roll and starts the pump. `pause_end(d)` writes the top-up. Each VAC
pause therefore becomes a seam.

Reproducer: one FLEURS clip of 7.2 s, `fleurs_en_1700`. The feed goes directly to `Stream`, without
WhisperLiveKit.

| feed | finals | text |
|---|---|---|
| original file, no VAC | 1 | `It is thinner under the Maria and thicker under the highlands.` |
| VAC-stripped audio, zeros from the package | 2 | `It is thinner under the.` / `-... Maria and thicker under the highlands.` |
| same stream, zeros replaced by noise at 1e-4 RMS | 1 | `It is thinner under the Maria and thicker under the highlands.` |

## The noise-floor fix does not work

Hypothesis: write a low noise floor in place of the zeros. **Rejected.**

The synthesized silence is also the signal for the pause detector in the shim. A level high enough to
stop the decoder costs the pause commits. The sweep uses the reproducer with 7 pauses:

| silence content | committed finals | text |
|---|---|---|
| exact zeros (shipped) | 2 | `It is thinner under the.` / `in... Maria and thicker under the highlands.` |
| noise 1e-8 RMS | 2, one with `reason=pause` | the same artifact |
| noise 1e-6 RMS | 2, both `flush` | the same artifact |
| noise 1e-5 RMS | 2, one with `reason=pause` | the same artifact |
| noise 1e-4 RMS | **0** | the text stays volatile, so the pause commits stop |

No amplitude window exists. Below the detector threshold the artifact stays. Above it the commit
cadence stops. This retracts an earlier claim that a noise floor corrected the fault.

The 1e-4 batch measurement below is real data. Read it as "the WER improves because the pause commits
stopped and the text fell back to the volatile stream". It is not a fix.

## The fix options that remain

- **Stop the removal of silence for this backend.** Preferred. The caller sends the original audio,
  the room tone stays correct, and the package writes no silence. Then no seam occurs. The verified
  case is `vac: false`: en 11.93% weighted, 0 of 30 artifacts, and no package change. In
  WhisperLiveKit terms this is a declared capability, "this backend wants continuous audio". It is a
  pipeline change, not a flag. It is also the correct change, because it removes the need to make
  silence.
- **Send the pause as a command, not as audio.** Correct, but larger. At present the package tells
  the shim about a pause by feeding silence, and this is what damages the decoding. A protocol
  command, "pause here, move the clock by d, commit", lets the analyzer receive continuous speech.
  The shim still commits at the pause. This needs Swift and protocol work in the package.
- **Remove the dot and dash runs from the committed text.** A band-aid. It does not give back the
  words that the seam removed.
- Add the replay harness of the package (`max_pause_latency < 0.3`) to the verification of each
  option. A bad fix stops the pause commits and writes no message. The WER then looks better, but the
  cadence is gone. The cadence is the purpose of the product. Do not accept a fix on WER evidence
  only.

## Evidence chain

1. **Ablation.** Four `wlk bench` runs on the same 30 samples. `vac: true` gives 27.92% and 18
   artifacts. `vac: false` gives 11.93% and 0 artifacts. `pause_segmentation_seconds` changes nothing,
   at 5.0 or at 600. `vac` is the only variable.
2. **Capture.** Every byte to the shim was recorded, for each sample. The total is 5,569,792 frames,
   that is 348.11 s. The zeros are 80.68 s of this total. The declared silence is 80.21 s. The
   synthesis is therefore correct in total. An excess of silence is not the fault.
3. **Comparison with the source clips.** Of the 80.7 s of zeros, 41.45 s fall on original silence.
   Only 6.11 s fall on clear speech (threshold above 30% of the speech p90 of the clip, and 3.01 s
   above 50%). A mute of speech is therefore not the main fault. The effect of the seam on the
   decoding is the main fault.
4. **Minimal reproducer.** The first table. The audio does not change. Only the content of the silence
   changes, and the artifact comes and goes with it. No WhisperLiveKit is in the loop.
5. **Batch measurement.** A full bench run with only `_write_silence` changed. See the second table
   and the warning above.

## Reproduce

- Reproducer script: `repro_vac_seam.py`, next to this file.
- Runner commands: the *Validation* section of the PR body.
- Raw reports: in this directory, as `bench-en-US-*.json` and `bench-zh-CN-locale.json`.
