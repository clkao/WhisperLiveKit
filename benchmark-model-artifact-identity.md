---
title: "benchmark: report which weights actually loaded, not an empty artefact record"
status: backlog
score: 0.5
source: found while measuring qwen3-asr 0.6B vs 1.7B (implementation cycle 10)
id: jg3ktjxtsqejkcgrnv6r9p94
---

`describe_model_artifacts(config)` in `whisperlivekit/benchmark/metrics.py` returns `{}` for a Hub model
id, so a benchmark report cannot state which weights produced it. `runner.py` calls it after timing and
stores the result on the report.

Why it matters: a 1.7B arm silently ran the 0.6B default because `--model` did not reach the backend,
and the only way that surfaced was that its WER was byte-identical to the 0.6B arm. A report that named
its weights would have caught it immediately.

Acceptance: a benchmark report for a Hub-id model carries a non-empty artefact record naming the model
id and a content identity (revision or digest); a run whose model differs from the request fails or
reports the mismatch. Falsifier: a report with an empty artefact record for a Hub id.

Note: the adapter half of that incident (honouring `model_size`) belongs to the mlx-qwen3-asr backend
change, not here. This task is the harness side only.
