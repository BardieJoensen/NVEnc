# Shadow source-fit admission on untouched content — 2026-08-04

> Quality-first research result. Nothing here was deployed and no output was
> routed differently. Production remains r4069 with bilateral separation,
> residual fitting and `modelsrc=off`.

## Decision

**Reject the exploratory correlation-plus-anisotropy conjunction as an
admission policy.** It remains useful descriptive evidence, but it is not a
semantic detector of film grain and must not be implemented in the analyzer.

The shadow rule was frozen before measurement:

```text
cross-frame correlation <= 0.127
AND source/model anisotropy mismatch <= 0.032
```

It admitted all eight unseen photochemical-positive scenes, but also admitted
three of four clean-CG negative scenes. Scene-level sensitivity was 8/8;
specificity on the labelled negative set was only 1/4. A detector that calls
clean rendered animation film grain is not conservative enough to control
source fitting.

This result does **not** reject source fitting. It rejects using those two
features to decide where source fitting is semantically appropriate. Once a
film interval is genuinely admitted, source fitting remains much closer to its
measured texture than residual fitting.

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

## Labelled controls

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
| Migration 31% | clean CG | **0.0306** | **0.0107** | **false admit** | 11 / 0 / 1 |
| Migration 68% | clean CG | 0.1064 | 0.0719 | reject | 0 / 8 / 2 |
| Elio 31% | clean CG | **0.0716** | **0.0087** | **false admit** | 12 / 0 / 0 |
| Elio 68% | clean CG | **0.0976** | **0.0129** | **false admit** | 11 / 0 / 0 |

The Migration scene flip is especially important. A title label cannot repair
the rule: one clean-CG scene looks strongly admissible on both axes while
another scene from the same source is rejected directionally.

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
- semantic admission asks whether that source texture is grain worth
  synthesizing.

The first cannot answer the second, however accurate it becomes.

## The amplitude clue is not a fix

On this new corpus, temporal sigma happened to separate the labelled groups:
film positives were `1.598..3.418` codes, while the three false-admitted CG
scenes were `0.808..1.376`. A fixed amplitude floor is nevertheless rejected:

- Interstellar is `1.285`;
- The Shining is `1.266`;
- Silo is `0.857`; and
- luma occupancy and scene selection change a whole-frame sigma.

A `sigma >= 1.5` rule would make the new table look perfect by discarding
known grain-bearing real content. It would repeat the earlier unweighted-luma
measurement error as a router.

## Next measurement

The next admission experiment must add genuinely new information rather than
retune the failed axes:

1. measure stochastic-distribution and codec-grid evidence inside fixed luma
   bands (excess kurtosis, absolute-to-RMS ratio, within-band amplitude spread,
   and 4/8/16-pixel boundary-gradient ratios);
2. normalize amplitude-dependent descriptors so they cannot rediscover the
   whole-frame sigma shortcut;
3. freeze any candidate feature on Migration/Elio plus the eight new film
   scenes; and
4. validate it on new, still-sealed film and clean-CG titles before considering
   analyzer code.

If no luma-controlled stochastic descriptor separates the controls, semantic
admission cannot safely be inferred from the analyzer's flat-block statistics
alone. The correct fallback would then be conservative external routing or
residual fitting, not a more complicated fitted threshold.
