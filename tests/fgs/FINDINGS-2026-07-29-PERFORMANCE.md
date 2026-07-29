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
production r4029 build and the clean-image r4033 build. End to end, r4033
roughly doubled FGS throughput and removed the old 91% FGS penalty. On this
input the optimized FGS encode even finished before the no-FGS control:
denoising reduced the residual that NVENC had to code, producing a 4.24 MB
stream instead of 5.79 MB, and that encoder saving more than paid for the
analyzer.

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
3. Matched-quality rate efficiency (bytes at a fixed quality target), alongside
   matched-rate quality; QVBR-only comparisons can hide the routing decision.
4. End-to-end media-minutes/hour, GPU utilization, energy/frame, output bytes,
   and failure rate at each Tdarr concurrency level.

Further CUDA work should profile a shared-memory or fused bilateral pass.
Removing a per-frame host synchronization would require GPU-resident selection
or pipelined one-frame-late decisions and has a larger correctness/latency risk.
