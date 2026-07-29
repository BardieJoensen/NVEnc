# AV1 film-grain performance follow-up — 2026-07-29

## Result

Two CUDA changes reduce the analyzer's measured film-grain kernel time by
about 82% on the production bilateral path without changing encoded output:

- `170b9a4c`: replace FP64 flat analysis and shared 64-bit model-stat atomics
  with FP32 residual analysis and local normal-equation accumulation.
- `1fa517e3`: process each 32x32 flat-analysis block with 128 CUDA threads
  instead of one serial CUDA thread.

`77e8329a` adds a source-grain scale diagnostic. It costs about 0.009 ms/frame
at 1080p and does not affect the model or encoded pixels.

All 17 GPU known-answer fixtures, both 8/10-bit retention sweeps (10 points),
the CPU solver and parser tests pass. Headline quality metrics and every
retention-sweep encoded byte count are unchanged.

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

Disabling chroma analysis on the same fixture reduces current FGS kernel work
from 0.5875 to about 0.398 ms/frame (-32%). It is only safe when the source has
negligible chroma grain. A future optimization could make `chroma=auto`
periodically classify and bypass clean chroma, re-enabling analysis at scene
changes.

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
strength somewhat better. FFT3D is stronger overall for luma grain fidelity
and edge distortion. For representable fine grain, the quality-first setting
remains:

```text
--av1-film-grain denoise=auto,chroma=auto,denoiser=fft3d,retain=auto
```

## Routing and the new grain-scale signal

The matched-rate result in `FINDINGS-2026-07-17.md` remains the largest quality
opportunity: coarse 35 mm grain should use a plain tuned encode because AV1's
compact grain model reproduces the energy with the wrong spatial texture.

The new detrended lag-one source correlation cleanly separates the generated
fixtures:

- Fine isotropic grain: -0.002 median.
- Fine grain plus structured detail: -0.003 median.
- Coarse correlated-grain proxy: 0.806 median.

The KAT guard requires coarse correlation at least 0.50 and fine-grain
magnitude at most 0.10. Those are regression bounds, not production routing
thresholds. A scene-labeled real-title calibration should precede automatic
Tdarr routing.

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
