# sa-spike — Apple SpeechAnalyzer streaming spike (macOS 26+)

Build (needs Swift from Terminal.app — the agent sandbox cannot compile):
    swiftc -O spike_speechanalyzer.swift -o sa-spike

Play (mic, zh-TW, volatile dim / final JSONL):
    ./sa-spike

File (paced real-time feed):
    ./sa-spike --file /Users/clkao/git/asr/_work/zh_long.wav
    ./sa-spike --file ... --fast          # full-speed

Hotword A/B (AnalysisContext):
    ./sa-spike --context "鐳射,雷射,紋身" --file /Users/clkao/git/asr/_work/zh_long.wav

Options: --locale zh-TW | --context a,b,c | --file p | --fast | --no-volatile

Output: JSONL per event:
  {"t": wall, "audio_t": sec, "type": "volatile"|"final", "text",
   "range": [start,end], "runs": [[word,start,end],...]}

First run downloads the locale asset if missing (one-time, OS-managed).
File mode converts any AVAudioFile-readable input via AVAudioConverter —
the 16kHz clips work as-is.

File-mode alternative with word timestamps + confidence (no shim needed):
    cd /tmp && git clone https://github.com/simonw/speech-analyzer-cli
    cd speech-analyzer-cli && ./scripts/install.sh
    speech-analyzer --list-locales
    speech-analyzer --locale zh-TW --format json ~/git/asr/_work/zh_long.json
