# AV1 film-grain performance follow-up — 2026-07-29

## Result

Two CUDA changes reduce the analyzer's measured film-grain kernel time by
about 82% on the production bilateral path without a measurable quality
change:

- `170b9a4c`: replace FP64 flat analysis and shared 64-bit model-stat atomics
  with FP32 residual analysis and local normal-equation accumulation.
- `1fa517e3`: process each 32x32 flat-analysis block with 128 CUDA threads
  instead of one serial CUDA thread.

`77e8329a` adds a source-grain scale diagnostic. It costs about 0.009 ms/frame
at 1080p and does not affect the model or encoded pixels.

One later quality fix uses the faster analyzer rather than changing encoder
levers:

- `f259e251` replaces the necessarily weak single-frame opening model as soon
  as the eight-frame rolling window fills.

The later `d23400f4`/`d807b990` correlation-adaptive bilateral experiment did
not generalize from generated grain to real film. `a4b84e1a` removes it after
matched-rate tests on both a real midpoint title and its intended Taxi Driver
endpoint; source correlation remains a diagnostic, not a filter control.

These commits modify `NVEncFilterFilmGrain.cu` and
`NVEncFilmGrainModel.{h,cpp}` and therefore require rebuilding NVEncC; they are
not test-only changes.

All 18 GPU known-answer fixtures, both 8/10-bit retention sweeps (10 points),
the CPU solver and parser tests pass. The speed-only commits leave headline
quality metrics and every retention-sweep encoded byte count unchanged;
`f259e251` intentionally changes opening model timing as measured below.

### Taxi Driver grain-strength correction

The original Taxi Driver routing conclusion exposed an analyzer defect rather
than an AV1 film-grain format limit. The sparse AR estimator sampled the same
8x8 lattice in every 32x32 model block. On the film residual that lattice
aliased the spatial correlation and inflated the fitted AR synthesis gain:

| Taxi 20 diagnostic | AR gain |
| --- | ---: |
| libaom, all usable pixels | 2.02 |
| old fixed lattice, frame 0 | 4.25 |
| old fixed lattice, 32 frames | 3.55 |
| staggered 64-point simulation, frame 0 | 2.04 |
| staggered 64-point simulation, 32 frames | 2.12 |

The strength curve is divided by this gain once, so the biased fit explained
why the old build signalled roughly half the required luma amplitude even
though its AR coefficient *shape* looked plausible. `09dae08c` keeps 64
observations per block but chooses one deterministic, block-staggered sample
from each spatial stratum. It also keeps every predictor inside its model
block, removing an out-of-frame read on the rightmost old sample.

On the exact same source/clean pairs, decoded luma-grain sigma now follows the
libaom oracle:

| Scene | Measured residual | Old NVEnc | Corrected NVEnc | libaom |
| --- | ---: | ---: | ---: | ---: |
| Taxi 20 | 1.255 | 0.707 | 1.208 | 1.178 |
| Taxi 40 | 1.675 | 0.430 | 1.359 | 1.366 |
| Taxi 60 | 1.243 | 0.393 | 1.013 | 1.084 |
| Taxi 80 | 1.305 | 0.639 | 1.115 | 1.079 |

The corrected result is within -6.6% to +3.3% of libaom on all four scenes.
The residual-to-synthesis ratio is not always one even for libaom because the
residual also contains separator error and components the compact AV1 model
does not reproduce.

The matched production-style QVBR 26 rerun changes the decision materially:

| Scene | Old MiB | Corrected MiB | Size change | Old retention | Corrected retention |
| --- | ---: | ---: | ---: | ---: | ---: |
| Taxi 20 | 25.75 | 19.99 | -22.3% | 0.741 | 0.921 |
| Taxi 40 | 28.82 | 19.59 | -32.0% | 0.611 | 0.828 |
| Taxi 60 | 26.70 | 19.78 | -25.9% | 0.758 | 0.878 |
| Taxi 80 | 28.73 | 19.66 | -31.6% | 0.614 | 0.854 |

This is the first real-title confirmation that Taxi Driver no longer needs to
be routed away merely because FGS under-signals its grain. It is not yet a
blind deployment recommendation: source-position distortion metrics penalize
correctly randomized synthesis heavily. On Taxi 20, SSIMULACRA2 moved from
17.19 to 5.12 and the Butteraugli max-norm p95 from 3.31 to 16.39 while grain
retention improved from 0.741 to 0.921. Those numbers describe a real
pixel-position difference but cannot distinguish correctly sized,
decorrelated grain from objectionable noise. A playback A/B of several dark,
bright and moving scenes remains the release gate.

Neither partial-retention control improved the decision. At the same QVBR,
`retain=0.25` left bytes and grain retention effectively unchanged and made
the distortion tails slightly worse; `retain=auto` reduced retention to 0.885
without saving bytes. Zero retention remains the Taxi candidate.

### Startup convergence and rejected coarse-grain adaptation

The analyzer deliberately accepts a model on frame zero so grain is present
from the first decoded frame. That first model only contains one frame of
statistics, however, and the ordinary 24-frame model-update cadence could hold
an atypical opening frame well after the rolling window became representative.
`f259e251` keeps immediate frame-zero signalling, then permits one immediate
replacement when the eight-frame window first fills. The new `warmup_luma`
fixture starts at sigma 4 and settles at sigma 6; its first full-window model
now replaces the opening fit on frame 7.

On the Taxi 60 production control this moves the first table boundary from
frame 25 to frame 7. Over decoded frames 8-23, synthesized luma sigma improves
from 1.014 to 1.058 (+4.4%) with a 697-byte size reduction.

The remaining bilateral limit appeared to be its fixed spatial response. An
experiment mapped the already-measured source correlation continuously between
the compact `[1 4 6 4 1]` profile and a wider `[1 2 2 2 1]` profile. On the
generated fixtures this looked narrowly positive:

| Bilateral KAT measure | Compact profile | Adaptive profile |
| --- | ---: | ---: |
| Fine-grain synthesized sigma | 5.42-5.69 | 5.42-5.69 |
| Fine-detail transfer | 0.468 | 0.468 |
| Structured-edge RMSE (8-bit) | 2.31 | 2.31 |
| Coarse-grain amplitude captured | 36% | 40% |

On the Taxi 60 control (frames 8-23), synthesized luma sigma rose from 1.053
to 1.173 (+11.3%) and lag-one spatial autocorrelation from 0.600 to 0.624,
with bytes effectively unchanged. Throughput was also unchanged within run
noise. Those local texture measures did not predict full-reference quality.

The first real check caught one failure. The initial interpolation began at
correlation 0.20, so Silo S03E01 at 0.36-0.47 partially activated it even
though that title already retained grain correctly. At the same QVBR 25.4,
the compact profile won:

| Silo S03E01, first 600 frames | Broad from 0.20 | Compact through 0.60 |
| --- | ---: | ---: |
| Bytes | 14,730,354 | 14,848,643 |
| SSIMULACRA2 / p5 | 80.39 / 74.90 | **80.66 / 75.21** |
| Butteraugli 2-norm / max p95 | 0.917 / 3.33 | **0.905 / 3.26** |
| VMAF / minimum | 93.68 / 83.00 | **93.85 / 84.19** |

Moving the onset to 0.60 fixed Silo but did not resolve the underlying
assumption. Real-title correlations occupy the middle of the ramp rather than
the synthetic endpoints. The Shining is the exact control: aggregate
correlation 0.696, with per-frame values around 0.68, so the narrowed ramp
applied roughly 40% of the wide profile. A 288-frame, 4K PQ comparison was
rate matched to within 0.19% for compact versus midpoint and 1.31% for wide
versus midpoint:

| The Shining | Compact | Ramp midpoint | Fully wide |
| --- | ---: | ---: | ---: |
| Bytes | 9,968,971 | 9,988,329 | 9,857,497 |
| SSIMULACRA2 / p5 | **17.68 / 10.95** | 16.87 / 10.44 | 14.11 / 7.71 |
| Butteraugli 2-norm / max p95 | **2.721 / 11.37** | 2.757 / 11.73 | 2.880 / 12.15 |
| VMAF / minimum | **94.43 / 92.22** | 94.33 / 92.17 | 93.86 / 91.50 |
| VMAF NEG | **93.81** | 93.71 | 93.20 |
| PSNR-Y / SSIM | **44.72 / 0.9984** | 44.59 / 0.9984 | 44.24 / 0.9983 |
| CIEDE2000 (lower is better) | 43.48 | 43.37 | **43.06** |

Compact wins every texture/distortion family except the small color-error
movement. More importantly, the intended endpoint also fails. Taxi Driver's
aggregate correlation is 0.823, so the narrowed ramp selects fully wide. A
second 288-frame matched-rate comparison gave the wider result 0.86% more
bytes:

| Taxi Driver | Compact | Fully wide |
| --- | ---: | ---: |
| Bytes | 30,175,070 | 30,435,728 |
| SSIMULACRA2 / p5 | **1.29 / -6.59** | -0.57 / -7.88 |
| Butteraugli 2-norm / max p95 | **3.271** / 13.82 | 3.341 / **13.71** |
| VMAF / minimum | **87.72 / 86.58** | 87.20 / 86.08 |
| VMAF NEG | **87.37** | 86.87 |
| PSNR-Y / SSIM | **40.07 / 0.9966** | 39.89 / 0.9965 |
| CIEDE2000 (lower is better) | 39.26 | **39.11** |

The wide profile again loses the main texture and fidelity metrics; only the
Butteraugli extreme tail and color error move slightly in its favor. The
synthetic coarse-capture improvement therefore does not justify a production
code path. `a4b84e1a` restores the compact profile everywhere and returns the
coarse KAT to its original regression-only 30% floor (actual capture 36%).
Correlation stays in diagnostics for measurement and future research.

Three tempting variants were rejected rather than committed:

- Fully bypassing bilateral refinement in coherent blocks raised detail
  transfer from 0.468 to 0.657 but raised edge RMSE from 2.31 to 5.46.
- A regularized strength curve reduced Taxi synthesis by 1.5%; the separator,
  not sparse curve bins, was limiting the result.
- Four times as many luma AR observations improved Taxi synthesis by only
  0.12%, confirming the staggered 64-point estimator is already converged.

## Correctness audit

The parallel flat-analysis reduction intentionally reuses shared storage:
`reduce4` holds `localNormY` in the plane-fit phase and
`localCorrelationProduct` in the residual phase. The reuse is safe because all
threads cross the `__syncthreads()` after the fitted plane is published before
any thread overwrites `reduce4`.

FP32 is sufficient for the plane-fit sums: a 32x32 block contains 1024 values
no larger than 1023, so the unweighted sum is at most about 1.05 million, below
FP32's exact-integer limit of 2^24. Variance is accumulated from fitted
residuals rather than subtracting two large squared quantities, avoiding the
catastrophic-cancellation case. The correlation numerator can cancel, but the
observed fine-grain residual is about 2e-9 of its energy denominator and does
not affect the classification.

## Bilateral CUDA profile

Nsight Systems, RTX 5060 Ti, 120-frame 1920x1080 P010 raw output:

| Stage | Before | Current | Change |
| --- | ---: | ---: | ---: |
| Flat-region analysis | 1.0782 ms/frame | 0.0586 ms/frame | -94.6% |
| Luma + chroma model statistics | 1.7256 ms/frame | 0.0721 ms/frame | -95.8% |
| Bilateral filtering | 0.4387 ms/frame | 0.4386 ms/frame | unchanged |
| Level compensation | 0.0183 ms/frame | 0.0181 ms/frame | unchanged |
| **All named FGS kernels** | **3.2608 ms/frame** | **0.5875 ms/frame** | **-82.0%** |

These are analyzer kernel times, not end-to-end encode times. Resolution,
NVENC settings, storage, decoding, and concurrent Tdarr jobs determine the
wall-clock result. The remaining profile is dominated by the two bilateral
passes; two required per-frame GPU-to-host decision points are the other
architectural floor.

## End-to-end production result

A fixed 1200-frame input was run for three alternating rounds through the
production r4029 build and the clean-image r4033 build. Median elapsed time
fell from 4.2 to 2.7 seconds (58.5% higher throughput in the unrounded
measurement), removing the old 91% FGS penalty. A separate warm r4033 control
rounded both FGS and no-FGS to 2.2 seconds. Denoising reduced the residual that
NVENC had to code, producing a 4.24 MB stream instead of 5.79 MB, so the
encoder saving paid for the analyzer on this input.

The output is not literally byte-identical after FP64-to-FP32 analysis. The
elementary bitstream moved by 11,348 bytes (+0.081%), while the scored quality
was measurably identical:

| Build | Grain retention | CAMBI | SSIMULACRA2 |
| --- | ---: | ---: | ---: |
| r4029 | 1.009 | 0.000 | 80.0153 |
| r4033 | 1.009 | 0.000 | 80.0172 |

This supersedes the earlier operational assumption that FGS deliberately
traded throughput for quality. The current production recommendation is to
rebuild the tdarr-node image with r4033 and restart only after its in-flight
encodes have drained.

## Exact follow-up optimizations

Two additional bit-exact changes were profiled after the r4033 deployment
candidate:

- `ec413f96` cooperatively loads each bilateral block's 5x5 halo into shared
  memory instead of repeatedly addressing the same global pixels.
- `b252f866` handles the zero-difference center tap directly, avoiding one
  precise reciprocal out of 25.

At 1080p they reduce bilateral time from 0.4386 to 0.3700 ms/frame (-15.6%)
and all named FGS kernels from 0.5875 to 0.5187 ms/frame (-11.7%). The
shared-tile change alone reduces the 4K FGS profile by 11.7%. A 32-frame fixed
input produces the same cleaned-base SHA-256 as r4033; the AV1 elementary
stream and container size are also identical.

These are useful future-build improvements, not a reason to interrupt the
fresh r4033 production deployment: r4033 has already removed the measurable
FGS wall-clock penalty on the production control.

An experimental approximate range reciprocal reduces the 1080p FGS profile
further to 0.4492 ms/frame (-23.5% versus r4033). All 17 KAT cases and 10
retention points pass, but dark-scene rounding moves by 0.01 and encoded bytes
move by up to +0.11%. It remains uncommitted pending a real-content A/B. An
exact warp-barrier reduction was also tested; it produced no measurable
improvement and was reverted.

### Determinism methodology

Do not use whole-MKV hashes to test encoder determinism: Matroska includes a
random SegmentUID and mux timestamp, so identical elementary streams can have
different container hashes. Compare a fixed input's video stream instead:

```sh
ffmpeg -i output.mkv -map 0:v:0 -c copy -f md5 -
```

Both tested binaries are deterministic by that comparison. Avoid using
`--seek` with hardware decode for this check; identical runs showed a 6% size
swing because the decoded sample boundary was not stable. Pre-cut the source
once or decode the same seek-free fixed fixture for every build.

Disabling chroma analysis on the same fixture reduces current FGS kernel work
from 0.5875 to about 0.398 ms/frame (-32%). It is only safe when the source has
negligible chroma grain. More importantly, a production comparison measured
`chroma=off` at **+41% output bytes at identical retention**: bypassing analysis
keeps chroma grain in the coded base, so the profiler win can be a library-size
regression. Any future adaptive `chroma=auto` work must measure bytes as a
primary result, periodically resample chroma, and re-enable analysis at scene
changes. It is not presently recommended.

## Quality and denoiser choice

The optimized FFT3D path is now only about 5-7% slower than bilateral in the
isolated raw benchmark, while the synthetic controls show a quality trade-off:

| Measure | FFT3D | Bilateral |
| --- | ---: | ---: |
| Fine-grain synthesized/source sigma | 0.98-1.02 | 0.89-0.94 |
| Fine-detail transfer through base | 0.429 | 0.469 |
| Structured-edge RMSE (8-bit) | 1.89 | 2.31 |
| Coarse-grain amplitude captured | 41% | 40% |

Bilateral preserves slightly more high-frequency detail and models chroma
strength somewhat better. FFT3D is stronger on these generated controls for
luma grain fidelity and edge distortion, but this result does not generalize
to the real-title production comparison available so far:

| Silo S03E01/E02, QVBR 29 | SSIMULACRA2 | p5 | Butteraugli | Grain retention |
| --- | ---: | ---: | ---: | ---: |
| Bilateral | **80.02** | **73.95** | **1.32** | **1.01** |
| FFT3D | 78.87 | 73.18 | 1.40 | 0.96 |

Lower Butteraugli is better. Bilateral wins all four reported real-content
measures. Generated-grain KATs and a real camera/film encode exercise different
separation errors, so the synthetic result is a regression diagnostic, not a
production denoiser ranking. Keep the measured production setting while a
broader real-title A/B is collected:

```text
--av1-film-grain denoise=auto,chroma=auto,denoiser=bilateral
```

## Quality and size operating points

The FGS bitrate saving can either remain a storage saving or be spent on the
clean base. Two 60-second Silo controls were encoded with the deployed r4033
bilateral path and rescored over the same first 600 frames. The QVBR 27 HQ arm
lands close to the old plain QVBR 29 byte budget while leaving played-out grain
unchanged:

| Clip / setting | MiB | VMAF | VMAF min | SSIMULACRA2 | p5 | Butteraugli p95 | Grain retention |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E01 HQ QVBR 29 | 13.39 | 93.42 | 84.01 | 80.71 | 74.99 | 3.68 | 1.009 |
| E01 HQ QVBR 27 | 17.02 | 93.79 | 84.67 | 81.62 | 76.11 | 3.28 | 1.009 |
| E02 HQ QVBR 29 | 13.45 | 93.87 | 85.80 | 78.08 | 74.43 | 3.62 | 1.000 |
| E02 HQ QVBR 27 | 17.09 | 94.17 | 86.36 | 78.99 | 75.38 | 3.43 | 1.000 |

Lower Butteraugli is better. QVBR 27 costs 27.1% more than the QVBR 29 FGS
arm, but the resulting 17.02/17.09 MiB files are still no larger than the
17.1/18.0 MiB plain QVBR 29 controls. It improves every reported distortion
measure without changing grain retention. This is the clean quality-first
choice when the pre-FGS byte budget is acceptable. Keep QVBR 29 when the
22-25% FGS size reduction is the goal.

The earlier three-class FGS sweep shows the same separation between grain and
base quality. Moving QVBR 29 to 27 costs 26.6% on grainy film and 27.5% on
clean digital while changing retention by 0.000 and +0.004 respectively; VMAF
improves by 0.80/0.24 and SSIMULACRA2 by 2.57/0.78. Animation's QVBR 34 to 31
step costs 41.1% for +0.42 VMAF and +1.73 SSIMULACRA2, so the current animation
bucket has a much weaker quality-per-byte case for lowering QVBR.

`retain=auto` is a different trade rather than a free improvement:

| Clip / setting | MiB | VMAF | VMAF min | SSIMULACRA2 | p5 | Butteraugli p95 | Grain retention |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E01 QVBR 29, retain 0 | 13.39 | 93.42 | 84.01 | 80.71 | 74.99 | 3.68 | 1.009 |
| E01 QVBR 29, retain auto | 13.93 | 94.19 | 86.55 | 81.51 | 76.03 | 3.48 | 0.939 |
| E02 QVBR 29, retain 0 | 13.45 | 93.87 | 85.80 | 78.08 | 74.43 | 3.62 | 1.000 |
| E02 QVBR 29, retain auto | 14.19 | 94.80 | 86.38 | 79.25 | 76.32 | 3.49 | 0.890 |

Auto retention improves all listed distortion metrics for only 4.0-5.5% more
bytes, but it also lowers measured grain energy by 7-11%. The risk detector
selected mean retention 0.429/0.456 and spent much of both clips at its 0.50
cap. It is therefore a defensible clean/digital fidelity mode, not the default
for a grain-retention pipeline. The compensation model should be calibrated on
more real titles before auto retention is promoted.

Two encoder-side candidates did not produce a general win:

- UHQ changes the meaning of the QVBR scale; QVBR 24 was required to
  approximately match HQ QVBR 29 size. At that matched rate it improved mean
  VMAF by 0.43-0.45 and the Butteraugli tail by 0.27-0.28, but reduced VMAF
  minimum by 0.26-0.31 and mean SSIMULACRA2 by 0.14-0.19. It also enables
  lookahead and temporal filtering and is slower. Keep HQ for production.
- Pinning AQ strength 8 moved bytes by +0.08%, left mean quality and retention
  effectively unchanged, and moved tail metrics in opposite directions. Keep
  the driver's automatic AQ strength.

## Routing and the new grain-scale signal

The matched-rate Taxi Driver sample in `FINDINGS-2026-07-17.md` accurately
described the old build, but its routing conclusion is superseded by the
fixed-lattice correction above. The AV1 model was not the primary ceiling:
NVEnc's strength fit was too small. A plain tuned encode remains a useful
control, not the preferred Taxi route solely on the old result.

The new detrended lag-one source correlation cleanly separates the generated
fixtures:

- Fine isotropic grain: -0.002 median.
- Fine grain plus structured detail: -0.003 median.
- Coarse correlated-grain proxy: 0.806 median.

The KAT guard requires coarse correlation at least 0.50 and fine-grain
magnitude at most 0.10. Those are generator-specific regression bounds and
must not be used as production routing thresholds. Six real 4K remasters span
0.33-0.82 continuously; a 0.50 split flags five of six, including four whose
measured retention is 0.88-1.08. The clean fixture separation is therefore a
property of the generated controls, not evidence of bimodal film classes.

`grainCorr` remains useful as a continuous descriptor and as one input to a
failure predictor. It is not an engage/disengage gate by itself. Taxi Driver
was the highest-value targeted case because it combined the highest observed
source correlation (0.823) with the only failing retention result; the
corrected four-scene result shows why routing on that correlation would have
hidden a fixable estimator error.

## Next measurements

The highest-value additions are:

1. Local grain-energy flicker over time, including scene-percentile tails
   rather than only clip means.
2. The quality tooling now records multi-lag spatial autocorrelation. Add
   radial correlation and scene-percentile summaries so grain size is measured
   beyond one neighbouring pixel and one clip mean.
3. Broader matched-quality rate efficiency. The two Silo controls above now
   establish one production operating point, but not a cross-title curve.
4. End-to-end media-minutes/hour, GPU utilization, energy/frame, output bytes,
   and failure rate at each Tdarr concurrency level.

The shared-memory bilateral pass is now implemented. Further CUDA work should
profile fusing its two passes, although the intermediate frame dependency makes
that substantially more complex than fusing independent kernels. Removing a
per-frame host synchronization would require GPU-resident selection or
pipelined one-frame-late decisions and has a larger correctness/latency risk.
