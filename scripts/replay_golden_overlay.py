#!/usr/bin/env python3
"""Replay a golden/captured caption event stream through the overlay's display
state and print the FULL FRAME the user sees at each event — all four fields:
the EN history row, the current EN row, the zh history field, and the zh
reading buffer. This is the ground-truth check for "does the overlay make
sense from the user's perspective".

Field semantics (overlay.py):
  en_prev   previous completed translation (bright, history)
  en        current translation line (draft dim -> final bright)
  zh        the PREVIOUS committed source sentence (promoted when new words arrive)
  partial   the zh reading buffer (rolling tail -> committed sentence)

Usage:
  .venv/bin/python scripts/replay_golden_overlay.py tests/golden/zh_long_ideal.jsonl
"""
import sys
from datetime import datetime, timedelta

from whisperlivekit.caption_events import EventLog
from whisperlivekit.overlay_model import OverlayDisplayModel

def _src_join(a, b):
    if not a:
        return b
    if not b:
        return a
    if a[-1].isspace() or b[:1].isspace():
        return a + b
    def _cjk(ch):
        return ("\u4e00" <= ch <= "\u9fff"
                or ch in "\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001\uff09\u300d\u300f\u3011")
    if _cjk(a[-1]) and _cjk(b[0]):
        return a + b
    return a + " " + b


EPOCH = datetime(2026, 1, 1)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, s: float) -> None:
        self.now += s


class Frame:
    """The four overlay fields, as the user sees them."""

    def __init__(self) -> None:
        self.en_prev = ""
        self.en_cur = ""
        self.en_style = ""
        self.zh_hist = ""
        self.zh_buf = ""

    def render(self, n: int, event_type: str, audio_t: float) -> str:
        lines = [
            f"  ┌ EN history : {self.en_prev}",
            f"  │ EN current : {self.en_cur}",
            f"  └ zh history : {self.zh_hist}",
            f"    src buffer : {self.zh_buf}",
        ]
        return "\n".join(lines)


def main():
    path = sys.argv[1]
    events = EventLog.load(path).events
    clk_run = [0.0]

    class C:
        def __call__(self):
            return clk_run[0]

        def advance(self, s):
            clk_run[0] += s

    clk = C()
    model = OverlayDisplayModel(hold_sec=3.5, clock=clk)
    # mirror the OverlayRenderer field state (zh reading buffer + history)
    zh_buffer_state = "rolling"
    zh_buffer_text = ""
    zh_hist = ""
    prev_spans = []
    print(f"=== {len(events)} events from {path} — frames as the user sees them ===\n")
    # mirror the OverlayRenderer field state (zh reading buffer + history)
    zh_committed = ""
    zh_sentence_complete = False
    zh_hist = ""
    print(f"=== {len(events)} events from {path} — frames as the user sees them ===\n")
    for i, e in enumerate(events):
        t = e.type
        if t == "transcription_provisional":
            if zh_sentence_complete:
                zh_hist = zh_committed
                zh_committed = ""
                zh_sentence_complete = False
            # the rolling tail is DISPLAY-ONLY: it never joins the committed
            # accumulation (only transcription_final commits)
            zh_buffer_text = _src_join(zh_committed, e.text)
        elif t == "transcription_final":
            zh_committed = _src_join(zh_committed, e.text)
            if e.text.rstrip().endswith(("。", "！", "？", ".", "!", "?")):
                zh_sentence_complete = True
            zh_buffer_text = zh_committed
        elif t == "translation_provisional":
            model.preview([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        elif t == "translation_final":
            model.translation([(None, e.text)], EPOCH + timedelta(seconds=e.audio_t))
        clk.advance(0.2)
        model.tick()
        cur = "".join(sp.text for sp in model.state().current)
        prev = "".join(s.text for s in model.state().prev)
        marker = ""
        if t == "translation_final":
            marker = "   <<<< FINAL LANDS (bright)"
        elif t == "transcription_final":
            marker = "   (clause committed -> buffer)"
        print(f"[{e.audio_t:6.2f}] {t}")
        print(f"    ┌─prev─: {prev}")
        print(f"    ├─cur : {cur}")
        print(f"    ├─zh  : {zh_hist}")
        print(f"    └─src : {zh_buffer_text}")
        if marker:
            print(f"    {marker}")


if __name__ == "__main__":
    main()
