# Animation: the July collapse is gone, one real caveat remains — 2026-08-06

> Offline measurement only. Nothing deployed, `modelsrc` default-off.

Every "no harmful input found" statement in this project rested on ten cells
that were all **film**. Animation is the class that collapsed in the 2026-07
11-title campaign — VMAF minimums of `31`--`60` against plain's `94`--`96` —
and `FINDINGS-2026-08-03-GENERAL-SOURCEFIT-GATE.md` records that the analyser
emits grain on every frame of every title tested including animation. It had
never been run end to end on the current architecture.

Three titles spanning the class: Kiki's Delivery Service (cel animation, film
scan), From Up on Poppy Hill (later Ghibli, cleaner transfer) and Batman: The
Long Halloween (modern digital, essentially grain-free). Plain, production FGS
and the source-fit candidate, QVBR 29, all nine streams passing complete
`libdav1d -xerror`.

## Both July blockers are closed

| title | plain | production | candidate |
| --- | ---: | ---: | ---: |
| Kiki | 7,797,859 | 5,019,652 (-35.6%) | 5,022,978 (-35.6%) |
| Poppy Hill | 3,547,316 | 3,202,381 (-9.7%) | 3,201,195 (-9.8%) |
| Long Halloween | 1,751,417 | 1,626,985 (-7.1%) | 1,628,485 (-7.0%) |

**Files shrink**, so the "FGS grows non-grain content" failure does not
reproduce. And the worst candidate VMAF **minimum** across all three is
`75.55`, against July's `31`--`60`. The collapse is gone.

Production and candidate are within `0.06%` of each other on all three, so any
quality difference between them is model choice, not bitrate.

## The VMAF ordering is the metric bias again, not harm

| title | p1: plain → production → candidate |
| --- | --- |
| Kiki | 93.06 → 89.85 → 87.55 |
| **Poppy Hill** | 95.08 → 89.03 → **77.20** |
| Long Halloween | 94.06 → 92.21 → 90.48 |

Poppy Hill loses `11.8` p1 against production, which looks alarming until the
delivered grain is measured against what the source actually contains:

| title | source temporal sigma | production synth | candidate synth |
| --- | ---: | ---: | ---: |
| Kiki | 1.897 | 1.588 (84%) | **1.887 (99%)** |
| Poppy Hill | 1.259 | 0.977 (78%) | **1.302 (103%)** |
| Long Halloween | 0.377 | 0.713 (189%) | 0.928 (**246%**) |

**Kiki and Poppy Hill are film-scanned animation and genuinely carry grain**
(`1.90` and `1.26` eight-bit codes). The candidate reproduces it almost
exactly — 99% and 103% — where production delivers only 84% and 78%. So the
title with the largest VMAF penalty is the one where the candidate is *most
faithful*, which is the bias this project measured directly in
`FINDINGS-2026-08-02-METRIC-SENSITIVITY.md`. Not harm.

## The one real caveat: grain-free digital animation

Long Halloween's source carries `0.377` codes of temporal noise — effectively
none. Both arms synthesize onto it anyway: production `0.713` (1.9x) and the
candidate `0.928` (**2.5x**). The candidate also raises its texture from
lag-1 `0.069` to `0.251`, so it is not only more grain but coarser grain.

This is the analyser doing what
`FINDINGS-2026-08-03-GENERAL-SOURCEFIT-GATE.md` said it does — emitting grain
regardless — and the candidate does it harder. It **partially** adapts:
`0.93` on grain-free Long Halloween against `1.89` on grainy Kiki, so it scales
with content rather than applying a constant. It just does not scale to zero.

Whether `0.93` codes of invented grain on a flat animation cel is visible is a
perceptual question this cannot answer. The VMAF cost is small — `1.73` p1,
the least of the three titles — which is consistent with it being subtle.

## Verdict on the standing claim

**"No harmful input found" survives, narrowly, and now covers animation.** No
title regressed catastrophically, none grew, and on the two titles with real
grain the candidate is markedly more faithful than production.

The qualification is specific: on genuinely grain-free digital animation the
candidate synthesizes about **2.5x** the source's noise, coarser than
production's, and that is the closest thing to a harmful admission this project
has produced. It is not established as harm — no measurement here shows the
output is worse than plain in a way that is not metric bias — but it is the
first case where the analyser is clearly adding something the source does not
contain, on content where there is no correct grain to be faithful to.

## Answering the routing question directly

The temporal-static selector **can** tell grainy from non-grainy: it admitted
**zero** blocks on a Poppy Hill frame and `temporal_grain_report` aborted
outright, because the test requires temporal and spatial variance to agree,
which drawn flat regions fail. The measurement distinguishes the classes
cleanly. The analyser simply does not act on that signal — nothing routes on
it.
