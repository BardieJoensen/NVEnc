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

What is still unexplained: why the three weak-grain planes over-signal at all,
given their spatial estimates are not unusually inflated. That is the open
question, and no mechanism for it has survived measurement yet.

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
3. **The weak-grain over-signal has no surviving explanation.** Gate any future
   work on measured plane grain strength rather than plane identity. All
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
