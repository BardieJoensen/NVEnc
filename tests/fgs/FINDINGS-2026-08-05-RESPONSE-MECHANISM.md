# Why the guarded response reverses on The Deer Hunter — 2026-08-05

> Offline measurement only. Nothing deployed, `modelsrc` default-off.

`FINDINGS-2026-08-05-ARM-ROBUSTNESS.md` found the guarded response arm improves
5/6 titles on an independent frame set but regresses The Deer Hunter, stably
across three frame sets. This is the mechanism, and it is simple.

## The response arm raises delivered lag-2, by a roughly fixed amount

| title | source lag-2 | static delivers | static deficit | response delivers | raise applied |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scarface | +0.004 | -0.028 | **-0.032** | +0.003 | +0.031 |
| **Deer Hunter** | +0.032 | +0.031 | **-0.001** | +0.089 | +0.058 |
| The Shining | +0.258 | +0.185 | **-0.073** | +0.255 | +0.070 |
| Casino | +0.375 | +0.335 | **-0.040** | +0.401 | +0.066 |
| Interstellar | +0.422 | +0.346 | **-0.076** | +0.405 | +0.059 |
| Taxi Driver | +0.432 | +0.403 | **-0.029** | +0.465 | +0.062 |

The raise is **+0.031 to +0.070**, applied on 6/6 titles. Static source fitting
**under-delivers lag-2 on 6/6**, which is why the correction exists and why it
usually helps.

## The reversal is a deficit/correction mismatch

Static's deficit is `0.029`--`0.076` on five titles — comparable to the raise,
so the correction lands close:

- Scarface `-0.028` becomes `+0.003` against a source `+0.004`;
- The Shining `+0.185` becomes `+0.255` against `+0.258`.

**The Deer Hunter's deficit is `-0.001`.** Static already delivers its lag-2
essentially exactly. The response then applies its usual `+0.058`, overshooting
to `+0.089` against a source of `+0.032`. The correction is roughly 60x larger
than the error it is correcting.

That is the whole reversal. Not a bad model — the two arms' luma AR
coefficients differ by one or two quantisation steps per tap — just a
correction applied where there was nothing to correct.

## Both extremes are stable

At thirty frame pairs:

| title | static | response | response better on |
| --- | ---: | ---: | --- |
| Interstellar | 0.06350 | **0.02611** | **29/30 frames** |
| The Deer Hunter | **0.01706** | 0.03965 | 4/30 frames |

So the arm is bimodal by title rather than noisy, and both modes reproduce.

## The conditioning variable

**Apply the response only when static's own lag-2 deficit is comparable to the
correction it would apply.** Deer Hunter is the sole title in the corpus where
it is not, and it is the sole regression.

This is computable before emission: the analyser already has the source AR fit
and the base covariance, so the predicted static deficit is available at the
same point the current `0.01` predicted-improvement margin is evaluated. The
present guard asks "does the response candidate predict a lower axis error";
the proposed one asks "is there a deficit large enough to be worth correcting"
— related, but the second is scale-aware and the first is not, which is exactly
where Deer slips through.

Not implemented. This is a measurement result and any change would touch
`NVEncCore/`, which is outside this session's offline-only scope.

## What this does not touch

The covariance closure underneath, established by exact normative replay
against a frozen oracle in `FINDINGS-2026-08-04-TEXTURE-LEAK-CLOSURE.md`. That
oracle correctly produced a *negative* lag-2 target for Deer Hunter
(`0.452 / -0.090`) and preserved its sign. The defect is in the runtime
selector's fixed-margin guard, not in the covariance mathematics.
