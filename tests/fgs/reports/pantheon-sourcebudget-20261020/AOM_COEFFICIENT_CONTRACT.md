# Round6: final-decision coefficient observation

Status: implementation preparation; no Round6 result yet.

Primary question: in the admitted libaom PSNR parent, how much of the observed
midpoint texture loss occurs in initial quantization, later coefficient
processing, or paths that never execute a transform?

Use unchanged original E05 fixture, all336 frames, installed parent pass1
statistics and pass2 settings. The target is input216/scored120, selected by
original whole-frame MD5 `94fa8bde346a2a52d40b26f8183afea5`, not by a wrapped
order hint. Export the entire visible luma plane, including every skip region.
No new source region or acceptance threshold is selected from output quality.

Worker owns a fresh private implementation under
`worker/aom-tu-r6/implementation-v1`; parent owns replay, admission, analysis,
report and Git index. Reviewer independently audits arithmetic, admission,
patch and results. No production changes, recursive delegation or changes to
earlier evidence are authorized. Private build/encodes use four threads,
nice10/CPU0–7; GPU work remains serialized.

## Admission

The same private binary with observation disabled and enabled must reproduce
the admitted installed IVF exactly. Reuse existing rate, decoder and full-window
GPU campaign evidence only after this identity is established. Record library,
complete source manifest, patch, configuration, commands, input, statistics,
trace and output identities. Pass2 replay time is instrumentation cost, not a
new end-to-end candidate benchmark.

`OUTPUT_ENABLED` excludes RD trials but is insufficient to identify the final
frame attempt. The existing recode counter saturates. Use an explicit
unsaturated generation around the actual main frame encode, keep exploratory
screen-tool encodes outside it, and admit only the generation named after final
successful packing. Unsupported superres or pipelined-filter paths must fail
closed for the target. Bind final packed bytes and parsed reference/display
history to the target; do not assume one IVF packet contains one coded frame.

For each exercised final luma transform, retain the source, exact predictor,
residual, forward coefficients, initial and final qcoeff/dqcoeff/EOB, transform,
scan domain and realized quantizer state. Capture initial values immediately
after `av1_xform_quant`, before trellis or dropout. Produce three independent
scratch inverses from the identical predictor using the codec's production
inverse: raw-forward, initial-dq and final-dq. Preserve packed reduced domains
for transforms containing a64 dimension.

Require exact final-dq equality to the actual per-TU reconstruction and exact
assembled visible-plane equality to an independently captured encoder pre-loop
plane. Bind encoder post-loop output separately to the ordinary decoder.
Decoder output cannot validate a pre-loop plane.

Whole coding-block skips and TU skip/skip-mode paths have no observed transform
coefficients. Preserve their predictor-only pixels and status, with absent
vectors. Do not invent an expected transform or read stale buffers. Require
exactly one visible-pixel owner across exercised transforms and explicit skip
spans, with no holes or overlap. Reject write errors, missing final receipts,
ambiguous attempt identity or traces exceeding250MB.

## Predeclared analysis

Report source, predictor, raw-forward, initial-dq, final-dq, actual pre-loop and
post-loop maps. Use the existing shirt, background and face ROIs and all858
source-defined midpoint control tiles from the frozen15-frame control set.
Report full-frame and group error distributions, HF amplitude with ACF and
source-HF correlation, edge error, quantizer state and skip/exercised coverage.
Retain all tile results, not only improvements.

In addition to whole-ROI mosaics, report HF on neighborhoods wholly inside
actually transformed pixels. Separate exercised-EOB-zero from no-transform
skips. Stratify raw-forward error by transform dimensions, including reduced
64-dimension support. Coefficient counts and magnitudes are proxies, never
coded-bit measurements.

Interpretation is conditional:

- Raw-forward restoration followed by initial-dq loss supports a scalar
  quantization loss under those selected decisions.
- Initial-dq restoration followed by final-dq loss supports a later coefficient
  processing loss under those selected decisions.
- Large no-transform coverage leaves quantization unobserved there and points
  to a separate skip/decision experiment.
- Raw-forward failure leaves prediction, partition, selected transform support
  and integer rounding as alternatives; it cannot establish a codec limit.

These assembled planes are local counterfactual mosaics. Later predictors and
reference frames still come from the real encode. They are neither coherent
alternative decodes nor repair candidates, and imply no rate feasibility or
playback quality. Any later real intervention must demonstrate what changed,
measure actual video packets and face every unchanged full-window gate.

## Corrections before implementation

The initial preflight called coding-block skips whole-SB skips, treated the
saturating recode count as an identity, and suggested a decoder pre-loop binding.
Parent required exact terminology, an explicit final generation and separate
pre-loop versus post-loop checks. Independent review required packed coefficient
domains and exact scratch inverse equality. These are validity corrections;
the repair criteria and original-rate ceiling are unchanged.
