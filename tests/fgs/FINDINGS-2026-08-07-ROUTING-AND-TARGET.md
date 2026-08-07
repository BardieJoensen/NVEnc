# How many routes, and what VMAF 95 costs — 2026-08-07

> Two titles excluded before any conclusion: Elemental's encode sits one frame
> ahead of its reference, and Abbott Elementary's differs at every lag. Both
> produced impossible scores (39.07 and 2.52 VMAF-neg). The remaining seven are
> alignment-verified.

## 1. One extra route is enough — and it is not the one expected

qvbr reproducing each title's pre-lookahead quality:

| class | title | qvbr | deployed |
| --- | --- | ---: | ---: |
| 4K film | Alien 1979 | **28.9** | 28 |
| 4K WEB-DL | House of the Dragon | **27.6** | 28 |
| clean 1080p | Silo | 28.5 | 28 |
| clean 1080p | Cape Fear | 29.0 | 28 |
| clean 1080p | Big Brother | 30.8 | 28 |
| clean 1080p | Star Trek SNW | 31.5 | 28 |

**The 4K override does not need splitting.** Alien's grainy 1979 remux and
HotD's clean HMAX stream want `28.9` and `27.6` — a gap of 1.3, smaller than
the spread inside any other group. The deployed 28 serves both.

**The 1080p fall-through does**, at roughly `30` against the deployed `28`.

**Further splitting is not justified.** Spread within clean 1080p is `3.0`
(28.5--31.5), larger than the 1.3 between the two 4K classes and comparable to
the 1.1 between 4K film and the clean mean. **Variance is per-title, not
per-category**: Silo (dark, detailed) and Star Trek (bright, mixed) differ more
from each other than the categories differ. A third or fourth route would be
splitting noise.

That is the ceiling of bucket-based routing. Going further needs per-title
quality targeting, not more branches.

## 2. VMAF 95 is free on 4K and unreachable on streaming 1080p

| title | qvbr for neg 95 | size there | vs pre-lookahead bucket |
| --- | ---: | ---: | ---: |
| Alien 1979 (4K film) | 26.8 | 7.47 MB | **0.92x** |
| HotD (4K WEB-DL) | 28.8 | 4.37 MB | **0.57x** |

**On 4K, targeting VMAF-neg 95 costs nothing** — both land *below* what the old
settings produced. Lookahead more than pays for the quality increase.

On 1080p WEB-DL it is not reachable at any sane rate. Best VMAF-neg at qvbr 20:

| title | best neg | best vmaf |
| --- | ---: | ---: |
| Star Trek SNW | 94.69 | 95.51 |
| Big Brother | 92.87 | 93.55 |
| Silo | 91.99 | 92.53 |
| Cape Fear | 91.52 | 92.21 |

Only Star Trek passes 95 on plain VMAF, none on neg, and qvbr 20 already costs
2--4x the bytes. **The ceiling is the source**: these are already-compressed
streaming files, and a transcode cannot exceed the quality of what it was given.
Chasing 95 there buys nothing but size.

## Recommendation

- 4K (both classes): keep **28**. If VMAF-neg 95 is wanted, **27** delivers it
  and is still smaller than the pre-lookahead library.
- non-4K fall-through: new route at **30**.
- animation: keep **34**.
- Do not add routes beyond that; per-title variance dominates.

## Limits

144-frame segments, one per title, single seek point. Class means rest on n=1
for both 4K classes. Elemental and Abbott are excluded and animation therefore
rests on Long Halloween alone here — the earlier three-title animation sweep
(`34.3 / 34.5 / 34.0`) is the better evidence for that bucket and is unaffected.
