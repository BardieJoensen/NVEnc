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
2. prototype expected-delivery normalisation offline on Casino (near target),
   Interstellar (over) and The Deer Hunter (under);
3. require one mechanism to correct both signs without changing AR texture;
4. only then consider a cheap production implementation and repeat the full
   six-film corpus;
5. keep chroma modelling and the blinded motion perceptual review as separate
   open gates.

Nothing in this checkpoint is approved for Tdarr production.
