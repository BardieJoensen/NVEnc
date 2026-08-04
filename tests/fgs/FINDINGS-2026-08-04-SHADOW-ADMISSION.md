# Shadow source-fit admission on untouched content — 2026-08-04

> Quality-first research result. Nothing here was deployed and no output was
> routed differently. Production remains r4069 with bilateral separation,
> residual fitting and `modelsrc=off`.

## Decision

**Do not implement the exploratory correlation-plus-anisotropy conjunction
yet.** The shadow run proves that it is not a detector of photochemical origin,
but the post-run quality adjudication also proves that photochemical origin was
the wrong label to demand. Migration and Elio contain measurable stochastic
texture, and source fitting reconstructs it substantially better without a
meaningful size or base-fidelity cost.

The shadow rule was frozen before measurement:

```text
cross-frame correlation <= 0.127
AND source/model anisotropy mismatch <= 0.032
```

It admitted all eight unseen photochemical scenes and three of four scenes
pre-registered as clean-CG negatives. That initially looked like 8/8
sensitivity and 1/4 specificity. The temporal playback measurement invalidated
the negative labels: all four CG scenes move materially closer to source truth
with source fitting, including the Migration scene the rule rejects.

The supported conclusion is narrower and more useful. These axes cannot tell
*where* stochastic texture came from. They may still help decide whether the
texture is temporally stochastic and AV1-representable, but this corpus has no
quality-labelled harmful admission with which to measure specificity. A gate
validated only against beneficial inputs is not ready to control output.

## Pre-registration and integrity

The runner, complete 24-scene corpus and frozen policy were committed and
pushed as `a5315de5` before the first new admission statistic was measured.
The corpus uses two fixed seek fractions, 0.31 and 0.68, on each of 12 titles.

Every input is a retained progressive H.264 source. Library AV1 files were
explicitly rejected after a preflight check found that several filenames still
said AVC even though their content had already passed through the flow. The
runner refuses AV1 input so previously synthesized grain cannot become source
truth accidentally.

For every scene the pinned candidate generated a residual-fit and a
temporal-static source-fit table. All 48 direct AV1 streams passed complete
`libdav1d -xerror` decoding. The campaign returned `routing_verdict: null` and
`changes_output: false` at the interval, sample and corpus layers.

Candidate:

```text
commit  47ebe9708544b19cd641fd894bc46a4daae08738
binary  f96bf3e4254f2ecfa6d145d867e9d35e3c66d282998c58441d5d8fe2402f60d7
```

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-shadow-admission-20260804/
```

## Pre-registered semantic labels

The table below preserves the original labels and results because changing
them after measurement would hide the experiment's mistake. “CG negative” was
an origin label, not quality ground truth; the next section supersedes the
`false admit` interpretation.

| scene | class | cross-frame | anisotropy mismatch | shadow result | interval admit / reject / insufficient |
| --- | --- | ---: | ---: | --- | ---: |
| Quiz Show 31% | film | 0.0575 | 0.0090 | admit | 14 / 0 / 0 |
| Quiz Show 68% | film | 0.0541 | 0.0099 | admit | 15 / 0 / 1 |
| Life of Brian 31% | film | 0.1114 | 0.0177 | admit | 11 / 1 / 1 |
| Life of Brian 68% | film | 0.0853 | 0.0218 | admit | 6 / 6 / 0 |
| Drunken Master 31% | film | 0.0473 | 0.0091 | admit | 12 / 0 / 0 |
| Drunken Master 68% | film | 0.0393 | 0.0131 | admit | 12 / 0 / 0 |
| Jerry Maguire 31% | film | 0.0688 | 0.0160 | admit | 13 / 1 / 1 |
| Jerry Maguire 68% | film | 0.1030 | 0.0283 | admit | 8 / 5 / 0 |
| Migration 31% | clean CG | **0.0306** | **0.0107** | admit | 11 / 0 / 1 |
| Migration 68% | clean CG | 0.1064 | 0.0719 | reject | 0 / 8 / 2 |
| Elio 31% | clean CG | **0.0716** | **0.0087** | admit | 12 / 0 / 0 |
| Elio 68% | clean CG | **0.0976** | **0.0129** | admit | 11 / 0 / 0 |

The Migration scene flip is still important. A title label cannot repair the
rule, and the rejected scene turns out to benefit from source fitting too.

## Post-run quality adjudication corrects the labels

`temporal_grain_report.py` used source-selected production-flat/static blocks,
decoded both arms with dav1d grain on and off, and measured base residue,
synthesis and played total against adjacent-frame source truth. Ratios below
are played amplitude divided by source truth; lag-1/lag-2 are amplitude-free
texture shape.

| scene | source truth lag-1/2 | residual total lag-1/2 | source-fit total lag-1/2 | played total residual -> source | bytes delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Migration 31% | 0.324 / 0.047 | 0.122 / -0.104 | **0.331 / 0.053** | 0.896 -> **1.035** | -0.100% |
| Migration 68% | 0.749 / 0.563 | 0.680 / 0.520 | **0.753 / 0.587** | 0.877 -> **1.052** | +0.043% |
| Elio 31% | 0.628 / 0.267 | 0.465 / 0.133 | **0.642 / 0.319** | 0.724 -> **0.955** | +0.053% |
| Elio 68% | 0.458 / 0.152 | 0.202 / -0.043 | **0.477 / 0.184** | 0.853 -> **0.977** | +0.287% |

Migration 68% had only one static block at the default frame 58, so its report
uses frames `10,100,140,180,220,280`, chosen only from the already-recorded
coverage counts. The other three use the standard six frames.

The base operator remains equivalent. Residual-vs-source grain-disabled base
PSNR is 60.38, 49.81, 55.62 and 59.40 dB respectively. Base VMAF against the
grainy source moves by `-0.0099`, `+0.0012`, `-0.0492` and `-0.1799`; PSNR-Y
moves by less than 0.006 dB on every scene. The Elio 68% VMAF movement remains
a guard-rail observation, but it is not evidence of separator damage and VMAF
still compares a denoised base against a textured source.

These are quality-positive source-fit results. The correct target is not “was
this photographed on film?” It is “does this interval contain stochastic
texture that the separator removes, the AV1 model represents, and playback
restores at the right amplitude?” On that target, all four CG scenes pass this
measurement.

## Unlabelled boundaries

These groups are descriptive, not false-positive counts:

| class | admitted / rejected scenes | interpretation |
| --- | ---: | --- |
| modern digital/VFX | 5 / 1 | some may carry intentional camera or grade texture |
| drawn animation | 3 / 1 | transfer texture and deliberate line texture are mixed |
| compressed digital WEB-DL | 0 / 2 | both East Side Sushi scenes were rejected |

The boundaries show severe interval heterogeneity. TAR 31% is an aggregate
admit although only 4 of 12 intervals admit. Long Halloween changes from a
clear aggregate reject to an aggregate admit across scenes. Poppy Hill 68%
aggregates to admit even though only 5 of 15 entries have enough evidence (3
admit, 2 reject, 10 insufficient). Coverage must therefore remain a separate
state; insufficient evidence is not a rejection and cannot authorize source
fitting.

## Why model improvement still cannot be admission

Source fitting reduced lag-1/lag-2 mean absolute error on all 24 scenes. The
smallest improvement was still positive (`+0.0018`, Spider-Man 31%). It also
improved all 16 earlier titles, including every prior animation/general
negative. This reproduces the architectural distinction:

- model fidelity asks whether AV1 follows the selected source texture;
- quality admission asks whether that source texture is stochastic,
  representable and safe to synthesize.

The first cannot answer the second, however accurate it becomes.

## The amplitude clue is not a fix

On this new corpus, temporal sigma happened to separate the origin labels:
film scenes were `1.598..3.418` codes, while the three admitted CG scenes were
`0.808..1.376`. A fixed amplitude floor is nevertheless rejected:

- Interstellar is `1.285`;
- The Shining is `1.266`;
- Silo is `0.857`; and
- luma occupancy and scene selection change a whole-frame sigma.

A `sigma >= 1.5` rule would make the origin labels look perfect by discarding
known grain-bearing real content and three quality-positive CG results. It
would repeat the earlier unweighted-luma measurement error as a router.

## Stochastic-descriptor replay

Commit `b8b8cebe` adds amplitude-normalized per-patch excess kurtosis,
absolute-to-RMS ratio, absolute skew, quadrant-energy variation and aligned
4/8/16-pixel boundary-gradient ratios. It reports them inside fixed luma bands
as well as in aggregate.

An aggregate conjunction can be fitted to the pre-registered origin labels:
for example quadrant variation `>=0.15` plus grid-8 ratio `>=1` separates the
eight film scenes from the three admitted CG scenes. It is rejected for three
reasons:

1. fixed-luma values overlap strongly (Migration overlaps Drunken Master and
   Jerry Maguire);
2. Elio's grid signature can be explained by its render/AVC pipeline rather
   than by the absence of useful stochastic texture; and
3. the playback result proves that rejecting those CG scenes would discard a
   quality improvement.

The descriptor experiment is useful instrumentation but does not produce a
new admission threshold.

## Next measurement

Admission now needs a quality-labelled negative rather than another content
class:

1. construct or find an interval where source fitting demonstrably synthesizes
   persistent picture/codec structure that temporal truth says is not noise;
2. require the gate to reject that specimen while retaining the film and the
   now-quality-positive CG controls;
3. keep solver validity, coverage and residual fallback separate from any
   semantic/stochastic evidence; and
4. continue the independent coarse-grain representability oracle, because a
   texture can be worth preserving yet exceed AV1's compact model.

Until a known harmful admission exists, this conjunction cannot be called a
validated safety gate. The conservative behavior remains residual fallback on
solver/coverage failure and no production default change. The evidence also
weakens the premise that an ontology classifier is required at all: a
universal source model may be viable if its actual safety, amplitude and
representability gates close on output quality.
