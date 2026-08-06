# The compressive-response hypothesis does not hold up — 2026-08-06

> Offline measurement only. Nothing deployed, `modelsrc` default-off.
> **Negative result, reported as such.**

With both noise floors exonerated (`FINDINGS-2026-08-06-FLOOR-ABLATION.md`), the
one-defect relationship had to come from the estimator. Reading the emitted
tables suggested a specific shape: grain-free animation emits luma scaling
points in the same range as grainy film (medians `56`--`158` against
`93`--`168`), with almost all the amplitude difference carried by the
power-of-two shift. That looks like a compressive response — `delivered ~
source^b` with `b < 1` — rather than a floor, and a floor would anyway predict a
knee where the one-defect scatter is straight.

The hypothesis was worth testing and it did not survive.

## What looked convincing

One point per title, emitted curve RMS against source flat-block sigma, nine
titles:

**`b = 0.666`, `r = 0.701`, `t = 2.60`, `n = 9`** — implied ratio slope
`-0.334`, against ONE-DEFECT's `-0.414`.

That is a replication on a genuinely independent instrument: different corpus,
emitted rather than delivered amplitude, and a source measure computed here
rather than reused. At `n = 9` though, the interval on `b` spans roughly
`0.06`--`1.27`, so it establishes a relationship and not an exponent.

Fitting **within** title across the analyser's own luma bins gives ~8
observations per title from the same estimator, and holds `templateGain` fixed
by construction — which matters, because for luma `templateGain = arGain`, a
variance *ratio* free to differ per title without any defect being present:

**`b = 0.614 +/- 0.193`, `n = 7` titles** — implied ratio slope `-0.386`,
closer still to `-0.414`, and apparently excluding correct tracking at
`z = -2.00`.

## Why it fails

`z = -2.00` is `p ~ 0.046`. Two of the seven within-title fits are not fits at
all — Kiki `t = 1.19`, Interstellar `t = -0.32` — and they are the two lowest
values of `b`. Excluding non-significant fits:

| subset | n | b | z against `b = 1` | |
| --- | ---: | --- | ---: | --- |
| all fits | 7 | `0.614 +/- 0.193` | `-2.00` | excluded |
| `|t| >= 2.0` | 5 | **`0.844 +/- 0.176`** | `-0.88` | **NOT excluded** |
| `|r| >= 0.9` | 4 | **`0.896 +/- 0.218`** | `-0.48` | **NOT excluded** |

**The entire result is carried by two fits that are statistically noise.** On
the fits that are actually determined, the exponent is `0.84`--`0.90` and
correct tracking sits comfortably inside the interval. The compressive-response
hypothesis is **not established** and must not be built on.

This is the same failure mode as the three claims already retracted this
session: a real-looking pooled statistic resting on cells that individually say
nothing.

## What does survive

Among the five well-determined fits the exponent is genuinely heterogeneous:

| title | b | r | t |
| --- | ---: | ---: | ---: |
| Scarface | 0.850 | 0.988 | 15.86 |
| Casino | **1.462** | 0.972 | 7.17 |
| The Shining | 0.872 | 0.904 | 5.18 |
| Taxi Driver | 0.636 | 0.764 | 2.65 |
| Poppy Hill | **0.401** | 0.926 | 5.48 |

A single estimator defect would give one exponent. This spans `0.40`--`1.46`,
with tight fits at both ends, and Casino above `1` means over-tracking there —
the opposite sign. **Whatever produces the one-defect relationship is not a
fixed response curve inside the per-bin strength fit.** The per-title spread is
the finding, and it points at something that varies per title: `templateGain`
(`arGain` for luma) is the obvious candidate, being a correlation-structure
ratio rather than an amplitude.

## Limits

Nine titles, one QVBR, emitted curve rather than delivered amplitude, 24 frames.
Source sigma is measured here with a structure/noise split rather than by the
encoder's own flat-block scorer, so it approximates the analyser's regressor
without reproducing it.

Two measurement faults were found and fixed while building this, both of which
had produced confident-looking numbers first: ranking blocks by raw pixel
gradient selects letterbox bars (five titles read sigma exactly `0.000`, all of
them 2.35:1), and after cropping it still selects the uniform fills in digital
animation. Both are the bias `NVEncFilterFilmGrain.cu:2400` documents. The
current selector ranks on 8x8-pooled structure and takes the residual as noise.

## Next

Not another response-curve fit. The lead is the per-title spread: measure
`arGain` per title from the emitted AR coefficients and test whether it explains
which titles over-deliver. That is analysis over tables already on disk.
