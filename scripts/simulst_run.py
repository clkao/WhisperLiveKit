#!/usr/bin/env python3
"""SimulST eval harness runner.

Iterates devset audios (or a single-audio smoke), invokes the emitter
per audio, then runs ``alignatt-eval`` over the collected
``hypothesis.jsonl``.

Usage:
    # Single-audio smoke (AC-1):
    python scripts/simulst_run.py --audio ccpXHNfaoy.wav \
        --mode asr-only --skip-comet \
        --output-dir outputs/simulst_smoke

    # Full devset (AC-2):
    python scripts/simulst_run.py --devset full \
        --mode asr-mt --target zh \
        --output-dir outputs/simulst_anchor

    # Flagship compare (AC-4):
    python scripts/simulst_run.py --devset full \
        --mode asr-mt --asr-backend nemotron-mlx --target zh \
        --output-dir outputs/simulst_flagship
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Default paths (relative to AlignAtt4LLM repo root or absolute).
ALIGNATT4LLM_ROOT = Path("/Users/clkao/git/asr/AlignAtt4LLM")
DEVSET_AUDIO_DIR = ALIGNATT4LLM_ROOT / "data" / "devset" / "audio"
DEVSET_SEGMENTS = ALIGNATT4LLM_ROOT / "data" / "devset" / "audio-segments.yaml"
DEVSET_REF_DIR = ALIGNATT4LLM_ROOT / "data" / "devset" / "ref"

# Eval venv Python (has omnisteval + alignatt4llm via .pth).
EVAL_VENV_PYTHON = Path("/Users/clkao/git/asr/_eval_venv/bin/python")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SimulST eval harness runner.",
    )
    parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="Single audio filename (e.g., ccpXHNfaoy.wav) for smoke test.",
    )
    parser.add_argument(
        "--devset",
        type=str,
        default=None,
        choices=["full"],
        help="Run the full devset (all 21 audios).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="asr-only",
        choices=["asr-only", "asr-mt"],
        help="Emitter mode.",
    )
    parser.add_argument(
        "--asr-backend",
        type=str,
        default="mlx-qwen3-asr",
        choices=["mlx-qwen3-asr", "nemotron-mlx"],
        help="ASR backend.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="en",
        help="Target language code (en for ASR-only, zh for en→zh MT).",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="en",
        help="Source language code.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/simulst_run",
        help="Output directory for hypothesis + evaluation artifacts.",
    )
    parser.add_argument(
        "--chunk-sec",
        type=float,
        default=2.0,
        help="Audio chunk size in seconds.",
    )
    parser.add_argument(
        "--skip-comet",
        action="store_true",
        help="Skip XCOMET-XL scoring (latency-only).",
    )
    parser.add_argument(
        "--asr-model-id",
        type=str,
        default=None,
        help="Override ASR model ID.",
    )
    parser.add_argument(
        "--mt-model-id",
        type=str,
        default=None,
        help="Override MT model ID (for asr-mt mode).",
    )
    parser.add_argument(
        "--no-second-pass",
        action="store_true",
        help="Disable ASR two-pass re-decode (lower latency).",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Skip emission; only run alignatt-eval on existing hypothesis.jsonl.",
    )
    return parser.parse_args()


def discover_devset_audios() -> list[str]:
    """Return sorted list of wav filenames in the devset audio dir."""
    if not DEVSET_AUDIO_DIR.exists():
        raise FileNotFoundError(f"Devset audio dir not found: {DEVSET_AUDIO_DIR}")
    return sorted(p.name for p in DEVSET_AUDIO_DIR.glob("*.wav"))


def resolve_audio_path(wav_name: str) -> str:
    """Resolve a wav filename to an absolute path."""
    p = Path(wav_name)
    if p.is_absolute() and p.exists():
        return str(p)
    candidate = DEVSET_AUDIO_DIR / wav_name
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError(f"Audio not found: {wav_name} (looked in {DEVSET_AUDIO_DIR})")


def run_emitter(
    audio_path: str,
    output_dir: str,
    *,
    mode: str,
    asr_backend: str,
    target_lang_code: str,
    source_lang_code: str,
    chunk_sec: float,
    asr_model_id: str | None,
    mt_model_id: str | None,
    second_pass: bool,
) -> None:
    """Run the emitter for one audio."""
    from simulst_emit import HypothesisEmitter

    emitter = HypothesisEmitter(
        audio_path,
        mode=mode,
        asr_backend=asr_backend,
        target_lang_code=target_lang_code,
        source_lang_code=source_lang_code,
        chunk_sec=chunk_sec,
        asr_model_id=asr_model_id,
        mt_model_id=mt_model_id,
        second_pass=second_pass,
    )
    emitter.emit(output_dir)


def _patch_omnisteval_serial():
    """Monkey-patch omnisteval to use serial execution instead of Pool.

    The sandbox blocks multiprocessing semaphores. This patch replaces
    the parallel ``align_words`` with a serial equivalent.
    """
    try:
        import omnisteval.alignment as _align
        from omnisteval.alignment import _process_single_recording
    except ImportError:
        return

    if getattr(_align, "_serial_patched", False):
        return

    def _align_words_serial(ref_words, hyp_words, char_level):
        new_segmentation = {}
        for inst_ref in ref_words:
            for ref in inst_ref:
                if ref.seq_id is not None:
                    new_segmentation[ref.seq_id] = []
        args_list = [
            (i, ref, hyp, char_level)
            for i, (ref, hyp) in enumerate(zip(ref_words, hyp_words))
        ]
        results = [_process_single_recording(args) for args in args_list]
        for result in results:
            for word in result:
                if word.seq_id is not None and word.seq_id in new_segmentation:
                    new_segmentation[word.seq_id].append(word)
        return new_segmentation

    _align.align_words = _align_words_serial
    _align._serial_patched = True


def run_alignatt_eval(
    output_dir: str,
    *,
    target_lang_code: str,
    skip_comet: bool,
) -> int:
    """Run alignatt-eval on the output directory. Returns exit code."""
    _patch_omnisteval_serial()

    target_ref = DEVSET_REF_DIR / f"{target_lang_code}.txt"
    source_ref = DEVSET_REF_DIR / f"en.txt" if source_ref_exists() else None

    cmd = [
        str(EVAL_VENV_PYTHON),
        str(Path(__file__).parent / "simulst_eval_wrapper.py"),
        "--output-dir", output_dir,
        "--speech-segmentation", str(DEVSET_SEGMENTS),
        "--target-reference", str(target_ref),
        "--target-lang-code", target_lang_code,
    ]
    if source_ref:
        cmd.extend(["--source-reference", str(source_ref)])
    if skip_comet:
        cmd.append("--skip-comet")

    logger.info("Running alignatt-eval: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def source_ref_exists() -> bool:
    return (DEVSET_REF_DIR / "en.txt").exists()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine which audios to process
    if args.audio:
        audio_names = [args.audio]
    elif args.devset == "full":
        audio_names = discover_devset_audios()
    else:
        logger.error("Specify --audio <wav> or --devset full")
        sys.exit(1)

    logger.info("Processing %d audio(s): %s", len(audio_names), audio_names)

    # --- Emission phase ---
    if not args.eval_only:
        # For single-audio mode, emit directly into output_dir.
        # For multi-audio mode, emit each into a sub-dir, then merge
        # all hypothesis records into a single hypothesis.jsonl.
        if len(audio_names) == 1:
            audio_path = resolve_audio_path(audio_names[0])
            logger.info("Emitting: %s", audio_path)
            run_emitter(
                audio_path,
                str(output_dir),
                mode=args.mode,
                asr_backend=args.asr_backend,
                target_lang_code=args.target,
                source_lang_code=args.source,
                chunk_sec=args.chunk_sec,
                asr_model_id=args.asr_model_id,
                mt_model_id=args.mt_model_id,
                second_pass=not args.no_second_pass,
            )
        else:
            # Multi-audio: emit each into a sub-dir, merge records
            import json
            all_records: list[dict] = []
            for wav_name in audio_names:
                audio_path = resolve_audio_path(wav_name)
                sub_dir = output_dir / Path(wav_name).stem
                logger.info("Emitting: %s → %s", wav_name, sub_dir)
                run_emitter(
                    audio_path,
                    str(sub_dir),
                    mode=args.mode,
                    asr_backend=args.asr_backend,
                    target_lang_code=args.target,
                    source_lang_code=args.source,
                    chunk_sec=args.chunk_sec,
                    asr_model_id=args.asr_model_id,
                    mt_model_id=args.mt_model_id,
                    second_pass=not args.no_second_pass,
                )
                # Read the hypothesis record
                hyp_path = sub_dir / "hypothesis.jsonl"
                if hyp_path.exists():
                    for line in hyp_path.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            all_records.append(json.loads(line))

            # Write merged hypothesis.jsonl
            from alignatt4llm.artifacts import write_jsonl, write_json, HYPOTHESIS_FILENAME, MANIFEST_FILENAME
            write_jsonl(output_dir / HYPOTHESIS_FILENAME, all_records)
            # Write a manifest for the merged run (from the first sub-dir)
            first_manifest = output_dir / Path(audio_names[0]).stem / MANIFEST_FILENAME
            if first_manifest.exists():
                import shutil
                write_json(output_dir / MANIFEST_FILENAME, json.loads(first_manifest.read_text()))

    # --- Evaluation phase ---
    logger.info("Running alignatt-eval on %s", output_dir)
    exit_code = run_alignatt_eval(
        str(output_dir),
        target_lang_code=args.target,
        skip_comet=args.skip_comet,
    )
    if exit_code != 0:
        logger.error("alignatt-eval failed with exit code %d", exit_code)
        sys.exit(exit_code)

    # --- Check evaluation results ---
    eval_json = output_dir / "evaluation.json"
    if eval_json.exists():
        import json
        eval_data = json.loads(eval_json.read_text(encoding="utf-8"))
        scores = eval_data.get("contract_scores", {})
        logger.info("Contract scores:")
        for key, val in scores.items():
            logger.info("  %s = %s", key, val)
    logger.info("Done. Results in %s", output_dir)


if __name__ == "__main__":
    main()
