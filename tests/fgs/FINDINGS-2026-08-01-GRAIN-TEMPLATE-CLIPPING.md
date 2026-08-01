# The grain template saturates on coarse grain, 2026-08-01

## Result

Coarse grain synthesises at 70-82% of the amplitude its own signalled table asks
for. Fine grain synthesises at 99.7%. The cause is not the fit, the separator, or
the AV1 model's expressiveness: **the decoder's grain template clips against
`GrainMin`/`GrainMax`, and the encoder derives the strength curve as if it did
not.**

`grainScaleShift`, the format field that exists to prevent exactly this, is
hardcoded to 0 (`NVEncFilmGrainModel.cpp:272`).

## The chain, and where it breaks

The encoder divides the strength curve by the AR process's theoretical
stationary variance gain (`NVEncFilmGrainModel.cpp:121`, `:170`):

```cpp
solved.arGain   = sqrt(predictorVariance / innovationVariance);
solved.strength[bin] = sqrt(variance) / solved.templateGain;
```

The decoder is then expected to multiply that curve by a template whose standard
deviation is `arGain * innovation_std`. Predicting the decoder's output from the
table alone -- curve value, `scaling_shift`, and the template std obtained by
running the spec's AR recursion over the fitted coefficients -- and comparing
against the measured synthesised sigma:

| fixture | predicted | measured | ratio |
| --- | ---: | ---: | ---: |
| `detail_luma` (white grain) | 5.988 | 5.970 | **0.997** |
| `coarse_luma`, bilateral | 2.631 | 2.160 | 0.821 |
| `coarse_luma`, fft3d | 3.554 | 2.490 | 0.701 |
| `coarse_luma`, motion | 3.420 | 2.410 | 0.705 |

White grain validates the whole calculation end to end at 0.997, so the
prediction method is sound and the table is asking for the right amount. The
loss is downstream of the table, and only for correlated grain.

## It is clipping, and the numbers match

AV1 builds the 82x73 luma template by drawing samples of std ~32 (8-bit) and
running the AR recursion over them, clipping each output to
`GrainMin`/`GrainMax` = +/-128 at 8-bit. A correlated fit has a large variance
gain, so the recursion drives the template far beyond what that range holds:

| arm | template std, unclipped | clipped | % samples clipped | predicted loss | observed |
| --- | ---: | ---: | ---: | ---: | ---: |
| white | 32.07 | 32.07 | 0.01% | 1.000 | 0.997 |
| bilateral | 86.70 | 69.34 | 8.25% | 0.800 | **0.821** |
| fft3d | 108.65 | 75.85 | 12.75% | 0.698 | **0.701** |
| motion | 109.63 | 75.68 | 12.20% | 0.690 | **0.705** |

Predicted and observed agree to within 0.02 on all four arms. At a template std
of 108 against a +/-128 clip, the limit sits at 1.18 sigma; white grain at std 32
sits at 4 sigma and never touches it.

The bug is bit-depth independent: at 10-bit the innovation is 128 and the clip
+/-512, so the ratio is identical. Real 4K film confirms it:

| table | AR gain | template std | clipped | loss |
| --- | ---: | ---: | ---: | ---: |
| Casino, bilateral | 1.76 | 225.6 | 2.49% | 0.949 |
| Taxi, bilateral | 1.96 | 251.2 | 4.85% | 0.896 |
| Taxi, fft3d | 2.13 | 272.7 | 7.46% | 0.833 |
| Taxi, motion | 2.18 | 278.7 | 8.04% | 0.804 |
| Taxi, `psd=on` | 2.28 | 292.0 | 10.08% | **0.735** |

## This explains why every separator improvement backfired

The loss grows with the AR gain, and the AR gain grows with how much grain
correlation the separator preserves. So each arm that captured the source's
spatial structure better also saturated the template harder and delivered less
of the amplitude it signalled. Ranked by preserved correlation, the arms are in
exactly the reverse order of delivered amplitude.

That reframes several results from this session:

- **`bilateral` looks best on real film partly because it is worst at its job.**
  It whitens the residual, which keeps the AR gain low (1.76-1.96), which keeps
  the template inside the clip range, so it actually delivers what it signals.
  This is a separate effect from the known full-reference metric bias, and it is
  not a measurement artifact.
- **`psd=on` is a net loss on real film** partly for this reason: it has the
  highest gain of any arm and the worst clipping loss (0.735). It was fixing the
  separator while the synthesis path silently taxed the fix.
- **The "46.3% model ceiling"** in `FINDINGS-2026-07-31-WIENER-PSD.md` --
  libaom's own figure with an ideal clean base -- is the extreme case of this,
  not a representational limit of the AV1 grain model. A perfect residual is the
  most correlated one, so it produces the highest gain and clips hardest.

## The fix is a field that is currently pinned off

`grain_scale_shift` scales the innovation down before the AR recursion, giving
it headroom, and the strength curve compensates. It is a 2-bit field with range
0-3 and is hardcoded to 0. Simulating `coarse_luma`'s fft3d model at 8-bit:

| `grain_scale_shift` | innovation std | template std | clipped | amplitude retained |
| ---: | ---: | ---: | ---: | ---: |
| 0 (current) | 32.0 | 75.9 | 12.82% | 0.698 |
| **1** | 16.0 | 52.2 | 1.34% | **0.959** |
| 2 | 8.0 | 27.2 | 0.00% | 1.000 |
| 3 | 4.0 | 13.7 | 0.00% | 1.000 |

One step recovers most of it; two removes clipping entirely. The cost is
quantisation headroom in the template, so the correct choice is the smallest
shift that keeps the template inside the range -- derivable directly from
`solved.arGain`, which the encoder already computes.

A second, independent option is to divide the strength curve by the *realised*
post-clip template gain rather than the theoretical stationary gain. The encoder
can compute that exactly: the template is a deterministic function of the fitted
coefficients. That corrects the amplitude without spending headroom, but leaves
the template's shape distorted by saturation, so it is the weaker fix.

## Implemented, and it behaves as predicted

`build_film_grain_params` now picks the smallest shift that pushes the clip out
to `FGS_TEMPLATE_CLIP_SIGMA` = 3.5, and multiplies the strength curve by the
same factor so the signalled sigma is unchanged --- only the split between curve
and template moves.

| fixture | capture before | capture after |
| --- | ---: | ---: |
| `coarse_luma` | 41% | **60%** |
| `coarse_detail` | 41% | **59%** |
| `detail_luma` | 99% | **99%, per-band sigmas bit-identical** |

60% was predicted at 57% from the fft3d residual capture of 0.568 times a
clipping loss of 1.0. Fine grain selects shift 0 and is untouched by
construction rather than by tuning. Full KAT 21/21.

**This passes the 46.3% "model ceiling"**, which confirms that number was a
symptom of this bug and not a representational limit of the AV1 grain model.

On real 4K film the saturation is gone entirely:

| Taxi arm | shift chosen | clipped before | clipped after | retained before | after |
| --- | ---: | ---: | ---: | ---: | ---: |
| bilateral | 1 | 4.85% | 0.02% | 0.896 | **0.999** |
| fft3d | 2 | 7.46% | 0.00% | 0.833 | **1.000** |
| motion | 2 | 8.04% | 0.00% | 0.804 | **1.000** |

## What is not established

Whether correcting the amplitude improves *perceived* quality. It makes
synthesised grain stronger, so full-reference metrics will get worse for the
reasons already documented, and the release gate remains a playback A/B.

The separator comparison has to be redone. Every arm was previously judged under
a tax that grew with how much grain correlation it preserved, which is the
ranking variable itself --- so `bilateral`'s advantage on real film, `motion`'s
collapse, and `psd=on` being a net loss were all measured through it. Those
conclusions are suspended, not overturned; the corpus is re-running.

## Method

`ar_acf.py` runs the AV1 spec's AR recursion (7.18.3.3) over a fitted table and
reports the resulting field's std and clipped fraction; it is validated against
constructed tables (a 0.5 horizontal tap returns lag-1 0.506, a 0.797 tap returns
0.798 with lag-2 0.638 = rho^2). Predicted synthesis sigma is
`curve(luma) * template_std / 2^scaling_shift`, with the innovation std taken as
`512 / 2^(12 - bit_depth + grain_scale_shift)` from the spec's
`gaussian_sequence`. Measured sigma is the KAT's grain-on minus grain-off
decode. Tables come from `separator_acf.py` (fixtures) and direct
`--film-grain-table-out` runs on 4K film.
