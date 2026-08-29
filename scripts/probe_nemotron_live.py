"""Probe: feed a real wav through NemotronMLXOnlineProcessor directly.

Isolates backend vs audio_processor loop: if file audio produces tokens here,
the backend is fine and the problem is in audio_processor's loop (or the mic
chunking); if not, the backend is broken for this configuration.

Usage:
    python scripts/probe_nemotron_live.py [--second-pass] [--chunk-sec S] [wav_path]
"""
import os
import sys

from whisperlivekit.asr_nemotron_mlx import NemotronMLXASR, NemotronMLXOnlineProcessor


def main():
    wav_path = "/Users/clkao/git/asr/_work/zh_long.wav"
    for a in sys.argv[1:]:
        if a.endswith(".wav"):
            wav_path = a
    two_pass = "--second-pass" in sys.argv
    chunk_sec = 0.26
    for i, a in enumerate(sys.argv):
        if a == "--second-pass":
            continue
    # chunk size from env (default: mic-like 0.26s)
    import os
    chunk_sec = float(os.environ.get("CHUNK_SEC", "0.26"))
    CH = int(chunk_sec * 16000)

    from mlx_audio.stt.utils import load_audio
    audio = load_audio(wav_path or "/Users/clkao/git/asr/_work/zh_long.wav", 16000)
    print(f"[probe] {len(audio)/16000:.1f}s audio, max={abs(audio).max():.3f}, two_pass={two_pass}")

    asr = NemotronMLXASR(
        nemotron_mlx_asr_model="mlx-community/nemotron-3.5-asr-streaming-0.6b",
        nemotron_mlx_asr_two_pass=two_pass,
        lan="zh",
    )
    proc = NemotronMLXOnlineProcessor(asr)

    t = 0.0
    total_tokens = 0
    for i in range(0, len(audio), CH):
        chunk = audio[i:i + CH]
        t += len(chunk) / 16000.0
        proc.insert_audio_chunk(chunk, t)
        tokens, end = proc.process_iter()
        if tokens:
            total_tokens += len(tokens)
            print(f"[probe] iter@{t:5.1f}s -> {len(tokens)} tokens: "
                  f"{''.join(tok.text for tok in tokens)!r}")
    buf = proc.get_buffer()
    print(f"[probe] total tokens={total_tokens}, buffer={buf.text!r}")


if __name__ == "__main__":
    main()
