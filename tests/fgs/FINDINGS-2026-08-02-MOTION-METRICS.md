# Motion separator: metric review and a direct ghosting measurement, 2026-08-02

> **Audit correction, 2026-08-02:** the metric tables below are reproduced by
> their artifacts, but the original causal interpretation of `beta` was too
> strong.  A controlled translating-edge test produces positive `beta` from a
> purely spatial blur that never reads the previous frame.  Until positive
> temporal-blend and negative spatial-filter controls pass, call this a
> previous-frame-direction projection, not a literal blend fraction or vector
> failure rate.  Motion remains a non-candidate; the correction weakens the
> claimed mechanism, not the conservative deployment decision.

Run against the blinded review set in `FINDINGS-2026-08-02-MOTION-REVIEW.md`
because the perceptual pass could not be scheduled.  **This does not replace
that review.**  It records a large objective arm separation, while the audit
above reopens which mechanism produced it.

Note for whoever reads the review set next: this document names which arm is
which, so it deblinds `FINDINGS-2026-08-02-MOTION-REVIEW.md`.  Read the clips
first if a clean impression still matters.

## What was scored

The 12 blinded clips (3 titles x A/B x base/finished), 287--288 frames each,
using every paired frame, against
a lossless centre crop of the original source built from the retained 4K
`clip_*-ref288.mkv` / `clip_The_Deer_Hunter.mkv` lossless excerpts:

```text
crop=1920:1080:960:540
```

The crop offset was verified rather than assumed: at the centre offset the base
scores PSNR-Y 45.6 dB, at (0,0) it scores 15.5 dB.  Both reference and
distorted are lossless here, so the distorted decode is a plain ffmpeg decode
and not `libdav1d` -- `campaign.vmaf_run` hardcodes the AV1 decoder and is the
wrong entry point for this set.

HD models (`vmaf_v0.6.1`, `vmaf_v0.6.1neg`) because the crop is 1080p.  All
CUDA extractors, `--gpumask 0`, `psnr_cuda`/`ssim_cuda`/`ciede_cuda`, plus
FFVship SSIMULACRA2 and Butteraugli.  Artifacts:

```text
/media/merged-storage/media/test-encodes/review-vmaf-20260802/
```

## The temporal projection under audit

Full-reference metrics cannot rank these two arms on their own.  Motion removes
more grain than bilateral by design, FR metrics punish grain removal, and the
project has already been burned once by a Butteraugli number produced under
exactly that bias.  So the primary instrument here is not a quality metric.

**Previous-frame-direction projection.**  A temporal blend is one mechanism
that makes the base error point in the direction of frame `n-1`.  Regress the
base's error onto that direction:

```text
err_n  = base_n - src_n
prev_n = src_{n-1} - src_n
beta   = sum(err*prev) / sum(prev*prev)
```

For the specific model `base_n = (1-a)*src_n + a*src_{n-1}`, `beta = a`.
That implication does not run backwards: a moving edge processed by a spatial
blur can project onto the same direction.  The first version incorrectly
claimed a spatial denoiser had no mechanism to produce positive `beta`.

One confound had to be killed first.  Both planes still carry grain: `err`
contains roughly `-grain_n` and `prev` contains `grain_{n-1} - grain_n`, so
`E[err*prev]` picks up `+E[grain_n^2]` for **any** denoiser, in proportion to
how much grain it removes.  That would hand motion a spurious positive `beta`
precisely because it denoises harder.  Both fields are therefore box-averaged
before the regression: temporally independent grain drops with the box area
while displaced structure survives.

### Instrument validation

The Shining base, same data, three box sizes (16 does not divide 1080):

| box | motion beta | bilateral beta |
| ---: | ---: | ---: |
| 4 | 0.1408 | 0.0049 |
| 8 | 0.1405 | 0.0015 |
| 24 | 0.1412 | **-0.0005** |

Motion's `beta` is invariant to averaging; bilateral's decays to zero.  This
successfully rejects the identified grain-removal confound.  It does not reject
spatial smoothing or another moving-edge error, so it validates the statistic
as a structure-correlated signal rather than validating its original causal
label.

### Result

`beta` at box 8, and within bins of `|prev|` (motion magnitude):

| title | arm | kind | beta | 0-4 | 4-16 | 16-64 | >64 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| The Shining | bilateral | base | 0.0015 | 0.2396 | 0.0677 | 0.0072 | 0.0001 |
| The Shining | **motion** | base | **0.1405** | 0.3604 | 0.2195 | 0.1744 | 0.1366 |
| The Deer Hunter | bilateral | base | 0.0079 | 0.1226 | 0.0711 | 0.0179 | 0.0024 |
| The Deer Hunter | **motion** | base | **0.1486** | 0.3819 | 0.3370 | 0.1961 | 0.1287 |
| Scarface | bilateral | base | 0.0245 | 0.2433 | 0.1435 | 0.0199 | 0.0046 |
| Scarface | **motion** | base | **0.1694** | 0.4550 | 0.3763 | 0.1418 | 0.1439 |

The low-`|prev|` bins are where the residual grain confound lives, which is why
bilateral still reads 0.12-0.24 there and ~0.000-0.005 in the high-motion bin.
The `>64` column is the one to read.

**Motion's base error has a 13-14% projection onto the previous-frame
difference in the highest-motion bin. Bilateral reads 0.0-0.5%.**  This is a
large moving-structure separation.  It is not yet a literal measurement of how
much previous-frame content survives.

The result is consistent with uncompensated temporal blending, which is the
disocclusion failure the review set was built around.  It is not specific to
that mechanism.  A known-alpha temporal blend, spatial blur, translating edge
and previous-versus-next regression are required before `beta` can be used as a
motion-vector tuning objective.

### Synthesis does not remove it

The finished clips give `beta` 0.1406 / 0.1501 / 0.1695 against the bases'
0.1405 / 0.1486 / 0.1694.  Grain synthesis leaves the measured projection
intact to three decimals.  This
does not prove that the error is displaced prior-frame content or that it is
*visible* through the grain; masking is perceptual and this probe is not.

## Full-reference metrics

Motion loses on every metric, every title, in both the base and finished pairs.
Base pair:

| title | arm | VMAF | VMAF NEG | PSNR-Y | SSIM | CIEDE | SSIMU2 | SSIMU2 p5 | Butter 2norm | **Butter max p95** |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| The Shining | bilateral | 93.38 | 92.30 | 45.41 | 0.9939 | 44.43 | 33.44 | 22.17 | 3.10 | **11.22** |
| The Shining | motion | 82.09 | 80.50 | 41.92 | 0.9858 | 42.90 | 6.85 | -41.21 | 4.85 | **52.30** |
| The Deer Hunter | bilateral | 76.42 | 75.46 | 36.95 | 0.9831 | 37.71 | 28.86 | 21.17 | 2.44 | **11.20** |
| The Deer Hunter | motion | 62.80 | 61.65 | 36.01 | 0.9655 | 37.45 | 8.24 | -22.79 | 3.19 | **43.67** |
| Scarface | bilateral | 80.06 | 79.37 | 37.30 | 0.9863 | 38.07 | -5.20 | -15.26 | 3.68 | **11.18** |
| Scarface | motion | 76.36 | 75.00 | 36.94 | 0.9807 | 37.98 | -16.63 | -26.82 | 4.05 | **35.33** |

The Butteraugli max norm is the strongest localized-artifact guard rail.  It is
a localized-artifact signal that mean-pooled VMAF and SSIMU2 average away, and
**bilateral sits at 11.18 / 11.20 / 11.22 across three completely different
films** -- a floor -- while motion ranges 35.3 to 52.3 and varies with content.
The pattern is consistent with localized picture damage, but the metric remains
full-reference and is not proven independent of spatially varying grain
removal.  It supports the conservative decision; it does not identify the
mechanism by itself.

Finished pair, motion minus bilateral:

| title | VMAF | SSIMU2 | SSIMU2 p5 | Butter max p95 |
| --- | ---: | ---: | ---: | ---: |
| The Shining | -10.79 | -17.74 | -42.05 | +38.32 |
| The Deer Hunter | -10.36 | -12.79 | -26.78 | +30.53 |
| Scarface | -3.11 | -4.97 | -3.28 | +21.62 |

Synthesis narrows the mean-pooled gaps slightly and leaves the localized one
essentially untouched: motion's Butteraugli max p95 moves 52.30 -> 52.91,
43.67 -> 44.63, 35.33 -> 36.57 between base and finished.

### The plain control, and why VMAF cannot carry this finding

Standing rule: any comparison trading real grain for synthesised grain needs a
plain encode at the same encoder setting as an anchor, because FR metrics
reward pixel-aligned grain.  These are same-QVBR controls, not matched-bitrate
encodes.  The QVBR-29 plain encodes were decoded, cropped
identically and scored:

| title | arm | VMAF | VMAF NEG | PSNR-Y | SSIM | 4K bytes | vs plain |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| The Shining | **plain** | **95.04** | **93.93** | **46.54** | **0.9946** | 15,893,822 | -- |
| The Shining | bilateral | 90.72 | 89.10 | 42.92 | 0.9880 | 9,641,094 | -39.3% |
| The Shining | motion | 79.93 | 78.06 | 40.37 | 0.9797 | 7,336,183 | -53.8% |
| The Deer Hunter | **plain** | **75.63** | **74.18** | **37.30** | **0.9709** | 30,412,001 | -- |
| The Deer Hunter | bilateral | 70.12 | 67.74 | 34.21 | 0.9529 | 29,776,484 | -2.1% |
| The Deer Hunter | motion | 59.76 | 57.94 | 33.76 | 0.9355 | 21,719,212 | -28.6% |
| Scarface | **plain** | **81.37** | **80.09** | **37.89** | **0.9827** | 31,029,894 | -- |
| Scarface | bilateral | 77.16 | 75.60 | 34.33 | 0.9691 | 20,696,806 | -33.3% |
| Scarface | motion | 74.04 | 72.13 | 34.15 | 0.9637 | 14,159,983 | -54.4% |

Plain wins every metric on every title while being the largest file by up to
2.2x.  **The FR ranking is the exact inverse of the compression ranking**, and
it is also the ranking of how much real grain each arm keeps.  So VMAF, PSNR,
SSIM and SSIMU2 cannot separate "this arm damaged the picture" from "this arm
denoised harder", and the -10.8 VMAF gap between motion and bilateral must not
be quoted as damage on its own.

That is why the result cannot rest on pooled FR metrics.  The projection and
Butteraugli tail together say the motion arm needs more investigation, but the
projection is not immune to spatial-filter errors and must pass the controls
listed above before it carries a causal finding.

### The suspended number is no longer suspended

`FINDINGS-2026-08-01-SOURCE-FIT.md` suspended motion's Butteraugli p95 of 53.86
on the grounds that it predated `grain_scale_shift` and `modelsrc`, under a
regime that taxed arms in proportion to the grain correlation they preserved,
and said it should not be quoted again until re-measured.  It has now been
re-measured under the current regime, with both fixes in, on a different title
set: **52.91 on The Shining finished, 44.63 Deer Hunter, 36.57 Scarface.**

The result survives its own re-measurement.  Motion's localized-artifact
penalty was not an artifact of the old grain handling.

## Why the damage does not rank with beta

Scarface has the *highest* local drag (0.169) and the *smallest* metric
penalty (-3.7 VMAF).  That is not a contradiction -- the two measure different
things, and the block distribution confirms it:

| title | 0-4 | 4-16 | 16-64 | >64 | share above 16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| The Shining | 48.3% | 28.9% | 15.3% | 7.5% | **22.7%** |
| The Deer Hunter | 35.0% | 45.5% | 15.8% | 3.6% | **19.4%** |
| Scarface | 53.5% | 39.2% | 6.2% | 1.2% | **7.4%** |

`beta` is weighted toward locations where inter-frame difference is large; the
metrics are whole-frame damage.  Scarface is a static-camera scene with moving
people, so its projection touches a small share of the frame.  With only three
titles, the distribution is consistent with the metric spread but cannot be
said to explain it.

## What this does and does not settle

Supported by this run:

- motion has a much larger previous-frame-direction projection than bilateral,
  including in the highest-motion bin;
- grain synthesis does not materially change that projection;
- the earlier Butteraugli result reproduces under the current fixes;
- every full-reference metric available ranks motion worse on every title, in
  both base and finished form.

Not settled:

- whether the projection is temporal blending, spatial smoothing or a mixture;
- any literal previous-frame fraction or vector-failure rate;
- **whether it is visible in normal playback.**  None of this is perceptual.
  A 13% blend of the previous frame on a moving high-contrast edge is in the
  range where trails are usually visible, but "usually" is not a measurement,
  and grain may mask more than these metrics suggest;
- whether a stricter motion-confidence threshold or a disocclusion fallback to
  the spatial filter recovers most of the 46.4% at a much lower `beta`.  That
  becomes a useful tuning question only after the statistic is calibrated.

## Bearing on the project

The 46.4% corpus saving is motion's alone -- bilateral saves 23.1% and misses
the 30-40% target.  Everything the amplitude work has been refining
(`modelsrc`, leak closure, per-luma delivery) sits downstream of a separator
that these numbers say is damaged.  The fidelity work is not wasted if motion
is rejected: source fitting and leak closure are separator-independent and
apply to bilateral unchanged.  What would be lost is the headline compression
number.

`beta` is cheap and needs no human, but it is not yet a safe tuning objective.
The next step is to calibrate it against known temporal blends and spatial
moving-edge controls, including previous-versus-next asymmetry.  Only if that
separates the mechanisms should the confidence threshold be swept against the
corrected statistic and bytes.

`modelsrc` remains default-off, motion remains a non-candidate, and nothing
here was deployed.
