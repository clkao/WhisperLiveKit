"""The time-based accessible frontier for the simultaneous-MT commit policy.

The text frontier maps the ASR-committed text, so the commit policy's view of
the source only advances when the ASR commits. The time frontier instead makes
a source word accessible once its end time is behind the audio cursor (minus
hold-back), decoupling the frontier from the commit cadence. These tests pin
the frontier semantics: text mode unchanged by default, cursor-driven tail
interpolation, hold-back, the stale-tail drop, and the config/factory wiring.
"""

import json

from whisperlivekit.timed_objects import ASRToken, HypothesisTail


def _test_calibration(tmp_path, source_language="en", target_language="zh"):
    """A synthetic calibration for a 2-layer/4-head model (no download)."""
    from whisperlivekit.translation_mlx_llm_mt import MlxLlmTranslation

    engine = MlxLlmTranslation(source_language=source_language, target_language=target_language, warmup=False)
    data = {
        "model": engine._config.repo,
        "direction": f"{source_language}-{target_language}", "num_layers": 2, "num_heads": 4,
        "used_pairs": 100, "token_alignment_heads": [
            {"layer": layer, "head": head, "ts": 0.5} for layer in range(2) for head in range(4)
        ],
        "promotion_gate": {"eligible_for_promotion": True},
        "stability_checks": [{"stable_vs_full": True, "max_abs_ts_delta_vs_full": 0.01}] * 3,
        "runtime": {"backend": "mlx-lm", "model_revision": "a" * 40, "source_sha256": "0" * 64,
                    "quantization": {"bits": 8}, "prompt": engine._prompt},
    }
    path = tmp_path / "heads.json"
    path.write_text(json.dumps(data))
    return path


def _make_simul(tmp_path, source_language="zh", **kwargs):
    """A simul engine with the model load mocked out (no download)."""
    from whisperlivekit.translation_mlx_llm_mt_simul import MlxLlmTranslationSimul

    b = MlxLlmTranslationSimul(
        source_language=source_language, target_language="en", warmup=False,
        calibration_file=_test_calibration(tmp_path, source_language, "en"), **kwargs,
    )
    b._translate_text = lambda text: f"[EN:{text}]"
    b._ensure_simul_model = lambda: (None, None)  # type: ignore[assignment]
    return b


def _token(text, start, end):
    return ASRToken(start=start, end=end, text=text)


def _tail(text, start=0.0, end=0.0):
    return HypothesisTail(start=start, end=end, text=text)


def test_engine_default_frontier_is_text(tmp_path):
    """The engine-level default frontier_mode is "text": without an explicit
    frontier the committed text maps exactly as before (the time machinery
    must not engage). The core factory resolves the config's "auto" to
    "time" before constructing (see the factory test below)."""
    b = _make_simul(tmp_path)
    assert b._frontier_mode == "text"
    captured = {}

    def fake_simul(source, committed):
        captured["committed"] = committed
        return "Hello"

    b._translate_simul = fake_simul
    b.audio_position = 10.0  # even with a cursor set, text mode ignores it
    b.insert_tokens([_token("你好", 0.0, 0.5), _tail("世界", 0.5, 1.0)])
    b.process()
    assert captured["committed"] == "你好"


def test_time_mode_no_cursor_falls_back_to_text(tmp_path):
    """Time mode without a cursor (audio_position None) is identical to text
    mode — safe degradation, not a crash."""
    b = _make_simul(tmp_path, frontier_mode="time")
    b._MIN_RELEASED_TOKENS = 0  # frontier-mechanics test; the fragment guard is covered separately
    captured = {}
    b._translate_simul = lambda source, committed: captured.setdefault("committed", committed) or "Hello"
    b.insert_tokens([_token("你好", 0.0, 0.5), _tail("世界", 0.5, 1.0)])
    b.process()
    assert captured["committed"] == "你好"


def test_time_mode_extends_into_tail_by_cursor(tmp_path):
    """Time mode: the accessible prefix extends INTO the tail proportionally
    over the tail's window. Cursor 0.8 covers the committed token (end 0.5)
    plus 0.3 of the tail's 0.5s window -> 60% of its chars."""
    b = _make_simul(tmp_path, frontier_mode="time")
    b._MIN_RELEASED_TOKENS = 0  # frontier-mechanics test; the fragment guard is covered separately
    captured = {}
    b._translate_simul = lambda source, committed: captured.setdefault("committed", committed) or "Hello"
    b.insert_tokens([_token("你好", 0.0, 0.5), _tail("abcd", 0.5, 1.0)])
    b.audio_position = 0.8
    b.process()
    # committed "你好" + 60% of the 4-char tail "abcd" -> "ab"
    assert captured["committed"] == "你好ab"


def test_time_mode_fully_covered_tail_equals_source(tmp_path):
    """Cursor past the tail end: the whole source is accessible (the
    no-hold degenerate case the paper's hold-back guards)."""
    b = _make_simul(tmp_path, frontier_mode="time")
    b._MIN_RELEASED_TOKENS = 0  # frontier-mechanics test; the fragment guard is covered separately
    captured = {}
    b._translate_simul = lambda source, committed: captured.setdefault("committed", committed) or "Hello"
    b.insert_tokens([_token("你好", 0.0, 0.5), _tail("世界", 0.5, 1.0)])
    b.audio_position = 1.5
    b.process()
    assert captured["committed"] == "你好世界"


def test_time_mode_respects_hold_back(tmp_path):
    """Hold-back delays accessibility: with 0.5s hold-back and cursor 0.8, a
    token ending at 0.5 is NOT yet accessible (0.5 > 0.8 - 0.5 is false), so
    nothing is accessible and no draft call fires."""
    b = _make_simul(tmp_path, frontier_mode="time", hold_back_s=0.5)
    calls = []
    b._translate_simul = lambda source, committed: calls.append(committed) or "Hello"
    b.insert_tokens([_token("你好", 0.0, 0.5), _tail("世界", 0.5, 1.0)])
    b.audio_position = 0.8
    result, buffer = b.process()
    assert calls == [], "a draft fired before the hold-back released anything"
    assert not (buffer.text or "")


def test_time_mode_hold_back_zero_includes_just_finished_word(tmp_path):
    """0ms hold-back (the paper's operating point): a word is accessible the
    moment its end time reaches the cursor."""
    b = _make_simul(tmp_path, frontier_mode="time", hold_back_s=0.0)
    b._MIN_RELEASED_TOKENS = 0  # frontier-mechanics test; the fragment guard is covered separately
    captured = {}
    b._translate_simul = lambda source, committed: captured.setdefault("committed", committed) or "Hello"
    b.insert_tokens([_token("你好", 0.0, 0.5), _tail("世界", 0.5, 1.0)])
    b.audio_position = 0.5
    b.process()
    assert captured["committed"] == "你好"


def test_time_mode_stale_tail_still_dropped(tmp_path):
    """A hypothesis predating the commit boundary never extends the
    accessible prefix, same as the text frontier's stale-tail rule."""
    b = _make_simul(tmp_path, frontier_mode="time")
    b._MIN_RELEASED_TOKENS = 0  # frontier-mechanics test; the fragment guard is covered separately
    captured = {}
    b._translate_simul = lambda source, committed: captured.setdefault("committed", committed) or "Hello"
    b.insert_tokens([_token("你好", 0.0, 0.5), _tail("你好", 0.0, 0.4)])
    b.audio_position = 1.0
    b.process()
    assert captured["committed"] == "你好"


def test_frontier_fields_carried_by_new_session(tmp_path):
    session = _make_simul(tmp_path, frontier_mode="time", hold_back_s=0.25).new_session()
    assert session._frontier_mode == "time"
    assert session._hold_back_s == 0.25
    assert session.audio_position is None


def test_config_frontier_fields_exist():
    from whisperlivekit.config import WhisperLiveKitConfig

    config = WhisperLiveKitConfig()
    assert config.mlx_llm_mt_simul_frontier == "auto"
    assert config.mlx_llm_mt_simul_hold_back_s == 0.0


def test_core_factory_resolves_auto_frontier_to_time():
    """"auto" resolves to the time frontier for every simul backend: the
    measured A/B (zh→en 0.63→0.83, en→zh 0.55→0.70 on real clips) showed the
    time frontier dominates, and the text frontier lacks the fragment guard
    and drain clamp. "text" remains the explicit opt-out."""
    import re

    src = open("whisperlivekit/core.py").read()
    m = re.search(r'if frontier == "auto":\n\s+frontier = "time"', src)
    assert m, "auto must resolve to the time frontier unconditionally"
    assert "frontier_mode=frontier" in src


def test_end_of_feed_clamp_releases_full_tail(tmp_path):
    """End-of-feed clamp: once source_complete is set, the whole unstable tail
    is accessible even though the audio cursor has stopped advancing (the
    tail's time window is anchored to the ASR clock, which outlives the feed;
    without the clamp the fractional release froze mid-sentence for the whole
    drain)."""
    b = _make_simul(tmp_path, frontier_mode="time")
    b._MIN_RELEASED_TOKENS = 0  # frontier-mechanics test; the fragment guard is covered separately
    b.audio_position = 2.0
    b.insert_tokens([_token("Hello", 0.0, 1.0), _tail("world and more words here", 1.0, 5.0)])
    # Before the clamp: the tail is only fractionally accessible (cursor 2.0
    # inside a 1.0-5.0 window).
    partial = b._accessible_text()
    assert "Hello" in partial and "more words" not in partial
    # After the clamp: everything spoken has been fed; release it all.
    b.source_complete = True
    full = b._accessible_text()
    assert full.startswith("Hello") and "more words here" in full


def test_fragment_guard_holds_stub_drafts(tmp_path):
    """Fragment guard (time frontier): a first draft publishes only once the
    RELEASED prefix carries at least _MIN_RELEASED_TOKENS (6) source tokens.
    A 1-3 word stub must not flash at a sentence open."""
    b = _make_simul(tmp_path, frontier_mode="time")
    b.audio_position = 0.5
    b.insert_tokens([_token("今", 0.0, 0.5), _tail("天来讨论", 0.5, 1.0)])
    released = b._accessible_text()
    assert b._accessible_gate_open(released) is False
    result = b.process()
    assert result[0] is None, "a stub released prefix must not publish a draft"
    # Enough released text opens the gate.
    b.audio_position = 1.0
    b.insert_tokens([_token("我们今天来讨论镭射技术在医学上的应用。", 0.5, 1.0)])
    assert b._accessible_gate_open(b._accessible_text()) is True


def test_fragment_guard_exempts_text_mode_and_uncursed_time(tmp_path):
    """The guard only gates the time frontier with a live cursor: text mode
    (released prefix == committed text, historically ungated) and time mode
    before the first cursor update behave exactly as before."""
    bt = _make_simul(tmp_path)
    assert bt._accessible_gate_open("今") is True  # text mode: never gated
    bc = _make_simul(tmp_path, frontier_mode="time")
    assert bc.audio_position is None
    assert bc._accessible_gate_open("今") is True  # no cursor yet: not gated
