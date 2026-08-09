# Source provenance changes the tail magnitudes, not the tail decision — 2026-08-09

> Measurement and experiment selection only. No encoder or production-flow
> setting changed. The Tdarr node remained paused while this audit ran.

## Why the previous population cannot be used as a calibration corpus

The July library population used a cached source-pair list. Its estimator was
already using one source-derived flat mask and excluding letterbox bars, but the
pair provenance was not fail-closed. The cache included both different releases
of the same episode and cross-title matches which happened to share `SxxExx`.

One concrete example is Fallout S02E06. The remux library file had been compared
with a 1920x800 PERLMAN x264 release rather than its 1920x1080 SmAckdOwn remux.
The wrong pair reported about 3.064. Repeating three scenes against the exact
SmAckdOwn source reports 0.977, 1.514 and 1.482 (median 1.482). The upper-tail
signal survives, but the old magnitude does not.

Therefore the earlier `n=22` percentiles in `grain-watch.py` are historical
monitor baselines, not encoder calibration evidence. In particular, do not tune
gain or admission from the old p5/p90 values or the old maximum of 2.244.

## Pair rebuild

The source discovery was rebuilt from every retained TV source rather than from
the source selected by the old list. A pair now requires:

- the same show and episode;
- duration within one percent;
- identical decoded video geometry;
- the same release group whenever a group is present on both sides; and
- one unambiguous winner. Ambiguity is a skip.

Audit output:

`/media/merged-storage/media/test-encodes/grain-watch/tv-pairs-review-20260809.json`

| stage | count |
| --- | ---: |
| library TV files considered | 2,158 |
| unique retained source candidates | 2,041 |
| show + episode candidates | 1,793 |
| unambiguous exact-release pairs | 1,651 |
| historical CAMBI rows with a trusted pair | 1,572 / 2,034 |

The review file is separate from the live monitor cache. Building it did not
silently rewrite monitoring history or change production.

## Clean five-scene production population

The just-completed redo batch provided 50 output/source pairs with five frozen
positions per title: 0.150, 0.325, 0.500, 0.675 and 0.850 of duration. Retention
uses the source mask for source, grain-on decode and grain-off decode. Points
whose source sigma is below 0.25 8-bit code values remain ungraded.

The same name/release, duration and geometry gates leave 36 graded titles.
Fourteen are excluded: one has no graded source point, one movie is another
release, and the remainder cannot currently prove compatible source geometry
or availability. Excluded pairs do not contribute a zero or a guessed value.

| percentile | title-mean played/source retention |
| --- | ---: |
| minimum | 0.690 |
| p5 | 0.789 |
| p10 | 0.873 |
| p25 | 0.994 |
| median | 1.046 |
| p75 | 1.139 |
| p90 | 1.302 |
| p95 | 1.350 |
| maximum | 1.508 |

This changes the conclusion in a useful way:

1. Production is centred close to one. A global gain correction is wrong.
2. Both tails remain after exact provenance. They are not explained solely by
   the broken pair cache.
3. Scene spread can be large. A title mean alone is not a sufficient gate.
4. The next question is which analyser/separation layer creates the tails, not
   whether all output should be globally louder or quieter.

Repeatable lower examples include Korra S02E12 (mean 0.690, 0.343--0.981),
Korra S02E07 (0.801, 0.652--0.925), and How I Met Your Mother S04E17 (0.863,
0.466--1.017). Repeatable upper examples include How I Met Your Mother S09E15
(1.508, 0.876--2.032), Widows Bay S01E05 (1.376, 1.080--1.698), and Trying
S02E06 (1.341, 1.211--1.562).

## Frozen tail gate

The first architecture run uses two lower titles, two upper titles and two
ordinary centre controls. Five positions are retained per title so a single
scene cannot decide the arm:

| class | title | production mean | range | reason |
| --- | --- | ---: | ---: | --- |
| low | The Legend of Korra S02E12 | 0.690 | 0.343--0.981 | strongest repeatable lower title |
| low | The Legend of Korra S02E07 | 0.801 | 0.652--0.925 | lower result without one extreme point |
| centre | Abbott Elementary S02E02 | 0.995 | 0.791--1.199 | ordinary progressive WEB-DL control |
| centre | Planet Earth S01E06 | 0.976 | 0.724--1.139 | film-origin, coarse/detail and cadence control |
| high | How I Met Your Mother S09E15 | 1.508 | 0.876--2.032 | largest clean title mean |
| high | Trying S02E06 | 1.341 | 1.211--1.562 | high at every graded scene, independent series |

Planet Earth is retained deliberately but must be extracted through ffmpeg to a
fixed-frame lossless clip before NVEncC sees it. Its source is flagged `tt` but
decodes progressive; sending the original directly through field-order routing
would reintroduce the already-diagnosed soft-telecine error.

For each scene, compare the same bilateral separator and operating point:

1. residual-fitted production behaviour;
2. `modelsrc=on` source fitting without response closure;
3. `modelsrc=on` with guarded covariance/texture response;
4. plain AV1 without film-grain synthesis.

Before interpreting quality, require exact source identities, matching frame
counts, a complete dav1d decode and a candidate-control equivalence check. Then
measure played/base/synth amplitude by luma band, spatial ACF, grain-disabled
base fidelity, encoded bytes and per-scene spread. Chroma is observed but no
new chroma correction is allowed into this run.

## Decision boundary

- If a production tail does not repeat on the frozen clips, fix sampling.
- If source fitting moves energy and ACF toward the exact original without
  changing the bilateral base, it is the first minimal promotion candidate.
- If only guarded response closes a repeatable tail, promote neither mechanism
  until the response itself survives independent held-out titles.
- If every FGS arm is worse than plain, keep that title as the missing labelled
  admission negative.
- If the source fit is correct but every synthesized arm shares a texture miss,
  record an AV1 representation limit instead of adding another analyser knob.

