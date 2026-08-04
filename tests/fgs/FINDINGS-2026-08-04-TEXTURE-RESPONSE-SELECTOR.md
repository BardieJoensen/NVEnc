# Texture-response selector: confidence gate and real-film closure

Date: 2026-08-04 UTC  
Branch: `fgs/test-automation`  
Authority: research only; no production or routing authority

## Question

Source fitting fixes the AR model's input, but the encoded base still carries
some correlated texture.  A full-source AR model therefore overcounts that
texture when AV1 synthesis is added back.  The dynamic covariance arm tried to
subtract the surviving base covariance directly.  It improved the macro result
but regressed the fine Scarface control and coarse Shining control.

The response arm asks a narrower question: among the frozen covariance weights
`0, 0.75, 0.85, 0.925, 1`, which *quantized AV1 model* is predicted to deliver
the lowest played luma-axis error after the encoded base and synthesis are
combined?  The four axes are `h1`, `h2`, `v1`, and `v2`; amplitude remains in
the separate strength/retention system.

This experiment tests whether that selector can improve spatial grain texture
without the dynamic arm's title regressions.  It does not test semantic grain
admission, chroma closure, per-luma strength, or perceptual temporal stability.

## Two implementation defects found before the final run

### Response weights were applied in the wrong unit space

The frozen response grid was calibrated against *post-encode* base covariance,
but the runtime selector applied its weight directly to the stronger
*pre-encode* denoised-base covariance.  For Deer Hunter,
`(postLeak / preLeak)^2` is about `0.419`, so a nominal weight of `0.75` behaved
like approximately `1.79` in the calibrated space.

Commit `99cfedb3` maps every grid weight back into the pre-encode accumulator:

```text
preencode weight = response weight * postLeak^2 / preLeak^2
```

The conversion fails closed on invalid or non-finite leak estimates and has a
host-only known-answer test.

### Small predicted gains could reverse sign after normative synthesis

Exact libaom replay on two Shining runtime windows showed that the fitted
response approximation was not accurate enough to choose every close result:

| Shining window | predictor choice | exact best | exact error at 0 | exact error at predictor |
| --- | ---: | ---: | ---: | ---: |
| frame 49 | 0.85 | 0 | 0.01276 | 0.01367 |
| frame 141 | 0.925 | 0 | 0.00317 | 0.02352 |

The unguarded unit-corrected arm consequently moved Shining from a source-fit
baseline error of about `0.01371` to `0.02944`.

Commit `40b987ff` requires a non-zero response candidate to improve predicted
mean axis error over weight zero by at least `0.01`.  Otherwise it emits the
weight-zero source-fit model.  The raw predicted improvement is still logged as
`responseGain`, including when the candidate is suppressed.  The threshold was
chosen after observing the Shining failure and is therefore exploratory, not a
preregistered confirmation.

## Pinned build and default-off safety

The candidate was built from exact commit `40b987ffcd80930ad2911971eeae526da92b3115`
in the already provisioned CUDA 13.3 build container.  All six affected build
steps completed, including `NVEncFilterFilmGrain.cu`, and the final link passed.

```text
binary: /home/bardie/.cache/fgs-gate/builds/
        pin-40b987ff-20260804-response-margin/build-gate-provisioned/nvencc
sha256: 042cb34e93154deecf898771897eeea6e95310f0358e78c3cd3f3831671903c2
version: NVEnc 9.29 r4287, CUDA 13.3
```

With no research environment variables, the complete 22-fixture GPU KAT
passed.  Report:

```text
/home/bardie/.cache/fgs-gate/reports/
    20260804T-response-margin-default
```

The selector remains reachable only through all of:

```text
modelsrc=on
QVBR 25..39
retain=0
NVENC_FGS_TEST_SOURCE_STATIC=on
NVENC_FGS_TEST_TEXTURE_LEAK=response
```

`modelsrc` remains default-off.  No Tdarr configuration or production binary
was changed.

## A false-green KAT result was invalidated

The earlier nominal response KAT under
`20260804T161728Z/kat-response-fixed` did **not** exercise the response path.
It ran CQP 20 without `modelsrc=on`; every encode log says both hooks were
ignored.  Its 22/22 result bounds ordinary FGS only.

The corrected response run used QVBR 29, bilateral, and `modelsrc=on`:

```text
/home/bardie/.cache/fgs-gate/reports/
    20260804T-response-margin-hook
```

Raw result: 19/22 fixtures passed.  The three failures were reproduced with
the response hook disabled and otherwise identical arguments:

- `coarse_detail`: the documented bilateral base-layer failure, edge RMSE
  `2.04` in both arms.  Response changed synthesis capture from 84% to 86% but
  cannot change this base error.
- `retain_luma` and `retain_10bit`: `retain=0.6` intentionally disables the
  response hook.  Both arms retained about 0.22 under the QVBR run; these KAT
  bounds were established for the ordinary CQP gate.

Seventeen of eighteen hook-eligible fixtures passed outright; the remaining
eligible fixture is the identical bilateral base failure above.  The four
retain/auto-retain fixtures do not exercise texture closure.

Commit `9c37ab62` prevents this failure mode from recurring: if a research hook
is requested without compatible QVBR, `modelsrc`, static-source, and retain
settings, `fgs_kat.py` now exits before encoding instead of accepting NVEncC's
warning and testing the wrong arm.

## Eight-film real-content result

All values below are decoded-total-to-source mean absolute error across
`h1/h2/v1/v2`, measured on the same six frozen frame pairs.  Lower is better.

| title | unchanged source fit | dynamic covariance | guarded response |
| --- | ---: | ---: | ---: |
| Casino | 0.06292 | **0.00908** | 0.02103 |
| Interstellar | 0.06214 | 0.03048 | **0.00575** |
| Scarface | 0.01026 | 0.01566 | **0.00736** |
| Taxi Driver | 0.05455 | **0.00748** | 0.02221 |
| The Deer Hunter | 0.04494 | **0.01386** | 0.03086 |
| The Shining | 0.01371 | 0.03652 | **0.01252** |
| Ju-on | 0.02400 | **0.00480** | 0.01259 |
| Coming to America | 0.10020 | 0.03547 | **0.01972** |
| **macro mean** | **0.04659** | **0.01917** | **0.01651** |

The important distinction is safety, not the small macro lead.  Dynamic
covariance improves 6/8 titles and regresses Scarface and Shining.  Guarded
response improves 8/8 relative to unchanged source fit.  It deliberately gives
up some of the large dynamic gain on Taxi and Deer to avoid forcing ambiguous
windows.

Shining was the stop/go control.  Guarding the response reduced its unguarded
`0.02944` error to `0.01252`; eleven of fourteen emitted table updates chose
weight zero.  Scarface stayed at `0.00736`.  Deer still improved over baseline,
but less than the unguarded arm (`0.03086` versus `0.01847`), confirming that a
fixed margin is conservative rather than free.

The eight outputs all passed a complete `libdav1d -xerror` decode.  Artifacts
are split across:

```text
/media/merged-storage/media/test-encodes/
    sourcefit-texture-response-margin-shining-20260804
    sourcefit-texture-response-margin-controls-20260804
    sourcefit-texture-response-margin-remaining-20260804
    sourcefit-texture-response-margin-heldout-20260804
```

## Genuinely unseen film-positive result

The eight-film corpus contributed to earlier response fitting, so it cannot by
itself establish generalization.  Four 288-frame film-positive scenes from the
pre-registered source-fit admission corpus had never been used by the texture
response experiment: Quiz Show, Life of Brian, Drunken Master, and Jerry
Maguire.  They were tested with the same pinned binary in three arms, changing
only the texture-closure environment.

| unseen scene | same-build static source fit | dynamic covariance | guarded response |
| --- | ---: | ---: | ---: |
| Quiz Show 31% | 0.02243 | 0.02941 | **0.00671** |
| Life of Brian 31% | 0.06392 | 0.01809 | **0.00848** |
| Drunken Master 31% | 0.01136 | 0.01256 | **0.00346** |
| Jerry Maguire 31% | 0.04970 | **0.00951** | 0.01212 |
| **macro mean** | **0.03685** | **0.01739** | **0.00769** |

Guarded response improves 4/4 unseen scenes over the exact same-build static
control and wins 3/4 against dynamic covariance.  Dynamic covariance regresses
Quiz Show and Drunken Master.  Across the original eight plus these four
unseen scenes:

| arm | 12-scene macro error | improves/equal versus static |
| --- | ---: | ---: |
| static source fit | 0.04335 | baseline |
| dynamic covariance | 0.01858 | 8/12 |
| **guarded response** | **0.01357** | **12/12** |

Artifacts:

```text
/media/merged-storage/media/test-encodes/
    sourcefit-texture-response-margin-newfilms-20260804
```

Every fresh static, dynamic, and guarded output passed full libdav1d decoding.

## Grain-off bases are very close, but not byte-identical

An identical repeat of the Quiz Show static arm produced the same grain-off
MD5, so encoding is deterministic.  Static, dynamic, and guarded arms do not
share that hash.  Changing AV1 film-grain parameters therefore changes the
encoded base slightly—likely through NVENC rate-control interaction, although
the mechanism was not traced here.

The difference is bounded on the four unseen scenes:

- static-versus-guarded grain-off luma PSNR: `50.32` to `53.26` dB;
- output-size delta: `-0.210%` to `+0.037%`;
- maximum movement of any measured base texture axis: `0.0037`.

The synthesized-grain axis error moves much more:

| scene | static synthesis error | guarded synthesis error | max base-axis movement |
| --- | ---: | ---: | ---: |
| Quiz Show | 0.02877 | 0.00595 | 0.00151 |
| Life of Brian | 0.06873 | 0.00983 | 0.00366 |
| Drunken Master | 0.01410 | 0.00263 | 0.00112 |
| Jerry Maguire | 0.05878 | 0.01852 | 0.00101 |

The result is therefore predominantly a synthesis-texture correction, but
future documents must say "same separator and near-identical base," not
"identical base."

## Oracle robustness fix

Jerry Maguire contains a valid short grain-off interval at frame 193.  The
texture oracle previously required film-grain side data on *every* earlier
decoded frame, even when the grain-off frame was not selected for measurement;
both control and candidate aborted on the same interval.

Commit `3cd04f75` lets measurement callers require side data only on their
explicit frame pairs.  Emission audits retain the strict all-frame default.
The original six frozen frame pairs then measured Jerry without changing the
sample after seeing its result.

## Verdict

This is the strongest luma texture-closure candidate so far.  It validates the
architectural direction—fit source texture, measure what correlated texture
survives in the base, and choose a representable AV1 model by delivered
response—rather than merely finding another global interpolation lever.

It is **not ready for production**.  The evidence authorizes continued
default-off development only:

1. the `0.01` confidence margin is exploratory and calibrated only at QVBR 29;
2. temporal texture stability/flicker across model updates has not been scored;
3. per-luma strength closure remains open;
4. chroma amplitude, especially V, remains independently open;
5. semantic grain admission is still a measured shadow policy, not a safe
   implementation;
6. conventional/base-fidelity metrics should be rerun on the final integrated
   candidate before perceptual review.

The next quality-first step is temporal stability on static, dynamic, and
guarded arms, using several windows that cross table updates.  If guarded
response does not pump or flicker, freeze its luma texture path and resume the
separate per-luma-strength and chroma-amplitude investigations.  Do not tune the
margin again on these twelve scenes.
