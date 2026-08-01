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

---

# Implemented as `modelsrc=on`, 2026-08-01

`e0ca3d3d`. `kernel_fgs_model_stats` fits each block's mean-plus-plane on the
source and takes its AR observations from that instead of from
`residual_at(src, denoised)`. The block plane is fitted cooperatively by the
same 64 threads that draw the samples, and `fgs_stratified_sample_offset`
already keeps every AR tap inside the model block, so one plane per block
covers every pixel it is applied to. Chroma fits a second plane on luma, so
its co-located-luma tap comes from the same domain as the rest of the model.

## The strength curve had to move with it

A source fit measures the **total** grain. The base still carries whatever the
denoiser missed, so synthesising the total on top of it over-delivers -- 1.268x
on Taxi, measured. Subtracting the base's own detrended variance over the same
sample positions leaves exactly the variance that is missing:

    signal_variance = var(detrended source) - var(detrended base)

This also disposes of the picture contamination that the sensitivity sweep
above found in the source amplitude. Whatever structure survives the plane fit
is present in *both* planes -- the denoiser preserves picture, that is its job
-- so it cancels in the difference rather than inflating the curve. The 7.6%
over-estimate needed no separate treatment.

## Delivered, against the temporal ground truth

Decoded with dav1d, measured on flat blocks selected once from the source and
applied unchanged to every arm:

| Taxi Driver | sigma vs truth | lag-1 | lag-2 |
| --- | ---: | ---: | ---: |
| source grain (truth) | 1.000 | 0.804 | 0.450 |
| plain encode, no FGS | 0.540 | 0.856 | 0.654 |
| `modelsrc=off` | 0.832 | 0.620 | 0.226 |
| **`modelsrc=on`** | **1.030** | **0.768** | **0.438** |

| Casino | sigma vs truth | lag-1 | lag-2 |
| --- | ---: | ---: | ---: |
| source grain (truth) | 1.000 | 0.772 | 0.379 |
| plain encode, no FGS | 0.788 | 0.838 | 0.598 |
| `modelsrc=off` | 0.815 | 0.660 | 0.395 |
| **`modelsrc=on`** | **0.948** | **0.791** | **0.554** |

Amplitude error goes from -17% to +3% on Taxi and -19% to -5% on Casino.
Lag-1 error goes from -23% to -4% and from -15% to +2%. Casino overshoots
lag-2 (0.554 against 0.379); its plain encode reads 0.788 amplitude and lag-1
0.838, so a large part of what is being measured in its flat blocks at this
rate is codec ringing rather than grain, and the number should be treated as
softer than Taxi's.

Note the `plain` row on both titles: an encode with no FGS at all keeps only
54-79% of the grain amplitude and replaces it with something *more* correlated
than film grain (lag-1 0.84-0.86, lag-2 0.60-0.65). That is ringing and
blocking, not grain, and it is the reason a whole-frame high-pass estimator
reads plain encodes as retaining more grain than they do.

Bitrate cost of `modelsrc=on`: +0.8% on Taxi, +0.5% on Casino.

## Interaction with the template clipping fix

`grain_scale_shift` rises from 1 to 2 on Taxi on its own, because the source
fit's variance gain is higher (3.711 against 2.648). Without `f92922c2` this
change would have been taxed in proportion to how much correlation it
recovered -- the exact mechanism that made every previous separator
improvement backfire. The two fixes have to ship together.

## Safety

KAT is 22/22 with the flag on and with it off. The film grain table produced
with `modelsrc=off` is **byte-identical** to the one HEAD produces, verified by
building HEAD separately rather than by inspection.

## Determinism and full-fixture recheck, 2026-08-01

The candidate was run three times from the same 24-frame 4K Taxi Driver source,
with identical arguments, for both `bilateral,modelsrc=on` and
`motion,modelsrc=on`.  This was checked below the Matroska container layer so a
random SegmentUID cannot create a false difference:

| arm | table SHA-256s | copied video-stream MD5s | byte sizes |
| --- | --- | --- | --- |
| bilateral + source fit | 3/3 identical | 3/3 identical | 3/3 identical |
| motion + source fit | 3/3 identical | 3/3 identical | 3/3 identical |

The exact hashes were `58698059...4164` / `3cc72761...1374` for bilateral and
`c90be6ad...a5f6` / `3a862932...6b51` for motion.  The candidate binary SHA-256
was `75eb0c01...ba9`.  Source fitting is therefore deterministic in both the
model it writes and the encoded video it drives; this run gives no evidence of
an atomic-order or temporal-state race.

The complete GPU KAT was also rerun with `FGS_KAT_EXTRA=modelsrc=off` and
`FGS_KAT_EXTRA=modelsrc=on`: **22/22 pass in both modes**.  On the known
correlated-grain control, delivered capture moves from 60% (3.59 / 6.01) to
101% (6.05 / 6.01).  The fine-detail, moving-detail, disocclusion, scene-cut,
HDR, chroma, retention and clean-input checks all remain inside their existing
bounds.  Source fit changes the model and synthesis as intended; it does not
change the base, so this does not clear motion's separate disocclusion risk.

## Still open

The default is `off` pending the corpus run. What is measured here is fidelity
to the source's grain statistics, which is not the same as perceived quality,
and full-reference metrics will get worse because the grain is now the right
size (-392 SSIMULACRA2 points per unit of retained grain). The compression case
is the one to press: the denoiser is no longer required to leave a faithful
residual, so it is free to be more aggressive than `bilateral`, and that is
where the missed 30-40% target lives. Nothing here has tested a more aggressive
denoiser under `modelsrc=on` yet -- and that combination, not this commit
alone, is the actual objective.

---

# The compression target is met: `denoiser=motion,modelsrc=on`, 2026-08-01

**NOT YET VALIDATED PERCEPTUALLY. Do not ship on this alone.**

The point of decoupling the model from the residual was that the denoiser stops
having to leave a faithful residual and is free to be more aggressive. Testing
that directly on Taxi Driver, qvbr 29 preset p4, against a 3.41 MB plain encode,
with grain measured on 412 static flat blocks against the temporal truth
(sigma 7.237, lag-1 0.804, lag-2 0.450):

| arm | MB | vs plain | sigma | lag-1 | lag-2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| bilateral `modelsrc=off` | 2.98 | -12.6% | 0.832 | 0.620 | 0.226 |
| bilateral `modelsrc=on` | 3.00 | -11.9% | 1.030 | 0.768 | 0.438 |
| fft3d `modelsrc=off` | 2.91 | -14.6% | 0.866 | 0.638 | 0.216 |
| fft3d `modelsrc=on` | 2.93 | -14.1% | 0.971 | 0.751 | 0.398 |
| motion `modelsrc=off` | 1.86 | -45.4% | 0.887 | 0.671 | 0.297 |
| **motion `modelsrc=on`** | **1.89** | **-44.6%** | **1.023** | **0.753** | **0.402** |

`motion` + `modelsrc=on` saves **44.6%** against the plain encode while
delivering grain that matches the source's statistics as well as bilateral
does. The corpus target was 30-40% on heavy grain and the general library was
managing 17.4%.

`modelsrc` costs 0.5-0.8% of bitrate on every denoiser and buys back roughly
half the missing correlation on all three, so its benefit is independent of
which separator is used.

## The catch, and it is a real one

`motion` was previously rejected for damaging the picture, and **this does not
address that**. The model fix changes what is signalled, not what the denoiser
does to the base. The disocclusion failure is unchanged and is structural:
`coarse_detail_occl` still ranks motion worst by base-vs-ideal edge RMSE
(6.79 against bilateral's 5.11), because content uncovered by a moving object
was never in the previous frame and no temporal predictor can supply it.

Detail damage in the base, on the most textured decile of Taxi's blocks chosen
once from the source and applied unchanged to every arm:

| base | detail corr | HF energy kept | RMSE vs source |
| --- | ---: | ---: | ---: |
| bilateral | 0.9601 | 0.9676 | 5.04 |
| fft3d | 0.9534 | 0.9478 | 5.86 |
| motion | 0.9621 | 0.9668 | **6.72** |

Motion is **best** on detail correlation and HF energy and **worst** on RMSE.
That combination is the signature of correctly-shaped detail in the wrong
place -- ghosting and displacement, which correlation and energy ratios do not
see and absolute error does. It is the same disagreement
`detail_transfer_gain` shows on the moving fixtures, and it is why neither of
those measures may be used alone to rank motion.

So the 44.6% is real and the fidelity is real, but the damage motion does is
also real and is not measured by anything here. **The remaining question is
entirely perceptual and needs the playback A/B.**

## Where this leaves the earlier "motion is catastrophic" result

Suspended, not overturned. Motion's Butteraugli p95 of 53.86 was measured
before `grain_scale_shift` and before `modelsrc`, under a regime that taxed
arms in proportion to the grain correlation they preserved -- and motion
preserved the most. It has not been re-measured since either fix. That number
should not be quoted again until it is.

---

# Six-film corpus gate, 2026-08-01

The Taxi result generalises as a compression result, but unrestricted source
fitting does **not** yet generalise as a safe grain model.  Six 288-frame 4K
lossless excerpts were encoded at qvbr 29 with a plain arm and with
`modelsrc=on` using both bilateral and motion separation:

| title | plain bytes | bilateral bytes | vs plain | motion bytes | vs plain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Taxi Driver | 30,678,671 | 30,589,682 | -0.3% | 19,666,605 | -35.9% |
| Casino | 24,444,601 | 13,826,098 | -43.4% | 9,846,160 | -59.7% |
| The Shining | 15,893,822 | 9,641,094 | -39.3% | 7,336,183 | -53.8% |
| Scarface | 31,029,894 | 20,696,806 | -33.3% | 14,159,983 | -54.4% |
| The Deer Hunter | 30,412,001 | 29,776,484 | -2.1% | 21,719,212 | -28.6% |
| Interstellar | 18,442,464 | 11,510,240 | -37.6% | 8,212,064 | -55.5% |
| **weighted total** | **150,901,453** | **116,040,404** | **-23.1%** | **80,940,207** | **-46.4%** |

The 44.6% Taxi result therefore was not a lucky title.  Aggressive motion
separation clears the 30--40% corpus target; bilateral does not.  This remains
a statement about bytes, not permission to ship motion: its known
disocclusion and misplaced-detail damage is unchanged.

## Grain-texture result

`temporal_grain_report.py` replaces whole-frame `hf_sigma` for this question.
It selects static flat blocks once from the source and estimates the source
grain as `(source[n] - source[n+1]) / sqrt(2)`.  Synthesised grain is measured
independently as decoded grain-on minus decoded grain-off.  Amplitude and
normalised lag-1/lag-2 autocorrelation are reported separately, including in
fixed normalised-luma bands.  Energy therefore stays with the retention
detector and cannot hide a texture error.

| title | source lag-1 / lag-2 | residual-fit bilateral lag-1 | source-fit motion amplitude / lag-1 / lag-2 |
| --- | ---: | ---: | ---: |
| Taxi Driver | 0.805 / 0.456 | 0.569 | 1.034 / 0.797 / 0.456 |
| Casino | 0.739 / 0.305 | 0.523 | 0.892 / 0.767 / 0.381 |
| The Shining | 0.632 / 0.170 | 0.453 | 0.984 / 0.750 / 0.399 |
| Scarface | 0.286 / -0.005 | 0.141 | 0.933 / 0.306 / 0.018 |
| The Deer Hunter | 0.496 / -0.007 | 0.321 | 0.838 / 0.529 / 0.050 |
| Interstellar | 0.707 / 0.334 | 0.503 | 1.044 / 0.835 / 0.592 |

Source fitting reduces the mean absolute lag-1 error from about 0.192 to
0.056 and improves every title.  It also clearly over-correlates The Shining
and Interstellar.  Tightening the flat-block mask from 20% to 2% leaves The
Shining synthesis near 0.757 lag-1 while the source remains near 0.62, and the
fixed luma bands show the same excess in every populated band.  This is not a
dark-film occupancy artifact or a loose-mask artifact.  A mean-plus-plane fit
can still interpret picture structure as grain.

The analyser's independent one-pixel `grainCorr` statistic is much closer to
the temporal truth on all six films (title means 0.811, 0.761, 0.679, 0.300,
0.582 and 0.775 respectively).  It is measured from the source before motion
confidence is applied and is therefore a useful independent regulariser for
the longer AR fit rather than a replacement for it.

## Offline autocorrelation-cap prototype

`cap_table_acf.py` is deliberately an offline table experiment, not production
code.  It simulates each emitted table entry's autocorrelation and uniformly
scales the luma AR coefficients only when implied lag-1 exceeds that entry's
measured `grainCorr` by a conservative 0.05.  It compensates template sigma so
the experiment is meant to change texture rather than energy.  Re-encoding
the emitted clean base with the original table reproduced the original AV1
elementary stream byte-for-byte on The Shining and Interstellar, so the A/B
below isolates the table rule from the separator and encoder.

| title | uncapped amplitude / lag-1 / lag-2 | capped amplitude / lag-1 / lag-2 |
| --- | ---: | ---: |
| Taxi Driver | 1.034 / 0.797 / 0.456 | unchanged |
| Casino | 0.892 / 0.767 / 0.381 | 0.907 / 0.755 / 0.352 |
| The Shining | 0.984 / 0.750 / 0.399 | 0.988 / 0.714 / 0.324 |
| Scarface | 0.933 / 0.306 / 0.018 | unchanged |
| The Deer Hunter | 0.902 / 0.578 / 0.142 | 1.053 / 0.539 / 0.050 (expanded sample) |
| Interstellar | 1.044 / 0.835 / 0.592 | 1.069 / 0.794 / 0.500 |

On the initial common frame set, mean lag-1 error falls another 27%, from about
0.056 to 0.041; lag-2 error falls about 31%, from 0.107 to 0.074.  Correct Taxi
Driver and Scarface entries are untouched.  An expanded Deer Hunter sample
then exposed the decisive failure in the strength compensation.  At frame 275,
source truth is lag-1 0.621 / lag-2 0.111.  The cap correctly moves synthesis
from 0.876 / 0.695 to 0.601 / 0.049, but its simulated template-gain correction
raises amplitude from an already-high 1.283 to **2.339**.  The near-unstable
source fit asked for a 3.80x strength correction; realised decoder gain is not
linear in that estimate.  Interstellar also rises from 1.044 to 1.069.

The correlation bound is promising, but the current strength compensation is
unsafe.  An implementation must either recompute gain from the regularised
regression before quantisation and validate the realised decoder template, or
reject/hold a fit that would require a large correction.  A hard correction
bound and explicit affected-interval coverage are requirements before C++.
The offline tool now defaults to rejecting any entry that would need more than
1.25x strength (`--max-strength-gain`); on the Deer Hunter table it adjusts the
ordinary 1.14x entry and preserves/rejects the pathological 3.80x entry.

## Labelled negative and libaom arm

The new temporal report was run against the retained r4047 widening / r4050
corrected Taxi pair.  Both tables were applied to one byte-identical clean
base.  The widened table moves synthesis amplitude from 0.576 to 0.642 and
lag-1 from 0.561 to 0.596; the difference appears in every populated luma band.
This proves the detector can see the known change rather than merely returning
plausible values on good controls.  It does not call widening "worse" in
isolation: the production r4047 defect was substitution caused by the changed
base as well as the changed table, and that judgement belongs to base fidelity.

libaom was then fitted to each motion-clean base and its table was synthesised
through the same NVEncC application path.  The existing oracle's
source-minus-clean texture score is not the deciding number here: it gives
libaom the residual it was fitted to while `modelsrc` deliberately fits total
source grain.  Scoring both synthesis layers against the independent temporal
source truth removes that asymmetry:

| title | source lag-1 / lag-2 | source-fit amp / lag-1 / lag-2 | libaom amp / lag-1 / lag-2 |
| --- | ---: | ---: | ---: |
| Taxi Driver | 0.803 / 0.451 | **0.986 / 0.795 / 0.443** | 0.596 / 0.667 / 0.225 |
| The Shining | 0.624 / 0.152 | 0.889 / 0.755 / 0.412 | 0.685 / 0.544 / 0.072 |
| Interstellar | 0.718 / 0.333 | 0.982 / 0.863 / 0.655 | 0.564 / 0.609 / 0.213 |

Taxi confirms source fitting can beat the conventional residual analyser on
both energy and texture.  The Shining and Interstellar show the opposite split:
libaom is closer in texture but throws away 31--44% of amplitude, while source
fit gets amplitude right and over-correlates.  This rules out "the compact AV1
model cannot express it" as the explanation for those two source-fit failures.
It also rules out reverting wholesale to the residual model.  The useful next
candidate is source-derived strength and long-range shape, regularised by the
independent one-pixel source correlation, with gain recomputed from the
regularised regression rather than patched after table quantisation.

## Decision

Keep `modelsrc` default-off and experimental.  The restructuring is viable:
it recovers the right grain band, substantially improves texture on every
real title tested, and makes the compression target achievable.  The current
unrestricted source AR fit is not production-ready, and motion remains a
separate perceptual blocker.  The next safe step is to validate the cap on
every affected interval, bound its amplitude change, then implement a precise
deterministic regulariser and rerun KAT, this corpus and the known-bad texture
pair.  Do not flip the default or deploy the motion arm before that gate.
