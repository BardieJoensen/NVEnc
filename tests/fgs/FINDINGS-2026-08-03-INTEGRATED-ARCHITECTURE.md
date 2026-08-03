# Integrated source-fit architecture gate, 2026-08-03

> Research only.  Nothing in this experiment was deployed to Tdarr.
> `modelsrc` remains default-off and paired centred motion remains available
> only through its test environment hook.  The production image is still
> r4069.

## Question and priority

Does the two-operator architecture improve real-film grain fidelity without
hiding picture damage, and which remaining code problem should be solved next?
Quality is the objective.  Compression is reported because it is a useful
consequence; throughput was not controlled and is not used for a decision.

The four arms were:

- `plain`: same-QVBR compression and full-reference bias control;
- `production`: deployed r4069 bilateral separator and residual-derived model;
- `causal`: motion separator, one past reference, `modelsrc=on`, `thsad=640`;
- `paired`: one past plus one future reference, admitted at the weaker of the
  two affinities, `modelsrc=on`, `thsad=640`.

All encodes used AV1 10-bit, QVBR 29, 20 Mbit/s maximum, preset P4, tune HQ and
no AQ.  This is deliberately the regime on which the QVBR leak transfer was
calibrated; a later production-settings transfer test must not be mixed into
this result.

Candidate source was `c6a4605c`; candidate binary SHA-256 was
`0e5b34278cbd3ddc62140ff0404850045414ce88789595fa4f82f3ffde324d63`.
The production binary SHA-256 was
`33233900224c3d1d049b8592a0b592479def9d26ba7999fa9ccd6fe1990b1c5b`.

Corpus: 287/288-frame lossless 4K excerpts from Casino, Interstellar,
Scarface, Taxi Driver, The Deer Hunter and The Shining.

Artifacts and resumable manifests:

```text
/media/merged-storage/media/test-encodes/sourcefit-integrated-20260803/
```

Reproduction entry points:

```text
tests/fgs/integrated_architecture.py
tests/fgs/integrated_quality_report.py
```

## Safety result

- all 24 direct AV1 streams completed;
- every stream passed a complete `libdav1d -xerror` decode;
- each quality pair passed exact frame-count and relative-PTS validation;
- all scored crops carried matching limited-range BT.2020/PQ metadata;
- the CPU suite passed 88/88 after the two integrated harnesses were added.

This clears continued testing, not production.

## Grain texture: the architectural change works

`temporal_grain_report.py` selected fixed static flat blocks from the source
and applied the same mask to every arm.  Lag-1 and lag-2 are
amplitude-independent grain-size descriptors: high positive values are
coarser/more correlated grain; values near zero are finer grain.

Mean absolute luma synthesis error across six films:

| arm | lag-1 error | lag-2 error |
| --- | ---: | ---: |
| production residual fit | 0.2231 | 0.3434 |
| causal source fit | 0.0219 | **0.0343** |
| paired source fit | **0.0192** | 0.0358 |

Production is systematically too fine.  Taxi, for example, has source
lag-1/lag-2 `0.804/0.438`; production synthesises `0.564/0.003`, causal
`0.790/0.426`, and paired `0.812/0.485`.  The two-operator design therefore
fixes the coarse-grain failure rather than merely moving grain energy.

The result generalises to chroma texture:

| plane | production lag-1 / lag-2 MAE | causal | paired |
| --- | ---: | ---: | ---: |
| U | 0.191 / 0.198 | **0.019 / 0.025** | 0.024 / 0.026 |
| V | 0.312 / 0.291 | **0.055 / 0.048** | 0.060 / **0.043** |

This is the direct answer to whether the analyser can distinguish fine and
coarse grain: yes, and fitting the AR model from source flat-block statistics
reduces that error by roughly an order of magnitude.

## Strength: much better, still luma-shaped

Whole-title energy must be variance weighted.  Equal-frame amplitude means
overweighted low-grain frames and initially made Deer Hunter paired look like
`1.067`; global sigma was `1.010`, and the independent production-static
closure population measured `0.946`.  The discarded equal-frame number stays
recorded in the temporal JSON rather than being silently replaced.

Variance-weighted played-total luma on the production-static closure mask:

| title | production | causal | paired |
| --- | ---: | ---: | ---: |
| Casino | 0.683 | 0.909 | **0.972** |
| Interstellar | 0.728 | **1.061** | 1.074 |
| Scarface | 0.851 | 1.002 | 1.006 |
| Taxi Driver | 0.684 | **0.991** | 0.979 |
| The Deer Hunter | 0.776 | 0.932 | **0.946** |
| The Shining | 0.683 | **0.992** | 1.010 |

Production mean/MAE to one are 0.734/0.266.  Causal is 0.981/0.040 and paired
0.998/0.032.  The corpus mean is no longer the problem.  Opposite per-luma
errors remain:

| title | paired populated-band range | labelled failure |
| --- | ---: | --- |
| Casino | 0.957 .. 1.008 | none large |
| Interstellar | 0.978 .. **1.179** | darkest band high |
| Scarface | 0.982 .. 1.125 | 1.125 band has only 122 blocks |
| Taxi Driver | **0.907** .. 1.038 | brightest populated band low |
| The Deer Hunter | **0.919 .. 1.295** | dark-to-bright slope |
| The Shining | 0.972 .. 1.046 | none large |

Measured base-plus-synthesis variance versus played total closes within 0.006
throughout.  The earlier exact emission audit established pixel-exact
normative synthesis on this path, and the current streams all pass full dav1d
decode, but a fresh exact audit remains part of the next offline response test.
The present evidence localises the large errors to the signalled curve/target
population rather than variance composition.  Interstellar and Deer Hunter
are strong enough labelled cases to justify that test; they do not justify
adding a CUDA synthesis pass yet.

Variance-weighted global chroma totals also improve, but U remains low:

| plane | production mean | causal | paired |
| --- | ---: | ---: | ---: |
| U | 0.833 | 0.901 | **0.916** |
| V | 0.862 | 0.970 | **0.972** |

Chroma strength therefore remains a separate modelling task.  Its texture is
already substantially fixed; a blind chroma gain would repeat the luma
occupancy mistake.

## Separator direction: paired does exactly what it claims

`temporal_drag.py` streamed every frame and jointly projected clean-base error
onto previous and next source directions.  Values below are overall / highest
motion-bin lag asymmetry:

| title | production | causal | paired |
| --- | ---: | ---: | ---: |
| Casino | -0.00004 / 0.00013 | 0.02183 / 0.00842 | **-0.00008 / -0.00006** |
| Interstellar | 0.00171 / -0.00055 | 0.03166 / 0.01589 | **0.00119 / -0.00039** |
| Scarface | 0.00037 / 0.00001 | 0.03921 / 0.01001 | **0.00094 / -0.00030** |
| Taxi Driver | -0.00056 / -0.00115 | **0.12866** / 0.01052 | **-0.00174 / -0.00144** |
| Deer Hunter | 0.00030 / 0.00035 | 0.01467 / 0.00638 | **0.00064 / 0.00073** |
| The Shining | 0.00041 / 0.00031 | 0.01052 / 0.00562 | **0.00018 / 0.00001** |

Paired removes causal direction on all six titles.  Taxi confirms that this is
not merely a stricter-SAD effect: most of its causal signal is low-motion
brightness/state drag, which SAD cannot reject.

But paired increases the symmetric projection on every title.  Removing
direction is not the same as preserving the picture.

## Base fidelity: paired is not the quality solution

All metrics below score the grain-disabled direct AV1 base against the
lossless source over the complete 1920x1080 centre crop.  Full-reference base
scores still reward leaving source grain in the base, so they are guard rails,
not a separator objective.  Butteraugli max-p95 is the localized-artifact
column; lower is better.

| title | VMAF production / causal / paired | Butter p95 production / causal / paired |
| --- | ---: | ---: |
| Casino | 85.79 / 84.35 / **83.62** | 8.95 / 12.05 / **15.03** |
| Interstellar | 87.47 / 86.02 / **85.10** | 10.79 / 12.28 / **11.83** |
| Scarface | 79.04 / 79.00 / **78.32** | 10.81 / 11.21 / **11.41** |
| Taxi Driver | 84.13 / 82.30 / **80.00** | 11.94 / 14.85 / **14.99** |
| Deer Hunter | 75.54 / 75.10 / **72.87** | 10.33 / 12.93 / **14.61** |
| The Shining | 92.72 / 92.18 / **91.74** | 10.10 / 15.76 / **15.57** |

Paired versus causal:

- saves another 16.1--24.8% of the causal bytes;
- loses base VMAF on 6/6, mean -1.216;
- loses mean base SSIMULACRA2 on 6/6, mean -2.526;
- worsens Butteraugli max-p95 on 4/6, mean +0.724.

The old loose-confidence motion result was Butter p95 35--52.  Causal 640 at
11.2--15.8 is a large real improvement, not a rebranding of the old failure.
It still has directional error.  Paired eliminates that error by accepting a
more strongly averaged symmetric base and is not a quality-first successor.

Finished full-reference scores are retained in `scores.json`, but they are not
used to rank grain fidelity.  The plain control again shows why: these metrics
penalise independently positioned synthesis, and the candidates intentionally
move much more grain from coded picture to synthesis.

## Compression, secondary to the quality decision

| arm | corpus bytes | saving vs plain |
| --- | ---: | ---: |
| plain | 150,902,000 | -- |
| production | 115,812,295 | 23.25% |
| causal source-fit | 102,274,152 | **32.22%** |
| paired source-fit | 82,889,020 | **45.07%** |

Causal now reaches the low end of the original 30--40% target under the much
safer threshold.  Paired clears it comfortably, but its extra bytes saved are
currently purchased with worse base fidelity.

## Decision and next code work

1. **Keep the source-derived AR architecture.**  It is the largest measured
   grain-quality improvement and works on luma and chroma, fine and coarse
   grain.
2. **Keep the rate-aware strength closure as opt-in research.**  It moves
   whole-title amplitude close to target but still has labelled per-luma
   failures.  Run the sparse fixed-seed actual-pixel response prototype on the
   new Interstellar and Deer Hunter cases before considering implementation.
3. **Do not promote paired centred motion.**  It proves that centered timing
   can remove causal state, but its symmetric averaging worsens the base.
4. **The next separator code experiment is rejection, not more averaging:**
   trace forward/backward motion-vector cycle consistency and fall back to the
   current-frame/spatial estimate where the pair is inconsistent or newly
   uncovered.  Rank it on drag, base Butter tail, base VMAF/SSIMU2 and bytes.
5. **Keep chroma strength separate.**  U is still about 8--10% low overall and
   per-luma weak-grain bands can move in the opposite direction.
6. A blinded high-disocclusion playback review remains mandatory for any
   motion-based separator.  No aggregate metric replaces it.

No speed optimisation follows from this gate.  The quality architecture and
separator admission must settle first.
