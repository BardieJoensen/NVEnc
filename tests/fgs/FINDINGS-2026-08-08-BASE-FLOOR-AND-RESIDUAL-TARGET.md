# Base floor falsified; then the retention metric itself fails

2026-08-08. Follows the eight eliminations recorded in
`FINDINGS-2026-08-08-COMPRESSION-ELIMINATIONS.md` and
`FINDINGS-2026-08-08-EMISSION-CADENCE.md`.

> **Read section 5 first.**  Sections 1-4 were written against the premise that
> delivered grain tracks source grain as `source^0.726` (r = -0.985), with
> weak-grain sources over-delivering.  Section 5 shows that premise was
> substantially an artifact of the retention metric: with numerator and
> denominator measured on a common, source-ranked block set, over-synthesis
> largely evaporates (Long Halloween 1.263 -> 1.040) and the correlation falls
> from -0.985 to -0.269.  The corrected reading is a mild, fairly uniform
> **under**-delivery of ~10-15%.
>
> Sections 1-4 are kept because their A/B comparisons remain internally valid
> and because the retraction in section 2 stands on its own.  Their framing of
> the effect's magnitude and direction does not.
>
> Sections 6-8 carry the conclusions: `modelsrc=on` removes the residual trend
> under the corrected metric and is corroborated by 08-01's ground-truth
> amplitudes; the under-delivery was **not** caused by tuning against the bad
> metric; and what the fault actually did was invent an over-synthesis problem
> that did not exist.

The premise as it stood when this file was started: delivered grain tracks
source grain as `source^0.726` (r = -0.985).  Weak-grain sources over-deliver,
strong-grain sources under-deliver.  Eight mechanisms falsified with direct
evidence.

## 1. The base layer is not the explanation

FGS assumes the base it encodes is clean and that everything the viewer sees is
what synthesis put there.  It is not clean: it carries whatever the denoiser
missed, plus codec noise from encoding the base.  Both are high-frequency energy
on flat blocks, so both are counted as grain by the retention metric and by the
library verifier.

If that leftover were a roughly constant *absolute* floor, then
`retention = sqrt(base^2 + (k*src)^2)/src` would blow up as `src -> 0` and tend
to `k` as `src` grows -- exactly the measured shape, with a crossover.

It is not a floor.  Measured by decoding the *same bitstream* twice, with dav1d
synthesis on and off (`-filmgrain 0`), so played and base carry no alignment
risk relative to each other:

| title | src | played | base | synth | retention | synth/src |
| --- | --- | --- | --- | --- | --- | --- |
| Elemental | 6.029 | 5.558 | 1.974 | 5.196 | 0.922 | 0.862 |
| Silo S03E06 | 3.941 | 3.755 | 0.492 | 3.723 | 0.953 | 0.945 |
| LongHalloween | 1.479 | 1.960 | 0.591 | 1.869 | 1.325 | 1.264 |

The base tracks the source rather than sitting at a floor, and removing it
leaves the compressive spread nearly intact (0.862 .. 1.264).

**Falsified -- the ninth.**  What it buys is a real localisation: the
compression is in the *synthesized component*, not in leftover base energy.

Harness: `base_floor.py`.

## 2. Retraction: the emitted-table reconstruction does not work

`emitted_vs_delivered.py` reconstructs the amplitude the emitted AOM `filmgrn1`
table asks for, as `ar_gain * rms(scaling(luma)) / 2^scaling_shift`, with the AR
gain taken in closed form (mean of `1/|1 - A(w)|^2` over the frequency plane)
so the gaussian sequence's unknown constant cancels in cross-title ratios.

It produced an apparently clean split -- request slope +0.601 against source,
delivery +0.725 -- which would have put the defect inside the analyser's
per-luma-bin variance.  **That conclusion is withdrawn.**

It fails its own consistency check.  The deployed binary and the gate build
deliver *identical* grain (synth 5.189/1.870/3.723 vs 5.196/1.869/3.723) while
their reconstructed intent differs by nearly 2x on Elemental, giving slopes of
+0.601 and +0.971 for the same nominal configuration.  Identical output from
materially different reconstructed requests means the reconstruction is wrong,
not the encoder.

It is not AR instability: gains are well-behaved across every segment of every
table (1.015 .. 3.385).  The error is somewhere in the scaling-curve to
amplitude mapping.  The script is kept, marked unreliable; **no conclusion about
analyser-versus-synthesis may rest on it** until the mapping is validated
against a known-amplitude case.

This is the second time in this investigation a confident split has come from an
unvalidated estimator.  Delivered amplitude, measured from decoded frames, is
the only amplitude this project should adjudicate on.

## 3. The model is fitted to the denoiser residual, and that was never tested

With the production default (`modelFromSource(false)`,
`NVEncFilterFilmGrain.cu:1730`), the model target is

```cpp
values[tid] = modelFromSource
    ? detrended_at<...>(src, srcPitch, x, y, component, blockPlane)
    : residual_at<...>(src, srcPitch, denoised, denoisedPitch, x, y, component);
```

`NVEncFilterFilmGrain.cu:681`.  The default branch fits to `src - denoised`:
what the denoiser *removed*, not the source's grain.  The comment at
`:613-622` already states the consequence and names the source fit as the
correction.

The "denoiser response shape" elimination compared bilateral against fft3d and
found similar slopes (-0.258 vs -0.242).  That asks *which denoiser*, and cannot
falsify *whether the residual is the right target* -- both denoisers share the
target.  **This mechanism was never actually tested.**  It moves from eliminated
to live.

It has the right sign, too: the residual carries removed picture detail as well
as grain, which inflates it where grain is weak, and no denoiser removes strong
grain completely, which deflates it where grain is strong.  Both push toward a
compressive response.

## 4. First pass on `modelsrc=on`, three titles, same binary both arms

| title | src | default | modelsrc=on |
| --- | --- | --- | --- |
| LongHalloween | 1.479 | 1.263 | 1.298 |
| Silo S03E06 | 3.869 | 0.962 | 1.002 |
| Elemental | 6.029 | 0.862 | 1.176 |
| | slope | **+0.726** | **+0.898** |

The slope moves toward 1.0 and the spread narrows (0.401 -> 0.296), but every
title over-delivers afterwards, which is the signature of a global gain change
rather than a selectivity fix.  Three titles spanning source HF 1.5 .. 6.0
cannot separate the two.

Base layers and encoded sizes are identical across arms, which is the expected
check passing: the flag changes the model fit, not the base encode.

**Not a deployment candidate on this evidence.**  The full-range run
(`residual_target_test.py`, weak plus the strong-grain controls Alien, Taxi
Driver, The Shining, Casino) is what decides it, against the standard this
project already set in `measure_rank_gate.py:10-16`: weak must fall toward 1.0
and strong must not move.

### Build provenance for sections 1-4

Nothing deployed.  `modelsrc` remains default-off; Tdarr untouched.  Both arms
ran on `~/.cache/fgs-gate/builds/pin-4b611c92-measure-rank/build-gate/nvencc`.

The section-4 verdict ("not a deployment candidate", "a global gain change")
is **superseded by section 6**, which re-scores the same encodes on a common
block set and finds the opposite.

## 5. The retention metric does not survive its own free parameters

Found while testing whether the energy FGS models is temporally grain-like.
Two contaminations, and then a structural fault.

**Letterbox bars and near-black blocks.**  They are the flattest blocks in any
scope-ratio frame and carry almost no grain, so a naive "flattest 25%" selector
fills up with them and the median source HF collapses.  Casino read source HF
`0.000`; Long Halloween read `1.479` instead of `4.142`.  Source HF is the
denominator of every retention number in this investigation.

**Independent per-arm block selection -- the structural fault.**  `campaign.py`
and every harness here rank the flattest 25% *separately in the source and in
the encode*.  The base layer is denoised, so its flatness ranking differs, and
numerator and denominator describe different regions of the picture.

Eight defensible variants of the same measurement, same encode, Long Halloween:

| frames | selection | dark blocks | retention |
| --- | --- | --- | --- |
| 192 | per-frame | included | 1.263 |
| 64 | per-frame | included | 1.113 |
| 192 | per-frame | excluded | 1.091 |
| 64 | fixed | included | 0.706 |
| 192 | fixed | included | 0.686 |
| 64 | per-frame | excluded | 0.684 |
| 192 | fixed | excluded | 0.645 |
| 64 | fixed | excluded | 0.576 |

The verdict flips between "over-delivers by 26%" and "under-delivers by 42%" on
measurement choices alone.

### Corrected construction

`retention_common_blocks.py`: rank blocks once on the **source**, excluding
near-black and near-saturated blocks, and read those same indices in the
source, the played output, and the base layer.

| title | src | fixed rank | per-frame rank | old metric |
| --- | ---: | ---: | ---: | ---: |
| Elemental | 8.03 | 0.653 | 0.880 | 0.862 |
| LongHalloween | 3.51 | 0.704 | **1.040** | **1.263** |
| Silo S03E06 | 4.21 | 0.890 | 0.894 | 0.962 |
| Sugar S02E08 | 6.13 | 0.873 | 0.877 | 0.882 |

Over-synthesis largely evaporates: Long Halloween, the title that triggered the
hunt, moves 1.263 -> 1.040, and nothing in the corpus over-delivers
meaningfully.  The compressive response is partly metric too -- with fixed
source-ranked blocks, corr(log src, log retention) falls from **-0.985 to
-0.269**.  A milder trend survives per-frame source ranking (slope +0.829,
r = -0.973), so it is not purely artifact, but the spread is 0.877..1.040
rather than 0.862..1.325.

**Corrected reading: FGS under-delivers slightly and fairly uniformly, ~10-15%.**
That is a different and much smaller defect than "over-synthesizes on clean
content".

### Consequences

- The premise of the nine-mechanism hunt was substantially inflated by the
  metric that defined it.  The individual eliminations remain valid as A/B
  comparisons within one metric, but the effect they chased was overstated.
- The batch report's over-synthesis finding needs re-checking against the
  corrected construction before any further work is justified.
- The metric should have been interrogated before the ninth mechanism.

### Open

Four weak-class titles only; the strong-grain controls were still encoding.
Fixed and per-frame ranking disagree on Elemental (0.653 vs 0.880) because
fixed ranking admits more textured blocks, which inflates the measured base --
neither variant is canonical yet, and that choice must be settled before the
corrected numbers are treated as final.

## 6. `modelsrc=on` under the corrected metric

Re-scored with `retention_common_blocks.py --per-frame` (blocks ranked on the
source, same indices read in every arm), same encodes as section 4:

| title | default | `modelsrc=on` |
| --- | ---: | ---: |
| Elemental | 0.880 | 1.205 |
| LongHalloween | 1.040 | 1.083 |
| Silo S03E06 | 0.894 | 0.952 |
| Sugar S02E08 | 0.877 | 1.019 |
| slope | **+0.829** | **+1.031** |
| corr(log src, log retention) | **-0.973** | **+0.142** |

The compressive trend disappears -- correlation goes from strongly negative to
nil -- and delivery centres near 1.0, slightly over.

This **corroborates `FINDINGS-2026-08-01-SOURCE-FIT.md` from a completely
independent direction**.  That file measured amplitude against ground truth on a
fixture with injected grain of known strength, and on Taxi Driver:

> truth 7.24 on Taxi, residual **3.97 (55%)**, source **7.79 (108%)**

Two measurements sharing no machinery -- injected-grain ground truth, and
delivered retention on common source-ranked blocks -- agree that residual
fitting under-delivers and source fitting lands near or slightly above unity.
The corrected metric's ~1.06 mean for `modelsrc=on` matches that 108%.

Caveat: fixed-rank scoring disagrees (slope +1.343, Long Halloween 0.654)
because fixed ranking admits more textured blocks, which inflates the measured
base (1.737 vs 1.052 on Long Halloween).  Per-frame source ranking is the more
defensible construction, but this choice is still unsettled and is the main
open question against these numbers.

## 7. Did tuning against the bad metric cause the under-delivery?

The natural inference on discovering the metric fault is that months of tuning
were steered by it -- the metric said "over-delivering", so changes that reduced
grain looked good, and FGS was pushed into under-delivery.  **The evidence does
not support that.**

1. **The nine-mechanism hunt changed nothing.**  Every candidate was falsified
   and none shipped.  All its hooks are environment-gated and default-off.

2. **Every encoder-side FGS commit since 2026-07-25** is either a `test(fgs):`
   hook (default-off) or a fix *inside* the source-fit path, which is itself
   behind `modelsrc=off`.  The deployed default -- residual fitting -- was not
   tuned down in response to the bad readings.

3. **Under-delivery was measured a week earlier without the faulty metric.**
   The 08-01 ground-truth fixture put residual-fit amplitude recovery at 55% on
   Taxi Driver.  That predates and is independent of the retention metric.

So the under-delivery is a long-standing property of fitting the grain model to
`src - denoised`, not damage introduced by tuning.  What the metric fault did
was different and arguably worse: it **invented an over-synthesis problem that
did not exist**, and sent the investigation chasing it through nine mechanisms
while the real, already-measured defect -- and its already-implemented fix --
sat in a file from 2026-08-01.

## 8. Where this leaves FGS

- The over-synthesis that motivated this investigation is largely a measurement
  artifact.  Nothing in the corpus meaningfully over-delivers once numerator and
  denominator describe the same blocks.
- The real defect is a modest, fairly uniform under-delivery under the deployed
  residual fit.
- `modelsrc=on` addresses it, and now has two independent lines of evidence.
  It remains blocked on admission (step 2 of
  `FINDINGS-2026-08-04-SOURCEFIT-ADMISSION.md`), not on amplitude.
- Production is unaffected by any of this: the deployed qvbr buckets and the
  568.5 GB of measured savings came from VMAF and file sizes, not from the
  retention metric.

### Open

- Settle fixed vs per-frame source ranking as the canonical construction.
- Re-check the batch report's over-synthesis column; the library verifier very
  likely selects flat blocks the same independent-per-arm way, in which case it
  is reporting the same artifact.
- Strong-grain controls (Alien, Taxi Driver, The Shining, Casino) were still
  encoding when this was written; the corpus here is four weak-class titles.
- `campaign.py` and the other harnesses still use the flawed selector and
  should be migrated to the common-block construction.
