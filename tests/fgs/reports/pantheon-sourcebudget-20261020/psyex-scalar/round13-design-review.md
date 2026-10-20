# R13 independent design review

Reviewed contract SHA-256: `c6ce21643dde4213ade5cb666771dcf3259b6934c620d61d57e59aae0a9af619`.

## Disposition

Accepted for implementation with one measurement clarification below. I found no blocking methodological defect. The design is a valid single-point closure of the R12 fixed-decision scalar question: q1 and q32 use the same raw coefficients, predictor, partition, transform, scan, QM/IQM, inverse, clipping, and invoked-owner population, so their distances from the admitted raw inverse distinguish whether q32 left substantial avoidable scalar loss. Original-referenced descriptors remain context for texture relevance; they do not establish scalar convergence by themselves.

The q1 terminology is correct. In the pinned source, runtime qindex is clipped to a minimum of 1 specifically because index 0 is the unsupported lossless state (`rc_process.c:1558-1560`, `1600-1602`, and `1652-1654`). The reused native inverse explicitly rejects the lossless transform path (`native.c:91-103`). Thus q1 is the lowest nonzero table index in this implementation, but remains a nonlossless quantized diagnostic. The contract properly avoids “lossless,” “encoder limit,” and general codec claims.

## Necessary measurement clarification

Make the primary raw-distance comparison on the **same invoked-owner pixel support** globally and within each frozen ROI. Report full ROI mosaics, including the 720 unchanged owners, as the secondary end-surface description. Line 29 retains per-intersection support and line 33 requires identical support, so this is consistent with the contract; the implementation should make it explicit. Otherwise unchanged predictor-only owners could dilute q1-to-raw MAE/MSE and exact-equality fractions, especially in the face ROI.

For both supports report q1, q32, and baseline FP against the *same* raw surface: exact pixel count/fraction, changed count, maximum absolute error, MAE, and MSE. Coefficient comparisons apply only to the 2,187 invoked TUs and should include exact DQ equality to raw coefficients where meaningful, nonzero counts, EOB, and L1/maximum residual. Keep original/coding-input comparisons separate from raw distance.

## Interpretation constraints

No new numerical pass threshold is needed. “Approach” and “material floor” should be reported as continuous exact distances and q1-versus-q32 reductions, with exact equality called out if obtained. Creating a post-outcome cutoff would introduce criteria drift. The predetermined stop after q1 prevents a favorable-point sweep.

Possible outcomes have narrow meanings:

- If q1 becomes exact or nearly exact to the raw inverse while q32 does not, q32 was insufficiently fine for this fixed invoked support. This still says nothing about a legal encode, packet cost, later optimization, feedback, filters, or skipped owners.
- If a material q1-to-raw residual remains, report the native nonlossless FP floor under these tables and fixed decisions. Do not call it a codec or encoder floor.
- Original-referenced improvement can show relevance, but cannot make raw a bound. Nonlinear HF/ACF may be nonmonotonic, and R12 already showed upstream shirt loss before this scalar stage.

The unchanged acceptance gates and explicit exclusions for rate, quiet regions, full-window controls, temporal behavior, banding, playback, and repair are sound. A promising q1 surface would only motivate a separately admitted real mechanism; it would not qualify one.
