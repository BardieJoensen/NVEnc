# Automatic retention: colour structure and local grain fidelity

Status: source-fidelity, cost/detail, real-footage, CPU and final GPU
qualification complete for this optional-mode improvement.

This iteration fixes two demonstrated source-fidelity faults in optional
automatic retention: softened colour-only structure and excessive synthesized
grain in small weak or quiet regions. It also adds source-labelled gradient,
fade and transition coverage. Production remains on core `497caa64` with
ordinary retention; these optional-mode changes are not deployed by this work.
These failures were reproduced in controlled optional-auto encodes. They do
not establish additional damaged library titles or expand the recovery scope.

Tested candidate SHA-256:
`642e8b9b21eb5487127edf2bbbb72420ec03846a92f98ff2ed435c9d1f5ebdb4`.
The reference is optional-auto core `9b8217ec`, binary
`151650189b2edb24e99d023764ea8379cbcd26dbc332262632314eae88aa28ac`.
The incremental build retains the cached Meson label r4245; use the binary
and core-source hashes in `candidate-v11-build.json` to identify this build.

## Demonstrated faults and fixes

Luma can be flat while colour contains picture detail. Previously the local
colour denoiser inherited the luma noise estimate and had no independent
directional protection. Optional bilateral auto now measures the two colour
components separately on 16-pixel blocks and averages along supported colour
structure. Chroma fitting excludes coherent colour texture. Explicit denoise
strength still takes precedence over automatic noise estimates.

Auto mode also restores a source colour component when the selected model
signals no synthesis for it. An all-zero scaling curve is inactive even when
its point count is nonzero. Restoration handles both components together or
one component of NV12/P010, as well as separate planes. FFT3D and motion auto
receive this restoration, with their existing filters otherwise unchanged.
Four additional 48-frame clean/asymmetric colour controls cover both alternate
denoisers at 8 and 10 bits and pass the same decoded colour checks.

The prior grain-amplitude check reused the sparse evidence used for model
fitting. It could miss narrow brightness regions and excluded quiet patches
that are unsuitable for fitting AR coefficients. A stable synthesis model
could consequently add substantial grain where the source had little or none.

Bilateral auto now gathers independent local luma evidence on a 16-pixel
grid. It removes a fitted plane from the inner 12-by-12 source/base patch,
then accumulates source variance, base variance and their covariance in
one-code brightness buckets. Four patches are required per bucket. The
predicted total accounts for both residual retention and synthetic grain:

```
predicted variance = (1-r)^2 * base variance + r^2 * source variance
                   + 2*r*(1-r) * source/base covariance
                   + (1-r^2) * synthesis variance
```

The new evidence participates in the existing current-frame model retry,
source fallback and recovery hysteresis. Quiet and weak patches are evidence
for validation even when they should not be used for coefficient fitting.
The compact 10 KiB host readback uses the existing model synchronization.
No extra host barrier is introduced. The original synthesis-safety checks
remain in force.

This small-patch energy calculation is calibrated for approximately
independent grain. Strongly correlated grain and coherent texture are
excluded; the additional grid is skipped when the measured frame grain is
outside that correlation range. The pre-existing model checks still apply.
Absent or sparse local evidence is not certification of the whole picture.
The new check is luma-only; it does not independently validate fine local
colour-grain energy. Integer rounding, clipping, encoding quantization and
grain correlation limit the prediction's precision.

## Source-labelled decoded results

All three arms use QP 20. The plain arm compresses the same source without
FGS; previous and candidate auto both use `retain-max=0.1`. Every one of the
48 frames per control is decoded with grain off and on. The reported colour
gain is transfer of the known AC pattern, not a percentage of overall quality.

| Control | Previous auto | Candidate auto | Plain compression |
| --- | ---: | ---: | ---: |
| Noisy SDR colour pattern, U/V gain | 0.578 / 0.611 | 0.971 / 0.982 | 0.975 / 0.973 |
| Moving HLG colour pattern, U/V gain | 0.599 / 0.628 | 0.987 / 0.990 | 0.992 / 0.993 |
| Narrow weak region, source sigma 2.02 | 4.61 | 1.56 | 1.55 |
| Narrow weak region, source sigma 1.04 | 4.27 | 0.12 | 0.12 |
| Quiet regions, source sigma 0 | 5.49 | 0.00 | 0.00 |

Grain amplitudes are mean regional sigma in normalized 8-bit codes. The very
weak-grain case also demonstrates ordinary compression loss: preserving the
source before encoding is not lossless encoding. Both narrow transitions
retain all 16 problematic middle frames and recover synthesis afterwards.
The quiet-region control retains all 48 source frames.

The 19 controls cover SDR 8/10-bit gradients, PQ/HLG gradients and fades,
near-black/midrange/wide gradients, clean/noisy/asymmetric colour components,
moving colour and cuts, grain cuts, two narrow strength transitions, and quiet
regions beside grain. Per-frame checks bound mean shifts, gradient-profile
errors, contour changes, colour-pattern transfer and local grain amplitude.
Artificially stepped gradients and deliberately blurred colour verify that
the measurements detect those faults. Re-evaluating the prior auto output
with the final assertions rejects five cases, including all three local-grain
negatives. These were decoded failures, not merely header flags.

The initial high-pass-only colour diagnostic overemphasized the quantization
steps of weak 8-bit sinusoids. Known-pattern AC projection and a plain encode
exposed that confound. The high-pass value remains a separate diagnostic.
One raw clean-colour control verifies exact source C samples before encoding;
encoding that raw base without FGS reproduces the quantization contribution.
No QP change was used to qualify the filtering improvement.

## Gradients and banding

No new gradient regression was found in the tested SDR, PQ and HLG controls.
That is a bounded result, not proof that all gradients are free of banding.
Profile measurements compare both decoded playback modes with the source and
the prior encoder. They are code-value engineering measurements, not HDR
visibility or just-noticeable-difference thresholds.

The additional SDR CAMBI run measures source and each decoded output on all
48 frames. The metric's default visibility model is BT.1886; see the
[upstream CAMBI documentation](https://github.com/Netflix/vmaf/blob/master/resource/doc/cambi.md).
This run records independent no-reference scores and per-frame positive
output-minus-source differences; it does not claim to have invoked CAMBI's
full-reference option or established calibrated HDR perception.

| SDR control | Source mean CAMBI | Previous off / on | Candidate off / on |
| --- | ---: | ---: | ---: |
| Clean 8-bit gradient | 18.153 | 18.115 / 18.115 | 18.115 / 18.115 |
| Clean 10-bit gradient | 4.459 | 4.328 / 4.328 | 4.328 / 4.328 |
| Noisy gradient fade | 0.000 | 7.968 / 0.000 | 7.990 / 0.000 |
| Grain cut on gradient | 0.000 | 5.707 / 0.000 | 5.707 / 0.000 |

The clean inputs already contain quantization contours. Noisy grain-off bases
also have contours that the grain-on output masks in this test. The new work
does not claim to remove those existing limitations. CAMBI is a contour
measurement and does not replace ripple, colour-transfer or local grain checks.

## Storage and runtime

| New control | Candidate size versus previous auto |
| --- | ---: |
| Noisy SDR colour | +24.32% |
| Moving HLG colour | +28.44% |
| Clean-colour 8-bit / 10-bit | -86.82% / -83.80% |
| Narrow transition, weak sigma 2 / 1 | +48.40% / +13.77% |
| Quiet regions beside grain | +835.64% |

Restoring colour detail costs bits on the noisy controls. Independent colour
analysis also removes expensive false whole-frame fallback on the clean-colour
controls. The large quiet-region ratio reflects the old output's incorrectly
cheap synthetic replacement; the new output is essentially the plain source
encode. This synthetic ratio is not a whole-library forecast.

The measured-baseline admission remains a separate offline pilot policy.
Oversized candidates retain the input; these guards do not raise QP or remove
detail to force admission. `retain-max=0.1` limits residual blending, not file
size, and complete source fallback can be far more expensive.

An output-preserving optimization skips the pixel-centred edge calculation
when directional confidence is already saturated. Four controls, including
moving HLG colour, have identical complete grain-on/off decoded hashes across
the optimization-only comparison (192 frames in each playback mode). Runtime
measurements and the final candidate comparison are recorded separately.

The isolated raw-output Gentlemen ABBA run records mean film-grain filter
times of 4.697 ms before and 4.654 ms after the shortcut (0.92% lower).
Mean wall time is 1.82% lower. The differences are small, the individual runs
vary, and the hardware is shared; this is bounded evidence of cost, not a
general throughput guarantee. The pixel-equality check is independent of
those timing measurements.

The final candidate's 150-second Gentlemen ABBA encodes take 36.15 / 35.78
seconds for the previous auto binary and 35.80 / 36.04 seconds for the
candidate: means of 35.96 and 35.92 seconds. The 0.13% difference is too small
to establish a throughput improvement on shared hardware. Output is 0.96%
larger. The 24-frame Taxi, Silo and Alien auto outputs change by +0.37%,
+1.61% and -0.96%; their short timings are dominated by startup. These
measurements compare optional auto at equal settings and are not forecasts
for whole films or the ordinary production mode.

## Qualification and rejected prototypes

The final candidate passes the CPU suite, all 19 new picture controls, the
16-case cost/detail sweep at both 0.1 and 0.5 ceilings, eight texture-residual
cases, the cost regression gate, and all nine sharp-curve/edge controls.
The two intentionally unrepresentable sharp-curve controls retain source
pixels exactly as the preceding source-preservation reference does.
All 16 real outputs pass complete grain-on/off decoding, synthesis-texture
scanning and source-property checks. Both candidate repeats pass the three
Gentlemen jacket samples. The three ordinary-mode clip pairs have identical
decoded pixels. The final quick GPU gate passes its 21 known-answer fixtures,
table export/failure paths, and both the rejected-model and accepted-model
controls. All seven final qualification stages exit successfully.

Earlier prototypes remain rejected. Adding more samples inside the old coarse
bins did not fix the narrow-region failure. Comparing removed-residual energy
alone falsely rejected valid sharp curves because grain also remained in the
base. Ignoring covariance/residual blending was incomplete. Applying the
small-patch model to coarse grain or woven structure caused unnecessary
fallback and failed the cost gate. Excluding quiet patches, then retaining
the AR-fitting score threshold for weak patches, left local overshoot gaps.
The final source controls and broader cost/texture tests cover those cases.

## Evidence and operating state

Reports: `/opt/docker-apps/logs/fgs-ripple-repair-20260906/quality-retention-20260910`.
Encoded/decoded artifacts: `/tmp/downloads/fgs-quality-retention-20260910`.

- `candidate-v11-build.json` and `candidate-v11.patch`: candidate binary,
  pinned build image and exact core sources.
- `qualification-v11.json`, `cpu-v11.log`: actual stage commands and results.
- `pictures-v11/report.json` in the artifact root, `pictures-v11-summary.json`
  and `negative-previous-auto.json`: source/decoder hashes, frame evidence,
  accepted candidate and rejected previous-auto cases.
- `controlled-v11`, `strength-v11` and `real-v11` in the artifact root;
  `texture-v11.json`, `quick-gate-v11`, and `alternate-denoisers-v11.json` in
  the report root: broader qualification and unchanged-default checks.
- `cambi-v11/report.json`: source-relative SDR contour measurements.
- `fastpath-pixels.json` and `fastpath-speed.json`: isolated optimization
  evidence; these intermediate binaries do not qualify the final grain guard.
- `work-plan.json` and final `acceptance.json`: completed foreground scope,
  tested core identity and production state. Older prototype reports remain
  separate and cannot substitute for final candidate qualification.

No ordinary Tdarr validation stage, production flow, library replacement,
repair/audit service, Emby-yield policy or recovery-download hold is changed
by this work. The FFprobe XML/AddressSanitizer investigation stays deferred.
