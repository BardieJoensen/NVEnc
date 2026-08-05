# Chroma does not need covariance closure — 2026-08-05

> Offline measurement only. Nothing deployed, `modelsrc` default-off.

Run before building a chroma version of `texture_leak_oracle.py`, to check that
the mechanism which produced luma's `-76.6%` played-texture result applies to
U/V at all. **It does not, and the oracle should not be built.**

## The question

`FINDINGS-2026-08-04-TEXTURE-LEAK-CLOSURE.md` justified covariance subtraction
with a specific diagnostic: on Coming to America the *base* retained texture at
lag-1 `0.928` against a source of `0.625`, so adding a source-shaped AR model
on top pushed played correlation to `0.693` when the target was `0.585`. Base
amplitude there was `0.343`, i.e. 11.8% of source variance — enough covariance
to matter.

The same diagnostic on U/V, current candidate, six frame pairs:

| cell | source l1/l2 | base l1/l2 | base amp | base var | synth | needed for 1.000 | over | played total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Taxi U | 0.615/0.218 | 0.837/0.716 | 0.116 | 1.3% | 0.956 | 0.993 | 0.96x | 0.962 |
| Taxi V | 0.638/0.249 | 0.784/0.653 | 0.113 | 1.3% | 1.073 | 0.994 | 1.08x | 1.079 |
| Shining U | 0.570/0.152 | 0.773/0.629 | 0.191 | 3.6% | 0.913 | 0.982 | 0.93x | 0.936 |
| **Shining V** | 0.668/0.405 | 0.746/0.598 | **0.469** | **22.0%** | 1.158 | 0.883 | **1.31x** | **1.267** |
| Casino U | 0.491/0.093 | 0.895/0.761 | 0.226 | 5.1% | 0.958 | 0.974 | 0.98x | 0.984 |
| Casino V | 0.552/0.181 | 0.827/0.708 | 0.256 | 6.6% | 0.951 | 0.967 | 0.98x | 0.990 |

## Why the mechanism does not transfer

**The precondition holds but is weak.** Chroma base is more correlated than
chroma source on 6/6 cells, exactly as luma was — so the double-counting
mechanism is real in principle. But covariance contribution scales with
*variance*, and chroma base carries only `1.3%`--`6.6%` of source variance
against luma's `11.8%`. There is very little covariance to subtract.

**And the symptom it would fix is absent.** Chroma played texture is already
close to source: mean absolute error lag-1 `0.020`, lag-2 `0.039`, which is the
same order as luma *after* its closure (`0.011`--`0.017`). Casino U and V land
within `0.009` and `0.001`. Covariance closure corrects texture
over-correlation; chroma does not have texture over-correlation.

**Chroma's failure is amplitude, and it is a different arithmetic.** Five of
six cells sit at `0.936`--`0.990` played total, slightly under-delivering. The
one real failure is The Shining V at `1.267`.

## The Shining V failure is fully explained by variance closure

Its synthesis is `1.158` where independent-layer variance closure requires
`sqrt(1 - 0.469^2) = 0.883` — a `1.31x` over-signal. Measured total `1.267`
against predicted `sqrt(0.469^2 + 1.158^2) = 1.249` confirms the layers compose
as expected, so nothing exotic is happening.

The distinguishing feature is that Shining V is the only cell where base
retention is large (`0.469`, 22% of variance) rather than negligible. That is
consistent with `FINDINGS-2026-08-04-TEMPORAL-SOURCE-OBSERVATIONS.md`: luma
moved to a temporal source/base estimate while **chroma still uses the spatial
source-minus-base estimate**. Where chroma base retention is small the spatial
estimate's error barely matters; where it is large, the strength is
over-signalled in proportion.

## Extended to all twelve cells: it is weak-grain planes, not V

The three remaining films were measured on both planes. Over-signal is
`synth / sqrt(1 - base_amp^2)`, i.e. how much stronger the delivered synthesis
is than independent-layer variance closure requires.

| cell | source sigma | base amp | needed | synth | over | played total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Deer U | 7.23 | 0.154 | 0.988 | 0.983 | 0.99x | 0.995 |
| Scarface U | 6.80 | 0.142 | 0.990 | 0.943 | 0.95x | 0.955 |
| Casino U | 5.77 | 0.226 | 0.974 | 0.958 | 0.98x | 0.984 |
| Taxi U | 4.38 | 0.116 | 0.993 | 0.956 | 0.96x | 0.962 |
| Interstellar U | 4.16 | 0.164 | 0.986 | 0.983 | 1.00x | 0.998 |
| Shining U | 2.87 | 0.191 | 0.982 | 0.913 | 0.93x | 0.936 |
| Deer V | 2.46 | 0.208 | 0.978 | 0.999 | 1.02x | 1.022 |
| Taxi V | 2.20 | 0.113 | 0.994 | 1.073 | 1.08x | 1.079 |
| Casino V | 2.11 | 0.256 | 0.967 | 0.951 | 0.98x | 0.990 |
| **Interstellar V** | **1.03** | 0.468 | 0.884 | 0.958 | **1.08x** | 1.092 |
| **Shining V** | **0.67** | 0.469 | 0.883 | 1.158 | **1.31x** | 1.267 |
| **Scarface V** | **0.41** | 0.412 | 0.911 | 0.928 | **1.02x** | 1.018 |

Correlations across the twelve: over-signal against source sigma `-0.543`,
against base retention `+0.649`, and source sigma against base retention
`-0.699`.

Split at sigma `1.5`:

| group | n | over-signal range | mean |
| --- | ---: | --- | ---: |
| weak-grain planes | 3 | 1.02--1.31 | **1.138** |
| everything else | 9 | 0.93--1.08 | **0.989** |

The nine ordinary cells average `0.989`, essentially closed. The three weak
planes are the whole error, and all three are V — but **V is not the cause**.
The distinguishing property is plane grain strength: the three weak planes are
also the three highest base retentions (`0.412`--`0.469` against `0.113`--`0.256`),
which is what the `-0.699` correlation says. Where real grain is faint, the
retained base is proportionally large, and the spatial source-minus-base
estimate has the least grain and the most picture structure to confuse.

That reframes the fix. A per-plane correction would be fitting the wrong
variable, which is consistent with `FINDINGS-2026-08-04-AMPLITUDE-CLOSURE.md`
rejecting exactly that. The conditioning variable is measured plane grain
strength, and the correction is to stop using a spatial estimate where it is
least reliable.

## The proposed mechanism is wrong

The section above explained the weak-grain over-signal by saying the spatial
source-minus-base estimate is dominated by picture structure where grain is
faint. That was asserted, not measured. Measuring it
(`chroma_estimate_probe.py`, same luma-derived mask, both estimates per plane):

| cell | source sigma | spatial est | temporal est | spatial/temporal | measured over |
| --- | ---: | ---: | ---: | ---: | ---: |
| Deer U | 7.13 | 7.335 | 7.075 | 1.037 | 0.99x |
| Scarface U | 6.72 | 7.119 | 6.677 | 1.066 | 0.95x |
| Casino U | 5.64 | 6.151 | 5.553 | 1.108 | 0.98x |
| Taxi U | 4.27 | 5.119 | 4.249 | **1.205** | 0.96x |
| Interstellar U | 4.08 | 4.246 | 4.039 | 1.051 | 1.00x |
| Shining U | 2.78 | 2.845 | 2.747 | 1.036 | 0.93x |
| Deer V | 2.38 | 2.526 | 2.356 | 1.072 | 1.02x |
| Taxi V | 2.14 | 2.685 | 2.131 | **1.260** | 1.08x |
| Casino V | 2.02 | 2.333 | 1.993 | 1.171 | 0.98x |
| Interstellar V | 0.92 | 0.914 | 0.842 | 1.085 | 1.08x |
| **Shining V** | 0.60 | 0.589 | 0.545 | **1.080** | **1.31x** |
| Scarface V | 0.39 | 0.444 | 0.367 | 1.210 | 1.02x |

**Correlation between spatial inflation and measured over-signal: `+0.043`.**
None.

The spatial estimate *is* inflated — `1.04x`--`1.26x`, mean `1.115` — but the
inflation does not grow with weak grain and does not predict which planes
over-signal. Shining V, the worst over-signal at `1.31x`, has one of the
*smaller* inflations at `1.080`, while Taxi V and Scarface V inflate more
(`1.260`, `1.210`) and deliver `1.08x` and `1.02x`.

So the empirical finding stands — over-signal tracks weak grain and high base
retention — but **the stated cause does not**. Switching chroma strength to a
temporal base estimate would remove a real `~11%` systematic inflation, which
is worth having, but it would not fix Shining V, and the recommendation below
must not be read as a proposed fix for the weak-grain cells.

What is still unexplained by *that* mechanism: why the weak-grain planes
over-signal at all. The section below finds one that does survive.

## A mechanism that survives: chroma strength does not track time

Per-frame amplitude on the worst cell, The Shining V. `absolute synth sigma`
is `synth amplitude ratio x that frame's own truth sigma`:

| frame | truth sigma | synth ratio | absolute synth sigma |
| ---: | ---: | ---: | ---: |
| 58 | 0.427 | 1.617x | 0.690 |
| 106 | 0.538 | 1.385x | 0.745 |
| 10 | 0.560 | 1.294x | 0.725 |
| 154 | 0.586 | 1.136x | 0.666 |
| 202 | 0.853 | 0.821x | 0.700 |
| 250 | 1.034 | 0.696x | 0.720 |

The synthesised amplitude is almost **constant** — `0.666`--`0.745`, CV `4%` —
while the plane's real grain varies more than twofold, CV `33%`. Over- and
under-delivery are not an estimation-level error; they are the residue of a
model that does not follow the source in time. The ratio column is a perfect
monotone inversion of the truth column.

Across all twelve planes, temporal coefficient of variation of the source
against measured over-signal:

| cell | truth CV | synth CV | over |
| --- | ---: | ---: | ---: |
| Interstellar V | 0.419 | 0.193 | 1.08x |
| **Shining V** | **0.343** | **0.040** | **1.31x** |
| Interstellar U | 0.152 | 0.084 | 1.00x |
| Casino V | 0.121 | 0.058 | 0.98x |
| Scarface V | 0.085 | 0.096 | 1.02x |
| Casino U | 0.068 | 0.046 | 0.98x |
| Shining U | 0.048 | 0.029 | 0.93x |
| Taxi V | 0.043 | 0.038 | 1.08x |
| Deer V | 0.039 | 0.107 | 1.02x |
| Deer U | 0.021 | 0.048 | 0.99x |
| Taxi U | 0.017 | 0.018 | 0.96x |
| Scarface U | 0.015 | 0.028 | 0.95x |

**`corr = +0.699`** (`t = 3.09`, `df = 10`, `p < 0.05`) — the strongest of any
predictor tested, against `+0.043` for spatial inflation, `-0.417` for
quantisation granularity and `-0.551` for mean grain strength.

**It also fixes the case the weak-grain story got wrong.** Scarface V is the
faintest plane in the corpus at sigma `0.41`, so a grain-strength rule predicts
it should be among the worst; it is `1.02x`. Its grain is temporally *stable*
(CV `0.085`), and the temporal account predicts exactly that. The Shining V at
sigma `0.67` is not the faintest but is by far the most variable (CV `0.343`),
and is the worst at `1.31x`.

### Honest limits on this

- **Collinearity.** truth CV correlates `+0.828` with base retention, which
  itself correlates `+0.648` with over-signal. With `n = 12` these cannot be
  fully separated, and base retention may be partly a proxy for temporal
  variability rather than an independent cause.
- **The constancy is not universal.** Synth CV is below truth CV on 7 of 12
  planes, median ratio `0.78`. On very stable planes (Deer U/V, CV `0.02`--`0.04`)
  synth actually varies *more* than the source. The defensible statement is that
  synthesised and true amplitude are temporally **decoupled**, not that
  synthesis is fixed.
- Six frame pairs per plane, so each CV is estimated from six samples.

## Recommendation

1. **Do not build a chroma covariance oracle.** It would require porting
   normative chroma synthesis — its own AR taps including the luma-correlation
   term, `chroma_scaling_from_luma`, separate scaling curves, 16x16 blocks and
   the shared `ar_coeff_shift` constraint — to fix a defect chroma does not
   have.
2. **A temporal base estimate is worth having but is not the weak-grain fix.**
   It would remove a measured `~11%` mean spatial inflation across all twelve
   planes. It is *not* the rejected experiment —
   `FINDINGS-2026-08-04-AMPLITUDE-CLOSURE.md` rejected fitted per-plane QVBR
   *deadzone constants*, not a measured residue — but the probe above shows it
   would not correct Shining V. Do not justify it as the chroma amplitude fix.
3. **The failure is temporal adaptivity, not estimation level.** Any fix should
   make chroma strength follow the source's frame-to-frame variation rather
   than estimate a better single value; a per-plane or per-title constant
   cannot address a decoupling. Gate on measured temporal variability rather
   than plane identity or grain strength. All
   three failing cells are V, but nine cells show V behaving normally; the
   separating property is weak grain with correspondingly high base retention.
   Shining V (`sigma 0.67`, over `1.31x`) is the strongest single test and
   Scarface V (`sigma 0.41`, over `1.02x`) is the control that a plane-based
   rule would get wrong.

## Caveat

Three titles, six frame pairs, luma-masked chroma blocks. Per
`FINDINGS-2026-08-05-HEVC-ARTIFACT.md`, six frames is adequate for the pooled
texture axes quoted here but too sparse for arm-versus-arm played-error means;
no such comparison is made above. The amplitude ratios are pooled block
statistics, not per-frame means.

---

# Follow-up, same day: part of the over-signal is the score, not the delivery

## Densification confirms the CVs

The temporal CVs above come from six frame pairs. Re-measured at sixteen on the
three V planes they are stable, so the earlier analysis was not a sampling
artifact:

| plane | truth CV 6 | truth CV 16 | synth CV 6 | synth CV 16 |
| --- | ---: | ---: | ---: | ---: |
| The Shining V | 0.343 | 0.342 | 0.040 | 0.062 |
| Interstellar V | 0.419 | 0.404 | 0.193 | 0.237 |
| Scarface V | 0.085 | 0.136 | 0.096 | 0.155 |

## Dynamic-range compression is the strongest predictor

Compression is `truth CV / synth CV` — how much the delivered amplitude
flattens the source's frame-to-frame variation.

| cell | compression | over |
| --- | ---: | ---: |
| The Shining V | 8.64 | 1.31x |
| Interstellar V | 2.17 | 1.08x |
| Casino V | 2.09 | 0.98x |
| Interstellar U | 1.81 | 1.00x |
| Shining U | 1.67 | 0.93x |
| Casino U | 1.46 | 0.98x |
| Taxi V | 1.15 | 1.08x |
| Taxi U | 0.95 | 0.96x |
| Scarface V | 0.89 | 1.02x |
| Scarface U | 0.54 | 0.95x |
| Deer U | 0.44 | 0.99x |
| Deer V | 0.36 | 1.02x |

`corr = +0.872`, `t = 5.64`, `n = 12` — against `+0.699` for truth CV alone,
`+0.649` base retention, `+0.043` spatial inflation, `-0.417` quantisation.

## But roughly 40% of the worst cell is Jensen inflation

`temporal_grain_report`'s amplitude figure is a **mean of per-frame ratios**.
When delivered amplitude is near-constant and the source varies,
`mean(c / x) > c / mean(x)` by Jensen's inequality, and the gap grows with the
variance of `x`. So compression and score inflation are the same phenomenon
seen twice, and part of the correlation above is definitional.

| cell | mean-of-ratios | ratio-of-means | gap |
| --- | ---: | ---: | ---: |
| **The Shining V** | 1.158 | **1.062** | **+0.096** |
| **Interstellar V** | 0.958 | **0.861** | **+0.097** |
| Casino V | 0.951 | 0.941 | +0.010 |
| Interstellar U | 0.983 | 0.971 | +0.012 |
| all eight others | — | — | `<= 0.003` |

Confirmed at sixteen pairs: The Shining V reads `1.155` as a mean of ratios and
`1.042` as a ratio of means.

**The Shining V's over-signal is therefore about `1.18x`, not `1.31x`** — still
the worst cell, but the headline figure overstated it by roughly a third.

## Luma is unaffected

| | luma | chroma |
| --- | ---: | ---: |
| truth CV range | 0.010--0.151 | 0.015--0.419 |
| mean Jensen gap | **+0.0003** | +0.019 |
| max Jensen gap | **+0.0028** | +0.097 |

Every luma played-total figure in this project is safe: the inflation needs a
temporally variable source, and luma's amplitude is stable frame to frame. It
bites only on the two chroma V planes with CV `0.34`--`0.42`, which are exactly
the cells that looked worst.

## Consequences

1. **Quote chroma amplitude as a ratio of means, not a mean of ratios**, or the
   most variable planes are penalised for their variability. This is a scoring
   change, not an encoder change.
2. **The residual is still real.** At `1.18x` The Shining V remains the worst
   cell and the compression ordering survives, so temporal decoupling is not
   dismissed — only its magnitude was overstated.
3. **The earlier corpus figure of `1.087` mean V played total is inflated** by
   the same effect on its two most variable members and should be recomputed
   before being used as a target.
