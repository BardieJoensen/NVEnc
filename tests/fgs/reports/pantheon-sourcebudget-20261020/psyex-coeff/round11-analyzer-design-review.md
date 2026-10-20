# R11 analyzer design review

Reviewed `parent/psyex-coeff-r11/analyze.py` SHA256 `fb0cee4b8b7dc4c9131013bb95919b9a4138f824069248e81cd4a4833a6f7743` before any R11 numerical result existed.

## Required corrections

1. `coeff_stats` labels every nonzero after array index zero as `ac_nonzero` (`analyze.py:36-39`). That is not a valid universal DC/AC distinction for the captured arbitrary transform types, especially ADST/IDTX. Rename it to `nonzero_excluding_index0`, or emit `ac_nonzero` only under a transform-specific definition and carry TX type into that decision. The same correction applies to raw, q, and DQ summaries.

2. `numerically_changed` omits an invoked stage when it changed zero arrays (`111-118`). This makes a missing key ambiguous between “never invoked” and “invoked but unchanged,” exactly the distinction R11 is intended to preserve. Initialize every invoked stage's change count to zero before conditionally incrementing it. Scalar's change relative to raw should remain undefined rather than fabricating a cross-domain comparison.

3. `gradient_mae` is normalized by horizontal-plus-vertical edge count (`43-47`), but ROI aggregates weight each per-intersection value by pixel count (`129-135`). For varying and clipped TU intersections, that is not the combined gradient MAE and its reported support is not gradient support. Aggregate this field with each descriptor's `gradient_support`, retaining the support count, or explicitly label it “pixel-area-weighted mean of per-intersection gradient MAEs.” Pixel weighting remains correct for per-intersection MSE.

4. Rename row field `skipped_quantization` (`106-108`) to `final_encdec_quantizer_invoked` or an equivalently explicit final-call label. The absence of R11 stages proves that this final EncDec invocation took the observed skip path. It does not prove that quantization never ran during search or that final syntax alone caused the absence.

The per-owner HF/ACF/correlation aggregates are nonlinear descriptive summaries. Keep their unweighted and pixel-area-weighted fields explicit and do not substitute them for the separately computed contiguous full-ROI descriptors. A short population-semantics field would make that distinction durable.

## Accepted methodology

- The analyzer reopens the admitted trace through the exact final validator, binds the exact R10 helper (`d10bfb16...`) and boundary descriptor helper, and requires the R11 token manifest and all admission identities. It uses the independently bound R9 original as the common reference and keeps coding input, predictor, preloop, and postloop distinct.
- Ten-bit samples are converted once to eight-bit-equivalent values. Full native arrays remain in admission; visible pixel diagnostics clip padded bottom TUs. Source/predictor/reconstruction joins are rechecked before measurement.
- Stage carry-forward is faithful: raw inverse only where the forward transform ran; scalar is the first actual scalar result; fast/requant and optimizer surfaces change only when those calls occurred; final is actual preloop after possible noise normalization. Skipped final EncDec calls explicitly retain their predictor.
- Fixed ROIs are fully covered by nonoverlapping visible TU mosaics. Full-ROI ACF/HF uses contiguous arrays, while TU intersections are also contiguous; there is no disconnected masked-array ACF artifact. Original, coding-input, stage, preloop, and postloop descriptors therefore answer different boundaries without silently changing the reference.
- Invocation counts and q/DQ/EOB coefficient summaries are observational. The scope correctly excludes coherent re-encoding, entropy cost, full-window safety, repair, and playback conclusions.

For final provenance, capture or assert the analyzer's own SHA before and after execution, not only when writing the result. This is a small reproducibility improvement rather than a metric-validity blocker.
