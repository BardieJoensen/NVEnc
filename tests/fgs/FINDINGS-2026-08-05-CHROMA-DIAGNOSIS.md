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

## Recommendation

1. **Do not build a chroma covariance oracle.** It would require porting
   normative chroma synthesis — its own AR taps including the luma-correlation
   term, `chroma_scaling_from_luma`, separate scaling curves, 16x16 blocks and
   the shared `ar_coeff_shift` constraint — to fix a defect chroma does not
   have.
2. **The chroma target is variance closure on a temporal base estimate**, the
   same change luma received. Note this is *not* the rejected experiment:
   `FINDINGS-2026-08-04-AMPLITUDE-CLOSURE.md` rejected fitted per-plane QVBR
   *deadzone constants*, whereas this would use the directly measured temporal
   base residue with no fitted transfer.
3. **Test it on Shining V first.** It is the only cell where the two estimates
   can diverge enough to matter, so it is both the strongest test and the
   cheapest.

## Caveat

Three titles, six frame pairs, luma-masked chroma blocks. Per
`FINDINGS-2026-08-05-HEVC-ARTIFACT.md`, six frames is adequate for the pooled
texture axes quoted here but too sparse for arm-versus-arm played-error means;
no such comparison is made above. The amplitude ratios are pooled block
statistics, not per-frame means.
