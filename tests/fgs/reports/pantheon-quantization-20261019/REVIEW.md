# Independent method review and reconciliation

A separate read-only reviewer inspected the final-TU patch, parser and native
representability probes. No offset, quantizer-index, final-capture or inverse
reconstruction error was found. Whole-stream byte identity and stage checks were
confirmed as strong validation. Material limits were reconciled as follows:

1. The post-optimization capture is named `rdoq_*` in the raw format, but this
   name alone does not establish the executed quantizer path. `stages.py` now
   derives that path from the recorded initial EOB, actual RDOQ flag, transform
   area and gate thresholds. Every baseline transformed TU intersecting either
   diagnostic ROI has thresholds 255/255 and nonzero initial EOB, so neither
   density fallback nor fast optimization can execute; full `optimize_b` does.
   Other paths are explicitly labeled; a fast-path ambiguity stays unresolved.
2. Private scalar probes use the regular B quantizer, while actual RDOQ-enabled
   encoding starts with FP quantization. They hold predictor/input/partition and
   exercised transform fixed, **not quantizer algorithm or RDOQ policy**. They
   are diagnostics, not full-stream encodes or a complete RDOQ-off ablation.
3. Bypassed TUs never exercised their stored transform. Their private transforms
   are hypothetical. Parser results separately report quantizer-run-only
   neighborhoods and stratify unquantized error by actual/hypothetical paths.
4. Quantizer bypass and final zero-residual area are separate statistics. A TU
   may run quantization and still end with EOB zero. Neither is a bit count.
5. E05 budget1 combines absolute-q16 allocation with a **global** TX32 cap. Its
   regression cannot be uniquely attributed to allocation. E04 retains the
   baseline transform cap. There is no matched-rate TX32-only ablation.
6. Grain results support local, same-frame matched-code behavior on the fixed
   base. They do not establish whole-shot or universal AV1 unrepresentability.
   Endpoint occupancy confounds larger E05 probe scales; the principal native
   check uses scale16 and records occupancy. E04's prior-AR coefficients for this
   interval are zero, so its two named shapes are not independent tests.

The unchanged amplitude (10%) and ACF1 (0.05) screens were enforced. E04 QP8 fails
ACF despite passing amplitude; the prematurely started q32 budget branch was
canceled before completion when this result arrived. It supplies no quality or
matched-rate evidence. No acceptance criterion was relaxed.

The new FFV1 clip pixel-hash check caught a display-panel synchronization issue
in E04: source/decoded Matroska millisecond timestamps can differ at23.976fps.
Comparison assembly now sets a common rational time base and PTS from frame
index before stacking. Final clips must match all four source crops, every
frame. This affects visual assembly only, not sequence-indexed metrics or the
validated encoder reconstruction.

Final independent review: no remaining substantive correctness issue. The
reviewer confirmed the derived full-optimize path and agreement between the
report, reproduction guide, parser and measurements, including all four panels
× 240 exact 10-bit crop hashes for both corrected clips.
