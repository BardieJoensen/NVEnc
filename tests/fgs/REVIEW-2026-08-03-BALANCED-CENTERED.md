# Balanced-centred separator playback gate, 2026-08-03

## Status

**Superseded; do not use this package for the current decision.** The later
detail-aware finishing arm improved the labelled fixture, six-film base VMAF
and temporal drag. Its replacement playback gate is documented in
`REVIEW-2026-08-03-MOTION-FINISH.md`. This older set remains retained as an
audit artifact only.

Research remains undeployed. Production is still r4069 with the bilateral
separator, and `modelsrc` remains default-off.

The review set is at:

```text
/media/merged-storage/media/test-encodes/sourcefit-balanced-review-20260803/blind/
```

It compares production bilateral against the test-only balanced-centred
motion/source-fit arm on Scarface, Taxi Driver, The Deer Hunter and The
Shining. The mapping is sealed until observations are recorded. For every
title, A/B is held constant between the grain-disabled `base` pair and the
grain-enabled `finished` pair.

## Why this is the shipping gate

Balanced-centred motion is the best measured motion separator so far. Against
causal motion it removes directional lag and improves all mean base-fidelity
metrics; against ordinary centred motion it avoids the extra temporal
exposure that caused excessive smoothing. Its luma grain texture and pooled
amplitude remain close to source truth, and it saves 33.98% against the plain
corpus encode.

It nevertheless loses to production bilateral on all-six-title mean base
SSIMULACRA2 and Butteraugli. Objective full-reference metrics cannot decide
whether motion's remaining absolute error is visible ghosting or an acceptable
trade for moving real grain out of the encoded base. A high-disocclusion
playback comparison is therefore mandatory before any production proposal.

## Review method

Review `base` first. It removes the independent synthesis pattern and exposes
separator errors directly. Look during motion for trailing contours, texture
at an object's old position, doubled hair or facial detail, displaced hands or
rifle edges, and smearing as a detailed background is uncovered. Then review
`finished` to determine whether any defect survives normal grain-enabled
playback and whether grain scale, strength or temporal stability differs.

Record title, A/B, approximate time and the observed defect or preference.
Instantaneous synthesized grain positions are intentionally independent and
must not be treated as a mismatch.

The files are lossless 1920x1080 10-bit FFV1 centre crops derived from the
already validated six-film corpus; bytes are not part of this review.

## Strength work held behind perception

The remaining per-luma amplitude error is real but no safe correction has
cleared an external gate. A global correction is already ruled out. A quick
per-bin fractional closure reduced error but still missed a populated band by
about 13%, while a physically motivated absolute-sigma deadzone generalized
worse across titles. Earlier sparse pixel-aware response and Jacobian
normalizers also failed held-out gates.

Consequently the next strength experiment depends on the playback result. If
balanced motion has visible separator damage, quality work stays on the base
operator. If it passes, the next target is the population/curve estimator for
Interstellar, Taxi Driver and The Deer Hunter—not another global gain.
