"""The caption driver's display plumbing (``scripts/lc_terminal.py``).

Two seams are covered here, both without loading a model or touching audio:

  - the flag surface: the production command line parses, and the flags this
    base cannot honour are stated rather than silently accepted;
  - the overlay adapter: caption events reach the display model as TEXT (the
    overlay owns a ``CaptionDisplay``; it renders ``DisplayState`` and holds no
    display policy of its own).

``overlay`` imports AppKit lazily, so the renderer is exercised headless: the
model updates, the field writes are no-ops.
"""
from __future__ import annotations

import importlib.util
import pathlib

from whisperlivekit.caption_display import PROVISIONAL, CaptionDisplay
from whisperlivekit.caption_events import CaptionEvent

DRIVER = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "lc_terminal.py"


def _driver():
    spec = importlib.util.spec_from_file_location("lc_terminal", DRIVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The captain's production command line, minus the program name and the extras
# (which are ``uv run``'s business, not the parser's).
PRODUCTION_ARGV = [
    "--backend", "nemotron-mlx-asr", "--source", "mic", "--no-second-pass",
    "--mlx-llm-mt-model", "hy-mt2-1.8b-8bit", "--simultaneous",
    "--simul-commit", "mass", "--overlay", "--overlay-mode", "target",
    "--opencc", "s2twp", "--target-language", "en", "--mem",
]


def test_production_command_line_parses():
    args = _driver()._build_parser().parse_args(PRODUCTION_ARGV)
    assert args.backend == "nemotron-mlx-asr"
    assert args.source == "mic"
    assert args.second_pass is False
    assert args.mlx_llm_mt_model == "hy-mt2-1.8b-8bit"
    assert args.simultaneous is True
    assert args.simul_commit == "mass"
    assert args.overlay is True
    assert args.overlay_mode == "target"
    assert args.opencc == "s2twp"
    assert args.target_language == "en"
    assert args.mem is True


def test_backend_choices_are_the_engine_choices():
    """The driver offers exactly the backends this base can build.

    A choice the engine does not have (the PR #425 ``mlx-qwen3-asr`` adapter this
    driver was ported from) fails only at model load, so the two lists must
    agree."""
    from whisperlivekit.parse_args import build_parser as build_engine_parser

    driver = {a.dest: a for a in _driver()._build_parser()._actions}
    engine = {a.dest: a for a in build_engine_parser()._actions}
    assert list(driver["backend"].choices) == list(engine["backend"].choices)
    assert driver["backend"].default in engine["backend"].choices
    assert driver["backend"].default == "nemotron-mlx-asr"


def test_second_pass_defaults_off_and_is_only_offered_as_optional():
    """This ASR backend has no two-pass re-decode: the honest default is off.

    ``--second-pass`` exists only so the flag can be rejected with a message
    instead of being silently ignored (see ``main``)."""
    parser = _driver()._build_parser()
    assert parser.parse_args(["--audio", "a.wav"]).second_pass is False
    assert parser.parse_args(["--audio", "a.wav", "--no-second-pass"]).second_pass is False
    assert parser.parse_args(["--audio", "a.wav", "--second-pass"]).second_pass is True


def test_simul_commit_offers_mass():
    """``mass`` is reachable through the merged simul engine's policy selector."""
    parser = _driver()._build_parser()
    actions = {a.dest: a for a in parser._actions}
    assert set(actions["simul_commit"].choices) == {"argmax", "mass", "paper"}


class _Upper:
    """Stand-in for an OpenCC converter (the extra is not needed to test wiring)."""

    def convert(self, text: str) -> str:
        return text.upper()


def _event(kind: str, text: str) -> CaptionEvent:
    return CaptionEvent(t=0.0, audio_t=0.0, type=kind, text=text)


def test_overlay_sink_feeds_the_model_text():
    """Every caption event kind lands on the model's text API: the source
    partial, the source commit, the target draft and the target final."""
    driver = _driver()
    from whisperlivekit.overlay import OverlayRenderer

    renderer = OverlayRenderer(overlay_mode="target", hold_sec=0.0)
    sink = driver.OverlaySink(renderer)
    display = renderer.state()
    assert display.current == [] and display.partial == ""

    sink.emit(_event("transcription_provisional", "我們今天來討論"))
    assert renderer.state().partial == "我們今天來討論"

    sink.emit(_event("transcription_final", "我們今天來討論鐳射。"))
    # the commit clears the live row (the model owns it) and retires what the
    # reader was reading into the source history — the segment text is not
    # re-assembled into a line
    assert renderer.state().partial == ""
    assert renderer.layout().history == ("我們今天來討論",)

    sink.emit(_event("translation_provisional", "Today we discuss laser."))
    renderer.pump()  # the frame clock releases the draft onto the line
    draft = renderer.state().current
    assert [span.text for span in draft] == ["Today we discuss laser."]
    assert draft[0].style == PROVISIONAL

    sink.emit(_event("translation_final", "Today, we discuss lasers."))
    renderer.pump()
    final = renderer.state().current
    assert [span.text for span in final] == ["Today, we discuss lasers."]
    assert final[0].style != PROVISIONAL


def test_overlay_sink_converts_the_display_text():
    """--opencc converts what the window shows; the model sees converted text."""
    driver = _driver()
    from whisperlivekit.overlay import OverlayRenderer

    renderer = OverlayRenderer(overlay_mode="target", hold_sec=0.0)
    sink = driver.OverlaySink(renderer, opencc_conv=_Upper())
    sink.emit(_event("transcription_provisional", "网络"))
    assert renderer.state().partial == "网络".upper()


def test_overlay_sink_state_is_the_model_state():
    """The harness attaches ``sink.state()`` to every TestState it publishes."""
    driver = _driver()
    from whisperlivekit.overlay import OverlayRenderer

    renderer = OverlayRenderer(overlay_mode="target", hold_sec=0.0)
    sink = driver.OverlaySink(renderer)
    sink.emit(_event("transcription_provisional", "镭射"))
    assert sink.state() == renderer.state()
    assert isinstance(renderer.state(), type(CaptionDisplay(hold_sec=0.0).state()))
