# Four open problems look like one defect — 2026-08-06

> **Amended 2026-08-07.** The Long Halloween row is second-generation input
> (see `FINDINGS-2026-08-07-LIBRARY-AUDIT.md`) and should be dropped. The
> relationship survives on the remaining cells -- three of the four
> low-signal cells are film.


> Offline measurement only. Nothing deployed, `modelsrc` default-off.

The project has been tracking these as separate open items:

1. chroma V over-delivery, worst on the two most temporally variable planes;
2. per-luma band errors, worst in dark bands (Interstellar V darkest at `2.76x`);
3. over-synthesis on grain-free digital animation (`2.5x` on Long Halloween);
4. chroma over-delivery on neutral/desaturated regions (up to `5.18x`).

Pooling every (true signal amplitude, delivered/source ratio) pair measured
today across all four gives one relationship.

| measurement | true signal | delivered/source |
| --- | ---: | ---: |
| Long Halloween luma (animation) | 0.377 | **2.460** |
| Interstellar V darkest band | 0.480 | **2.763** |
| Scarface neutral chroma | 0.530 | **5.183** |
| Shining V band 0.25--0.375 | 0.810 | 1.472 |
| Poppy Hill luma | 1.259 | 1.034 |
| Casino V darkest band | 1.820 | 1.164 |
| Kiki luma | 1.897 | 0.995 |
| Interstellar neutral chroma | 2.340 | 1.708 |
| Shining neutral chroma | 2.719 | 0.995 |
| Interstellar saturated chroma | 3.023 | 1.235 |
| Taxi skin chroma | 4.715 | 1.099 |
| Scarface saturated chroma | 5.582 | 0.947 |
| Casino skin chroma | 6.198 | 0.997 |
| Deer skin chroma | 8.406 | **0.830** |

(19 rows total; abridged.)

**Log-log correlation `-0.802`, `t = -5.54`, `n = 19`, slope `-0.414`.**

| true signal | n | delivered/source |
| --- | ---: | --- |
| `< 1.0` | 4 | **1.47 -- 5.18** |
| `>= 3.0` | 8 | **0.83 -- 1.24** |

Wherever the real signal is weak, the analyser over-delivers; wherever it is
strong, delivery is close to correct. That single statement covers luma and
chroma, animation and film, per-band and per-region, across four problems
tracked separately for a week.

## What the slope says

A slope of `-1` would mean delivered amplitude is *constant* regardless of
source — the analyser emitting a fixed quantity of grain everywhere. The
measured `-0.414` is roughly halfway between that and correct tracking
(slope `0`), so the analyser **partially** follows the source and partially
emits a floor. That is consistent with every individual observation:
Long Halloween scaled down from Kiki's `1.89` to `0.93` but not to `0.38`;
chroma neutral regions scaled down but not to the source's `0.53`.

## Why this reframes the open list

These have been getting separate estimators, separate rejections and separate
findings documents. Six amplitude estimators have been rejected, each fitted to
one symptom. If the underlying defect is a single floor-like behaviour in
strength estimation at low signal, then per-plane, per-band and per-title
constants were always going to fail — they were fitting projections of one
mechanism onto different axes.

It also explains why the whole-frame aggregates keep looking acceptable while
the decompositions do not: strong-signal regions dominate the average and sit
at `0.95`--`1.10`, so the weak-signal excess is diluted out.

## What this is not

**Not a mechanism.** It is a strong empirical regularity across heterogeneous
measurements, several of which use different estimators, different bit depths
and different frame sets. The pooling is deliberately crude and the correlation
should not be read as a fitted model.

**Not yet actionable.** Nothing here identifies *where* in the analyser the
floor arises — candidate sources include the `fmax(0, V_source - V_base)`
rectification clamp, quantisation of small scaling points, the minimum
representable curve value, and the spatial-estimate fallback. Those are
separable offline and that is the next work.

**Not a licence to fit a global correction.** A single compensating curve on
source amplitude would be exactly the corpus-derived scalar this project has
rejected six times, now applied to a bigger corpus. The value here is that it
points at one place to look, not at a coefficient to tune.
