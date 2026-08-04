# Source-fit admission: held-out fine/coarse film — 2026-08-04

> Quality-first research result. Nothing here was deployed. Production remains
> r4069 with bilateral separation, residual fitting and the existing Tdarr
> route. `modelsrc` remains default-off.

## Decision

**Do not change the Tdarr routing.** The evidence now supports source fitting
as the better grain-model architecture for admitted film, but it does not
support a title-, genre- or NFO-level route. The appropriate eventual boundary
is per model interval inside the analyzer:

1. bilateral separation produces the base;
2. independent evidence decides whether source texture is film-like enough to
   model as grain;
3. source fitting is preferred for admitted intervals;
4. residual fitting is used for non-admitted or source-solver-rejected
   intervals; and
5. copying the original remains the last resort only if neither model is safe.

Commit `8439bd0e` implements steps 3--5 behind `modelsrc=on`. Step 2 remains a
measurement, not code that changes output.

## Held-out positive controls

Two retained lossless clips from original 1080p remuxes were added after the
exploratory admission axes had already been described:

- **Ju-on**: high-energy fine 35 mm grain;
- **Coming to America**: coarse 35 mm grain, previously measured at Taxi
  Driver's spatial scale.

Each gate arm contains 288 frames at QVBR 29. All grain-on and grain-off
outputs pass complete dav1d decoding. Neither source-fit run emits residual
fallback or reaches the original-copy fallback.

| title | source-fit bytes vs residual control | source-fit base VMAF delta | emitted source / fallback frames |
| --- | ---: | ---: | ---: |
| Ju-on | +0.277% | +0.0966 | 288 / 0 |
| Coming to America | +0.063% | +0.0186 | 288 / 0 |

The unchanged bilateral separator and effectively flat byte/base results
isolate the grain-model architecture. Finished-frame VMAF is not used to rank
the arms because independently seeded synthesis is spatially unaligned and
VMAF has a measured preference for fine grain at fixed energy.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-film-holdout-gate-20260804/
```

## Decoded grain result

The temporal-static report compares synthesis against source grain with the
picture cancelled. Lag-1 and lag-2 describe spatial scale independently of
amplitude.

### Fine grain: Ju-on

| layer | amplitude / truth | lag-1 | lag-2 | played total |
| --- | ---: | ---: | ---: | ---: |
| source truth | 1.000 | 0.354 | -0.075 | 1.000 |
| residual-fit synthesis | 0.833 | 0.201 | -0.232 | 0.868 |
| source-fit synthesis | **0.990** | **0.359** | **-0.083** | **1.021** |

This is close on energy and both texture lags. U total is 0.982. V improves
from 0.774 to 0.914 but remains low, so real-film V amplitude is still open.
The darkest populated luma band is high at 1.113 while the other populated
bands are 0.987--1.052; corpus means must not hide that shape error.

### Coarse grain: Coming to America

| layer | amplitude / truth | lag-1 | lag-2 | played total |
| --- | ---: | ---: | ---: | ---: |
| source truth | 1.000 | 0.651 | 0.277 | 1.000 |
| residual-fit synthesis | 0.638 | 0.366 | -0.069 | 0.753 |
| source-fit synthesis | **0.915** | **0.729** | **0.430** | **0.997** |

Source fitting closes played energy and is much closer than production, but it
overshoots correlation by +0.078 at lag-1 and +0.153 at lag-2. This is useful
evidence for the remaining coarse-grain/AV1-model limit: the architecture is
directionally right, but the current quantized AR model is not exact. U/V
played totals are 1.005/1.004.

## Admission evidence

The exploratory conjunction was fixed before these four held-out controls were
run:

```text
cross-frame correlation <= 0.127
AND source/model anisotropy mismatch <= 0.032
```

It is still diagnostic, not a production threshold. It was selected after the
initial six-film/six-general corpus, and both boundaries sit close to an
initial positive. The held-out result is nevertheless informative:

| held-out title | label | cross-frame correlation | anisotropy mismatch | diagnostic result |
| --- | --- | ---: | ---: | --- |
| Ju-on | fine film positive | 0.022 | 0.009 | accept |
| Coming to America | coarse film positive | 0.107 | 0.014 | accept |
| Phineas and Ferb | animation negative | 0.141 | 0.030 | reject |
| Legend of Korra | animation negative | 0.161 | 0.092 | reject |

The unchanged conjunction therefore separates four held-out controls across
both sides and both grain scales. Four controls are not enough to turn it into
a router, especially because the positive clips were deliberately selected as
grain-bearing scenes.

## The counterfactual that prevents a wrong router

`sourcefit_admission_compare.py` compares the source-fit and residual-fit
tables against their temporal source evidence while always returning
`routing_verdict: null`. Positive values below mean that source fitting reduces
mean absolute lag-1/lag-2 error.

| title | class | cross-frame | anisotropy mismatch | source lag MAE | residual lag MAE | source improvement |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Casino | film | 0.118 | 0.019 | 0.022 | 0.294 | +0.272 |
| Interstellar | film | 0.071 | 0.032 | 0.087 | 0.271 | +0.184 |
| Scarface | film | 0.027 | 0.015 | 0.027 | 0.115 | +0.088 |
| Taxi Driver | film | 0.127 | 0.026 | 0.021 | 0.297 | +0.277 |
| The Deer Hunter | film | 0.031 | 0.012 | 0.013 | 0.261 | +0.247 |
| The Shining | film | 0.030 | 0.009 | 0.083 | 0.237 | +0.154 |
| Ju-on | held-out film | 0.022 | 0.009 | 0.008 | 0.175 | +0.167 |
| Coming to America | held-out film | 0.107 | 0.014 | 0.111 | 0.274 | +0.163 |
| Big Brother | general | 0.144 | 0.140 | 0.081 | 0.376 | +0.295 |
| Drag Race | general | 0.174 | 0.049 | 0.079 | 0.406 | +0.328 |
| Rick and Morty | general | 0.143 | 0.292 | 0.027 | 0.442 | +0.415 |
| Silo | general grain | 0.143 | 0.038 | 0.165 | 0.183 | +0.018 |
| Stormester | general | 0.194 | 0.056 | 0.068 | 0.488 | +0.420 |
| Supergirl | general | 0.102 | 0.047 | 0.037 | 0.466 | +0.429 |
| Phineas and Ferb | animation | 0.141 | 0.030 | 0.075 | 0.154 | +0.079 |
| Legend of Korra | animation | 0.161 | 0.092 | 0.016 | 0.469 | +0.454 |

Source fitting is closer on **all 16 titles**, including every labelled
negative. That does not mean it should be used everywhere. It means the source
fit faithfully describes whatever persistent high-frequency structure the
flat-block selector admits: film grain, animation texture, ringing or codec
structure. A better fit is a model-choice result only after independent
film-like admission; using it as admission would route every known negative in
the wrong direction.

Silo is a particularly useful boundary. Its model improvement is marginal
(0.018), its film-like axes miss the exploratory conjunction, and accepted
source-model spans over-deliver played luma to 1.142. Its solver-rejected spans
correctly use the new residual fallback. This is exactly why solver safety and
semantic admission must be different layers.

## What this changes and what it does not

Supported now:

- source fitting fixes production's incorrect fine/coarse grain structure on
  admitted real film;
- the residual fallback removes Silo's +26% failure-path regression without
  changing admitted film output;
- fine and coarse held-out film both benefit; and
- admission evidence must be independent of model-fit improvement.

Not supported yet:

- enabling `modelsrc` over the current production route;
- changing Tdarr routing by genre, NFO, correlation alone or animation label;
- treating the exploratory conjunction as a release threshold;
- claiming exact coarse-grain reproduction; or
- claiming chroma amplitude closure, particularly V.

## Recommended next sequence

1. **Shadow admission on a larger untouched corpus.** Record both axes and both
   model errors without changing output. Include unselected film scenes,
   low-grain live action, compressed digital material and additional animation.
2. **Keep the decision per interval, not per title.** Scene variation is large;
   a title-level Tdarr route would discard the residual fallback's main safety
   advantage.
3. **Investigate coarse correlation overshoot offline.** Any regularization
   must improve Coming to America's +0.078/+0.153 error without repeating the
   Deer Hunter amplitude regression or suppressing correct Taxi/Ju-on texture.
4. **Close chroma V and per-luma strength.** Ju-on V=0.914 and its dark luma
   band=1.113 are now concrete targets.
5. **Only then run the blind playback review and consider enabling source
   fitting.** Compression and speed remain secondary to these quality gates.

