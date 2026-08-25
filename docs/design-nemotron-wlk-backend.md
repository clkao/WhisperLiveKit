# Design: nemotron-streaming-ASR as a WLK backend

## Goal

Add the NVIDIA nemotron-3.5-asr-streaming-0.6b (cache-aware streaming transducer, via `mlx-audio`) as a new ASR backend for WhisperLiveKit, porting the implementation already running in the original livecaption.

## Contract — what a nemotron backend must expose

WLK's `AudioProcessor` drives an ASR via an "online processor" returned by `online_factory(self.args, models.asr, language=...)` (`audio_processor.py:202`). The qwen3 adapter wraps its processor in `_ASRTokenNormalizer` (`core.py:354`) which converts the backend's native tokens to WLK `ASRToken` via `_to_wlk_token` (`core.py:331`). The wrapped object must expose:
- `process_iter(...)` → `(tokens, end_time)` — called per audio chunk; tokens get normalized to `ASRToken` (must carry `.start`, `.end`, `.text`).
- `start_silence(...)` → same shape — called on VAD silence-start.
- `finish(...)` → same shape — called at utterance end.
- `get_buffer()` / `__getattr__` passthrough — WLK probes `finish` via `hasattr`, so the wrapper uses `__getattr__` (`core.py:362`).

**nemotron's tokens already carry the fields.** livecaption's `asr.py` uses mlx-audio's `AlignedTokens` with `.start` (per-token timestamps from the transducer). So `_to_wlk_token`'s `start=tok.start, end=tok.end, text=tok.text` mapping works directly — nemotron needs the same `_ASRTokenNormalizer` wrapper qwen3 uses, not a new one. The one gap: `has_punctuation()` is a WLK `ASRToken`/`TimedText` method; the normalizer converts to `ASRToken` which has it, so translation segmentation works.

## Boundary mapping — timestamps vs stable_text

This is the real design difference from qwen3. qwen3 has no mid-utterance timestamps and uses `stable_text` (text-stability) as the commit boundary; the qwen3 backend's `stable_commit.py` synthesizes this. nemotron is a transducer with **real per-token timestamps** (`.start` on `AlignedTokens`).

WLK's `AudioProcessor` decides committed-vs-unstable in `_queue_tokens_for_translation` (`audio_processor.py:258`) and feeds the unstable tail via `_queue_hypothesis_tail_for_translation` (`audio_processor.py:312`, gated by the translator's `wants_hypothesis_tail`). The commit decision today is driven by the online processor emitting tokens as "committed" — the processor, not AudioProcessor, decides.

So nemotron's design: the online-processor wrapper commits a token when its timestamp passes a stability threshold (analogous to qwen3's `stable_iterations`, but time-based using the real `.start`). The unstable tail is the tokens not yet committed. This is cleaner than qwen3's text-stability heuristic because the timestamps are ground truth. No new WLK hook is needed — the commit happens in the wrapper, and AudioProcessor consumes committed tokens + tail as today.

## Registration

1. **BACKENDS entry** (`cli.py:52`): `{"id": "nemotron", "module": "mlx_audio", "install": "pip install 'whisperlivekit[nemotron]'", "description": "NVIDIA nemotron streaming transducer on Apple Silicon (MLX)", "platform": "darwin-arm64", "policy": "—", "streaming": "native", "devices": ["mlx"]}`. nemotron is natively streaming (not chunked), so `streaming: "native"` like voxtral-mlx, not `"chunk"` like whisper.
2. **available check** (`backend_support.py`): `nemotron_backend_available()` → `module_available("mlx_audio")`. No torch/transformers requirement.
3. **config knobs** (`config.py`, mirror the `qwen3_streaming_*` block at ~line 150-170): `nemotron_model`, `nemotron_left_context_sec`, `nemotron_chunk_sec`, etc. livecaption's `asr.py` already exposes these as the mlx-audio nemotron streaming params.
4. **parse_args group** (`parse_args.py`): a `--nemotron-*` flag group, mirroring `qwen3_streaming_group`.
5. **online_factory branch** (`core.py` ~430-452): a `nemotron` case returning `_ASRTokenNormalizer(NemotronOnlineProcessor(asr))`.

## The transformers-pin advantage (real)

nemotron via `mlx-audio` is **pure MLX — no torch, no transformers**. This avoids the `transformers==4.57.6` pin that `qwen3-asr-causal` requires (and the fragile pin dance where installing mlx-lm or nllw bumps transformers to 5.x and silently breaks qwen3). A nemotron backend is dep-light and version-stable. This is a genuine design advantage over the qwen3-streaming path and should be called out in the backend's `install` framing.

## What to drop from livecaption's asr.py

livecaption's `asr.py` carries its own VAD (`mlx_audio.vad`), its own audio loop, and its own `AsrWorker(threading.Thread)` dispatcher. **WLK's `AudioProcessor` provides all of these** (VAD via `silero_vad_iterator`, the async processor loop, the threading). The nemotron backend keeps only: the mlx-audio nemotron streaming kernel reuse (`mlx_audio.stt.models.nemotron_asr.streaming`) and the `AlignedTokens` timestamp extraction. The VAD, the loop, and the dispatcher are dropped — they're the duplicated core.

## Gaps and risks

1. **nemotron is English-strong.** Weaker Chinese than qwen3-asr (which has native Taiwan Mandarin vocab). This is the known quality tradeoff; the design states it honestly. For zh-tw specifically, qwen3-streaming remains the quality pick; nemotron is the dep-light, timestamp-rich pick.
2. **Riskiest unknown: does mlx-audio's nemotron expose hooks for WLK's process_iter loop, or does it need a wrapper?** livecaption's `asr.py` drives nemotron with its own `_decode_chunk` loop, not a `process_iter`-shaped API. The port likely needs a thin wrapper that adapts mlx-audio's chunked decode to WLK's `process_iter(audio_chunk)` → `(tokens, end_time)` contract. This is the same kind of adapter qwen3 needed (`_ASRTokenNormalizer` + the online processor class) and is the bulk of the implementation work. Medium effort, not trivial.
3. **No diarization alignment risk noted** — qwen3 needed `_to_wlk_token` partly for diarization's `has_punctuation`; nemotron's tokens flow through the same normalizer, so this is covered.

## Honest scope

This design covers the plain nemotron ASR backend. It does NOT cover: the screen-OCR hotword loop (separate, ports via the `qwen3_streaming_context`-style config knob, but nemotron's mlx-audio path may not accept a context/hotword param — needs a probe), the overlay (a client concern, not a backend), or simultaneous MT (separate design).
