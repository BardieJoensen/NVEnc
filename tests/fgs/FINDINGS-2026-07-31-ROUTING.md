# Heavy-grain routing re-test, 2026-07-31

## Result

`FINDINGS-2026-07-17.md` concluded that the coarsest 35mm stock "is the worst
case for this feature, not the best, and is better served by a plain tuned
encode". That is no longer true.

At an equal VBR budget on real 4K film, FGS lands closer to the source's own
grain energy than a plain tuned encode on every title tested, at equal or
smaller size:

| title | grainCorr | src HF | plain: MB / retention (err) | FGS: MB / retention (err) |
| --- | ---: | ---: | --- | --- |
| Taxi Driver | 0.811 | 2.46 | 50.7 / 0.805 (0.195) | 51.0 (+0.6%) / 0.919 (**0.081**) |
| Casino | 0.779 | 1.57 | 49.9 / 0.803 (0.197) | 44.8 (**-10.2%**) / 0.917 (**0.083**) |
| The Shining | 0.670 | 1.30 | 51.2 / 0.623 (0.377) | 47.0 (**-8.2%**) / 1.154 (**0.154**) |
| Scarface | 0.302 | 6.11 | 49.6 / 0.556 (0.444) | 49.4 (-0.4%) / 1.018 (**0.018**) |

`err` is distance from 1.000. FGS is 2.4x closer on Taxi, Casino and Shining,
and 25x closer on Scarface. The plain arm is not merely worse, it degrades
sharply as grain gets finer: 0.80 on the two coarse titles, 0.62 on Shining,
0.56 on Scarface. Fine grain is high-frequency and is the first thing
quantization removes; coarse grain partly survives because it lives at low
frequencies the encoder preserves anyway.

## Mean metrics favour plain, tail metrics favour FGS

The full-reference battery splits cleanly and consistently:

| title | arm | VMAF | VMAF NEG | SSIMU2 | SSIMU2 p5 | Butt 2n | Butt p95 | PSNR-Y |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Taxi | plain | **94.25** | **93.27** | **29.31** | 8.93 | **2.278** | 13.77 | **43.98** |
| Taxi | fgs | 89.72 | 89.39 | 18.39 | **10.90** | 2.747 | **11.07** | 41.16 |
| Casino | plain | **97.18** | **96.41** | **63.64** | 53.10 | **1.204** | 9.09 | **49.09** |
| Casino | fgs | 94.92 | 94.51 | 60.18 | **55.24** | 1.489 | **7.05** | 45.79 |
| Shining | plain | **98.26** | **97.54** | **41.81** | 24.63 | **1.811** | 8.97 | **48.61** |
| Shining | fgs | 96.37 | 95.91 | 34.28 | **25.04** | 2.251 | **8.70** | 45.72 |
| Scarface | plain | **92.05** | **91.08** | -0.22 | -15.75 | **2.799** | 12.99 | **39.84** |
| Scarface | fgs | 90.82 | 90.01 | **1.63** | **-4.40** | 3.007 | **9.83** | 36.45 |

Lower is better for Butteraugli. Every mean metric favours the plain arm.
**Every tail metric favours FGS: SSIMULACRA2 p5 and Butteraugli max-p95 both
win on all four titles.**

That split is the point. If synthesis were simply worse, it would lose on the
tails too. Instead the uniform pixel-misalignment penalty depresses the mean
while the worst frames -- where the plain encode runs out of bits and smears
grain into blocking -- are measurably better protected. Read alongside
retention, this is the same conclusion the grain descriptors give.

Scarface is the clearest case: FGS wins SSIMULACRA2 mean *and* p5, Butteraugli
p95, and VMAF minimum. Only VMAF mean and PSNR favour plain there.

## Why the old conclusion was correct when written

The 07-17 build's sparse AR estimator sampled a fixed 8x8 lattice in every
32x32 model block. On real film that lattice aliased the spatial correlation
and inflated the fitted AR synthesis gain, and because the strength curve is
divided by that gain once, the encoder signalled roughly half the grain
amplitude it should have. `09dae08c` replaced it with deterministic
block-staggered stratified sampling.

The 07-17 routing conclusion was therefore a measurement of an analyzer defect,
not of the AV1 format or of coarse grain. `FINDINGS-2026-07-29-PERFORMANCE.md`
already superseded it on synthesis amplitude and said explicitly that the
matched-rate confirmation was still missing. This is that confirmation.

## Method

`routing_check.py`, which reuses the `campaign.py` and `matched_rate_sweep.py`
primitives. Per title: one plain tuned encode and one FGS encode at the same
`--vbr 31700`, 288 frames of 4K 10-bit, scored against a lossless ffvhuff
reference built from the same master.

Sources are the preserved lossless FFV1 masters in
`test-encodes/keep-original/`, not library transcodes. `denoiser=bilateral`,
the measured production setting, not the `fft3d` default.

Source grain characterisation over the corpus, from the analyzer's own
`grainCorr` and `noise` diagnostics:

| title | grainCorr | noise (8-bit sigma) | character |
| --- | ---: | ---: | --- |
| Taxi Driver | 0.811 | 5.41 | coarse, heavy |
| Casino | 0.779 | 3.50 | coarse, moderate |
| The Shining | 0.670 | 3.21 | coarse, light |
| The Deer Hunter | 0.570 | 10.80 | mid, very heavy |
| Scarface | 0.302 | 10.80 | fine, very heavy |

These reproduce the values recorded on earlier builds (Taxi 0.811 against 0.823,
Shining 0.670 against 0.696), so the analyzer is stable across the rebuilds.
Scarface is the control: the heaviest grain in the corpus but nearly
uncorrelated, so it separates "FGS fails on lots of grain" from "FGS fails on
coarse grain".

### A harness defect this exposed

`matched_rate_sweep.encode()` hardcodes `--avhw`. Every preserved master in
`keep-original/` is lossless FFV1, which NVDEC cannot decode, so that script
fails outright against this corpus with "codec ffv1(yuv420p10le) unable to
decode by cuvid". `routing_check.py` uses `--avsw`, which is also the
deterministic path for a fixed fixture. The defect remains in
`matched_rate_sweep.py`.

## A prediction that failed, and what it leaves

Shining over-signals (1.154) where Taxi and Casino under-signal (~0.92). The
obvious hypothesis was that the AR model overshoots on fine grain, which
predicted Scarface -- the finest grain in the corpus, lag-one -0.027 -- would
overshoot hardest. It did the opposite: 1.018, the most accurate of the four.

So FGS accuracy does not track grain fineness. What separates Shining is the
*shape* of its autocorrelation, not its magnitude:

| title | acf lag 1 / 2 / 3 | FGS retention |
| --- | --- | ---: |
| Taxi | 0.355 / 0.156 / 0.084 | 0.919 |
| Casino | 0.313 / 0.123 / 0.122 | 0.917 |
| Scarface | -0.027 / -0.023 / 0.032 | **1.018** |
| The Shining | 0.333 / **-0.035 / -0.052** | **1.154** |

White (Scarface) and monotone-decaying (Taxi, Casino) are both handled well.
Shining is the only non-monotone profile -- positive at lag one, negative
beyond -- and the only significant overshoot. That is an observation on four
titles, not a mechanism: the AV1 AR model has 24 free coefficients and can in
principle represent negative lags, so the error may originate in the strength
curve or the separator rather than the AR fit. It is worth one targeted
experiment before being treated as real.

## What this does not establish

Retention is grain *energy*. Energy alone cannot distinguish correctly-sized
grain from wrong-sized grain, which is the entire reason
`FINDINGS-2026-07-30-TEXTURE.md` exists. These pairs should be run through the
texture report before the routing rule is changed in production.

The mean full-reference metrics favour the plain arm on every title, and that
is not dismissed by calling it a known bias -- it is a real pixel-level
difference. The argument for reading it as bias rather than as regression is
that the tails move the other way on all four titles at once, which a genuine
quality loss would not do. A playback A/B remains the release gate.

Netflix reports the same limitation from the other direction: no dedicated
quality model for FGS, PSNR and VMAF "penalized" for exactly this reason, and
validation by internal assessment plus A/B over roughly 300 titles.
