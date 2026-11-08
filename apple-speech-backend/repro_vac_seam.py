"""Reproduce the interior-exact-zero seam artifact through the package's own pause path.

A silence-stripping VAD (as WhisperLiveKit's VAC is) is simulated with an energy gate:
speech spans are pushed, silence spans are announced via pause_start()/pause_end(d), so the
package itself synthesizes the gap silence. With the shipped `_write_silence` (exact zeros) the
en-US decoder splits the utterance at the seam; with a noise floor it does not.

  python repro_vac_seam.py            # shipped behaviour (expect the "-..." artifact)
  python repro_vac_seam.py --fix      # noise floor (expect clean text)
"""
import json, sys, wave, time
from pathlib import Path
import numpy as np
from apple_asr import Stream

FIX = "--fix" in sys.argv
LEVEL = 1e-4
SENTINEL = Path(__file__).resolve().parent
ROOT = SENTINEL.parent.parent.parent.parent / "WhisperLiveKit" if SENTINEL.name == "state" else Path.cwd()

import apple_asr.stream as AS
if FIX:
    rng = np.random.default_rng(0)
    def _write_silence(self, frames):
        if frames <= 0: return
        self._transport.write_audio((rng.standard_normal(frames) * LEVEL).astype(np.float32).tobytes())
        self._clock.add_written(frames, AS.SAMPLE_RATE)
    AS.Stream._write_silence = _write_silence

man = json.load(open(ROOT/"benchmarks/corpora/fleurs-90.json"))
entry = next(s for s in man["samples"] if s["name"] == "fleurs_en_1700")
base = Path.home()/".cache/whisperlivekit/benchmark_data"/man.get("cache_subdir","fleurs_v1")
p = base/entry["file"]; p = p if p.exists() else base/"en_us"/entry["file"]
with wave.open(str(p)) as w:
    sr = w.getframerate()
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)/32768.0
audio = audio[entry["start_sample"]:entry["end_sample"]]

# energy gate -> speech/silence spans
F = int(0.01*sr)
rms = np.sqrt((audio[:len(audio)//F*F].reshape(-1,F)**2).mean(axis=1))
voiced = rms > max(1e-4, 0.02*np.percentile(rms, 90))
MIN_SIL = int(0.15/F)          # silence runs at least this long are pauses
spans, i = [], 0
while i < len(voiced):
    j = i
    while j < len(voiced) and voiced[j] == voiced[i]: j += 1
    if voiced[i] or (j - i) >= MIN_SIL:
        spans.append((bool(voiced[i]), i*F, min(j*F, len(audio))))
    i = j
s = Stream(locale="en-US", mode="streaming", stderr="null", silent_timeout=0)
s.prepare()
finals = []
for is_speech, a, b in spans:
    if is_speech:
        for k in range(a, b, 8000):
            s.push(np.ascontiguousarray(audio[k:min(k+8000,b)], dtype=np.float32))
    else:
        s.pause_start(); s.pause_end((b-a)/sr)
    finals.extend([e for e in s.poll(0.0) if type(e).__name__ == "Final"])
s.flush()
t0 = time.time()
while time.time() - t0 < 20:
    got = s.poll(0.5); finals.extend([e for e in got if type(e).__name__ == "Final"])
    if any(type(e).__name__ == "Ended" for e in got): break
s.close()
print(f"{'FIX (noise floor)' if FIX else 'SHIPPED (exact zeros)'}: {len(spans)} spans, "
      f"{sum(1 for x in spans if not x[0])} pauses, {len(finals)} finals")
for e in finals: print("   FINAL:", repr(e.text))
