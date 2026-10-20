# R12: fixed-decision scalar rule versus precision

Primary question: does the scalar quantization rule, or its actual precision,
explain the exercised-TU texture loss observed in R11? This is a local diagnostic,
not a new encode or a bitrate-feasibility test.

Use all 2,187 invoked final-EncDec TUs from the admitted R11 trace, including
final-zero outputs. Keep the other 720 owners unchanged as actual predictors.
Keep original raw coefficients, native predictor, partition, transform type/size,
scan, log scale, matrix/IQM and bit depth fixed. Retain the three predeclared ROIs
and full native transform domains, clipping only visible pixels for reporting.
No choice of coefficients, TUs or ROIs may depend on improvement.

## Fixed contrasts

1. Replay the native high-bit-depth scalar FP operation at every captured actual
   qindex using its captured tables. Require exact qcoeff, DQ, EOB and inverse
   samples for every invoked TU, plus exact raw inverse reproduction. This is
   an admission prerequisite, not an outcome.
2. Replace only FP with native high-bit-depth scalar B, using all the same
   captured seven table rows and QM/IQM. This tests the scalar rounding/dead-zone
   rule at unchanged quantization parameters; no later optimizer is included.
3. Replay native FP at internal qindex32, substituting only the native FP
   quant/round/dequant rows while retaining the captured QM/IQM and all decisions.
   Require q32 to be lower than each baseline actual qindex. This is a precision
   control; no assertion that q32 is sufficient or practical is allowed.

No other setting is swept. If the lower-precision-number point still misses the
raw diagnostic, a further near-fine-limit point requires an explicit recorded
next-round decision based on the result; failure at q32 is not an impossibility.

## Native implementation and admission

Parent may link a small scratch helper to the already built, hash-pinned R11
codec objects. Reusing objects is read-only and does not alter the prior source,
build, library or encoded output. Record all linked objects, actual compiler/link
argv, dependencies and before/after identities. The alternative is a fresh
private observer build if object reuse proves infeasible; do not rebuild R11.

The C high-bit-depth kernels are acceptable only after exact baseline equality
with the admitted runtime-dispatched kernels on every captured TU. Additionally,
dual-run C and initialized runtime facades/native inverse on every baseline,
same-q B and q32 FP input; require exact q/DQ/EOB and inverse equality for every
arm. Baseline FP agreement alone does not validate novel B/q32 inputs. Do not call
the similarly named low-bit-depth facade. Use the source's native quant tables
and native inverse kernels, including the adjusted 64-point coefficient layout,
original transform and bit depth. EOB zero returns the predictor.

The q32 FP rows follow the pinned native table initializer and native DC/AC
quantizer lookups. First require all three generated baseline FP table rows
to equal captured values at every actual qindex; DC offset must be proven,
not assumed. Sharpness-dependent B tables remain captured and unchanged.
Document ignored versus used arguments in the native C helper. Do not reconstruct
an undocumented approximate quantizer. Reject unexpected transform/lossless,
shape, dtype, count, missing-field or input-identity state. Do not use optimized
Python that disables admission assertions.

Require exact source/reference and baseline inverse identities before scoring
the local images. These inherit R11/R9's admitted frame/color handling. There is
no new encoded path and no new GPU/full-window quality result. Actual R8 bytes
retain their previously measured campaign results.

## Reporting and decisions

Report the realized table values and internal qindex, q/DQ/EOB and exact pixel
deltas, whole-ROI HF amplitude paired with ACF and source correlation, MSE and
edge error, plus all-TU/intersection support and descriptive tails. Distinguish
no-quantizer, quantized-zero and positive populations. Coefficient counts are
proxies, not entropy-bit costs. Nonlinear descriptor changes are not additive
causal fractions.

Same-q B is a bundled scalar-algorithm contrast: it uses captured zbin, round,
quant and quant-shift where FP uses round_fp and quant_fp. It is not a change
to a single rounding parameter. Keep original and R9 coding-input identities
separate, and limit attribution to invoked support.

A promising rule or precision point justifies a subsequent real scratch encode
with runtime delivery, packet bitrate, harness/GPU metrics, all frozen controls,
banding and temporal checks. It cannot qualify as a repair itself. Original-rate
cap, source-clean protection, five-frame gates and human playback are unchanged.
No production/library/config changes are authorized.

Parent owns `parent/psyex-scalar-r12`, integration and Git. Reviewer owns new
`reviewer/round12-*` evidence; worker owns only assigned `worker/psyex-r12-*`
files. No recursive delegation. Bound native linking/analysis to four CPUs,
preserve failures, and stop interpretation immediately if exact controls fail.
