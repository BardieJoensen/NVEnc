# Companion diagnostic: legal grain on the improved SVT base

This probe establishes a local limitation of the measured white-grain response
on the new preset0 E05-1440 base. It is not a repair, estimator fit, exhaustive
legal-model search or proof of codec-wide unrepresentability.

The frozen held-out tile population yields three same-frame quiet/texture pairs
under the unchanged mean/histogram/texture-loss selection. All are preserved.
The highest-overlap pair is scored frame24, quiet(1688,776) and
texture(1784,968), each32×32. Exact10-bit luma histogram overlap is0.7490.
Within this pair, raw code192 (48.0 on the8-bit scale) maximizes the smaller
matched constant3×3 neighborhood population:64 quiet pixels and37 texture
pixels. Selection uses input equivalence and counts, not source amplitude.
Two-pixel synthesis overlap bands are excluded using global32-pixel coordinates.
No new minimum-count acceptance threshold is introduced; variance requires at
least two observations. These are conditioned subsets, not full-tile metrics.

| Conditioned population | Source HF | Source±10% interval | White16 ensemble HF mean | Observed range |
|---|---:|---:|---:|---:|
| Quiet |0.090807|0.081726–0.099887|0.356271|0.274156–0.466215|
| Texture |0.244292|0.219863–0.268721|0.348202|0.278396–0.431582|

The32 fixed seeds produce similar average amplitudes despite different source
requirements. None satisfies either interval at this scale; no seed satisfies
both. Texture/quiet output amplitude ratios range0.7673–1.5361. All matched
endpoint occupancies are zero, so clipping does not explain the observed gap.
Whole-tile output ACF1 averages−0.39194/−0.38673, versus source−0.01455/−0.17886;
white16 therefore does not reproduce spatial structure either. Conditional HF
and whole-tile ACF refer to different populations and are not a joint ROI gate.

The preserved native dav1d tool applies one legal model: scaling_shift10,
constant luma points(0,16)/(255,16), ARlag0/zero coefficients, ar_shift7,
grain_scale_shift0, no chroma scaling, overlap1 and restricted-range clipping1.
Its decoded base matches the validated preset0 application reconstruction on
all planes for all32 repeated outputs. The tool reports32 nonmutation checks.
Input10-bit depth is asserted by native code; scaling_shift10 is a separate
model parameter. No encoded signaling or bit cost is claimed for this offline
synthesis diagnostic.

The result supports a local same-input conflict for this base: a luma scaling
curve receives the same code in regions with different source requirements.
It does not prove that every finite seed, AR shape, scale, alternate base or
spatial/temporal strategy fails. The matched populations are small and no
motion/authenticity conclusion follows. The earlier E05-1460 finding is not
transferred by assumption; this is a distinct measured E05-1440 probe.

[Machine evidence](grain-fixed-result.json) includes every selected pair,
common-code count, seed result, identity and provenance. The scratch evidence
retains `crops-and-masks.npz`, legal model, command/log receipts and
`seed-amplitudes.png`. Two reproducible32-frame raw outputs were hashed and
removed after successful checks; their cropped samples remain. No previous
archive was modified. Reproduce in a fresh root with `grain_fixed_input.py`
followed by `grain_fixed_summary.py`, using `nice -n10 taskset -c 8-11` and the
analysis environment. Initial malformed affinity syntax was rejected before
Python ran; the failure log is preserved and reproduction syntax corrected.
