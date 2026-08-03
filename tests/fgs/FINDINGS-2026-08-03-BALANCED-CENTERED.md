# Causal-matched centred motion gate, 2026-08-03

> Research only. Nothing in this experiment was deployed to Tdarr.
> `modelsrc` remains default-off, and the balanced centred scheduler is
> reachable only through a test environment hook. Production remains on the
> conservative bilateral/residual-analyser configuration.

## Question

The first centred-motion prototype removed the causal separator's directional
lag, but it also changed the amount of temporal averaging. Its ideal prior was

```text
current=2, previous=1, next=1  -> references are 1/2 of the total
```

whereas the one-reference causal arm used

```text
current=2, previous=1          -> references are 1/3 of the total
```

That made the earlier paired result ambiguous: it changed direction and
strength at once. The new test-only `paired-balanced` arm uses
`current=4, previous=1, next=1`, preserving the centred past/future pair and
paired SAD confidence while matching causal's ideal one-third reference
exposure.

The decision question was quality-first: can centring remove directional
temporal error without buying the result through extra smoothing? Compression
is reported as a consequence. Throughput was not controlled and is not used
for a decision.

## Isolation and build

Candidate source was commit `b2925f06`; the pinned candidate binary SHA-256
was:

```text
23deca38469d854e4ee0cf296b13cb9424958113529c7292c3b2d00b4b7c0538
```

The candidate was built from the pinned clone created by `local_gate.sh`, not
from the live worktree. Before testing the new arm, the old r4066 candidate and
the new pinned binary were run on the same 32-frame disocclusion fixture:

| mode | clean base | grain table |
| --- | --- | --- |
| hook unset, causal | byte-identical | byte-identical |
| existing `paired` hook | byte-identical | byte-identical |

Only `NVENC_FGS_TEST_MOTION_CENTERED=paired-balanced` changes output. There is
no public option and no default change.

Artifacts and resumable manifests:

```text
/media/merged-storage/media/test-encodes/balanced-exposure-20260803/
/media/merged-storage/media/test-encodes/sourcefit-balanced-20260803/
```

The comparison corpus and older arms remain at:

```text
/media/merged-storage/media/test-encodes/sourcefit-integrated-20260803/
```

## Known-negative fixture

`coarse_detail_occl` is the labelled disocclusion specimen. The three arms
used the same pinned binary, `modelsrc=on`, one motion reference and
`thsad=640`.

| arm | capture | detail transfer | systematic edge RMSE | lag asymmetry | symmetric projection |
| --- | ---: | ---: | ---: | ---: | ---: |
| causal | 62% | 0.778 | 1.65 | +0.00448 | 0.00822 |
| ordinary centred | 68% | 0.786 | 1.62 | -0.00013 | 0.01079 |
| balanced centred | 60% | 0.786 | **1.61** | **-0.00007** | **0.00695** |

Balanced centred removes causal direction without inheriting ordinary
centred's stronger symmetric drag. The lower capture is consistent with less
temporal smoothing; it is not treated as a quality failure because detail
transfer is unchanged and both temporal diagnostics improve.

This fixture result was the gate for spending time on real film.

## Six-film corpus and safety

The corpus is the same 287/288-frame lossless 4K set used by the integrated
architecture gate: Casino, Interstellar, Scarface, Taxi Driver, The Deer
Hunter and The Shining. All arms use AV1 10-bit, QVBR 29, 20 Mbit/s maximum,
preset P4, tune HQ and no AQ.

- all six balanced AV1 streams and six lossless clean bases completed;
- every AV1 stream passed a complete `libdav1d -xerror` decode;
- all quality pairs passed exact frame-count and relative-PTS validation;
- all scored crops carried matching limited-range BT.2020/PQ metadata;
- no impossible VMAF/SSIMULACRA2 values or soft-telecine frame-count mismatch
  occurred.

This clears continued research, not production.

## Separator quality: balanced is the best motion arm

`temporal_drag.py` jointly projects clean-base error onto previous and next
source directions. Lower absolute asymmetry means less directional state;
lower symmetric projection means less two-sided temporal averaging.

| arm | mean absolute asymmetry | mean symmetric projection |
| --- | ---: | ---: |
| production bilateral | **0.00057** | **0.01041** |
| causal motion | 0.04109 | 0.03461 |
| ordinary centred motion | 0.00080 | 0.05050 |
| balanced centred motion | **0.00069** | **0.03365** |

Balanced removes the causal direction while reducing symmetric projection
against causal on 6/6 titles (mean -0.00097) and against ordinary centred on
6/6 (mean -0.01686). Taxi Driver is the strongest case:

| arm | lag asymmetry | symmetric projection |
| --- | ---: | ---: |
| causal | +0.12866 | 0.12386 |
| ordinary centred | -0.00174 | 0.18328 |
| balanced centred | **-0.00130** | **0.12193** |

The result falsifies the earlier interpretation that centring itself caused
the base-quality loss. The loss came primarily from doubling ideal temporal
exposure.

## Base-fidelity guard rails

The grain-disabled direct AV1 bases were scored against the lossless source
over the complete 1920x1080 centre crop. These scores reward leaving source
grain in the base, so they are guard rails rather than a separator objective.
Nevertheless, they agree consistently on the motion-arm comparison.

Balanced versus causal:

- base VMAF improves on 6/6, mean `+0.378`;
- mean base SSIMULACRA2 improves on 6/6, mean `+0.791`;
- mean Butteraugli 2-norm improves on 6/6, mean `-0.0399`;
- Butteraugli max-p95 improves on 5/6, mean `-1.269`.

Balanced versus ordinary centred:

- base VMAF improves on 6/6, mean `+1.594`;
- mean base SSIMULACRA2 improves on 6/6, mean `+3.317`;
- mean Butteraugli 2-norm improves on 6/6, mean `-0.0876`;
- Butteraugli max-p95 improves on 5/6, mean `-1.993`.

Balanced is still not a production-quality replacement for the bilateral arm.
Against production, mean base VMAF is `-0.579`, mean SSIMULACRA2 is `-5.517`,
and mean Butteraugli 2-norm is `+0.149`; production wins SSIMULACRA2 and
Butteraugli on all six. The architectural grain model is substantially better,
but motion separation still carries more base damage than bilateral.

Finished full-reference metrics are retained in `scores.json` but are not used
to rank grain fidelity: independent AV1 synthesis is positionally different
from source grain and is penalised even when its statistics are correct.

## Grain texture: the source-fit improvement survives

`temporal_grain_report.py` used fixed production-selector, temporal-static
source masks. Lag-1 and lag-2 are amplitude-independent spatial-scale
descriptors.

Luma synthesis mean absolute error across six films:

| arm | lag-1 MAE | lag-2 MAE |
| --- | ---: | ---: |
| production residual fit | 0.2231 | 0.3434 |
| causal source fit | 0.0219 | **0.0343** |
| ordinary centred source fit | **0.0192** | 0.0358 |
| balanced centred source fit | **0.0192** | 0.0368 |

Taxi Driver remains the direct coarse-grain check: source lag-1/lag-2 is
`0.804/0.438`; balanced synthesis is `0.812/0.485`. The balanced separator
therefore preserves the two-operator analyser's fine/coarse discrimination.

Chroma texture also remains close to the existing source-fit arms:

| plane | balanced lag-1 MAE | balanced lag-2 MAE |
| --- | ---: | ---: |
| U | 0.0237 | 0.0256 |
| V | 0.0620 | 0.0451 |

## Strength: globally excellent, locally unresolved

On the temporal-static mask, pooled played-total luma sigma is:

| arm | corpus mean | MAE to one |
| --- | ---: | ---: |
| production | 0.7428 | 0.2572 |
| causal | 0.9884 | 0.0294 |
| ordinary centred | 1.0095 | 0.0201 |
| balanced centred | **1.0001** | **0.0173** |

Balanced per-title luma totals are `0.961, 1.029, 0.991, 1.013, 1.010,
0.996`. The equal-frame Deer Hunter display is `1.065`; pooled sigma is
`1.010`. Both remain in the JSON so the weighting trap is visible.

The independent production-static closure mask gives balanced mean `0.989`
and MAE `0.031`, marginally better than ordinary centred's `0.998/0.032`.
Measured total agrees with base-plus-synthesis variance to mean absolute
`0.0017`, so the remaining strength error is not an emission-composition bug.

The labelled per-luma failures improve but remain:

| title | balanced populated-band range | comparison |
| --- | ---: | --- |
| Interstellar | 0.972 .. **1.151** | darkest band was 1.179 paired |
| Taxi Driver | **0.889** .. 1.031 | sparse brightest band remains low |
| The Deer Hunter | **0.917 .. 1.248** | high band was 1.295 paired |

Chroma amplitude is still separate. Balanced pooled totals are `0.912` for U
and `0.979` for V. A global U gain is not justified because luma-band errors
have different signs and weak chroma populations are noisy.

## Compression, secondary

| arm | corpus bytes | saving versus plain |
| --- | ---: | ---: |
| plain | 150,902,000 | -- |
| production | 115,812,295 | 23.25% |
| causal source-fit | 102,274,152 | 32.22% |
| balanced centred source-fit | 99,631,221 | **33.98%** |
| ordinary centred source-fit | 82,889,020 | 45.07% |

Balanced adds 1.75 percentage points of saving over causal while improving
every mean base-fidelity metric above. Ordinary centred's larger saving is
still rejected because it is purchased with extra temporal averaging.

## Decision

1. **Keep balanced centred motion as the leading research separator.** It is
   the first motion variant to remove directional lag and improve, rather than
   trade away, measured base fidelity.
2. **Do not deploy it yet.** Production bilateral still wins the base-quality
   guard rails on real film, `modelsrc` is default-off, and a blinded
   high-disocclusion playback review remains mandatory.
3. **Do not add motion-cycle admission.** The labelled negative already showed
   it ranks residual disocclusions in the wrong direction after paired SAD.
4. **Treat per-luma strength as the next independent analyser problem.** The
   global strength and texture are solved well enough that another global gain
   would make the result worse. Interstellar, Taxi Driver and Deer Hunter are
   the labelled cases for a population/curve estimator experiment.
5. **Keep chroma strength separate.** Its texture is good, but U amplitude
   remains about 9% low and does not share one safe correction with luma.
6. Speed work remains deferred. The quality architecture and perceptual
   separator clearance come first.

