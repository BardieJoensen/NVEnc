# Library audit: no demonstrated damage — 2026-08-07

> Read-only audit of what production FGS has actually done to the library since
> it went live on 2026-07-29. **Retracts two earlier claims**, including one I
> made to the user in this session.

## What was audited

428 library videos changed since FGS entered the flow. Of those, **306 are
AV1** (flow output); 54 h264 and 27 hevc were not transcoded.

Grain detection is behavioural, not parsed: decode the same frames twice
through dav1d, once normally and once with `-filmgrain 0`, and compare hashes.
Differing output means the stream really carries grain the decoder synthesized.
Exact, and it needs no reference — which matters because most originals are
gone.

| | |
| --- | ---: |
| AV1 transcodes since 2026-07-29 | 306 |
| carrying synthesized grain | 165 |
| titles flagged as grain-free sources | 10 |
| of those carrying grain | 8 |

## The eight flagged titles are not evidence of a misfire

Seven of the eight are Studio Ghibli — Ponyo, Totoro, Grave of the Fireflies,
Princess Mononoke, Howl's Moving Castle, The Wind Rises, From Up on Poppy Hill.
**Ghibli is cel animation photographed on 35mm.** Those sources plausibly carry
real photochemical grain, in which case synthesizing it is correct behaviour,
not a defect. The title-hint list that flagged them conflated *digital*
animation with *film-originated* animation.

No originals are retained for any of them, anywhere in the download tree, so
this cannot be settled for those seven.

The eighth, Soulm8te (2026, WEB-DL), does have its original:

| | flat-block noise (10-bit codes) |
| --- | ---: |
| original WEB-DL h264 | **3.844** |
| library AV1 + FGS | **3.830** |
| grain the decoder synthesizes | 2.03 |

Delivered noise matches the source to **0.4%**. The source genuinely had that
noise; FGS removed and re-synthesized it and landed on the right amount. On the
one flagged title that can be checked, the encoder is behaving correctly.

**No damaged transcode has been demonstrated.**

## Retraction 1: the animation over-synthesis result

`FINDINGS-2026-08-06-ANIMATION-GATE.md` reports the candidate synthesizing
~2.5x the source's noise on Long Halloween, Poppy Hill and Kiki, and that
number has been quoted since — including by me in this session, as "production
over-delivers ~1.9x on grain-free content".

**The inputs were library AV1 copies.** No originals for those titles exist in
`long-term-seeding` or anywhere else in the download tree, the gate's `-O`
clips are lossless FFV1 wrappers around a decode, and Poppy Hill's library copy
is itself one of the eight files carrying synthesized grain. So that experiment
measured **FGS applied to FGS output** — a second generation — against a
"source" that had already been denoised and re-grained once.

The user's own standing rule names this exact trap: score against the original
download, never a library copy, because it measures two stacked lossy
generations instead of one.

Consequences:

- the `2.5x` and `1.9x` over-synthesis figures on animation are **withdrawn**;
- the Long Halloween cell in `FINDINGS-2026-08-06-ONE-DEFECT.md`
  (`0.377` source, `2.460x`) is second-generation and should be dropped from
  that table. The relationship survives: it rests on 19 cells with three of the
  four low-signal cells being film (Interstellar V darkest, Scarface neutral
  chroma, Shining V band);
- `emission_exponent.py`'s nine-title fit includes three animation titles on
  second-generation input. The exponent is a statement about the analyser's
  response *to the files it was given*, which remains internally valid, but the
  corpus is not what it was labelled.

The provenance was never recorded in the harness or the findings doc, which is
how it survived. Source paths belong in the doc.

## Retraction 2: the urgency I attached to the content gate

I told the user the July campaign's finding — worst-frame VMAF collapsing to
31--60 on non-grain content — probably applied to files already transcoded, and
suggested auditing for damage first. That framing was too strong on two counts:
the July measurement predates source-fit and covariance closure, and the
animation evidence I leaned on is the withdrawn result above.

The gate is still worth adding as a safety measure. It is **not** a response to
demonstrated harm, and nothing found here says the library needs re-transcoding.

## Limits

Six frames per file at a fixed 300s offset; a title whose grain starts later
could read as grainless. Grain *presence* is exact, but whether it *should* be
present is only answerable where an original survives — which is one title out
of eight. The Ghibli question stays open unless those originals are re-acquired.

## What this changes

The audit was the right first step and it came back clean. The remaining plan
items stand on their own merits rather than on damage: the content gate as
cheap insurance, animation bucket calibration because those buckets now carry a
film-derived value, and a Tdarr smoke test before unpausing.
