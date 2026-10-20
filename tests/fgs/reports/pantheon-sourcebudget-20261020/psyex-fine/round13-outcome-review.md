# Independent R13 outcome review

## Disposition and verification

R13 is an admitted, correctly scoped negative closure of the fixed-decision scalar-precision question. Native FP at qindex 1 approaches the unquantized local inverse closely on the exercised support, showing that q32 was materially insufficient there. It does **not** make the fixed decisions preserve the shirt, establish a lossless bound, or demonstrate a usable encode.

I independently reconstructed the mosaics from the admitted R11 trace, R12 baseline/q32 arrays, and R13 q1 arrays. I verified gap-free token/array offsets, all 2,187 invoked and 720 uninvoked owners, 233,536 coefficient values, 242,752 invoked pixels, every q1 table substitution, scan-derived EOB, primary support masks, pixel distances, and fixed-ROI descriptors. All reproduced the reported values within `1e-12`. Both receipts are complete with unchanged before/after inputs; the execution log is empty.

Review derivation:

- `reviewer/round13-outcome/derive.py` SHA-256 `e5c350baf8ae34f5216096f8db6360d01dbcd9607973a9f0ec1976b6d09ca08a`
- `reviewer/round13-outcome/derived.json` SHA-256 `b213c615a4d05606f491f3470798db43ba77c5b01831c93dbd0599a6e20f9de1`
- Reviewed result SHA-256 `4511e7223f5c9b8b721e5d2f8c5d01d062ffb5d981bd106ae85ff59e0e1dbb93`; q1 arrays SHA-256 `11927240f6279d39f491885ab5b50ccd1b89da57ff59830b7265c8372719af09`.

## Observations

The realized q1 rows were `[7281]×8`, `[4]×8`, and `[9]×8`; every other table row matched the captured baseline TU. All 2,187 invoked TUs retained positive EOB. EOB equaled raw in 1,569 and was shorter in 618. The baseline actual qindices were 71–115, so this is a large counterfactual precision change at fixed decisions.

On identical invoked support, q1 is much nearer raw than q32:

| ROI | Invoked pixels | q32→raw MSE | q1→raw MSE | q1/q32 | q1 exact pixels | q1 max error |
|---|---:|---:|---:|---:|---:|---:|
| Shirt | 18,752 | 0.54609 | 0.02063 | 3.78% | 67.77% | 0.50 |
| Background | 42,744 | 1.25608 | 0.02229 | 1.77% | 65.93% | 0.75 |
| Face | 157,504 | 1.14373 | 0.02769 | 2.42% | 61.00% | 0.75 |

Globally, q1→raw MSE is `0.02543` versus q32's `1.06822`; 63.18% of q1 inverse pixels equal raw. This proximity does not mean coefficient identity: q1 DQ differs from raw at 205,275/233,536 positions (87.90%), with maximum absolute coefficient difference 98. That and the 618 shorter EOBs establish that q1 remains a quantized, nonlossless point.

Original-referenced full-ROI results show the practical limit of this local improvement:

| ROI/stage | HF/source | ACF1 error | MSE |
|---|---:|---:|---:|
| Shirt q32 | 41.39% | 0.39301 | 1.13211 |
| Shirt q1 | 62.79% | 0.08207 | 0.51353 |
| Shirt raw inverse | 64.82% | 0.06621 | 0.49534 |
| Shirt coding input | 72.79% | 0.03534 | 0.31279 |
| Background q1 / raw | 96.45% / 96.86% | 0.00823 / 0.00464 | 0.49816 / 0.47822 |
| Face q1 / raw | 93.69% / 93.69% | 0.02320 / 0.02238 | 4.34722 / 4.32936 |

Thus q1 greatly improves shirt structure relative to q32, but both q1 and raw still miss the unchanged shirt HF and ACF screens. Even the observed coding input contains only 72.79% of source shirt HF. Background HF is mildly nonmonotonic: q1 is slightly farther from source than q32 (`0.05951` versus `0.05427` absolute error), despite much lower pixel error and much better ACF. This is direct evidence that raw and finer scalar precision are not mathematical bounds for the nonlinear texture descriptors.

Support matters. Invoked owners cover 93.76% of shirt, 94.99% of background, and 65.63% of face pixels. Yet unchanged/uninvoked owners account for 19.34%, 83.50%, and 98.17%, respectively, of q1's original-referenced squared error in those ROIs. A finer scalar cannot change those pixels.

## Interpretation and limits

The supported inference is narrow: q32 left a large scalar approximation error on the already invoked TUs, while q1 removes most of that q32→raw inverse distance. At the lowest nonzero index, the remaining scalar pixel error is small but measurable. The shirt failure after this reduction localizes the remaining problem upstream of, or outside, scalar precision on fixed invoked support: processed coding samples, predictor/transform/partition choices, and uninvoked owners all remain.

This result does not test qindex 0's distinct lossless path, entropy cost, changed search decisions, prediction feedback, postfiltering, a valid bitstream, source-budget feasibility, temporal/quiet/full-window behavior, or playback. The q1 mosaics are noncoherent local counterfactuals. Existing R8 rate and campaign evidence cannot be transferred to them.

## Smallest next discriminator

The cheapest targeted discriminator is one fixed-decision **source-sample substitution** before another real encode: on the same invoked TUs, apply the native forward transform to `original source − captured predictor`, then native FP q1 and inverse with the same partition, TX, QM, clipping, and owner map; leave the 720 uninvoked owners unchanged. First require the same forward path fed with `coding input − predictor` to reproduce every captured raw coefficient and raw inverse exactly. Report invoked support separately from the full ROI.

If the original-sample replay restores shirt amplitude and ACF locally, it justifies one real preprocessing-off policy arm under the original packet ceiling. If it does not, or if only unchanged owners prevent recovery, the next policy should target prediction/partition/residual-support decisions rather than scalar precision. This diagnostic still would not estimate rate or feedback, but it directly resolves whether the already observed source preprocessing loss can pass through the selected geometry before paying for another full encode.

