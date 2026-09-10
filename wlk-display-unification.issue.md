# Issue draft: caption display semantics and a standardized caption event stream

> Paste into a GitHub issue on QuentinFuxa/WhisperLiveKit before the PRs.
> ASD-STE100. No internal vocabulary.

## Title

Caption display semantics: a shared display policy and a standardized caption event stream

## Body

### The problem

WhisperLiveKit produces caption state, and every consumer renders it directly.
The state has no display semantics, so each consumer invents its own rules or
shows raw fields. Four concrete problems follow:

1. **Untranslated source in the translation line.** `buffer_translation` is a
   plain string. For translation backends that do not produce provisional
   translations, the buffer holds the untranslated source queue. The web UI
   and any state-driven consumer show raw source text under the translation
   label until the real translation replaces it.
2. **No sentence structure.** Captions are ASR-commit-shaped. A translation
   that covers several sentences is one string, replaced wholesale on the
   next update. Nothing paces what a reader sees.
3. **No stability.** When a translation is corrected mid-sentence, the
   corrected text replaces the old text directly. Words a reader already saw
   can vanish and reappear.
4. **No testability.** Display behavior cannot be captured, replayed, or
   compared. Fixes are verified by watching live sessions.

### The proposal

Add two small layers, without changing what the web UI shows today:

1. **A caption event stream.** The pipeline emits four typed events:
   transcription provisional/final, translation provisional/final. Each
   carries the text, the committed and full source it was produced against,
   and whether a translation model call produced it. A tap in
   `AudioProcessor` fans out to sinks; an optional JSONL log records the
   stream. Recorded streams replay through any consumer, so display behavior
   becomes testable.
2. **A caption display policy.** A state machine that turns events into a
   display state under explicit rules: captions split at sentence ends
   (including CJK marks); a finished sentence is always shown and held for a
   minimum time, even when sentences finish in quick succession; a sentence
   flips to final style in place, never cleared and retyped; final text
   never visibly shrinks or rewords.

Two emission rules are enforced where events are created so that every
consumer inherits them: a translation buffer is shown as a draft only when
the backend actually produces drafts (backends declare this with a
`provides_drafts` flag and a `progress()` method), and identical consecutive
provisionals are suppressed.

### The web UI (follow-up)

The web UI can become another consumer of the event stream. Today it renders
`buffer_translation` directly, which is why problem 1 appears in the browser.
Migration needs no pipeline changes: the event tap supports multiple sinks,
and the diff WebSocket protocol remains the transport. The main design work
is a snapshot-on-reconnect policy on the JS side.

### What a PR for this would include

The event stream, the display policy, the emission wiring into the current
pipeline, the backend contract, recorded streams as test fixtures, and a
replay harness. The web UI is explicitly out of scope. Each display rule
would have a regression test that fails when the rule is broken.
