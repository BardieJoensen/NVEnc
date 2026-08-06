# Can the analyser route itself? Not on temporal sigma alone — 2026-08-06

> Offline measurement only. Nothing deployed, `modelsrc` default-off.

Question: rather than build a content classifier, can the analyser use a signal
it already computes to scale itself to zero where there is no grain, making
`modelsrc=on` safe for the whole library?

The candidate signal is **source temporal sigma** — grain amplitude measured on
flat blocks by frame differencing. `FINDINGS-2026-08-06-ANIMATION-GATE.md`
found the analyser over-synthesizes 2.5x on grain-free digital animation
because `NVEncFilterFilmGrain.cu:331` falls back to the *spatial* estimate when
temporal evidence is missing, and spatial variance on drawn art is line-art,
not grain.

## The signal is an excellent film detector

Median temporal sigma across the 24-scene shadow corpus:

| class | n | median range |
| --- | ---: | --- |
| **film** | 8 | **1.676 -- 3.724** |
| everything else | 16 | 0.500 -- 1.856 |

A threshold near `1.6` separates **23 of 24 scenes**. The only crossover is
Migration 68% (CG) at `1.856`, and that is not a misclassification: shadow
admission measured Migration as **quality-positive**, so a scene with genuine
stochastic texture reading high is the signal working.

## But a film detector is the wrong gate

Two facts kill it:

1. **Non-film content mostly benefits.** Shadow admission established that
   Migration and Elio improve under source fitting and re-labelled its own
   corpus accordingly. Gating on "is this film" would reject content that gains.
2. **It does not isolate the case where harm was measured.** Long Halloween —
   the only title with demonstrated 2.5x over-synthesis — sits mid-pack among
   non-film at `0.726` and `0.914`. Meanwhile **Poppy Hill 68% is lower at
   `0.500`**, and there the candidate reproduces real grain at 103%.

So the ordering by temporal sigma does not put the harmful case at the bottom.
A scalar threshold on this quantity cannot separate "no grain to model" from
"faint grain worth modelling".

## What this does and does not rule out

**Ruled out:** a single global threshold on source temporal sigma as a
self-routing gate. That is the obvious implementation and it does not work.

**Not ruled out**, and still the most promising direction: the fallback itself.
The defect is not that the analyser lacks a signal, it is that when temporal
evidence is *absent* it substitutes a spatial estimate that measures picture
structure. Making absent temporal evidence mean "emit no grain here" rather
than "guess from spatial" is a local change at the bin level, not a title-level
route, and it would leave Poppy Hill untouched — Poppy Hill *has* temporal
evidence (`0.500` is a real measurement, not a fallback).

That distinction matters: Long Halloween's problem frames had **zero** static
blocks and a source temporal sigma of `0.07`--`0.11`, while its per-title
median of `0.726` is dominated by frames that do have evidence. The title-level
statistic hides the per-bin failure, which is why the title-level threshold
fails.

## Recommended next measurement

Per-bin rather than per-title: for each luma bin in each emitted interval,
compare the temporal evidence available against the strength signalled. If the
bins with no temporal coverage are the ones carrying the excess, the fix is to
zero those bins and nothing else needs to change. That is testable offline from
the existing encodes and tables.

Do not set any threshold on the present corpus: one genuinely grain-free title
is not a sample.
