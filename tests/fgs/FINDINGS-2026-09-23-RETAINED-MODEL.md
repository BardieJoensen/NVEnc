# Complete retained-model construction

The native luma and chroma constructors now fit the grain missing from the
**actual rounded candidate base**. Native luma uses a checked algebraic
embedding in the bounded minimax solver; colour uses the exact quantized luma
template and its finite driver power. Both reject invalid source/base evidence,
non-PSD targets, unrepresentable coefficients and unsafe causal/spectral shapes.
They do not grant population, synthesis or output-selection clearance.

The finite luma evidence is immutable and carries its exact parameters. A new
integer-strength helper takes at most ten explicit measurement callbacks.
It supports native and averaged luma together and checks sampled monotonicity;
it does not assume weak-grain variance scales quadratically after rounding.
Selection still needs independent actual source reconstruction and all R1 checks.

Independent NumPy solves match 1,992 quantized coefficients across eight native
luma fits and 72 colour fits. Eight invalid targets remain rejected. Analytic
controls cover quantization, scaling, exact model binding, bounded calibration
and failure cases. Full CPU: 214 Python tests in 30 suites and 34 C++ programs.
The new native AOM synthesis oracle matches dav1d on 393,216 decoded samples
across the 8-bit and 10-bit controls.

## What the complete pictures show

Eight source-supported development frames expose limits that successful patch
fits did not resolve. Shared AR shift seven cannot represent the fitted Cb
driver; legal shared shift six fixes that parameter-construction failure.
Native luma refitting and measured strength calibration improve the specific
native-Y check to 377 of 384 held-out seed/frame comparisons. The seven failures
remain failures, and this check alone does not qualify averaged Y or colour.

The full colour search on the two native-Y-pass frames evaluates all five
declared fractions per component. Eighteen candidates reach actual synthesis;
two have invalid missing targets. None passes every held-out seed's complete
source covariance. Averaged-luma energy, finite colour-template variation and
direct Cb/Cr correlation remain material. No threshold or source classification
was relaxed, and no failed candidate entered encoder output.

The local D28 report is
`roadmap-r3-complete-model-20260923/report.json` in the current evidence root.
All disposable synthesized raw pictures have byte/hash receipts; compact
measurements, failed controls and native source/base inputs remain available.

## Continuing work

D29 constructs separate known-clean positive and negative controls for the
complete selector. These distinguish construction/representation limits from
the bilateral base, and include colour coupling, quiet content and persistent
detail. They are synthetic development controls, not real-media qualification.
The original low-retention inputs remain evidence; a separate fixed maximum-Y
proposal exercises the existing host API without changing its automatic policy.

R3 output integration and R4–R8 remain open. The encoder build is still
`04bd03aa` for diagnostics. Production stays ordinary `cb903a17`, retention and
FEL off. This CPU work owns no Tdarr pause and schedules no experiment.
