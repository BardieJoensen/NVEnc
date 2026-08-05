# The response margin generalises across QVBR — 2026-08-05

> Offline measurement only. Nothing deployed, `modelsrc` default-off.

Closes the open blocker named in
`FINDINGS-2026-08-04-TEXTURE-TEMPORAL-STABILITY.md`: the `0.01` confidence
margin in the guarded texture-response selector was "calibrated only at QVBR
29", and `FINDINGS-2026-08-04-TEXTURE-RESPONSE-SELECTOR.md` records that it was
chosen *after* observing the Shining failure, so it is post-hoc.

## Result

**It generalises.** Against a same-pipeline QVBR-29 control on the four
genuinely unseen film scenes:

| scene | my q29 | q25 | q34 | q25/q29 | q34/q29 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Quiz Show | 0.01905 | 0.01836 | 0.02155 | 0.96x | 1.13x |
| Life of Brian | 0.02611 | 0.02671 | 0.02908 | 1.02x | 1.11x |
| Drunken Master | 0.01239 | 0.01482 | 0.01839 | 1.20x | 1.48x |
| Jerry Maguire | 0.06056 | 0.05701 | 0.05340 | 0.94x | 0.88x |
| **mean** | | | | **1.03x** | **1.15x** |

QVBR 25 is indistinguishable from 29. QVBR 34 costs about 15% on average, with
Drunken Master worst at 1.48x and Jerry Maguire actually improving. No scene
degrades in the way a rate-specific constant would predict.

All eight arms plus four controls decode completely under `libdav1d -xerror`,
and both research hooks are confirmed active in every encode log.

## The near-miss, and why the control mattered

Compared against the **recorded** q29 figures rather than a same-pipeline
control, q25 and q34 looked `3.21x`--`5.31x` worse on all four scenes. That
would have been reported as the margin being a QVBR-29 artifact, and it is
wrong.

My own q29 control reads `2.8x`--`5.0x` higher than the recorded numbers for
the same scenes, same binary and same hooks. Bit depth is not the cause —
re-measuring Quiz Show in the 10-bit analyser domain gives `0.01900` against
`0.01905` at 8-bit, with block counts within 6.

**The cause is frame selection.** The same scene, arm and binary produce:

| measurement | frames | Drunken Master margin arm |
| --- | --- | ---: |
| response-selector table | six, set not recorded | `0.00346` |
| temporal-stability run | `1,27,52,...,286` (12) | `0.01561` |
| this run | `10,58,106,154,202,250` (6) | `0.01239` |

A **4.5x spread from frame choice alone**, on identical media. The stability
run's own frame sets differ per scene — Quiz Show uses 16 frames including
`1,7,27,28,34,...` — because they were derived from that candidate's emitted
table updates rather than fixed.

## Consequence

**Absolute texture-error figures are not comparable across documents in this
project unless the frame set matches.** Only ratios measured within one frame
set are meaningful. This is the third instance of the sampling caveat in two
days — after the HEVC harm that dissolved at 16 pairs and the chroma V totals
that rose at 16 pairs — and it is the most severe, because here the frame sets
were *deliberately* chosen per scene and the resulting numbers were tabulated
next to each other as if comparable.

Anything quoting a bare texture error should state its frames. The ratio
columns above are safe because every cell shares one frame set.
