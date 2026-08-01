# The separator is what loses the grain's spatial correlation, 2026-08-01

## Result

`FINDINGS-2026-08-01-RETENTION-DECOMPOSITION.md` established that synthesised
grain is the right strength and the wrong size: amplitude within ~8% of source,
lag-1 autocorrelation at 0.43-0.72 of it. It left the cause open between the
separator and the AR fit, and guessed at the AR fit.

That guess was wrong. Splitting the chain stage by stage puts the entire loss in
the separator, and the production denoiser is the worst of the three shipped.

The fix already exists, unmerged and off by default. `fft3d` with per-bin noise
PSD shaping (branch `fgs/fft3d-noise-psd`, `psd=on`) recovers lag-2 retention
from 0.325 to **0.857** against ground truth and lifts residual capture from
56.8% to **77.1%** --- better than any shipped denoiser, and for the reason the
mechanism predicts.

## The chain, on ground truth

Real film cannot answer this. A source's own autocorrelation is inflated by
picture structure that no flat-block mask fully removes, so "Taxi Driver source
0.811 -> residual 0.601" is not evidence of whitening. The `coarse_luma` KAT
fixture injects grain of known correlation onto a smooth base and writes the
ideal clean base alongside, so the injected grain is exactly source minus ideal.

Injected truth: sigma 6.012, lag-1 **0.839**, lag-2 **0.499**.

| denoiser | residual sigma | residual lag1 | residual lag2 | implied lag1 | implied lag2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| bilateral | 2.681 (44.6%) | 0.655 | **0.105** | 0.655 | 0.075 |
| fft3d | 3.413 (56.8%) | 0.687 | **0.162** | 0.709 | 0.170 |
| motion | 3.900 (64.9%) | **0.797** | **0.415** | 0.773 | 0.342 |
| fft3d + `psd=on` | 4.637 (**77.1%**) | **0.801** | **0.428** | 0.782 | 0.352 |

"Implied" is the correlation the fitted AR coefficients encode, obtained by
running the spec's AR recursion over them (`ar_acf.py`). **It tracks the
residual to within 0.01-0.02 on lag-1 in every arm.** The fit is not losing
anything; it is faithfully reproducing a residual that arrives already whitened.

The decoder is not losing anything either. On Taxi Driver the fitted
coefficients imply lag-1 0.604 and the decoded synth layer measures 0.569.

And it is not our solver. libaom's `noise_model` fitted to the *identical*
residual implies lag-1 0.593 against our 0.604 on Taxi and 0.559 against 0.567
on Casino, with AR cosine similarity 0.997 and 0.999. Both fitters agree,
because both are given the same whitened input.

## The mechanism: the separator is a high-pass

The row that names it is the grain **left behind** in the clean base:

| denoiser | leftover sigma | leftover lag1 | leftover lag2 |
| --- | ---: | ---: | ---: |
| bilateral | 4.166 | 0.910 | **0.711** |
| fft3d | 3.790 | 0.912 | **0.737** |
| motion | 3.212 | 0.886 | **0.643** |
| fft3d + `psd=on` | 2.599 | 0.889 | 0.715 |

The grain the separator fails to extract is *more* correlated than the grain
that went in (0.711 against 0.499). It keeps the fine, near-white end of the
grain spectrum and leaves the coarse end in the base, where the encoder then
spends bits on it or quantises it away.

That single fact explains the whole cluster of open symptoms: the 36-45% capture
ratio, the "right strength wrong size" synthesis, and why coarse 35mm is the
worst case. They are one defect seen from three directions.

### Why `psd=on` is the matching fix and not a coincidence

FFT3D's Wiener rule is `gain = (P - sigma) / P` with a **scalar** sigma
(`NVEncFilterDenoiseFFT3D.cuh:366`). A scalar sigma is the statement that the
noise is white --- equal power in every frequency bin. Coarse film grain is the
opposite: its power is concentrated at low and mid spatial frequencies. So the
rule subtracts a flat noise floor from a sloped noise spectrum, over-removing
where grain is weak and under-removing where it is strong. The extracted
residual is whitened by construction, and what is left behind is the coarse tail
--- which is exactly the leftover-correlation row above.

Shaping sigma per bin by an AR(1) PSD removes that assumption, and the measured
effect is the one predicted: capture 56.8% -> 77.1%, lag-2 retention
0.325 -> 0.857. The mechanism was identified independently of this measurement
(`FINDINGS-2026-07-31-WIENER-PSD.md`), which is why the agreement carries weight.

**The earlier evaluation of `psd=on` understated it badly.** It was recorded as
"coarse capture 41% -> 45%", measured end-to-end after encode and decode with
the whole-frame estimator. Measured at the stage the change actually acts on,
the separator output, it is 56.8% -> 77.1%. The change was nearly shelved on a
number produced by the same estimator that has now misled this work three times.

## Real film reproduces the ranking

Taxi Driver, 4K, source lag-1 0.811 / lag-2 0.477 (structure-inflated, so read
the ordering rather than the absolute):

| denoiser | residual sigma | residual lag1 | residual lag2 |
| --- | ---: | ---: | ---: |
| bilateral | 1.122 | 0.601 | **0.095** |
| fft3d | 1.532 | 0.682 | **0.201** |
| motion | 1.409 | **0.733** | **0.337** |
| fft3d + `psd=on` | 1.943 | **0.785** | **0.434** |
| *source* | *2.353* | *0.811* | *0.477* |

Same order, same magnitude of separation. `psd=on` recovers a residual whose
correlation is within a few percent of the source's on both lags, on real 35mm.
Casino behaves the same way.

## The production setting is the worst arm

`denoiser=bilateral` is what the tdarr integration path, `campaign.py`'s
consumers, and essentially every script under `/opt/docker-apps/scripts` pass.
NVEncC's own default is `fft3d`; `bilateral` was chosen deliberately.

The reason is recorded in `silo_fgs_retest.py`:

> `denoiser=bilateral` beats both `fft3d` (NVEncC's default) and `motion`
> (campaign.py's default) by a wide margin on exactly these reference metrics --
> SSIMULACRA2 30.50 vs 14.77 at equal retention.

Both halves of that justification fail against what is now measured.

**The metric is biased in exactly this direction.** `/opt/docker-apps/docs`
measures SSIMULACRA2 at **-392 points per unit of grain retention**: correctly
randomised grain is a new realisation, so a full-reference metric scores it as
error and rewards whichever denoiser destroys the most grain. Selecting a
separator on SSIMULACRA2 selects for grain destruction almost by construction,
and bilateral won because it discards the most.

**"At equal retention" was measured with the broken estimator.** Retention there
is `campaign.py::hf_sigma`, which high-passes the whole frame and therefore
counts encoder ringing as grain --- already documented in
`FINDINGS-2026-08-01-RETENTION-DECOMPOSITION.md` as having produced three false
findings in one session. It is also, being a high-pass, blind to precisely the
coarse-versus-fine distinction that separates these three denoisers. Bilateral
and motion can read "equal retention" on it while differing 4x in lag-2.

## What this does not yet establish

The separator is localised; the deployment decision is not made. `motion` costs
throughput (37.9 fps against fft3d's ... see the campaign table below once
complete) and its full-reference metrics will be *worse*, for the reason above.
That is expected and is not by itself an argument against it, but neither is
this measurement an argument for shipping it: nothing here shows a viewer
prefers the result. The release gate remains a playback A/B.

What has changed is that the choice is now made on a quantity that is not
metric-biased. Lag-2 retention against ground truth is 0.211 for bilateral and
0.832 for motion, and no part of that comparison passes through a
full-reference metric or through `hf_sigma`.

## Method

`separator_acf.py --denoiser {bilateral,fft3d,motion}` on `coarse_luma`;
`layer_acf.py --clean` for the real-film residuals; `ar_acf.py` for the implied
correlation; `reference_compare_real.py` for the libaom oracle. `ar_acf.py` is
validated against constructed tables: a 0.5 horizontal tap returns h1 0.506, a
0.797 tap returns h1 0.798 with h2 0.638 = rho^2, zero taps return 0.001.
`layer_acf.py` detrends with a box mean rather than a high-pass, and the
synthesised layer is invariant to the radius (0.569 at r=4 through 0.571 at
r=16) because it has no structure to remove --- the control that the operator is
not what creates the gap.
