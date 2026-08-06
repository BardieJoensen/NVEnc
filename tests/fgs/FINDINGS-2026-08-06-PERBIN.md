# The per-bin fallback hypothesis fails — 2026-08-06

> Offline measurement only. Nothing deployed.

`FINDINGS-2026-08-06-SELF-ROUTING.md` proposed that the animation
over-synthesis comes from `NVEncFilterFilmGrain.cu:331` substituting a spatial
estimate wherever temporal evidence is missing, and predicted that **bins with
low temporal coverage would carry the excess**. Tested per luma bin over 27
frames on all three animation titles.

## It does not hold

| title | corr(temporal coverage, over-synthesis) |
| --- | ---: |
| Long Halloween | **+0.430** |
| Poppy Hill | -0.676 |
| Kiki | +0.048 |

No consistent direction, and the sign is *positive* on the one title where harm
was measured — more coverage, more excess, the opposite of the prediction.

Within Long Halloween the contradiction is explicit: its worst bin
(`0.000`--`0.125`, ratio `1.97x`) has the **highest** coverage of its three
bins at `0.225`, while its best bin (`0.250`--`0.375`, ratio `0.79x`) has
`0.172`.

**The fallback is not the mechanism**, and zeroing uncovered bins would not fix
animation. That was the most promising remaining lead for making `modelsrc=on`
universally safe, and it is now closed.

## What the data shows instead: a dark-bin pattern

| title | bin | source sigma | synth | ratio |
| --- | --- | ---: | ---: | ---: |
| Long Halloween | 0.000--0.125 | 0.417 | 0.822 | **1.97x** |
| Long Halloween | 0.125--0.250 | 0.655 | 1.000 | 1.53x |
| Long Halloween | 0.250--0.375 | 1.544 | 1.221 | 0.79x |
| Poppy Hill | 0.000--0.125 | 0.337 | 0.968 | **2.87x** |
| Poppy Hill | 0.125--0.250 | 4.500 | 1.439 | 0.32x |
| Kiki | 0.125--0.250 | 1.388 | 1.632 | 1.18x |
| Kiki | 0.375--0.500 | 1.533 | 1.938 | 1.26x |

On both animation titles that have a darkest bin, that bin is the worst, and
the ratio falls monotonically as luma rises. Kiki has no `0.000`--`0.125` bin
in range and its ratios are flat at `1.03`--`1.26`.

This is the same shape as two results already on record: Interstellar V's
darkest chroma band at **`2.763x`** in
`FINDINGS-2026-08-05-CHROMA-DIAGNOSIS.md`, and the luma band errors in
`FINDINGS-2026-08-04-AMPLITUDE-CLOSURE.md`. Dark bins over-delivering may be
one cross-cutting defect rather than three separate ones.

## Caveats

Poppy Hill's darkest bin has only 76 flat blocks and Long Halloween's brightest
only 128, so the extreme ratios rest on small populations. Three titles. The
dark-bin observation is a pattern worth testing, not an established mechanism —
the film corpus check is the obvious next step and is running.

## Standing consequence

Animation remains an open risk for universal application. The 2.5x
over-synthesis on grain-free digital animation is real, the fallback does not
explain it, and no gate has been found that isolates it without rejecting
content that benefits.
