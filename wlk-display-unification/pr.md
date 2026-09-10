feat: caption display semantics and a standardized caption event stream

## Summary

The web UI renders the translation buffer as it comes from the MT layer. For
backends that do not produce provisional translations, that buffer holds
untranslated source text, so raw source shows up in the translation line.
Translations arrive as strings managed inside the MT layer: a correction
replaces text the reader already saw, a multi-sentence translation is
replaced wholesale by the next update, and sentence ends are nowhere in the
data. Display behavior also has no tests, because nothing is recorded.

This PR moves sentence derivation and display rules into a layer separate
from the MT layer:

- `caption_events.py` emits four typed events (transcription and
  translation, provisional and final) from a tap in `AudioProcessor`, each
  carrying the text and the source it was produced against. `--event-log`
  records the stream as JSONL for replay and testing.
- `caption_display.py` turns the stream into a display state: captions are
  derived per sentence, a finished sentence is held and always shown, a
  sentence flips to final style in place, and final text never visibly
  shrinks or rewords.
- Translation backends declare `provides_drafts` and a `progress()` method.
  Backends without drafts (NLLB, the AlignAtt sidecar) need no changes; the
  draft path is unreachable for them.

It does not wire the current web UI yet; that is the follow-up.

## User impact

- The web UI, FrontData, and `results_formatter` are unchanged.
- `--event-log` is new, off by default, and writes one JSONL line per event.
- The MLX engines expose state they already track; `process()` semantics
  are unchanged.

## Validation

- `test_caption_display.py`: each display rule has a test that fails when
  the rule is broken.
- `test_caption_events.py` and `test_translation_emission.py`: stream and
  emission contracts, no live model needed.
- A recorded zh→en simultaneous session
  (`tests/golden/zh_long_time_frontier.jsonl`) replayed through
  `CaptionDisplay` shows every finished sentence in order, each shown once.
- `uv run pytest -q tests/ --ignore=tests/test_pipeline.py`: same result as
  `main` apart from the new tests.
- Live run on Apple Silicon (Qwen3 ASR, `Hy-MT2-1.8B-8bit`, zh→en): the
  recorded log replays through `CaptionDisplay`.
- `ruff check .` passes; it also passes on `main`.

## Checklist

- [x] I added or updated tests for behavior changes.
- [ ] I updated documentation for user-facing changes. (A section for
      `--event-log` will be added.)
- [x] I ran `ruff check .`.
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or
      private data.
