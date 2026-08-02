# Leak-aware source-strength closure, 2026-08-02

This is the implementation and validation checkpoint after
`FINDINGS-2026-08-02-QVBR-EMISSION.md`.  It remains an opt-in experiment:
`modelsrc=off` is still the default, no Tdarr configuration or production
image was changed, and the PSD experiment remains excluded.

## Candidate and method

The implementation is commit `fef5264f`.  Its pinned binary is:

```text
/home/bardie/.cache/fgs-gate/builds/pin-fef5264f-1785662780/build-gate/nvencc
SHA-256 84fb31f1af278c8e2ddaac9e48e7f27d123b3ad2514c672a39e629d6fc23d50e
```

Under `modelsrc=on`, QVBR 25--39 and `retain=0`, the analyser measures luma
temporal source and clean-base variance on consecutive accepted blocks.  It
predicts post-encode base residue with the six-film QVBR fit:

```text
theta = 0.01579030304339795 + 0.004870139420489915 * QVBR
post_leak = max(0, pre_encode_leak - theta)
synthesis_fraction^2 = 1 - post_leak^2
```

The existing source strength bins are replaced by temporal source variance
times that synthesis fraction.  This deliberately reuses the existing
variance-closure arithmetic; it is not a second post-hoc gain.  Bins without
sufficient temporal coverage retain the spatial source-fit estimate.

Artifacts are under:

```text
/media/merged-storage/media/test-encodes/sourcefit-leakclose-20260802/
```

All closure results below use 24 frame pairs per title at frames
`6, 18, ..., 282`, the production static-block selector, motion separation,
QVBR 29, preset P4 and tune HQ.

Four source clips had newer lossless `ref288` copies than the retained control
run.  Exact decoded frame MD5s at every measured frame and its successor match
the old inputs, so this does not change the comparison.

## Safety and invariance gates

- the complete CPU test suite passes;
- the quick GPU gate passes all 18 KAT fixtures, rejects the labelled widening
  negative and accepts the shipping model;
- all six candidate AV1 streams pass a complete `libdav1d -xerror` decode;
- Taxi Driver with `modelsrc=off` produces a byte-identical table to the old
  binary (SHA-256
  `3807f980862b0e1b6b229be74a9c9b731286229a0960f629121604e665fc8973`)
  and the same elementary AV1 MD5
  (`c0035812c0634847631c03fac5b8a9fa`).

The implementation therefore does not affect the default path.  These gates
say it is safe to continue testing; they do not clear it for production.

## Six-film luma result

`actual target` is the synthesis amplitude that closes the measured
post-encode base residue to total amplitude 1.000.  `old` is the source-fit
candidate before leak closure; `new` is this candidate.

| title | pre-encode leak | actual target | old synth | new synth | old total | new total | old total error | new total error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Casino | 0.424 | 0.966 | 0.889 | 0.959 | 0.926 | 0.993 | 0.074 | **0.007** |
| Interstellar | 0.558 | 0.901 | 0.914 | 0.993 | 1.014 | 1.087 | **0.014** | 0.087 |
| Scarface | 0.225 | 0.997 | 0.956 | 1.001 | 0.959 | 1.005 | 0.041 | **0.005** |
| Taxi Driver | 0.372 | 0.976 | 0.874 | 0.956 | 0.899 | 0.979 | 0.101 | **0.021** |
| The Deer Hunter | 0.342 | 0.976 | 0.835 | 0.902 | 0.860 | 0.924 | 0.140 | **0.076** |
| The Shining | 0.449 | 0.960 | 0.892 | 0.942 | 0.935 | 0.983 | 0.065 | **0.017** |

Corpus aggregates:

| measurement | old | new |
| --- | ---: | ---: |
| mean synthesis amplitude | 0.893 | **0.959** |
| synthesis MAE to 1.000 | 0.107 | **0.042** |
| mean played total | 0.932 | **0.995** |
| played-total MAE to 1.000 | 0.072 | **0.036** |
| synthesis bias to true post target | -0.069 | **-0.004** |
| synthesis MAE to true post target | 0.074 | **0.036** |

The systematic deadzone correction is real: it removes essentially all of
the corpus-mean synthesis bias and improves five of six films.  It is not yet
a shippable solution.  Interstellar changes from an acceptable 1.014 total to
1.087, while The Deer Hunter remains low at 0.924.  A corpus mean close to one
cannot hide opposite per-title errors of this size.

File-size changes against the old QVBR-29 source-fit arm are only about
-0.02% to +0.17% (Taxi Driver +0.055%).  This change is an amplitude-fidelity
correction, not a new compression or speed result.  The earlier 46.4% motion
compression result is a separate property of the separator and still needs
the blinded perceptual gate.

## Exact emission and the remaining deterministic term

The exact side-data audit still closes completely on all six candidates:

- every non-seed table field matches the AV1 stream;
- no table seed matches NVENC's chosen bitstream seed, as expected;
- the local normative AV1 synthesis matches dav1d pixel-for-pixel;
- predicted/delivered amplitude is 1.000 on every title.

So the encoder and decoder emit the signalled grain exactly.  The remaining
error is not a corrupt bitstream, a decoder defect or a second hidden emission
gain.

`emission_audit.py --seed-samples` adds a deterministic expected-delivery
oracle: it applies each signalled table to the actual grain-disabled base and
the selected blocks over several well-spread normative AV1 seeds.  Dense
24-pair, eight-seed checks on the three diagnostic titles give:

| title | actual synth | expected synth | expected / actual | true target |
| --- | ---: | ---: | ---: | ---: |
| Casino | 0.9585 | 0.9542 | 0.9955 | 0.9658 |
| Interstellar | 0.9931 | 0.9959 | 1.0028 | 0.9005 |
| The Deer Hunter | 0.9015 | 0.8976 | 0.9957 | 0.9763 |

The table, the base-luma population and normative synthesis predict both the
Interstellar overshoot and Deer Hunter undershoot to within 0.5%.  The
opposite errors are therefore deterministic properties of model/curve
delivery, not random-seed noise.  That is a much narrower next problem: test
an expected-delivery normalisation offline before changing the encoder.  Do
not add a title, correlation or film-derived threshold.

## Expected delivery: aggregate proof succeeds, global form fails

`delivery_normalize.py` closes the analyser's predicted synthesis target
against the expected AV1 delivery from the quantized table.  It calculates one
factor from the pre-encode temporal leak, QVBR deadzone and normative
multi-seed expectation; it does not fit against a title's post-encode result.
Only luma scaling points change.  AR coefficients stay byte-identical, and if
the curve needs a lower shared `scaling_shift`, chroma points are requantized
to keep their physical amplitude unchanged.

The three deliberately different diagnostic titles require:

| title | predicted target | expected before | factor | expected after | after - target |
| --- | ---: | ---: | ---: | ---: | ---: |
| Casino (near) | 0.9638 | 0.9542 | 1.0100 | 0.9662 | +0.0025 |
| Interstellar (over) | 0.9163 | 0.9959 | 0.9201 | 0.9162 | -0.0000 |
| The Deer Hunter (under) | 0.9827 | 0.8976 | 1.0948 | 0.9765 | -0.0062 |

At whole-title aggregate, the same rule therefore corrects both signs, with a
maximum quantized-table target miss of 0.0062.  Combining the adjusted
expectation with each title's measured post-encode base residue predicts
played totals 1.0004 Casino, 1.0142 Interstellar and 1.0002 Deer Hunter.
Interstellar's residual 1.4% is the independent deadzone-model error; expected
delivery no longer contributes to it.

A matched four-seed texture audit held base pixels, blocks, seeds, range
clipping and AR coefficients fixed.  Scaling-curve quantization changed lag-1
by at most 0.00068 and lag-2 by at most 0.00022:

| title | old lag-1 | new lag-1 | delta | old lag-2 | new lag-2 | delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Casino | 0.74825 | 0.74829 | +0.00004 | 0.33984 | 0.33986 | +0.00003 |
| Interstellar | 0.77131 | 0.77089 | -0.00041 | 0.44856 | 0.44834 | -0.00022 |
| The Deer Hunter | 0.52819 | 0.52751 | -0.00068 | 0.05353 | 0.05333 | -0.00020 |

One harness defect was found and fixed during this test.  `filmgrn1` does not
carry AV1's restricted-output-range flag.  The first alternate-table oracle
therefore synthesized full-range output and made upward curve changes appear
superlinear on dark/bright blocks.  The corrected oracle inherits the flag
from decoded stream side data.  Commit `28fa523f` fixes this; none of the
numbers above use the invalid full-range run.

### Hardware replay

The harder upward case was replayed through the pinned NVEncC binary and
dav1d, using original and normalized tables against the exact same saved
motion-clean Deer Hunter base.

- both streams pass a complete `libdav1d -xerror` decode;
- their grain-disabled frame-MD5 stream SHA-256 values are identical:
  `6a4c0552bbba32a139f398daf8db187d1d7d2c950b24a8ae4b5a084b963f2f8f`;
- variance-weighted production-static synthesis moves 0.905 -> 0.984;
- played total moves 0.927 -> 1.004;
- decoded synthesis lag-1 moves only 0.540 -> 0.539.

The equal-frame temporal summary reads 1.041 after normalization because it
gives a low-grain frame the same weight as a high-grain frame.  The closure
target and all preceding corpus results are variance- and block-weighted;
under that same estimator the hardware result is 1.004.  This is an
aggregation distinction, not an encode/simulator disagreement.

But the mandatory luma-band decomposition rejects the global multiplier:

| normalized luma | blocks | true post target | original synth | normalized synth |
| --- | ---: | ---: | ---: | ---: |
| 0.000--0.125 | 13,204 | 0.982 | 0.883 | **0.956** |
| 0.125--0.250 | 4,633 | 0.981 | 0.895 | **0.980** |
| 0.250--0.375 | 7,250 | 0.939 | 1.016 | **1.112** |
| 0.375--0.500 | 846 | 0.931 | 1.107 | **1.212** |

Deer Hunter is dominated by dark blocks, so raising every scaling point makes
the whole-title number look correct while worsening already-overdone brighter
grain.  This is the same luma-occupancy trap in a new form.  The global factor
is therefore **rejected as a production design**.  What it proves is narrower
and still useful: deterministic expected delivery can correct both amplitude
directions without changing AR texture, but the correction must be a
per-luma curve correction and must close every populated luma band.

## Chroma real-film baseline

`temporal_grain_report.py` now measures U or V using the same fixed source-luma
flat/static mask mapped from 32x32 luma blocks to 16x16 4:2:0 chroma blocks.
This prevents each plane from silently selecting different picture content.
Zero-energy chroma bands are retained as amplitude zero with undefined texture
instead of being discarded or crashing the report.

Across all 12 title/plane combinations:

| measurement | old | new |
| --- | ---: | ---: |
| mean synthesis amplitude | 0.886 | 0.891 |
| synthesis MAE to 1.000 | 0.119 | 0.117 |
| mean played total | 0.940 | 0.945 |
| played-total MAE to 1.000 | 0.083 | 0.079 |

The luma-only closure causes only a small indirect cross-plane change and does
not regress chroma.  It also demonstrates that chroma is systematically
under-signalled overall.  Chroma is therefore a real, separate validation and
modelling gap; it must not be described as solved by the luma result.

## Rectification counter

The new diagnostic counter is live.  The maximum ratio of rectified spatial
blocks to temporal observations was 1.74% Casino, 3.25% Interstellar, 0.013%
Scarface, 0.080% Taxi Driver, 0.924% The Deer Hunter and 8.89% The Shining.
The populations are not identical, so these are conservative upper proxies,
not exact rectification rates.

Rectification cannot explain the current luma result because accepted temporal
bins replace the spatial strength sums.  The Shining rate is still high enough
to retain as a warning for the spatial fallback and for chroma, where that
replacement is not applied.

## Decision

The experiment is viable but incomplete:

1. keep the rate-dependent leak closure behind `modelsrc=on`, default-off;
2. reject the table-wide delivery multiplier despite its aggregate result;
3. next measure expected versus target delivery per fixed luma band, using the
   rolling model's existing 20-bin weights and quantized parameters, and
   validate the cheap estimator against the exact oracle on all six films;
4. implement only if one per-luma rule closes every populated band in both
   directions without a normative multi-seed simulator in the hot path, then
   repeat the full six-film encode/closure corpus;
5. keep chroma modelling and the blinded motion perceptual review as separate
   open gates.

Nothing in this checkpoint is approved for Tdarr production.
