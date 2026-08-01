# Fit the grain model from the source, not from the residual, 2026-08-01

## Result

Estimating the AR model from **plane-removed source flat blocks** instead of
from the separator's residual recovers essentially all of the grain correlation
that production currently loses -- on the fixture, on Taxi Driver, and on
Casino. No encoder change, no denoiser change, no new filter: the same lag-3
solver, run on a different input.

| | fixture `coarse_luma` | Taxi Driver 4K | Casino 4K |
| --- | ---: | ---: | ---: |
| truth, lag-1 / lag-2 | 0.829 / 0.471 | 0.804 / 0.450 | 0.772 / 0.379 |
| **residual fit** (production) | 0.665 / 0.095 | 0.578 / 0.032 | 0.531 / **-0.100** |
| **source fit** | **0.827 / 0.452** | **0.783 / 0.392** | **0.757 / 0.343** |

Production recovers 72-80% of lag-1 and **7-20% of lag-2**. On Casino it gets
lag-2 *backwards*, modelling anti-correlation where the film has +0.379. The
source fit recovers 95-100% of lag-1 and 78-96% of lag-2 on all three.

Amplitude, over the same blocks: truth 7.24 on Taxi, residual 3.97 (55%),
source 7.79 (108%).

## Why this is the fix rather than another separator tweak

The pipeline asks one operator to serve two conflicting objectives: produce a
base that keeps detail, and produce a residual that is a faithful sample of the
grain. The first wants an aggressive, detail-aware filter; the second wants a
filter that touches nothing but grain. No single filter does both, which is why
every separator change moved one at the other's expense and why `psd=on` --
which improved the residual's spectrum -- was a net loss on real film.

Two operators have no such conflict. The denoiser keeps producing the clean
base and is judged only on detail retention and bitrate. The model is estimated
separately from the source and is judged only on statistical fidelity.

The encoder is already most of the way there and discards the answer.
`spatialCorrelation` in `NVEncFilterFilmGrain.cu:299` is a flat-block lag-1
measured on the source; it reads 0.81 on Taxi -- the correct number -- and is
printed as a diagnostic (`grainCorr=` at `:1745`) and never used. The model is
fitted from the residual, which reads 0.58.

## The circularity objection, and why it does not bite

Fitting from the source means fitting from something that still contains
picture, and picture is far more correlated than grain. That objection is real
and is the reason this was not simply assumed. Two independent controls answer
it.

**Ground truth on the fixture.** `coarse_luma` injects grain of known
correlation over a known base, so `source - ideal` is the grain exactly. Running
the identical estimator on that residual is the contamination-free control:

| estimator | sigma | lag-1 | lag-2 |
| --- | ---: | ---: | ---: |
| injected grain (truth) | 5.783 | 0.829 | 0.471 |
| source fit (plane removed) | 5.694 | 0.823 | 0.454 |
| ideal-clean fit (control) | 5.694 | 0.823 | 0.454 |

Source fit and control agree **to every printed digit**. On this fixture the
plane removal leaves no picture at all.

**Ground truth on real film, from time.** Real film has no ideal base, so a
different control is needed. Grain is independent frame to frame and picture is
not, so on a block with no motion `(f_n - f_n+1)/sqrt(2)` is the grain field
with the picture removed exactly. Blocks qualify when their temporal difference
variance is close to their spatial variance -- what independent grain over
identical picture gives, and what motion does not. Selecting on the *ratio*
rather than on the difference variance alone is what keeps this from simply
picking the least-grainy blocks.

The temporal control validates against the fixture's injected truth
(0.832 / 0.479 against 0.829 / 0.471), so it is trustworthy where the injected
truth does not exist. It is the "truth" row for Taxi and Casino above.

**Sensitivity.** If the source fit were reading structure, loosening the flat
mask would admit more structure and inflate it. Sweeping Taxi across an 8x
change in block count:

| flat blocks | 241 | 804 | 2010 |
| --- | ---: | ---: | ---: |
| source fit lag-1 | 0.788 | 0.777 | 0.779 |
| source fit lag-2 | 0.411 | 0.387 | 0.392 |
| source fit sigma | 6.41 | 8.16 | 9.75 |
| residual fit lag-2 | 0.060 | 0.018 | 0.004 |

The **shape is invariant and the amplitude is not**. Correlation is normalised,
so contamination has to beat grain to move it and over flat blocks it does not;
variance is not normalised, so contamination adds to it directly. That splits
cleanly into what can and cannot be taken from a source fit:

- **AR coefficients: take them from the source.** Robust, and the measurement
  that production gets most wrong.
- **Strength curve: do not take it from the source unguarded.** It carries a
  7.6% over-estimate on Taxi at the default mask and worse as the mask loosens.

## The format can carry it

A source fit has a higher variance gain (4.70 against 3.55 on Taxi), so it could
in principle be unrepresentable. It is not:

| | max abs coeff | limit | at `ar_coeff_shift` 6 | int8 range |
| --- | ---: | ---: | ---: | --- |
| residual fit | 0.773 | 2.0 | max abs tap 49 | fits |
| source fit | 1.028 | 2.0 | max abs tap 66 | fits |

Implied ACF at shift 6 is 0.775 / 0.381 against 0.778 / 0.382 unquantised, so
quantisation costs nothing. The encoder's own `|coeff| > 2.0` rejection is not
approached.

Note that a higher variance gain is exactly what saturated the decoder's grain
template before `grain_scale_shift` was derived
(`FINDINGS-2026-08-01-GRAIN-TEMPLATE-CLIPPING.md`). That fix is a prerequisite
for this one: without it, a better-correlated model would have been taxed
harder, which is the mechanism that made every previous improvement backfire.

## What is not established

That this improves perceived quality or compression. It makes the synthesised
grain the right *size*, which is the axis full-reference metrics punish hardest,
so SSIMULACRA2 and Butteraugli should be expected to get worse. The compression
case is separate and stronger: the denoiser is no longer constrained to leave a
faithful residual, so it is free to be more aggressive, and grain it removes is
grain that stops costing bits. Neither is measured yet.

The amplitude path is unresolved. The source over-estimates it and the residual
under-estimates it (55% on Taxi), and the correct target is
`sqrt(source_var - base_var)` over the same blocks -- total grain minus what the
separator left behind. That is one extra launch of the existing flat-metrics
kernel on the clean base, and it is the leakage compensation that is separately
wanted for over-signalled titles.

## Method

`tests/fgs/source_fit.py`. Replicates `kernel_fgs_flat_metrics`' scoring
(including the plane-slope removal before the structure tensor) so block
selection matches the encoder, accumulates the lag-3 normal equations over
block-interior pixels only -- so every tap stays inside the block whose plane
was removed -- and holds that geometry identical across arms. Implied ACF comes
from `ar_acf.implied`, which runs the AV1 spec's own recursion (7.18.3.3) over
the fitted taps.

The implied-ACF simulation is run at innovation sigma 1.0 rather than the
spec's 32. The recursion's autocorrelation is a property of the taps alone, but
its clipping is not, and a gain-4.7 fit saturates the template at sigma 32 --
which would have hidden the fit's behaviour behind the clipping bug. `clip%`
reads 0.00 on every row above.
