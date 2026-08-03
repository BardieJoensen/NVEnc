# Detail-aware post-motion finish gate, 2026-08-03

> Research only. Nothing in this experiment was deployed to Tdarr.
> Production remains on r4069 with the bilateral separator, residual-derived
> model and no research environment hooks. `modelsrc` remains default-off.

## Question

The balanced centred motion arm improved the source-derived grain model and
removed directional lag, but production bilateral still won the real-film
base-fidelity guard rails. Inspection found that the motion child was not the
only luma operator: its output always received a second local spatial
bilateral pass. Unlike the equivalent FFT3D finishing pass, that pass ignored
the analyser's existing block-coherence metrics and therefore applied its full
strength over structured detail.

This gate isolates that second operator. Three arms use the same balanced
centred motion separator, one reference in each temporal direction,
`thsad=640`, and `modelsrc=on`:

- `uniform`: the existing unconditional luma finish;
- `detail`: fade the luma finish in coherent-detail blocks using the existing
  `FilmGrainBlockMetric` path;
- `nofinish`: skip only the luma finish while retaining the chroma pass.

The last arm is a control, not a proposed configuration. The motion child
handles only luma, so disabling chroma at the same time would confound two
questions.

## Isolation and build

The implementation is test-only. `NVENC_FGS_TEST_MOTION_FINISH=detail`
selects the detail-aware arm and `off` selects the chroma-only control. With
the variable unset, the default remains the old uniform pass. No public
option or default changed.

Candidate source was commit `a5aaaca5`; the pinned candidate binary SHA-256
was:

```text
46256276d961dd25549b4bd8164ce7ded88512e83fef4662982414b6bb165b81
```

The binary was built from the pinned clone produced by the local gate, not
from the live worktree. On the retained default balanced specimen:

- the grain table SHA-256 is exactly
  `32e044f4a751207e1b1f5f8bbc541eb44d070be4d8da32a9d40b92a141842141`;
- copied video-stream MD5 is exactly
  `b7b9199f2342f35d2683822432007df2` on both binaries;
- decoded raw-video MD5 is the same value on both binaries.

The Y4M file hashes differ only because one invocation wrote SAR `A0:0` and
the retained comparison wrote `A1:1`; their frame payloads are identical.
This is a payload/default-invariance pass, not a claim that the differently
invoked containers are byte-identical.

Artifacts and resumable manifests:

```text
/media/merged-storage/media/test-encodes/motion-finish-20260803/
/media/merged-storage/media/test-encodes/sourcefit-motion-finish-20260803/
```

## Labelled disocclusion fixture

`coarse_detail_occl` separates preservation of known fine structure from
capture of injected coarse grain.

| finish | coarse-grain capture | fine-detail transfer | systematic edge RMSE |
| --- | ---: | ---: | ---: |
| uniform | 60% | 0.786 | 1.61 |
| detail-aware | **64%** | **0.937** | **1.27** |
| no luma finish | 36% | 0.971 | **1.25** |

The no-finish control proves that the spatial pass is responsible for most of
the remaining structure loss, but removing it is not viable: coarse-grain
capture falls to 36%. The detail-aware pass retains nearly all of the
structure benefit while improving rather than trading away capture. It is the
only arm promoted to the real-film corpus.

## Six-film safety gate

The corpus is the same 287/288-frame lossless 4K set used by the integrated
architecture work: Casino, Interstellar, Scarface, Taxi Driver, The Deer
Hunter and The Shining. Encodes use AV1 10-bit, QVBR 29, 20 Mbit/s maximum,
preset P4, tune HQ and no AQ.

- all six encoded streams and six grain-disabled clean bases completed;
- every AV1 stream passed a complete `libdav1d -xerror` decode;
- all metric pairs passed exact frame-count and relative-PTS validation;
- all crops carried matching limited-range BT.2020/PQ metadata;
- the default-invariance check and labelled fixture passed before the corpus
  was run.

This clears continued research and blinded playback, not production.

## Base fidelity

The grain-disabled direct AV1 bases were scored against the lossless source
over the complete 1920x1080 centre crop. These metrics reward source grain
left in the coded base and are therefore guard rails, not grain-fidelity
objectives.

Detail-aware versus the previous uniform balanced arm:

- base VMAF improves on 6/6, mean `+1.940`;
- base VMAF p1 improves on 6/6, mean `+1.250`;
- base PSNR-Y improves on 6/6, mean `+0.221 dB`;
- mean base Butteraugli 2-norm improves on 4/6, mean `-0.0170`;
- mean base SSIMULACRA2 is effectively flat, mean `-0.057`, with 3/6 wins.

The finished streams show the same direction against uniform balanced:
VMAF improves on 6/6 by `+1.548`, SSIMULACRA2 improves by `+1.182` on
average, and Butteraugli 2-norm improves by `-0.0573` on 5/6.

The candidate does not yet beat production unambiguously. Against production
bilateral, its base VMAF is `+1.361` on average and wins 6/6, but production
wins base SSIMULACRA2 and Butteraugli on 6/6: candidate deltas are `-5.574`
and `+0.1322`, respectively. The metrics disagree about whether leaving more
grain-like structure in the base is fidelity or residue. This is precisely
where a blinded disocclusion review is required.

Finished full-reference metrics are retained in `scores.json` but are not
used to rank grain fidelity. Independently positioned normative AV1 grain is
penalised even when its amplitude and texture are correct.

## Temporal separator behaviour

`temporal_drag.py` jointly projects clean-base error onto previous and next
source directions. Detail-aware finishing preserves the centred scheduler's
near-zero direction while reducing symmetric contamination on every title.

| arm | mean absolute lag asymmetry | mean symmetric projection |
| --- | ---: | ---: |
| uniform balanced | 0.000685 | 0.033648 |
| detail-aware balanced | 0.000686 | **0.031068** |

The symmetric projection falls on 6/6 titles. Taxi Driver improves from
`0.12193` to `0.11676`; Scarface improves from `0.04448` to `0.03926`.
The gain is not obtained by reintroducing one-sided temporal state.

## Grain texture survives

The source-fit AR model remains independent of the finishing operator.
`temporal_grain_report.py` used fixed production-selector, temporal-static
source masks. Luma synthesis lag-1/lag-2 mean absolute error across six films
is:

| arm | lag-1 MAE | lag-2 MAE |
| --- | ---: | ---: |
| uniform balanced | 0.01919 | 0.03676 |
| detail-aware balanced | **0.01888** | **0.03596** |

Taxi Driver's coarse-grain truth is `0.804/0.438`; detail-aware synthesis is
`0.812/0.485`. The change therefore protects more of the clean base without
reverting to production's too-fine residual fit.

Chroma texture is likewise stable: U lag-1/lag-2 MAE is `0.02356/0.02532`
and V is `0.06043/0.04303`. The luma-only finish experiment does not smuggle
in a chroma model change.

## Strength and closure

Variance-weighted played-total luma on the temporal-static mask changes from
mean/MAE `1.0001/0.0173` to `0.9850/0.0188`. Per-title detail-aware totals are
`0.954, 0.969, 0.986, 1.006, 1.006, 0.989`.

On the independent production-static closure mask, mean/MAE improves from
`0.9890/0.0311` to `0.9737/0.0263`. That apparent contradiction is useful:
the new arm corrects Interstellar's large overshoot (`1.060 -> 0.995`) while
moving five already-low titles slightly lower. Measured total still agrees
with base-plus-synthesis variance to mean absolute `0.0015`, so this is not a
decoder-composition or emission failure.

The labelled per-luma errors remain:

| title | uniform populated-band range | detail-aware range |
| --- | ---: | ---: |
| Casino | 0.945 .. 0.991 | 0.939 .. 0.983 |
| Interstellar | 0.997 .. 1.151 | **0.951 .. 1.061** |
| Scarface | 0.992 .. 1.124 | 0.987 .. 1.125 |
| Taxi Driver | 0.889 .. 1.031 | 0.881 .. 1.027 |
| The Deer Hunter | 0.917 .. 1.248 | 0.912 .. 1.248 |
| The Shining | 0.957 .. 1.026 | 0.949 .. 1.025 |

This finishing-pass change fixes a separator problem; it does not fix the
independent per-luma strength-estimation problem. Deer Hunter remains the
clearest labelled failure. A global gain would undo Interstellar's correction
and is not justified.

U played-total amplitude remains low at `0.908` mean; V is `0.977`. This
experiment supplies no evidence for a blind chroma gain.

## Compression, secondary

| arm | corpus bytes | saving versus plain |
| --- | ---: | ---: |
| plain | 150,902,000 | -- |
| production bilateral | 115,812,295 | 23.25% |
| uniform balanced source-fit | 99,631,221 | 33.98% |
| detail-aware balanced source-fit | 116,499,857 | 22.80% |

The recovered structure costs the extra bytes that uniform motion previously
saved. That is acceptable for this quality-first gate, but it means the
candidate no longer supplies a compression reason to replace production.
Throughput was uncontrolled and is not used for a decision.

## Decision

1. **Keep detail-aware finishing as the leading research motion separator.**
   It improves labelled detail, six-film VMAF and temporal drag while retaining
   source-fit fine/coarse grain texture.
2. **Do not deploy it yet.** Production still wins the SSIMULACRA2 and
   Butteraugli base guard rails on every title, and motion-based separation
   still requires blinded high-disocclusion playback.
3. **Reject the no-finish arm.** Its 36% coarse-grain capture is not a viable
   quality trade.
4. **Keep the source-derived model and strength closure independent of the
   separator.** This experiment is direct evidence that the two-operator
   architecture works: the base operator changed substantially while grain
   texture remained stable.
5. **Treat per-luma strength as the next analyser problem.** Deer Hunter's
   slope survives, while Interstellar shows why a global correction is unsafe.
6. **Keep production on r4069/bilateral.** The candidate remains reachable
   only through test hooks and has not been placed in the Tdarr image.

