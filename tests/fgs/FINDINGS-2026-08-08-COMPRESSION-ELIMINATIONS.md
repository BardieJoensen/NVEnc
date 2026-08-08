# Compressive response: what it is not — 2026-08-08

## The effect, on the deployed encoder

Retention (delivered grain / source grain), production settings, verifier's own
metric, from originals:

| title | source HF | retention |
| --- | ---: | ---: |
| Long Halloween | 1.479 | **1.325** |
| Silo S03E06 | 3.869 | 0.971 |
| Sugar S02E08 | 5.177 | 0.918 |
| Elemental | 6.029 | 0.922 |

**log-log slope `-0.274`, `r = -0.985`** -> `delivered ~ source^0.726`.
Independently reproduces the `source^0.630` measured on emitted curves with a
different instrument and corpus.

**Crossover at source HF ~ 3.95.** Below it the encoder over-synthesises; above
it it slightly under-delivers. That explains the library batch shape directly:
the "light" grain bucket is worst (1.436) because light grain sits below the
crossover, while moderate and heavy sit above it.

It also corrects an assumption of mine: over-synthesis is **not** the general
behaviour. Three of these four titles under-deliver at baseline.

## Eliminated by direct experiment

| candidate | verdict | evidence |
| --- | --- | --- |
| flat-block selection ranking | **falsified** | removing the `-6682*varNorm` penalty made retention *worse* on 4/4 weak titles (Elemental 0.922->1.542, Long Halloween 1.325->2.019). The penalty is load-bearing: it suppresses blocks whose variance is texture, not grain |
| selection floor (`minNoiseLevel`) | does not bind | 0.05 and 0.5 admit the same 208 blocks |
| denoise floor | does not bind | 0.5 / 0.20 / 0.05 give byte-identical output on the residual path |
| scaling-point quantisation | too fine | one step is 0.6--6.7% of emitted values |
| AR-gain accounting | exact | realized vs fitted gain, slope `-0.981` against a coded `-1` |
| denoiser response shape | ~6% of the effect | bilateral slope `-0.258` vs fft3d `-0.242`; swapping the whole algorithm barely moves it |
| mean-of-variances inflation | no relationship | inflation vs grain level slope `+0.041`, `r = +0.295` -- wrong sign |

Seven candidates, seven eliminations. The arithmetic from measured variance to
delivered amplitude is correct at every step that has been checked.

## What survives

**The emission cadence.** `FGS_MODEL_MIN_UPDATE_FRAMES = 24` forces >= 24
frames between signalled models, and measured interval lengths sit at 25 on 8 of
9 titles -- the floor plus one. The fit refreshes every 8 frames and is held to
a third of that rate, so one model covers content whose grain moved, fitted at
the moment of acceptance. See `FINDINGS-2026-08-08-EMISSION-CADENCE.md`.

This is the only remaining candidate with direct evidence behind it, and it is
temporal rather than spatial -- which is consistent with every spatial
hypothesis above having failed.

**Untested:** per-luma-bin aggregation across scenes with differing grain, which
is the spatial partner to the cadence problem and was never isolated.

## Method note

Two hypotheses in this session were supported by offline emulation and then
falsified by direct experiment on the encoder. Emulating a mechanism in Python
and reproducing the *symptom* does not establish that changing that mechanism
in the encoder removes it. Only the direct arm counts.
