# R11 analyzer final clearance

Analyzer SHA256 `5e7ffc9405788bfad1534b5d2dab676de76975459557b0141948777355aa2f1b` is cleared for the admitted R11 analysis.

Focused verification confirms all requested corrections:

- coefficient counts now say `nonzero_excluding_index0`, avoiding a false universal DC/AC interpretation;
- every invoked stage initializes explicit zero change and comparison counts, while the first scalar stage correctly has no prior quantized-stage comparison;
- aggregate gradient MAE uses each intersection's actual `gradient_support`; its semantics record gradient sample-pair weighting;
- the per-token boolean is now `final_encdec_quantizer_invoked`, limiting the execution claim to the observed final call;
- full-ROI descriptors are declared primary and pixel-weighted owner-intersection HF/ACF summaries are explicitly nonlinear/descriptive;
- analyzer identity is captured before work and rechecked before output; the exact R9 analysis (`b2d4a19a...`) and each inherited lower-level helper are checked both before and after computation.

The inherited helper keys (`analyze_py`, `texture_py`, `high_pass_py`) do not collide with the analyzer's `units` and `boundary` keys when merged into result provenance. The updated carry-forward/scaling smoke remains consistent with the code. No real trace values or outcome were inspected for this clearance.
