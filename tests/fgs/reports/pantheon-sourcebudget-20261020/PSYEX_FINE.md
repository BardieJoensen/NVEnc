# R13: near-fine precision approaches the raw reconstruction, not the original shirt

Native FP at internal qindex1 removes most of the q32-to-raw pixel discrepancy
on the same invoked TUs. The shirt still fails the existing joint amplitude and
spatial-structure screen. Stop the local scalar sweep; the next discriminator
replaces altered coding-input pixels with original samples at fixed decisions.

The [contract](ROUND13_FINE_CONTRACT.md), [compact evidence](psyex-fine-result.json),
[reproduction](psyex-fine/README.md), and
[independent review](psyex-fine/round13-outcome-review.md) bind this result.
It is a one-frame local diagnostic with no bitstream, new bitrate or encoder
runtime. Its subprocess took2.466528s. The actual R8 encode remains9.6279048Mbps
(99.49757%ofsource),370.335769s/336frames across both passes, and fails texture.
No source-budget repair or playback acceptance is demonstrated.

## Delivery and measurements

All2187 invoked TUs use native q1 rows: quant_fp7281, round_fp4 and dequant9,
for both DC and AC. Other table rows, matrices, predictors, partition, transforms
and native clipping stay fixed. All720 uninvoked owners retain their predictors.
Every new q/DQ/EOB/inverse operation agrees between directC and native runtime.
Baseline/q32 arrays are reused; their whole-ROI descriptors, original/coding input
and raw descriptors match R12 within1e-12 before q1 metrics are interpreted.

All pixel errors below use8bit units, from native10bit divided by4 exactly once.
Primary scalar-distance populations contain only identical invoked-owner pixels.

| ROI | Invoked pixels | q32→raw MSE | q1→raw MSE | q1 maximum error | q1 exact pixels |
|---|---:|---:|---:|---:|---:|
| Shirt |18752|.54609|.02063|.50|67.77%|
| Background |42744|1.25608|.02229|.75|65.93%|
| Face |157504|1.14373|.02769|.75|61.00%|

| Full ROI | q1 HF/source | q1 ACF1 error | q1 original MSE | Raw HF/source | Raw ACF1 error |
|---|---:|---:|---:|---:|---:|
| Shirt |62.79%|.08207|.51353|64.82%|.06621|
| Background |96.45%|.00823|.49816|96.86%|.00464|
| Face |93.69%|.02320|4.34722|93.69%|.02238|

The shirt coding input already retains only72.79%of original HF. q1 source-HF
correlation improves to.75678 from q32's.24932, but neither q1 nor raw meets
both existing shirt screens. Background amplitude is slightly less accurate
atq1 thanq32 while structure and MSE improve: finer precision and raw inverse
are not mathematical bounds for nonlinear texture metrics.

q1 is not lossless: DQ differs from raw at205275/233536positions, maximum98,
and EOB is shorter in618/2187TUs. Uninvoked owners contribute19.34%shirt,
83.50%background and98.17%face of q1's original-referenced squared error;
a scalar change cannot affect those pixels. This error decomposition is
separate from the nonlinear HF/ACF comparisons.

## Review and interpretation

Independent reconstruction verifies every offset, population, table substitution,
EOB, primary support mask, distance and full-ROI descriptor within1e-12. Parent
inspected native-size rounded-luma shirt/background panels only; no playback.
No quiet controls occur in this frame, and there is no full-window, temporal,
banding, tail, entropy-cost or repair result for these local counterfactuals.

Unexecuted worker drafts were rejected for wrong paths/table indexing, redundant
baseline native calls and missing distinguishing distances. A second draft
also divided already-scaled references again. Parent identified that decisive
reference error; the independent reviewer corrected its initial oversight in
an explicit addendum. The final parent-hardened driver requires old descriptor
parity, exact baseline arrays, gap-free offsets, complete support, consistent
units and cross-bound receipts. All corrections precede the sole completed run;
no failed or mismatched metric result is used.

The tested precision points establish q32 insufficiency and q1 proximity to the
fixed raw surface. They do not prove a general quantizer/codec limit. The
[R14 contract](ROUND14_SOURCE_CONTRACT.md) now isolates visible source samples
from the retained prediction/transform/skip state. A real encode and measured
packet cost remain necessary after diagnostic preservation, followed by the
original-rate cap and all quality/playback gates.
