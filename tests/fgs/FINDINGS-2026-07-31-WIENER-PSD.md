# Coarse-grain plan: a per-bin noise PSD for the FFT3D denoiser, 2026-07-31

## Result

The FFT3D denoiser already applies a Wiener gain, but against a **scalar**
noise power. libaom's `aom_wiener_denoise_2d` applies the same gain against a
**per-frequency-bin** noise PSD. A scalar is equivalent to asserting the grain
is white, which is exactly wrong for the coarse correlated grain that this
project has repeatedly failed to capture.

`wiener_psd_sim.py` reproduces FFT3D's rule offline on the KAT's `coarse_luma`
grain generator and compares the two:

| arm | capture | detail |
| --- | ---: | ---: |
| A. scalar sigma (current NVEnc) | 0.366 | 0.829 |
| B. exact noise PSD (libaom-style) | **0.699** | **0.986** |
| C. AR(1) PSD from lag-one correlation only | 0.505 | 0.892 |

`capture` is residual sigma over injected sigma; `detail` is the high-pass
energy of the base over that of the clean signal. Arm A reproducing 0.366
against the 35.7-41% coarse capture measured on the real encoder is what makes
the rest of the table worth acting on -- the simulation is reproducing the
existing failure, not a toy.

The important property is that B and C improve capture **and** detail at the
same time. They are not trading base fidelity for grain energy.

## Why this is not the rejected widening experiment

`d23400f4`/`d807b990` attacked the same target by widening the bilateral
spatial kernel and were reverted in `a4b84e1a`. The 2026-07-29 notes diagnosed
that correctly: it "reallocates texture rather than improving retention" --
total decoded HF energy was unchanged because a wider spatial kernel removes
grain and detail at low frequencies indiscriminately.

A PSD-shaped Wiener gain is a different operation. It attenuates each frequency
bin by that bin's noise-to-total power ratio, so a bin dominated by picture
detail keeps its energy while a bin dominated by grain loses it. That
discrimination is not expressible as a spatial kernel width, which is why the
simulation shows detail *improving* (0.829 -> 0.892/0.986) while capture rises.

## Expected real-world gain is bounded, and by the format

`FINDINGS-2026-07-17.md` measured the ceiling: on coarse correlated grain NVEnc
reproduces 35.7% of source sigma while **libaom with an ideal clean base
reproduces 46.3%**. An ideal clean base means the denoiser was handed the true
signal, so 46.3% is the compact AV1 AR model's representational limit for this
grain stock, not a denoiser result.

The simulation measures the denoiser's residual capture, which is upstream of
the AR fit, so its +38% (arm C) does not transfer one-for-one. The realistic
target is to move final coarse capture from ~41% toward ~46%, roughly +13%
relative. Anything beyond that requires a different synthesis model, not a
better denoiser. This should be stated in any A/B so the result is not judged
against an impossible target.

Fine grain needs no help: FFT3D already lands at 0.98-1.02 of source sigma.

## Arm C is the implementable one

Arm B needs the true noise PSD, which is not available at encode time. Arm C
derives the shape from a single lag-one autocorrelation via the separable AR(1)
form `(1-rho^2)/(1 - 2*rho*cos(w) + rho^2)`, normalised to mean 1.

Two properties make this cheap:

- NVEnc **already measures rho** as `FilmGrainBlockMetric::spatialCorrelation`
  (`NVEncFilterFilmGrain.cu:295`), currently diagnostic-only. The 2026-07-29
  notes kept it deliberately: "Correlation stays in diagnostics for measurement
  and future research."
- Normalising to mean 1 means `rho = 0` reproduces the scalar case exactly, so
  white-grain content and the whole non-FGS `--vpp-denoise-fft3d` path stay
  bit-identical.

## Implementation plan

Not yet started. This touches a filter shared with the general vpp pipeline, so
the default must stay bit-exact.

1. `NVEncFilterDenoiseFFT3D.cuh`: `temporal_filter` takes an optional
   `const float *psdShape`; the Wiener line becomes
   `factor = max(limit, (power - sigma * shape[bin]) / power)` with
   `shape == nullptr` preserving today's arithmetic exactly.
2. `NVEncFilterDenoiseFFT3D.{h,cpp}`: an optional `block_size * block_size`
   device buffer on the param struct, null by default.
3. `NVEncFilterFilmGrain.cu`: aggregate the per-block `spatialCorrelation` the
   analyzer already produces into a frame rho, build the AR(1) table, upload it
   alongside the existing per-frame sigma reprogramming (`:1101`).
4. Gate it behind an explicit option rather than enabling it by default, so the
   production bilateral path and existing FFT3D users are unaffected.

## Verification plan

- `--vpp-denoise-fft3d` and FGS with the option off must produce identical
  video stream MD5s (the shape defaults to null).
- `coarse_luma` KAT capture ratio is the primary signal; it is currently
  guarded at 0.30 with an actual capture of 36-41%.
- `detail_luma` and the structured-edge RMSE guard must not regress -- the
  simulation predicts they improve, so a regression there falsifies the model.
- Real film last. FFT3D currently *loses* to bilateral on the Silo real-title
  comparison (SSIMULACRA2 80.02 vs 78.87), so this improves the arm that is
  behind; a real-title win is the bar for changing the production denoiser, and
  the 2026-07-30 texture report plus a playback A/B are the gate, not
  full-reference metrics.

Netflix independently reached the same conclusion about the metrics: they have
no dedicated quality model for FGS, note that PSNR and VMAF are "penalized"
because synthesized grain lands at different pixel positions, and validated
theirs by internal assessment and A/B over roughly 300 titles.

## Where NVEnc already beats libaom

Relevant because it calibrates how much of the gap is NVEnc's to close.
From `FINDINGS-2026-07-30-TEXTURE.md`, amplitude-independent texture distance
to the source residual (lower is better), same clean base for both arms:

| clip | spectrum TV (NVEnc / libaom) | ACF RMSE (NVEnc / libaom) |
| --- | --- | --- |
| Casino | **0.0497** / 0.0557 | **0.0202** / 0.0387 |
| Taxi | **0.0550** / 0.0572 | 0.0376 / **0.0349** |
| Shining | 0.0370 / **0.0344** | **0.0156** / **0.0169** |
| Silo | 0.0491 / **0.0341** | 0.0204 / **0.0142** |

Casino favours NVEnc on both measures, by 11% and 48%. Taxi favours NVEnc on
spectrum TV, Shining on ACF RMSE. Silo is libaom's clearest win. The corrected
Taxi strength fit is also closer to the measured residual than libaom's on two
of four scenes (`FINDINGS-2026-07-29-PERFORMANCE.md`). NVEnc is not uniformly
behind the reference; the coarse-grain case is a specific defect, not a general
deficit.
