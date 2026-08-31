# Simul-MT calibration heads: adding directions + fallback notice

## How to add calibration heads for a new (model, source, target) direction

The simultaneous-MT variant needs calibrated alignment heads per
(model, source, target) tuple — the (layer, head) indices whose
cross-attention locates committed source. Without them the variant
silently degrades to translate-on-close (see fallback notice below).

### The pipeline (two stages: detect → seed)

**Stage 1 — Detect heads (PyTorch/MPS, on the base model):**

Run `AlignAtt4LLM/detect_translation_heads.py` against the model. The
project's wrapper scripts (in `livecaption/scripts/`) patch it to use
lunaroute for the annotation LLM and add the Hunyuan prompt branch:

```
# annotation (aligns source↔target pairs; ~700 pairs, ~1h on MPS)
python livecaption/scripts/calibrate_hunyuan_heads.py \
  --src-path ../_corpus/zh.txt --tgt-path ../_corpus/en.txt \
  --direction zh-en --max-pairs 700 --step align --workers 1

# detection (loads the model on MPS, captures attention, scores heads)
bash livecaption/scripts/detect_heads_1.8b.sh full mps
#   → AlignAtt4LLM/data/alignatt_heads/translation_heads_<model>_<dir>.json
```

The JSON has a `token_alignment_heads` array with `{layer, head, ts, count}`
sorted by TS (alignment-stream score). A direction is promotable when ≥8
heads have TS > 0.1 and pass the stability splits
(`promotion_gate.eligible_for_promotion: true`).

**Stage 2 — Seed the registry:**

Transcribe the top-8 heads + their TS scores into
`whisperlivekit/simul_mt_capture.py`:

1. Add three module-level constants near the existing ones:
   - `<DIR>_ALIGNMENT_HEADS: List[Tuple[int,int]] = [(L,H), ...]`  (top 8)
   - `<DIR>_HEAD_TS_SCORES: Dict[Tuple[int,int], float] = {(L,H): ts, ...}`
   - `<DIR>_TOP_HEAD: Tuple[int,int] = (L,H)`  (the top entry)
2. Add an entry to `CALIBRATION_REGISTRY`:
   ```python
   ("hy-mt2-1.8b", "<src>", "<tgt>"): CalibrationEntry(
       heads=<DIR>_ALIGNMENT_HEADS,
       ts_scores=<DIR>_HEAD_TS_SCORES,
       top_head=<DIR>_TOP_HEAD,
       disabled_quants={"4bit"},  # only if probed and found divergent
   ),
   ```
3. The key's model id is the NORMALIZED id (org prefix and quant suffix
   stripped) — `hy-mt2-1.8b`, not `mlx-community/Hy-MT2-1.8B-8bit`.

### Existing calibrated directions (tencent/Hy-MT2-1.8B)

| direction | top head | TS | heads | disabled quants |
|---|---|---|---|---|
| zh→en | L9/H5 | 0.79 | 8 | 4bit |
| en→zh | L9/H5 | 0.86 | 8 | 4bit |
| ja→zh | L9/H5 | 0.89 | 8 | 4bit |

All three share the top head (L9/H5) — strong evidence these are general
alignment heads for the hunyuan_v1_dense architecture, not direction-specific.

### Quantization caveat

The 8bit heads are calibrated on the bf16 base model and transfer to the 8bit
MLX quant. The 4bit quant was probed (48.9% argmax match vs 8bit — attention
patterns diverge) and the promotion gate could not be run formally
(AlignAtt4LLM requires PyTorch/transformers, can't load MLX-format repos), so
4bit is in `disabled_quants` — it silently deactivates. A fresh calibration
on the 4bit weights (if the gate could be run) would be needed to enable 4bit.

## How a user gets informed about fallback mode

When the simultaneous variant is requested but no calibration exists for the
(model, source, target) tuple — or the requested quant is in
`disabled_quants` — `lookup_calibration()` returns `None`, and
`MlxLlmTranslationSimul.__init__` sets `_simul_active = False` and emits:

```
WARNING: MlxLlmTranslationSimul: no calibration for
(model=mlx-community/Hy-MT2-1.8B-8bit, src=en, tgt=zh) — deactivating
simultaneous mode (translation works via base; no provisional)
```

This is a Python `logging` WARNING on the `whisperlivekit.translation_mlx_llm_mt_simul`
logger, fired once at construction (per session). The variant then behaves as
the base `MlxLlmTranslation` (translate-on-close, no provisional, no capture) —
translation is correct, just not simultaneous.

### Current gap in the notice (for review)

The notice is a log line only. A user running the terminal/overlay may not see
stderr, so they may not realize they're on the fallback path. Two improvements
to consider (not in this port):

1. **Surface it in the display.** The terminal status line and the overlay
   could show a "simul: OFF (no calibration for en→zh)" marker when
   `_simul_active is False`, so the user sees the fallback state without
   watching logs.
2. **Promote to ERROR when explicitly requested.** If the user passed
   `--mlx-llm-mt-simultaneous` explicitly, a missing calibration is arguably a
   misconfiguration (they asked for simul and got fallback). A WARNING is
   right for the default-on case; an ERROR (or a clear startup banner) is
   right for the explicit-opt-in case.

### How to tell which path is active at runtime

`mt._simul_active` (bool) — `True` if calibration found and the simul path is
running; `False` if on the fallback (base-class translate-on-close).
`mt.wants_hypothesis_tail` mirrors it — `True` means the MT is receiving the
unstable ASR tail (simul path); `False` means it isn't (fallback).
