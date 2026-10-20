# R11: committed scalar quantization localizes the loss

The admitted final-EncDec trace identifies initial scalar FP quantization as the
decisive coefficient-stage loss on the exercised E05 frame120 transforms in the
frozen R8 policy. Later optimization changes no shirt coefficients or pixels;
noise normalization changes nothing in any captured unit. This is a high-confidence
local finding, not evidence that quantization alone explains all final perceptual
loss, or that lower quantization will fit the original bitrate.

The [contract](ROUND11_COEFFICIENT_CONTRACT.md), [compact machine result](psyex-coeff-result.json),
[reproduction](psyex-coeff/README.md), and [independent outcome review](psyex-coeff/round11-outcome-review.md)
bind the evidence. All 336 off/on encoded and reconstructed frames equal admitted
R8 bytes. Its measured scored rate remains **9.6279048 Mbps**, 99.49757% of the
9.6765224 Mbps original; both original encoding passes took **370.335769 s**.
The two observer replays execute only pass two and take 309.933/309.852 s;
these are diagnostic runtimes, not new practical speed results.

## Decisive observations

All 2,907 accepted tokens join their subsequent committed owners. There are 2,187
actual scalar-FP calls and 2,151 final positive-EOB units, including all 24 frozen
shirt positives. The full optimizer runs on all 2,151 positive units but changes
only six: none in shirt, one in background, five in face. It changes 0, 32 and
316 pixels respectively inside the fixed ROIs. Noise normalization and the
subsequent final capture change no coefficients or pixels.

| Fixed ROI | Original HF | Coding-input HF | Raw native-inverse HF | Scalar FP HF | Final preloop HF | Postloop HF |
|---|---:|---:|---:|---:|---:|---:|
| Shirt | .60632 | .44132 | .39301 | .09367 | .09367 | .05454 |
| Background | 1.67639 | 1.66549 | 1.62379 | 1.28049 | 1.28050 | .84776 |
| Face | 2.70085 | 2.69118 | 2.53031 | 2.45413 | 2.45411 | 2.15040 |

Texture structure changes too. Shirt source-HF correlation falls from .77270 at
raw inverse to .00818 at scalar; ACF1 error grows .06621→.19652. Background
correlation falls .96899→.53894 and ACF1 error grows .00464→.14186. Face
correlation falls .92130→.78707 and ACF1 error grows .02238→.06154. These are
whole-ROI nonlinear descriptors, not additive causal fractions. Full MSE, gradient
error, per-unit/intersection support, aggregates and tails remain in the bound
54 MB detailed result.

Actual forward qindex is 71 on shirt, 79–87 on background, and 71–115 on face.
The effective matrix is level11 for two-dimensional transforms, flat15 for
one-dimensional transforms. Requested and realized qindex agree for every
captured invocation. This does not equate those quantizers with original H264 QP.

Branch coverage constrains attribution:

| ROI | Quantized positive pixels | Quantized zero-EOB pixels | No final quantizer pixels |
|---|---:|---:|---:|
| Shirt, 20,000 pixels | 18,368 | 384 | 1,248 |
| Background, 45,000 pixels | 42,680 | 64 | 2,256 |
| Face, 240,000 pixels | 152,640 | 4,864 | 82,496 |

For example, shirt unit6203/token877 has 996 nonzero raw coefficients. Scalar FP
retains six; all later stages are identical. Those counts describe coefficients,
not coded bits or a percentage of perceptual texture lost. The face's 34.37%
no-quantizer support remains a separate decision problem.

## Validation and corrections

The route guard runs before every target SB dispatch and proves effective M4,
10-bit, picture/MD bypass disabled, complete 510-SB coverage. Each token binds
the raw coefficient producer, quantizer inputs, actual branch stages, native
reconstruction and later committed block copy. Source/predictor/preloop pixels
equal R9/R10; final DQ/EOB/qindex/IQM equal the independent decoder.

The first validator failed because SVT and libaom store identical coefficients
in row-major and column-major order. Independent source/scan analysis proved
the exact transpose on all 2,151 positive units and all 13 exercised scan
families. The same normalization matches 2,130 nonempty IQMs. The 21 remaining
one-dimensional units use flat matrices despite the frame-level level11 metadata.
The corrected validator retains exact equality without a numeric tolerance.
The failed validator, log and receipt are preserved.

Other corrections were resolved before admission: a compiler-rejected child
picture member access; replay driver identities/command receipts; rejected worker
analyzers that assumed nonexistent schemas and confused coding input with the
original reference. Parent replaced the analyzer with an original-referenced,
support-aware implementation and obtained independent review. Seven deliberately
malformed trace variants are rejected; this is targeted validation, not an
exhaustive parser proof.

## Scope and next experiment

Raw/scalar inverses hold actual local predictor, partition, transform and matrix
fixed. They do not propagate changed reconstructions through intra neighbors or
later reference frames, and they are not legal complete encodes. Skipped calls
retain their real predictors. Raw inverse also retains reduced 64-point transform
support; it is not assumed to reproduce source perfectly.

The shirt already loses material texture before EncDec. Postloop further changes
all regions and improves some pixel/ACF errors. No quiet control tiles occur in
the frozen frame120 population. Exact R8 bytes reuse its complete GPU metrics,
whole-window controls and temporal evidence; no new full-window quality claim is
made from this trace. Parent inspected native-size rounded-luma stills and a
descriptor plot, **not motion/player/display playback**. No candidate qualifies.

Auto decision: compare native scalar B with FP at the same captured quantizer,
then use an explicitly lower actual FP quantizer as the precision control, keeping
predictor, partition, transform and matrix fixed. First require exact native FP
replay of every invoked TU, including q/DQ/EOB and reconstructed samples. This
distinguishes scalar rounding/dead-zone policy from precision before paying for
a real encode. Any subsequent real policy must demonstrate delivery, actual
packet cost and full-window protection; the original-rate cap is unchanged.
