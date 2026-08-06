# The playback gate was run — 2026-08-06

> Records the first perceptual data this project has collected. Nothing
> deployed; `modelsrc` remains default-off.

The motion gate had been open since 2026-08-02 with two unwatched packages at
4.7 and 5.1 GiB. It was distilled to four 8-second side-by-side crops
(`minimal_review.py`), taken from the sealed blind package with no re-encode
from source, at the measured window and column where the two arms diverge most,
at native 1:1 resolution.

## Verdict on the A/B question

> "They seem so similar. I wouldn't know if I didn't have to look."

Reviewed on Emby, four titles, grain-disabled base pairs. That is the
**no-difference** outcome, and it is a pass: the review was aimed at the most
divergent 8 seconds of each title, in the 960-wide column with the largest
measured inter-arm difference, so it was the best available chance of seeing a
difference.

This bears directly on the deadlock in
`FINDINGS-2026-08-03-MOTION-FINISH.md`: the candidate wins base VMAF 6/6 while
production wins base SSIMULACRA2 and Butteraugli 6/6, and the two metrics were
arguing over whether extra grain-like structure in the base is useful detail or
residue. On this evidence the disagreement is **below the visible threshold**.

The A/B mapping was never opened and the verdict does not depend on it.

## Three specific observations, and what each turned out to be

**1. "At the hair it seems more obvious."** Real and measurable. Luma
high-frequency energy at that crop: original `19.512`, A `4.958`, B `6.004`.
Both bases sit 3--4x below the source because grain is disabled, and **B holds
21% more high-frequency structure than A** on The Deer Hunter, reversing to A
holding 9% more on The Shining. The reviewer located the one place the metric
disagreement is visible.

**2. "The jacket seems more yellow."** A defect in the review material, not the
encoder. The published clips carried no colour metadata, so BT.2020/PQ content
rendered as BT.709 SDR — which distorts warm midtones most. Source-level
chroma shifts are `+0.08`/`+0.11` out of 1024, about 0.01% and roughly a
hundred times below visibility. Re-published as HDR10 and the observation was
not reproduced.

**3. "The original looks flat and grey at the ear; the encodes have a red/pink
cast that makes sense."** Real, and it opened the largest structural finding of
the session. Hue and saturation match to `0.1%`; what differs is chroma
*noise*, which reads as grey speckle. Chasing it produced
`FINDINGS-2026-08-05-CHROMA-DIAGNOSIS.md`'s saturation non-uniformity and then
`FINDINGS-2026-08-06-ONE-DEFECT.md`.

## The target decision, made by the reviewer

The reviewer preferred the encodes' cleaner skin, then argued against their own
preference:

> "This is not what the creator wanted me to see. So no matter how much I like
> it, it's not the original movie and what I'm supposed to see."

That is the correct standard and it is now on record. FGS abandons pixel
fidelity by construction — it synthesizes a positionally different grain field
— so it can only be judged on *statistical* fidelity to the source. Under that
standard a perceptual preference for the cleaner result does not move the
target, and chroma delivery at `1.4`--`5.2x` source on low-signal regions is a
defect however it looks.

## Limits

One viewer, four titles, 8-second crops at pre-selected moments, on a
grain-disabled base pair plus a grain-on finished pair. It does not clear
disocclusion on high-motion content generally, and it is not a substitute for
watching a whole title. What it does establish is that the base-fidelity metric
disagreement does not correspond to a visible difference at the moments most
likely to show one.

## Consequence

The perceptual blocker on the motion arm is **provisionally cleared**. The
remaining blockers are amplitude fidelity — now consolidated as a single
low-signal defect — and the fact that the candidate configuration is reachable
only through test-only environment hooks.
