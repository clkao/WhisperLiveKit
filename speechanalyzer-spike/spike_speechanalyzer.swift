// spike_speechanalyzer.swift — Apple SpeechAnalyzer streaming spike (macOS 26+)
//
// Modes:
//   mic   (default)      live microphone -> JSONL events on stdout
//   --file <path>        audio file fed at real-time pace (or --fast)
// Options:
//   --locale <id>        BCP-47 locale, default zh-TW
//   --context "a,b,c"    AnalysisContext contextual strings (hotwords)
//   --fast               feed the file as fast as the analyzer takes it
//   --no-volatile        disable .volatileResults
// Output: one JSON object per line on stdout, flushed per event:
//   {"t":<wallclock_seconds>,"audio_t":<sec|0>,"type":"volatile"|"final",
//    "text":"...","range":[start,end],"runs":[[text,start,end],...]}
//
// Build:  swiftc -O spike_speechanalyzer.swift -o sa-spike
// Run:    ./sa-spike                (mic, zh-TW)
//         ./sa-spike --file a.wav
// First run downloads the locale asset if missing (one-time, OS-managed).

import AVFoundation
import Foundation
import Speech

func jesc(_ s: String) -> String {
    var out = ""
    for c in s.unicodeScalars {
        switch c {
        case "\"": out += "\\\""
        case "\\": out += "\\\\"
        case "\n": out += "\\n"
        case "\r": out += "\\r"
        case "\t": out += "\\t"
        default:
            if c.value < 0x20 { out += String(format: "\\u%04x", c.value) }
            else { out.append(Character(c)) }
        }
    }
    return out
}

func emit(_ type: String, _ audioT: Double, _ text: String, _ range: (Double, Double)?, _ runs: [(String, Double, Double)]) {
    var obj = "{"
    obj += "\"t\":\(String(format: "%.3f", Date().timeIntervalSince1970))"
    obj += ",\"audio_t\":\(String(format: "%.3f", audioT))"
    obj += ",\"type\":\"\(type)\""
    obj += ",\"text\":\"\(jesc(text))\""
    if let r = range { obj += ",\"range\":[\(String(format: "%.3f", r.0)),\(String(format: "%.3f", r.1))]" }
    else { obj += ",\"range\":null" }
    if !runs.isEmpty {
        obj += ",\"runs\":[" + runs.map { "[\"\(jesc($0.0))\",\(String(format: "%.3f", $0.1)),\(String(format: "%.3f", $0.2))]" }.joined(separator: ",") + "]"
    }
    obj += "}"
    print(obj, flush: true)
}

func fsec(_ s: String) -> Never {
    FileHandle.standardError.write(("ERROR: " + s + "\n").data(using: .utf8)!)
    exit(1)
}

@main
struct SaSpike {
    static func main() async {
        var localeId = "zh-TW"
        var contextStrings: [String] = []
        var filePath: String? = nil
        var fast = false
        var volatile = true

        var args = Array(CommandLine.arguments.dropFirst())
        while !args.isEmpty {
            let a = args.removeFirst()
            switch a {
            case "--locale": localeId = args.isEmpty ? fsec("--locale needs a value") : args.removeFirst()
            case "--context":
                let v = args.isEmpty ? fsec("--context needs a value") : args.removeFirst()
                contextStrings = v.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
            case "--file": filePath = args.isEmpty ? fsec("--file needs a path") : args.removeFirst()
            case "--fast": fast = true
            case "--no-volatile": volatile = false
            case "--help", "-h":
                print("usage: sa-spike [--locale zh-TW] [--context a,b,c] [--file path] [--fast] [--no-volatile]")
                return
            default: fsec("unknown arg: \(a)")
            }
        }

        guard #available(macOS 26.0, *) else { fsec("requires macOS 26+") }

        let wanted = Locale(identifier: localeId)
        guard let locale = await SpeechTranscriber.supportedLocale(equivalentTo: wanted) else {
            let supported = await SpeechTranscriber.supportedLocales.map { $0.identifier(.bcp47) }.joined(separator: ", ")
            fsec("locale \(localeId) not supported. supportedLocales: \(supported)")
        }

        let transcriber = SpeechTranscriber(
            locale: locale,
            transcriptionOptions: [],
            reportingOptions: volatile ? [.volatileResults] : [],
            attributeOptions: [.audioTimeRange, .transcriptionConfidence]
        )

        // One-time locale asset install (OS-managed storage).
        let installed = await SpeechTranscriber.installedLocales
        if !installed.contains(where: { $0.identifier(.bcp47) == locale.identifier(.bcp47) }) {
            FileHandle.standardError.write("downloading locale asset for \(locale.identifier(.bcp47))...\n".data(using: .utf8)!)
            do {
                if let req = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
                    try await req.downloadAndInstall()
                }
            } catch { fsec("locale asset install failed: \(error)") }
        }

        let analyzer = SpeechAnalyzer(modules: [transcriber])
        if !contextStrings.isEmpty {
            let context = AnalysisContext()
            context.contextualStrings[.general] = contextStrings
            do { try await analyzer.setContext(context) }
            catch { FileHandle.standardError.write("setContext failed (non-fatal): \(error)\n".data(using: .utf8)!) }
        }

        let analyzerFormat = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber])
        emit("meta", 0, "format=\(analyzerFormat.map { "\($0.sampleRate)Hz \($0.channelCount)ch float=\($0.isFloat) interleaved=\($0.isInterleaved)" } ?? "nil")", nil, [])

        // Ctrl-C -> graceful finalize via a signal-driven stream.
        let (interrupted, intCont) = AsyncStream<Bool>.makeStream()
        signal(SIGINT, SIG_IGN)
        let src = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
        src.setEventHandler { intCont.yield(true) }
        src.resume()

        // Results consumer: runs concurrently with audio feeding.
        let consumer = Task {
            for try await result in transcriber.results {
                let text = String(result.text.characters)
                guard !text.isEmpty else { continue }
                var runs: [(String, Double, Double)] = []
                var range: (Double, Double)? = nil
                if let ar = result.audioRange { range = (ar.start.seconds, ar.end.seconds) }
                for run in result.text.runs {
                    if let rr = run.audioRange {
                        runs.append((String(run.characters), rr.start.seconds, rr.end.seconds))
                    }
                }
                emit(result.isFinal ? "final" : "volatile", range?.0 ?? 0, text, range, runs)
            }
        }

        // Feeder: mic tap or paced file, both through one AsyncStream.
        let (inputs, inCont) = AsyncStream<AnalyzerInput>.makeStream()
        let feedTask = Task {
            for await input in inputs {
                try await analyzer.analyzeSequence(from: [input])
            }
        }

        do {
            if let path = filePath {
                try await feedFile(inCont, transcriber: transcriber, path: path, fast: fast, analyzerFormat: analyzerFormat!)
                await inCont.finish()
                await feedTask.value
                await analyzer.finalizeAndFinish()
            } else {
                let engine = try await startMic(inCont, transcriber: transcriber, analyzerFormat: analyzerFormat!)
                FileHandle.standardError.write("mic live — speak, Ctrl-C to stop\n".data(using: .utf8)!)
                _ = await interrupted.first { _ in true }  // block until Ctrl-C
                await inCont.finish()
                await analyzer.cancelAndFinishNow()
                engine.stop()
            }
        } catch {
            FileHandle.standardError.write("feed error: \(error)\n".data(using: .utf8)!)
            await analyzer.cancelAndFinishNow()
        }
        _ = await consumer.result
        FileHandle.standardError.write("done\n".data(using: .utf8)!)
    }

    static func feedFile(_ cont: AsyncStream<AnalyzerInput>.Continuation, transcriber: SpeechTranscriber, path: String, fast: Bool, analyzerFormat: AVAudioFormat) async throws {
        let file = try AVAudioFile(forReading: URL(fileURLWithPath: path))
        let srcFormat = file.processingFormat
        guard let converter = AVAudioConverter(from: srcFormat, to: analyzerFormat) else {
            fsec("cannot convert \(srcFormat) -> \(analyzerFormat)")
        }
        let outCap = AVAudioFrameCount(analyzerFormat.sampleRate)  // 1s out buffer
        let out = AVAudioPCMBuffer(pcmFormat: analyzerFormat, frameCapacity: outCap)!

        // Read 1s of source at a time; convert; emit ~100ms slices.
        while true {
            let inBuf = AVAudioPCMBuffer(pcmFormat: srcFormat, frameCapacity: AVAudioFrameCount(srcFormat.sampleRate))!
            var readErr: NSError? = nil
            file.read(into: inBuf, error: &readErr)
            if let e = readErr { fsec("read failed: \(e)") }
            guard inBuf.frameLength > 0 else { break }

            var err: NSError? = nil
            let got = converter.convert(to: out, error: &err) { _, outStatus in
                outStatus.pointee = .haveData
                return inBuf
            }
            _ = got
            if let e = err { fsec("convert failed: \(e)") }
            guard out.frameLength > 0 else { continue }

            let sliceFrames = AVAudioFrameCount(analyzerFormat.sampleRate / 10)
            var offset: AVAudioFrameCount = 0
            while offset < out.frameLength {
                let n = min(sliceFrames, out.frameLength - offset)
                let slice = AVAudioPCMBuffer(pcmFormat: analyzerFormat, frameCapacity: n)!
                if let src = out.floatChannelData, let dst = slice.floatChannelData {
                    for ch in 0..<Int(analyzerFormat.channelCount) {
                        memcpy(dst[ch], src[ch] + Int(offset), Int(n) * MemoryLayout<Float>.size)
                    }
                }
                slice.frameLength = n
                offset += n
                cont.yield(AnalyzerInput(buffer: slice))
                if !fast {
                    try await Task.sleep(nanoseconds: UInt64(1e9 * Double(n) / analyzerFormat.sampleRate))
                }
            }
        }
    }

    static func startMic(_ cont: AsyncStream<AnalyzerInput>.Continuation, transcriber: SpeechTranscriber, analyzerFormat: AVAudioFormat) async throws -> AVAudioEngine {
        let engine = AVAudioEngine()
        let inputNode = engine.inputNode
        let hwFormat = inputNode.outputFormat(forBus: 0)
        guard let converter = AVAudioConverter(from: hwFormat, to: analyzerFormat) else {
            fsec("cannot convert hw \(hwFormat) -> \(analyzerFormat)")
        }

        inputNode.installTap(onBus: 0, bufferSize: 4000, format: hwFormat) { buffer, _ in
            let cap = AVAudioFrameCount(Double(buffer.frameLength) * converter.sampleRateRatio + 64)
            guard let converted = AVAudioPCMBuffer(pcmFormat: analyzerFormat, frameCapacity: cap) else { return }
            var err: NSError? = nil
            _ = converter.convert(to: converted, error: &err) { _, outStatus in
                outStatus.pointee = .haveData
                return buffer
            }
            if err == nil && converted.frameLength > 0 {
                cont.yield(AnalyzerInput(buffer: converted))
            }
        }
        engine.prepare()
        try engine.start()
        return engine
    }
}
