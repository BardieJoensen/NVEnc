# R12 scalar-counterfactual design review

## Disposition

The experiment is scientifically useful and bounded, subject to one necessary
implementation admission correction: counterfactual C-kernel outputs must be
checked against the runtime-dispatched implementation for **each** tested arm,
not merely for the observed-q FP baseline.

Reviewed contract SHA-256:
`f3eea35131ba4d5da156feafb87ba8aee3426b39af78dce3e8946895a753a0ca`.
Reviewed route report SHA-256:
`4208666e17611fee383c0ffdeba89ef93d8bfbee6758b771e1fab703064461c7`.

## Why the contrasts answer the stated question

Exact native FP replay on all 2,187 captured final-EncDec invocations is the
right admission control. Same-q B then changes the bundled scalar rule while
holding raw coefficients, actual qindex, dequant row, predictor, partition,
transform, scan/log scale, and fixed QM/IQM constant. It is not a one-parameter
rounding experiment: B uses `zbin`, `round`, `quant`, and `quant_shift`, whereas
FP uses `round_fp` and `quant_fp`. The report should continue to call this a
bundled FP-versus-B scalar-algorithm contrast.

The q32 FP arm is a distinct precision control. Keeping captured QM/IQM is
deliberate fixed-QM isolation, not the QM that a real q32 encode would
necessarily select. Failure at this point rejects this fixed-decision q32
counterfactual only; success merely selects a later real encode.

The source supports the inputs: the high-bit-depth FP and B facades dispatch at
`full_loop.c:590-625` and `201-239`; the actual 10-bit encode branches use them
at `1727-1756`. The table initializer derives luma DC/AC, FP, B, shift, and
dequant rows at `md_config_process.c:132-167`. Adjusted 64-point layout is chosen
at `full_loop.c:1345-1352`, while `av1_get_max_eob(txsize)` fixes the coefficient
population.

## Required smallest correction: dispatch equivalence

Contract lines 40-44 currently permit direct C kernels after exact FP-baseline
agreement. That does not prove:

1. C B equals the runtime-dispatched B kernel on the B counterfactual inputs, or
2. C FP/inverse equals dispatch on the new q32 coefficient ranges.

Separate SSE4.1/AVX2 high-bit-depth implementations exist, and FP agreement at
the observed qindices cannot cover algorithm-specific B branches or new q32
values. The smallest sound implementation is a helper inside the pinned codec
context that calls the same high-bit-depth facades and native inverse wrapper as
the encoder. If direct C calls are retained, execute C and initialized runtime
dispatch on private buffers for every FP-baseline, B, and q32 TU and require
exact qcoeff/DQ/EOB/inverse equality before analysis. Record CPU/RTCD state. A
baseline-only C check is insufficient.

## Other admission and interpretation constraints

- Generate q32 FP rows through the pinned initializer/lookup functions. Bind the
  actual luma DC delta directly (or prove it by exact generated-versus-captured
  rows at every observed qindex) before using the q32 DC row. FP uses only its
  appropriate rows; B uses its separate captured zbin/round/quant/shift rows.
- Zero all full adjusted coefficient and pixel scratch domains before every
  call, retain native scan/iscan and original transform size/type, and require
  exact EOB-zero predictor copying. The baseline raw and FP inverse controls
  must cover reduced 64-point shapes and visible-edge clipping.
- Bind the original fixture and R9 coding input separately. Report errors and
  descriptors against the original, while retaining coding-input context so
  inherited upstream shirt loss is not assigned to quantization.
- Whole-ROI mosaics may leave the 720 no-quantizer owners at their admitted
  predictors. Conclusions about FP/B/q32 apply only to the 2,187 invoked TUs;
  the unchanged no-quantizer and quantized-zero populations must remain visible
  in support counts. Do not extrapolate to absent residuals.
- Read-only LTO/PIC object reuse is methodologically acceptable if every linked
  object/dependency and before/after identity is recorded. If private linkage
  cannot preserve initialized RTCD/table/inverse behavior, use a fresh scratch
  helper build and fail closed rather than approximating the codec path.

With the dispatch correction, the existing exact-baseline, all-population,
fixed-selection, and no-rate/no-repair controls are adequate. No broader sweep,
new metric gate, or encode is needed before this diagnostic.
