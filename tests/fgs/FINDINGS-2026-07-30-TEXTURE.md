# Real-film grain-texture detector, 2026-07-30

## Result

The missing texture axis now has a measurement harness and a labelled-negative
gate. It is deliberately separate from grain energy and clean-base fidelity:

| question | measurement |
|---|---|
| Was grain destroyed or overdone? | retention/energy monitor |
| Does synthesized grain have the right scale and behavior? | this texture report |
| Was real detail replaced by synthesized texture? | base-fidelity canary |

The texture report normalizes every block spectrum and autocorrelation before
aggregation, calculates every descriptor inside source-luma bands, and only
then forms an occupancy-weighted title summary. Median sigma is retained as a
labelled diagnostic but is not part of any texture distance.

Commits:

- `54483513`: independent flat selection, luma-banded descriptors, versioned
  JSON report, and CPU controls.
- `02768607`: real-film NVEnc/libaom synthesis and labelled-negative media
  harness.
- `84f0d02e`: byte-identical grain-off base requirement for controlled pairs.

## Flat-patch rule

The evaluator does not call the production analyzer's block classifier. The
mask is frozen from the reference source and its identically denoised clean
guide:

1. Divide the clean guide into 32x32 blocks.
2. Fit and remove a plane.
3. Rank by residual sigma multiplied by `1 + gradient coherence`.
4. Require at least 0.5 8-bit units of source-minus-clean residual sigma.
5. Evaluate both the lowest 25% (`core`) and lowest 60% (`expanded`) of
   eligible blocks.

Candidates never influence the mask. Bands with fewer than 32 blocks are
reported as `N/A`, and title summaries state the covered source-luma occupancy.
This keeps the evaluator independent while exposing sensitivity to its flatness
rule.

## Reproducibility

The real-film control used:

- r4050 NVEncC SHA-256
  `5a8e198a4ab5da3167278d340de038ae5a5606de5be49eb7f6bcc26a4d570edd`
- r4047 NVEncC SHA-256
  `28c1cae74f5e9002ce0d0d54240398df59098ea6f3f8e7f7f75ae61806145338`
- libaom `noise_model` SHA-256
  `706030adcfc7eac6036ff5d3290f5d032bc736d5556e68730f7c8fb1b9b21159`
- 24 aligned 3840x2160 10-bit frames per clip
- bilateral separator

Copyrighted clips and multi-gigabyte raw intermediates remain outside the
repository.

## r4050 versus the real-film oracle

The amplitude guard first reproduces the luma-occupancy correction:

| clip | weighted curve ratio | unweighted | AR cosine |
|---|---:|---:|---:|
| Taxi Driver, coarse 35mm | 0.9885 | 0.8139 | 0.99953 |
| Silo, fine digital | 1.0559 | 1.0471 | 0.99254 |

Both synthesized arms were applied to the same clean input. Their grain-off
decodes were byte-identical.

Amplitude-independent texture distance to the source residual:

| clip / arm | mask | luma coverage | spectrum TV | ACF RMSE |
|---|---|---:|---:|---:|
| Taxi / NVEnc | core | 1.000 | 0.0550 | 0.0376 |
| Taxi / NVEnc | expanded | 1.000 | 0.0605 | 0.0413 |
| Taxi / libaom | core | 1.000 | 0.0572 | 0.0349 |
| Taxi / libaom | expanded | 1.000 | 0.0620 | 0.0387 |
| Silo / NVEnc | core | 0.843 | 0.0491 | 0.0204 |
| Silo / NVEnc | expanded | 0.937 | 0.0242 | 0.0150 |
| Silo / libaom | core | 0.843 | 0.0341 | 0.0142 |
| Silo / libaom | expanded | 0.937 | 0.0151 | 0.0161 |

NVEnc versus libaom on the same base:

| clip | mask | spectrum TV | ACF RMSE |
|---|---|---:|---:|
| Taxi | core | 0.0173 | 0.0050 |
| Taxi | expanded | 0.0173 | 0.0050 |
| Silo | core | 0.0151 | 0.0126 |
| Silo | expanded | 0.0144 | 0.0125 |

Taxi's two analyzers are much closer to one another than either is to the
source residual. That makes a compact-model ceiling plausible, but it does not
prove one: a separately optimized best-fit AV1 model is required to establish
the format's expressiveness limit. Silo leaves mild model-fitting headroom,
but not enough evidence for an encoder change before broader baselines.

## Labelled negative: r4047 widening

The r4047 widened and r4050 corrected analyzers were run on the same Taxi
source. Both tables were then applied with r4050 to the exact same r4050 clean
input. The grain-off SHA-256 for both arms was:

`a42cf51dd60ffa15007db4a3c018418c8bc5a72b6730e51eac2900672f64d07c`

The detector separated the texture change on both masks:

| mask | luma coverage | r4047/r4050 spectrum TV | ACF RMSE |
|---|---:|---:|---:|
| core | 1.000 | 0.0616 | 0.0262 |
| expanded | 1.000 | 0.0617 | 0.0262 |

All five populated luma bands independently showed the effect:

- spectrum TV: 0.0602 to 0.0621
- lag-one correlation increase: 0.0340 to 0.0351

The conservative sensitivity floor is 0.01 for spectrum TV or ACF RMSE, with
at least 50% luma occupancy covered, on both masks. These are detector
sensitivity bounds, not production quality thresholds.

r4047 is not required to rank farther from the source on every texture
descriptor. In fact its widened texture is closer on some ACF summaries while
its base fidelity is known to regress. This is expected and reinforces the
three-axis design: the labelled negative proves the texture detector can see
the constructed change; the base-fidelity canary determines that the change
was achieved by replacing real detail.

## Release posture

No absolute real-film texture threshold is set yet. The current gate only
requires a known change to be detectable. Tightening should wait for
scene-by-scene baselines from corrected Taxi Driver, Casino, The Shining, and
Silo. Temporal local-energy spread is recorded now but should remain
informational until those baselines establish its natural film variability.
