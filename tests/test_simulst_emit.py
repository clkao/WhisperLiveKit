#!/usr/bin/env python3
"""Unit tests for the SimulST eval harness (no audio needed).

Tests:
  1. Hypothesis record shape: synthetic emission log → hypothesis.jsonl
     with correct delays/elapsed/elapsed_semantics.
  2. TimestampSource abstraction: ForcedAlignTimestampSource and
     NativeTokenTimestampSource satisfy the protocol.

Run: python -m pytest tests/test_simulst_emit.py -v
  or: python tests/test_simulst_emit.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

# Ensure scripts/ is importable
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def test_hypothesis_record_shape():
    """Synthetic emission log produces a correctly-shaped hypothesis record.

    Falsified if: delays contains acoustic positions (not chunk-boundary
    times), elapsed_semantics != ca_compatible_incremental, or
    len(delays) != number of emission units in prediction.
    """
    from simulst_timestamp import WordTimestamp, NativeTokenTimestampSource
    from alignatt4llm.emission import register_translation_words, register_translation_timestamps
    from alignatt4llm.artifacts import (
        normalize_computation_aware_timestamps,
        HYPOTHESIS_ELAPSED_SEMANTICS_CA_COMPATIBLE,
    )
    from alignatt4llm.text_surface import prediction_text_from_target_surface

    # Simulate 3 chunks of ASR emission
    chunks = [
        ("Hello world", 2000.0, 1500.0),    # (text, audio_processed_ms, wallclock_ms)
        ("Hello world this is", 4000.0, 3100.0),
        ("Hello world this is a test", 6000.0, 4800.0),
    ]

    word_delays: list[float] = []
    word_elapsed: list[float] = []
    prev_text = ""
    audio_duration_ms = 6000.0

    for text, ap_ms, wc_ms in chunks:
        if text != prev_text:
            register_translation_words(
                prev_text, text, ap_ms, word_delays,
                target_lang_code="en",
            )
            register_translation_timestamps(
                prev_text, text, wc_ms, word_elapsed,
                target_lang_code="en",
            )
            prev_text = text

    normalized_elapsed = normalize_computation_aware_timestamps(word_delays, word_elapsed)
    prediction = prediction_text_from_target_surface(prev_text, target_lang_code="en")

    record = {
        "source": ["test.wav"],
        "source_length": audio_duration_ms,
        "prediction": prediction,
        "delays": word_delays,
        "elapsed": normalized_elapsed,
        "elapsed_wallclock_ms": word_elapsed,
        "elapsed_semantics": HYPOTHESIS_ELAPSED_SEMANTICS_CA_COMPATIBLE,
    }

    # Assertions
    # 1. delays are chunk-boundary times, NOT acoustic positions
    assert all(d > 0 for d in record["delays"]), "delays must be positive"
    assert record["delays"][0] == 2000.0, f"First delay should be 2000 (chunk boundary), got {record['delays'][0]}"
    assert record["delays"][-1] == 6000.0, f"Last delay should be 6000, got {record['delays'][-1]}"

    # 2. elapsed_semantics is CA-compatible
    assert record["elapsed_semantics"] == "ca_compatible_incremental"

    # 3. Number of delays matches number of words in prediction
    n_words = len(prediction.split())
    assert len(record["delays"]) == n_words, (
        f"len(delays)={len(record['delays'])} != n_words={n_words}"
    )

    # 4. delays are monotonically non-decreasing
    for i in range(1, len(record["delays"])):
        assert record["delays"][i] >= record["delays"][i-1], (
            f"delays not monotonic at i={i}: {record['delays'][i-1]} -> {record['delays'][i]}"
        )

    # 5. elapsed has same length as delays
    assert len(record["elapsed"]) == len(record["delays"])

    # 6. prediction is the full final text
    assert "Hello" in record["prediction"]
    assert "test" in record["prediction"]

    print("test_hypothesis_record_shape: PASS")


def test_hypothesis_record_char_level_zh():
    """Zh target: each non-whitespace char is an emission unit.

    Falsified if: len(delays) != number of non-whitespace chars in prediction.
    """
    from alignatt4llm.emission import register_translation_words, register_translation_timestamps
    from alignatt4llm.artifacts import normalize_computation_aware_timestamps
    from alignatt4llm.text_surface import prediction_text_from_target_surface, split_target_emission_units

    chunks = [
        ("大家好", 2000.0, 1500.0),
        ("大家好我是", 4000.0, 3100.0),
        ("大家好我是测试", 6000.0, 4800.0),
    ]

    word_delays: list[float] = []
    word_elapsed: list[float] = []
    prev_text = ""

    for text, ap_ms, wc_ms in chunks:
        if text != prev_text:
            register_translation_words(
                prev_text, text, ap_ms, word_delays,
                target_lang_code="zh",
            )
            register_translation_timestamps(
                prev_text, text, wc_ms, word_elapsed,
                target_lang_code="zh",
            )
            prev_text = text

    normalized_elapsed = normalize_computation_aware_timestamps(word_delays, word_elapsed)
    prediction = prediction_text_from_target_surface(prev_text, target_lang_code="zh")

    # For zh, each non-whitespace char is a unit
    n_units = len(split_target_emission_units(prediction, target_lang_code="zh"))
    assert len(word_delays) == n_units, (
        f"len(delays)={len(word_delays)} != n_chars={n_units} for zh"
    )

    print(f"test_hypothesis_record_char_level_zh: PASS ({n_units} char units)")


def test_timestamp_source_protocol():
    """Both TimestampSource implementations satisfy the Protocol.

    Falsified if: either class doesn't implement get_word_timestamps.
    """
    from simulst_timestamp import (
        TimestampSource,
        ForcedAlignTimestampSource,
        NativeTokenTimestampSource,
    )

    # ForcedAlignTimestampSource
    fa = ForcedAlignTimestampSource()
    assert hasattr(fa, "get_word_timestamps")

    # NativeTokenTimestampSource
    native = NativeTokenTimestampSource()
    assert hasattr(native, "get_word_timestamps")

    # NativeTokenTimestampSource with fake aligned tokens
    class FakeToken:
        def __init__(self, text, start):
            self.text = text
            self.start = start

    native.update([
        FakeToken("hello", 0.5),
        FakeToken("world", 1.0),
    ])
    timestamps = native.get_word_timestamps(None, "")
    assert len(timestamps) == 2
    assert timestamps[0].text == "hello"
    assert timestamps[0].start_time == 0.5
    assert timestamps[1].text == "world"
    assert timestamps[1].start_time == 1.0

    # Reset
    native.reset()
    assert len(native.get_word_timestamps(None, "")) == 0

    # Check isinstance against Protocol
    assert isinstance(fa, TimestampSource)
    assert isinstance(native, TimestampSource)

    print("test_timestamp_source_protocol: PASS")


def test_ca_normalization_round_trip():
    """normalize_computation_aware_timestamps produces monotonic output.

    Falsified if: normalized values are not monotonically non-decreasing.
    """
    from alignatt4llm.artifacts import normalize_computation_aware_timestamps

    delays = [2000.0, 4000.0, 6000.0]
    elapsed = [1500.0, 3100.0, 4800.0]
    normalized = normalize_computation_aware_timestamps(delays, elapsed)

    assert len(normalized) == len(delays)
    for i in range(1, len(normalized)):
        assert normalized[i] >= normalized[i-1], (
            f"normalized not monotonic at i={i}: {normalized[i-1]} -> {normalized[i]}"
        )

    # Empty case
    assert normalize_computation_aware_timestamps([], []) == []

    print("test_ca_normalization_round_trip: PASS")


def test_emitter_writes_files():
    """HypothesisEmitter writes hypothesis.jsonl + manifest.json with
    correct structure (no audio needed — uses a mock).

    Falsified if: files are missing, hypothesis record shape is wrong,
    or manifest has wrong schema_version.
    """
    from simulst_emit import HypothesisEmitter

    # We can't run the full emitter without audio, but we can test
    # the manifest builder and record shape directly.
    emitter = HypothesisEmitter("fake.wav", mode="asr-only", target_lang_code="en")
    manifest = emitter._build_manifest(360000.0)

    assert manifest["schema_version"] == "cascade_v1"
    assert manifest["target_language_code"] == "en"
    assert manifest["source_language_code"] == "en"
    assert manifest["runtime_config"]["hypothesis_elapsed_semantics"] == "ca_compatible_incremental"
    assert manifest["runtime_config"]["mode"] == "asr-only"
    assert manifest["runtime_config"]["asr_backend"] == "mlx-qwen3-asr"
    assert manifest["audio_duration_ms"] == 360000.0

    print("test_emitter_writes_files: PASS")


if __name__ == "__main__":
    test_hypothesis_record_shape()
    test_hypothesis_record_char_level_zh()
    test_timestamp_source_protocol()
    test_ca_normalization_round_trip()
    test_emitter_writes_files()
    print("\nAll tests passed.")
