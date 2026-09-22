# R3: native blending, grain-scale units and exact brightness lookup

The playback-free trials have completed. R3 still needs complete model and
population evidence plus encoder output integration; these results qualify
specific prerequisites, not automatic retention for production.

## Native GPU blend

The 31 prepared cases pass the independent native CPU comparison: **141,191,039
valid samples match exactly**, including separate Y/Cb/Cr fractions, full-source
and denoised-base endpoints, planar and semiplanar storage, 8/10-bit data,
padding and unchanged input buffers. The deliberately invalid native sample is
reported, and all **434 invalid-call controls** reject. This verifies the
out-of-place blend from `64a6753b`; it does not assess compression or synthesis.

The owned pause lasted about two seconds and was released. The later four
ordinary-mode encodes also released their pause. The node was unpaused with
all four worker limits already zero before these tests; those settings were
preserved. Emby's watchdog retains independent pause ownership. No experiment
is scheduled to start automatically.

Evidence: `roadmap-r3-selector-20260922/blend-comparison-v1.json`,
`r3-blend-v1-execution.json` and `r3-blend-v1-pause.json` in the existing local
colour-recovery evidence root.

## Consistent grain-scale units

Commit `5826421d` corrects the experimental nonzero-scale path:

- Smooth strength prediction and local refitting now include the innovation
  shift, as do the nominal DC proxy and same-shift model-hold tolerance.
- A finite template's gain is explicitly its native RMS divided by nominal
  innovation sigma, `32 * 2^(bitDepth - 8 - grainScaleShift)`. The template helper
  exposes the actual rounded Gaussian second moment and gains converted to
  this convention. It also records depth and scale.
- The ordinary coarse stationary-gain refit explicitly refuses nonzero scale.
  Future recovery must supply fresh finite gain evidence for the exact model,
  depth and scale; a shifted old gain is insufficient.
- An already rounded retained base must be fitted with additional retention
  zero. Applying its original fraction again would count retained energy twice.
- Malformed point counts and invalid active-component gains cannot look like
  a valid quiet curve. Unrepresentable local fits leave the model unchanged.

The independent reference includes pinned AOM source at `18c52422b835`.
**576 templates** agree within `3.21e-16` normalized error; **144 converted
strength calculations** agree within `5.15e-8` float error. Twelve exact AOM
innovation constants are retained in the normal CPU regression. The new
normalization test fails against the old model implementation and passes with
the correction. Native 8/10-bit refitting, source-minus-base energy, shared
chroma-scale preservation, excessive-strength rejection and all-scale hold/DC
controls also pass.

Finite clipping matters. For the selected strongly correlated 10-bit template,
scale zero has gain 2.0385 and 4.64% clipped samples; scale one has gain 2.3477
and 0.039% clipped samples. Reusing the old gain would miss that change. These
are finite development examples, not calibrated worst-case limits.

These gains include template mean energy and exclude displayed-pixel rounding,
overlap and clipping. The DC result is a linear low-frequency amplification
proxy, not a maximum-pixel or worst-seed bound. Complete colour-template gains,
native decoded synthesis and source-population checks are still required.

The rebuilt encoder is `5826421d3f7a4a319da08f1b512c76f36a3897da`, SHA-256
`0ddbb547ac0f81192c8808ae4694ab8d73fa52eaed8a53eba9fbf0182890e281`.
Four fresh encodes compare it with the previously qualified diagnostic build
`da9ce557`: 240-frame SDR and UHD HDR excerpts, each on both builds. All **1,920
decoded frame observations**, with grain on and off, match exactly between
builds. Presentation clocks, frame/stream metadata and **960 grain/training
decision records** also match. This qualifies ordinary-mode equivalence on
these controls; it is not qualification of moving nonzero-scale retention.
Production remains on ordinary `cb903a17`.

Evidence: `roadmap-r3-scale-20260922/manifest.json`, `aom-reference.json`,
`old-normalization-negative.json`, `cpu-suite.json`, `integration-build.json`,
`integration-v1/comparison.json` and `integration-v1/pause.json`.

## Exact native brightness lookup

`NVEncFilmGrainScaling.h` provides the decoder's two integer interpolation
stages for 8-, 10- and 12-bit strength lookup. It resets stale output on invalid
curves, requires increasing positions and rejects out-of-range native samples.
An empty curve is explicitly zero. Callers must additionally enforce the
component point budget, chroma index calculation and complete shared AV1 syntax.
This helper has no encoder call sites; the ordinary smooth approximation is
unchanged except for the scale-unit correction above.

All **2,580,480 native values across 1,440 curves** match the pinned independent
AOM implementation exactly. Simply rounding the continuous curve differs at
231,063 values; leaving it smooth differs at 1,452,198. Both are retained
negative comparisons. This is relevant to weak grain and sparse brightness
ranges: a smooth amplitude estimate cannot certify the actual integer curve.
Nine independent full-domain AOM curve hashes and explicit weak-curve/endpoint/
invalid-input controls are part of the normal CPU suite.
The complete suite passes 185 Python tests in 26 suites and 23 C++ checks.

Evidence: `roadmap-r3-native-scaling-20260922/comparison.json`, `build.json` and
`cpu.json`. The [roadmap](RETENTION-ROADMAP.md) remains the ordered task list.
The reserved qualification corpus has not been opened. Full-picture model
support, actual selection/output, temporal behaviour and quality/size/speed
qualification remain open. No new library defect or repair scope is inferred.

## Separate common-colour source cohorts

`film_grain_collect_reduce_common_async` accumulates only the intersection where
source Y and both source colour components pass their gates. It uses separate
fixed 80-group storage, the same bounded batches and stream/identity contract,
and preserves the existing per-component reduction. It does not modify the
diagnostic's file format or add an encoder call site.

Twenty synthetic/real cases compare both populations independently against
native CPU measurements. Maximum source-energy-normalized moment error is
`1.20e-8`, below the unchanged `5e-6` arithmetic bound. Capacity/count negatives,
history rejection, multiple batches and repeated clear/accumulate passes also
succeed. A deliberately mixed positive has 224 per-component accepted blocks
and 192 common blocks; both folds of both colours have 48 common blocks, so
the test includes adequately populated groups. Mixed-population sums divided
by the smaller count fail the independent comparison.

The three real frames have 14, 18 and 20 common blocks in total, counting both
component groups. No individual brightness/fold/component group reaches 16.
This confirms insufficient joint-grain evidence for these candidates. It does
not establish that their pictures are damaged, and the support rule was not
relaxed. Quiet/rejected populations and useful whole-picture recovery remain
separate work.

Evidence: `roadmap-r3-common-cohort-20260922/comparison-v1.json`,
`comparison-positive-v1.json`, `positive-control-plan.json` and the released
`r3-common*-pause.json` receipts. The native CPU reference is
`joint_common_reference.py`; this is a manual development check, not routine
Tdarr validation.
