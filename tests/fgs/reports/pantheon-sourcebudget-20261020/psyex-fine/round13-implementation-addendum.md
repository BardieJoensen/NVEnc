# R13 v2 implementation review addendum: reference-scale blocker

This corrects my review of `experiment.py` SHA `8bd546141797d4559a5d919b0a103b84dd1a7bb4184ab7cb10b5a33ad1bdcdd4`. The prior review remains preserved.

## Missed blocking defect

`u.load_luma()` already returns `float64` samples divided by 4 (`worker/decoder-r10-analysis/analyze_decoder_units.py:23-29`; its self-check maps stored value 512 to 128). R13 v2 then divides both loaded references again:

```python
original = refs['original'] / 4
coding_input = refs['coding_input'] / 4
```

at `experiment.py:87`. The predictor, raw inverse, baseline, q32, and q1 mosaics are each divided exactly once when assembled at lines 90-96. Therefore original and coding-input references are at one quarter of the mosaics' native display scale.

This is a decisive validity failure, not harmless metadata. It invalidates all coding-input pixel distances and all original-referenced full-ROI descriptors as a coherent comparison. HF amplitude/ratios, MSE, gradients, and signed pixel errors are directly wrong; scale-invariant components do not rescue the combined evidence. Raw-inverse distances remain on a consistent scale, but the experiment cannot be admitted with broken source/coding-input context.

## Required remedy and control

Use the loaded references directly:

```python
original = refs['original']
coding_input = refs['coding_input']
```

Before calculating or emitting any novel q1 metric, reconstruct the reused baseline and q32 full-ROI surfaces and require every original-referenced descriptor to match the corresponding admitted R12 full-ROI descriptor within `1e-12` (including the reference/coding-input/raw stages where schemas overlap). This is an outcome-independent scale, crop, ownership, and helper-parity control. Fail before q1 interpretation on any mismatch.

My earlier statement that the `/4` handling was consistent is withdrawn specifically for the already-loaded original and coding-input references. The per-TU mosaics, raw surface, invoked mask geometry, float64 difference arithmetic, and int64 coefficient arithmetic remain structurally sound after this correction. The other blockers in `round13-implementation-review.md` still apply.
