#!/usr/bin/env bash
# Setup + run script for the Apple-Silicon backends on WhisperLiveKit.
# The mlx-qwen3-asr backend needs huggingface_hub==1.18.0 + transformers==5.11.0
# (matches the livecaption venv). uv resolves hub 1.14.0 (faster-whisper constraint),
# which breaks mlx-qwen3-asr model loading (silent: no ASR output).
# So: uv sync for the binary deps, then hand-install the working combo.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== uv sync (binary deps) ==="
uv sync --extra mlx-llm-mt --extra mlx-qwen3-asr --extra overlay --extra opencc --extra listen

echo "=== hand-install working hub + transformers (uv sync resolves 1.14.0, which breaks ASR) ==="
uv pip install --python .venv/bin/python 'huggingface_hub==1.18.0' 'transformers==5.11.0'

echo "=== verify ==="
.venv/bin/python -c "import huggingface_hub, transformers, mlx_qwen3_asr; print('hub', huggingface_hub.__version__, 'tf', transformers.__version__, 'asr', mlx_qwen3_asr.__version__)"

echo
echo "Done. Run with:"
echo "  .venv/bin/python scripts/lc_terminal.py --source mic --backend mlx-qwen3-asr --language zh --target-language en --mlx-llm-mt-model hy-mt2-1.8b-8bit --overlay --overlay-mode target --opencc s2twp --mem --simultaneous --no-second-pass"
echo
echo "Do NOT use 'uv run' — it re-syncs and reverts the hand-installed combo."
