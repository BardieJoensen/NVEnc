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

These commits modify `NVEncFilterFilmGrain.cu` and
`NVEncFilmGrainModel.{h,cpp}` and therefore require rebuilding NVEncC; they are
not test-only changes.

All 17 GPU known-answer fixtures, both 8/10-bit retention sweeps (10 points),
the CPU solver and parser tests pass. Headline quality metrics and every
retention-sweep encoded byte count are unchanged.

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
| Coarse-grain amplitude captured | 36% | 32% |

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

The matched-rate Taxi Driver sample in `FINDINGS-2026-07-17.md` remains a
useful routing hypothesis: on that sample, a plain tuned encode beat FGS
because the synthesized field carried the wrong spatial texture. It does not
establish a general coarse-film rule.

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
is the most useful targeted validation case because it combines the highest
observed source correlation (0.823) with the only failing retention result
(0.68 across four scenes).

## Next measurements

The highest-value additions are:

1. Local grain-energy flicker over time, including scene-percentile tails
   rather than only clip means.
2. Multi-lag and radial grain autocorrelation so grain size is measured beyond
   a single neighbouring pixel.
3. Broader matched-quality rate efficiency. The two Silo controls above now
   establish one production operating point, but not a cross-title curve.
4. End-to-end media-minutes/hour, GPU utilization, energy/frame, output bytes,
   and failure rate at each Tdarr concurrency level.

Further CUDA work should profile a shared-memory or fused bilateral pass.
Removing a per-frame host synchronization would require GPU-resident selection
or pipelined one-frame-late decisions and has a larger correctness/latency risk.
