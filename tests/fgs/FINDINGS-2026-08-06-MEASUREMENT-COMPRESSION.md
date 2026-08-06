# The defect is in the measurement, not the arithmetic — 2026-08-06

> Offline measurement only. Nothing deployed, `modelsrc` default-off.
> Partial result: a mechanism is confirmed and quantified, and it does **not**
> account for the whole effect.

## The chain, and where it breaks

For luma the strength fit is (`NVEncFilmGrainModel.cpp:172,179`):

```
arGain        = max(1, sqrt(predictorVariance / innovationVariance))
strength[bin] = sqrt(binVariance) / arGain
```

and playback multiplies the curve by the standard deviation of the AR field the
decoder builds from the emitted coefficients. So `curve x arGain` **is** the
encoder's own measured sigma, by construction.

**The AR accounting is exact.** Running the normative integer recursion
(`av1_grain.generate_luma_template`) on the emitted, quantised coefficients and
regressing over-delivery on the realized gain gives slope **`-0.981`** against a
coded `-1`. Realized gain matches fitted gain, so coefficient quantisation
introduces no error and `arGain` is exonerated.

**But `curve x arGain` does not equal an independent measurement of the source.**
Against source flat-block sigma measured here, it tracks as `source^0.630`:

| | |
| --- | --- |
| exponent | **0.630** |
| 95% CI | `[0.354, 0.905]` — **`b = 1` excluded** |
| r | 0.898 (0.701 before dividing out `arGain`) |
| leave-one-out | `0.613`--`0.662`, r >= 0.857 throughout |

Unlike the compressive fit rejected in
`FINDINGS-2026-08-06-EMISSION-EXPONENT.md`, this one survives its robustness
check — because removing the per-title `arGain` confound tightened the scatter.

So the encoder's *measurement* of source noise is compressive. Every one of the
six rejected amplitude estimators was correcting the output of an input that was
already wrong.

## The mechanism, confirmed and quantified

Flat-block selection. `NVEncFilterFilmGrain.cu:2400` documents the trap in its
own comment — "strong grain inflates the gradient metrics, so strict-threshold
selection alone samples only the weakest-grain regions and biases the strength
curve" — and takes the top score decile to mitigate it.

Emulating that selection directly: rank admitted blocks by the grain-sensitive
metric (raw pixel gradient), keep the flattest quantile, and remeasure.

| kept quantile | b | r |
| ---: | ---: | ---: |
| 0.05 | **0.833** | 0.879 |
| 0.10 (the encoder's decile) | **0.818** | 0.935 |
| 0.25 | 0.790 | 0.972 |
| 0.50 | 0.730 | 0.968 |
| 1.00 (no selection) | 0.602 | 0.906 |

Monotone across all five levels. Selecting on a grain-sensitive metric **is** a
compressive measurement, and at the encoder's own decile it closes `0.602` →
`0.818`, about **54% of the distance to correct tracking**.

A control rules out the obvious alternative: varying *breadth* on a
grain-**insensitive** metric (8x8-pooled structure) over a 3.2x range moves
nothing — `0.628` / `0.673` / `0.629`. The compression follows the metric's
grain sensitivity, not how many blocks are kept.

## What this does not establish

**The test is partly tautological and must be read with that in mind.**
Selecting the least-grainy blocks necessarily shrinks measured sigma more on
grainy titles than on clean ones, which compresses the regressor and mechanically
raises the fitted exponent. The *direction* is guaranteed; only the *magnitude*
is informative. What the numbers say is that at the encoder's actual selection
strength the effect is real but partial.

**A residual of ~0.18 in exponent is unexplained.** At the encoder's decile the
exponent is `0.818`, not `1.0`. Selection bias is a confirmed contributor and
not the whole defect, and no further candidate has been tested.

## Limits

Nine titles, one QVBR, 24 frames, luma only. Source sigma uses a structure/noise
split rather than the encoder's own block scorer, so it approximates the
regressor rather than reproducing it — recovering the encoder's per-block
`sigma` and `score` directly would remove that approximation and is the obvious
next instrument.

## Next

Two things, neither needing encodes beyond what exists:

1. Instrument the analyser to dump per-block `sigma`/`score`/admission, and
   compare its measured distribution against the source directly. That replaces
   the emulation above with the real selector and would settle the residual.
2. Check whether the residual is the top-decile rule interacting with
   `minFlatFraction`/`minFlatBlocks`: on grainy content the decile is taken from
   an already grain-biased score ranking, so the mitigation may itself be applied
   to a distorted ordering.
