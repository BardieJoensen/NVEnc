# Exact chroma emission and rolling-population audit — 2026-08-03

> Quality-first research only. Nothing here was deployed to Tdarr. Production
> remains r4069 with bilateral separation and the residual-derived model;
> `modelsrc` remains default-off, PSD is absent, and no research environment
> hook is set.

## Question

The temporal chroma-closure experiment improved some titles and regressed
others. This audit asks where the remaining U/V strength error actually enters:

1. analyzer observations and rolling history;
2. curve fill, smoothing and coordinate geometry;
3. chroma AR or the cross-plane luma predictor; or
4. normative AV1 synthesis, rounding, clipping or decoding.

Taxi Driver V is the labelled high case. Interstellar V is the mandatory
opposite-sign control.

## Exact normative synthesis closes

`chroma_emission_audit.py` now reproduces the AV1 4:2:0 Cb/Cr synthesis path:
plane-specific seed offsets, spatial AR recursion, the optional luma-grain
predictor, scaling lookup, one-pixel overlap, rounding and restricted-range
clipping. The model comes from the bitstream side data, including NVENC's real
per-frame seed rather than the unrelated table seed.

The local synthesizer matches dav1d exactly:

| title / plane | selected blocks | compared pixels | mismatches | max error |
| --- | ---: | ---: | ---: | ---: |
| Taxi Driver U | 7,234 | 3,703,808 | 0 | 0 |
| Taxi Driver V | 7,234 | 3,703,808 | 0 | 0 |
| Interstellar U | 2,831 | 1,449,472 | 0 | 0 |
| Interstellar V | 2,831 | 1,449,472 | 0 | 0 |

The luma-grain predictor is not the amplitude fault. Removing it changes Taxi
V synthesis by only 0.6% in aggregate and about 0.6--0.9% in the populated
bands; Interstellar is similarly small. Removing all spatial chroma taps cuts
amplitude to roughly 58% of the real result, proving that the AR template
matters globally, but its realised gain is stable across luma bands. Decoder,
seed, lookup domain and entry-wide template gain are therefore ruled out.

Artifacts:

```text
/media/merged-storage/media/test-encodes/chroma-closure-quality-20260803/
  reports/emission-chroma/
```

## The rolling analyzer is reproduced

`chroma_population_trace.py` independently reproduces production's exact
spatial flat-block selector, dense detrended source-minus-base variance,
20 hard source-luma bins, eight-frame history, empty-bin fill and 1-2-1
smoothing. Only one global scale is fitted when comparing the reconstructed
shape with each emitted table. That scale absorbs AR/template gain,
`grain_scale_shift` and `scaling_shift`, all of which are plane-global and
cannot explain a per-bin shape error.

Across six Taxi V model intervals and seven Interstellar V intervals:

| title | table/reconstruction cosine | weighted relative RMSE range |
| --- | ---: | ---: |
| Taxi Driver V | 1.0000 | 0.0059 .. 0.0096 |
| Interstellar V | 0.9999 .. 1.0000 | 0.0045 .. 0.0127 |

The emitted curve is therefore the expected output of the rolling statistics.
There is no stale-history or hidden-GPU-statistics discrepancy left to find.

Taxi's darkest populated V bin exposes the construction problem. Across the
six traced windows its raw sigma is `0.631 .. 0.808`, but the unconditional
three-bin smoother raises it to `1.123 .. 1.342`. Actual pixels then sit
between endpoint-grid controls and interpolate toward the much stronger next
bin. The exact played result is consequently too high.

## Coupled curve counterfactuals

Every candidate below changes only an offline copy of the selected chroma
curve. The coded clean base, AR coefficients and real bitstream seed are held
fixed, and synthesis is evaluated by the pixel-exact model above.

| V curve | Taxi synth/target | Interstellar synth/target |
| --- | ---: | ---: |
| current | 1.0926 | **0.8454** |
| centre coordinates only | 1.0451 | 0.8069 |
| approximately remove smoothing only | 1.0718 | 0.8529 |
| exact reconstructed raw bins, endpoint grid | 1.0736 | 0.8496 |
| exact reconstructed raw bins, centred grid | **1.0194** | 0.7966 |

The coupled raw/centred replay substantially improves Taxi. Its 0.050--0.100
band moves from `2.586` to `1.343` times target, and the dominant neighbouring
bands stay between about `0.89` and `1.09`. But the same change materially
worsens Interstellar's already-low aggregate. Interstellar's 0.250--0.300 band
remains only `0.615` of target. This is the mandatory negative: curve geometry
is a real contributor, not a universal fix.

## The zero clamp is not the missing gain

The previously unmeasured
`max(0, V_source - V_base)` clamp fires frequently in weak chroma bins:

- Taxi's darkest occupied V bin: 6.3--20.8% of blocks;
- Interstellar's dominant low-V bin: about 9.7--33.6% depending on interval.

That count looks alarming but the rejected differences are tiny. Allowing the
negative values to cancel changes Taxi's raw sigma by at most about `0.002`
and Interstellar's normally by `0.001 .. 0.006` in populated bins. More
importantly, the inequality is one-way:

```text
sum(max(0, difference)) >= max(0, sum(difference))
```

Per-block clamping raises rather than lowers the variance estimate relative to
a signed bin average. Excluding rectified blocks from the denominator would
raise it again (by as much as roughly 20% at a 30% zero rate). Neither change
can explain Interstellar's under-delivery, so no CUDA clamp change follows.

## Decision

1. Keep the source-fitted AR architecture. Its order-of-magnitude improvement
   in luma and chroma texture is independent of this amplitude finding.
2. Do not implement a coordinate remap, remove smoothing globally, exclude
   rectified blocks, or promote the temporal chroma-closure experiment. Every
   one has an opposite-sign real-film failure.
3. Treat chroma amplitude as an observation/transfer problem. The analyzer
   faithfully emits its spatial source-minus-base estimate, but that estimate
   does not equal temporal played-out truth on every title. AV1 emission is not
   the missing mechanism.
4. Do not build a second runtime normative-synthesis solver from this result.
   The corresponding bounded pixel-response approach has already failed its
   luma external gate; two chroma titles do not overturn that evidence.
5. The next quality gate is perceptual: production bilateral/residual versus
   bilateral/source-fit on Taxi Driver, Deer Hunter, Casino and The Shining.
   Judge grain scale, dark weak-grain bands, chroma crawling and picture detail
   independently. If the measured low-energy chroma errors are not visible,
   they should not block the architectural texture improvement. If they are
   visible, the next measurement is a per-plane, multi-QVBR temporal transfer
   study—not another fixed gain or fixture-derived threshold.

Speed remains deferred. Compression is unchanged by these table-only
counterfactuals because AV1 film grain is out of loop.
