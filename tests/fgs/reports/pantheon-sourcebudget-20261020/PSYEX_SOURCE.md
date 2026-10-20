# R14: original samples recover texture, but retained decisions still fail

Replacing the altered coding input with untouched original samples raises shirt
HF amplitude from 62.79% to 86.50% of source at the same native qindex1.
ACF error falls from .08207 to .04132, passing the existing structure screen;
amplitude still misses the unchanged ±10% screen. The fixed-transform raw
inverse reaches 88.89%, also below the amplitude gate.

The [contract](ROUND14_SOURCE_CONTRACT.md),
[compact evidence](psyex-source-result.json), [reproduction](psyex-source/README.md)
and [independent outcome review](psyex-source/round14-outcome-review.md) bind
this one-frame local diagnostic. It produces no bitstream, bitrate, encoding
speed or repair claim. The diagnostic subprocess took 2.672505 seconds.

## Intervention and controls

Every one of the 2187 invoked R11 final transform units uses original visible
source samples, with predictor, partition, transform type/size, matrices,
nonlossless state and q1 scalar rows fixed. All 720 uninvoked owners retain
their actual predictors. Changes are not propagated into later predictors.
There are no padded input pixels in this population.

Before substitution, every captured-source native forward coefficient and raw
inverse equals R11, and every q1 result through the new helper equals R13.
Direct C and initialized runtime dispatch agree for every baseline and new
forward, quantization and inverse operation. The intervention changes
83721/242752 source pixels and 111666/233536 raw coefficients; it was realized.
Independent reconstruction verifies ownership, offsets, original identities,
scan-derived EOB and all original/coding-input descriptors and support errors.

| Full ROI | Captured-input q1 HF/source | Original-input q1 HF/source | Original-input q1 ACF error | Original-input raw HF/source |
|---|---:|---:|---:|---:|
| Shirt |62.79%|86.50%|.04132|88.89%|
| Background |96.45%|97.03%|.00727|97.43%|
| Face |93.69%|93.90%|.02205|93.90%|

Shirt original-referenced MSE falls from .51353 to .23243 in 8bit luma units.
On invoked support it falls from .44178 to .14196. The unchanged 6.24% of shirt
pixels retains MSE 1.59165 and contributes 42.73% of the new squared error.
One invoked 64×64 transform covers another 15.12% of the shirt. These are
specific support/geometry suspects, not a controlled attribution of the
remaining loss. Uninvoked geometry/type in the compact report is encoder
metadata; it does not imply that a transform was executed or signaled there.

The reviewer also calculated an explicitly non-codec oracle replacing
uninvoked owners with exact source. Its raw shirt HF reaches 91.44%, while q1
reaches 89.12%. This ancillary calculation is not a contract arm, legal
reconstruction, nonlinear bound, bitrate estimate or repair.

## Interpretation and next experiment

High confidence within this fixed R11 state: changed input samples account for
a substantial part of shirt loss, and original samples plus very fine scalar
precision are still insufficient while all other decisions remain fixed.
This does not identify a single public TF setting as the isolated cause;
changing that policy can also change references, search, support and feedback.

The reviewer initially preferred source-off search at the old budget with
candidate RD-margin instrumentation. The parent chooses one real source-off,
near-fine public-QP arm first: it directly tests whether legal changing
decisions can preserve texture at all and measures the actual rate/runtime
cost. It uses existing reviewed encoder and observation paths, avoiding a new
candidate-search instrumentation layer before practical information exists.
This is a bundled feasibility test, with no isolated TF or precision claim.
Actual target-block quantization must be observed; requested bounds alone
cannot establish delivery. If preservation succeeds, original-budget
feasibility remains the next required test. Overshoot is diagnostic only.

Parent inspected the native-size rounded-luma shirt panel. No motion playback,
quiet-region, full-window, tail, banding or temporal acceptance follows from
R14. The original-rate ceiling and all quality gates remain unchanged.
