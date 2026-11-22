#!/usr/bin/env python3
"""Regenerate the checked-in golden caption streams through the real writer.

The goldens under ``tests/golden/`` are recorded caption event streams — the
regression pair for the display model and the replay instrument. They are
written, not hand-authored: this script replays every recorded event through
the production writer (``EventTap`` -> ``EventLog``), so the checked-in files
carry whatever line shape the pipeline currently emits. Hand-editing a golden
is what let the old ones keep a shape the writer had stopped producing.

What the script normalizes, and why:

  - the payload comes from ``CaptionEvent.to_dict()`` plus the session id
    ``EventLog`` adds, so a golden line has exactly the writer's keys;
  - ``t`` is stamped by ``EventTap`` from the replayed recording clock, so it
    means what the docs say (seconds since the stream started) instead of the
    raw ``perf_counter`` reading some captures carried. The replayed readings
    are rounded to milliseconds: sub-millisecond jitter is recorder noise, not
    caption timing;
  - ``session`` is pinned per stream (``EventLog`` mints a random id per
    instance) so the file is byte-stable and regeneration is a no-op.

``audio_t``, ``type`` and ``text`` are copied verbatim: the recording's content
is the test's expectation and is not the script's business.

Usage:
  python scripts/build_golden_streams.py            # rewrite the goldens
  python scripts/build_golden_streams.py --check    # exit 1 if any is stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from whisperlivekit.caption_events import EventLog, EventTap

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden"

EVENT_TYPES = (
    "transcription_provisional",
    "transcription_final",
    "translation_provisional",
    "translation_final",
)


class _ReplayClock:
    """Clock that replays the recorded ``t`` readings.

    ``EventTap`` reads its clock once when it is created (the stream's origin)
    and once per emitted event, so the recording's own timestamps reach the
    rewritten ``t`` as an offset from its first reading.
    """

    def __init__(self, readings):
        self._readings = list(readings)

    def __call__(self):
        return self._readings.pop(0)


def _session_id(stem: str) -> str:
    """A stable 8-character session id for this stream.

    The id is a row key, not content, so deriving it from the file name keeps
    regeneration byte-identical; 8 hex characters is what ``EventLog`` writes.
    """
    return hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]


def _read_recordings(path: Path):
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        if row["type"] not in EVENT_TYPES:
            raise ValueError(f"{path}: unknown event type {row['type']!r}")
        if not str(row.get("text", "")).strip():
            raise ValueError(f"{path}: blank text would not be emitted by the tap")
    return rows


def write_stream(rows, dest: Path, session: str) -> None:
    """Replay `rows` into `dest` through the real tap and log."""
    dest.unlink(missing_ok=True)  # EventLog appends
    log = EventLog(str(dest))
    log.session = session  # pinned, so the checked-in bytes are stable
    tap = EventTap(
        sink=log,
        clock=_ReplayClock(
            [round(rows[0]["t"], 3)] + [round(row["t"], 3) for row in rows]
        ),
    )
    try:
        for row in rows:
            getattr(tap, row["type"])(row["audio_t"], row["text"])
    finally:
        log.close()


def build_all(dest_dir: Path, goldens) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for golden in goldens:
        write_stream(_read_recordings(golden), dest_dir / golden.name, _session_id(golden.stem))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the checked-in goldens instead of rewriting")
    args = parser.parse_args(argv)

    goldens = sorted(GOLDEN_DIR.glob("*.jsonl"))
    if not goldens:
        print(f"no goldens under {GOLDEN_DIR}", file=sys.stderr)
        return 2

    if not args.check:
        build_all(GOLDEN_DIR, goldens)
        for golden in goldens:
            print(f"rewrote {golden.relative_to(GOLDEN_DIR.parent.parent)}")
        return 0

    stale = []
    with tempfile.TemporaryDirectory() as tmp:
        build_all(Path(tmp), goldens)
        for golden in goldens:
            if golden.read_bytes() != (Path(tmp) / golden.name).read_bytes():
                stale.append(golden.name)
    if stale:
        print("stale goldens (run scripts/build_golden_streams.py): " + ", ".join(stale))
        return 1
    print(f"{len(goldens)} goldens match the current writer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
