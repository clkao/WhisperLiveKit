feat: time-based accessible frontier for the simultaneous-MT commit policy

## Summary

The simultaneous-MT commit policy decides when a provisional translation may
commit against the source. Its view of the source currently advances only
when the ASR commits: the accessible frontier is derived from the committed
text prefix, so between commits the policy cannot see words that were
already spoken. Measured on real clips, that cadence is the bottleneck
(frontier accuracy caps at 0.41 for every candidate attention head), and it
starves sentence-tail drafts: on a zh→en clip, a final sentence's
translation covered only 0.40 of the draft text that pre-released it.

This PR adds a time-based accessible frontier. Source words become
accessible once their end time is behind the audio cursor (minus a
hold-back), decoupling the frontier from the ASR commit cadence. The
unstable tail is released fractionally as the cursor sweeps its window, so
the policy sees word-level progress without requiring word timestamps from
the ASR.

Through what:

- `frontier_mode` (text | time | auto) on the simultaneous engine; the
  config carries `mlx_llm_mt_simul_frontier` and `mlx_llm_mt_simul_hold_back_s`.
- `auto` (the default) resolves to the time frontier for every simul
  backend; `text` remains the explicit opt-out.
- End-of-feed clamp: when the audio feed completes, the whole unstable tail
  is released (the tail's time window is anchored to the ASR clock, which
  outlives the feed; without the clamp the release froze mid-sentence for
  the entire drain and the last segment's draft appeared only after its ASR
  final).
- Released-prefix fragment guard: the first draft publishes only once the
  released prefix carries at least 6 source tokens (estimated via a rolling
  chars-per-token ratio refined from the real source mapping), so 1-3 word
  stubs do not flash at sentence opens. Text mode and pre-cursor time mode
  are exempt.
- A DRAIN_RELEASE marker wakes the translation loop at end-of-feed to
  evaluate the clamped release immediately.

## User impact

- Measured A/B on real clips (same audio, same ASR output, paper commit
  policy): zh→en draft coverage 0.63 → 0.82–0.87; en→zh 0.55 → 0.70. Every
  previously starved final improved; draft churn did not increase.
- The drain no longer freezes: the last segment's full draft lands before
  its ASR final instead of 9 seconds after it.
- Backends without the contract behave exactly as before in text mode
  (byte-identical mapping of the committed prefix).
- Deviation from the AlignAtt paper, stated plainly: the paper commits only
  against ASR-committed source. Fractional tail release commits against
  text the ASR may still revise. The protection is the display layer's
  provisional grammar (draft rewording is expected and held), and the final
  translation is always a full re-translation.

## User impact notes

- This PR stacks on #448: the zh→en calibration file must exist for the
  simultaneous engine to construct.
- Depends on the frontend changes only through the display semantics that
  #449 documents; no frontend changes are required here.

## Validation

- `test_simul_frontier.py`: the frontier mapping (cursor interpolation into
  the tail, hold-back, stale-tail drop, session propagation), the auto
  resolution, the end-of-feed clamp, and the fragment guard. Each rule has
  a test that fails when the rule is broken; the guard tests include the
  exemption cases (text mode, pre-cursor time mode).
- `test_model_id_aliases.py`: the dot-form model-id aliases accepted by the
  profile registry.
- `uv run pytest -q tests/ --ignore=tests/test_pipeline.py`: same failure
  set as `main` (canary, deepgram, qwen3 shims, ffmpeg-dependent
  collection) — verified identical.
- Live A/B on Apple Silicon (Qwen3 ASR + `Hy-MT2-1.8B-8bit`): the numbers
  above; full runs recorded with `--event-log`.

## Checklist

- [x] I added or updated tests for behavior changes.
- [ ] I updated documentation for user-facing changes. (The config fields
      are documented in `config.py`; a docs section can follow the
      deactivate-policy decision in #448.)
- [x] I ran `ruff check .`.
- [x] I ran the relevant pytest suite.
- [x] I did not commit credentials, model weights, generated caches, or
      private data.
