# Korra S02E12: what the analyzer actually signals, 2026-08-01

## Result

`fgs-open-questions.md` §3g attributes the Korra retention collapse to "the
grain model is fitted once per file and applied uniformly", and lists as not
established whether it is literally one grain table or per-scene fits regressing
to the file mean. It says a bitstream-level count of distinct grain parameter
sets has not been done.

The `--log-level debug` `fgs-model` lines carry both the measured source noise
and the signalled model per frame, so no bitstream parsing is needed.
`model_trace.py` parses them. Over the full 84,440-frame episode:

| measure | value |
| --- | ---: |
| distinct parameter sets | **3,046** |
| model changes | 3,051 |
| scene resets | 332 |
| frames holding the previous model | 81,387 (96.4%) |
| source noise range | 0.98 - 9.19 (**9.4x**) |
| signalled amplitude range | 13.4 - 76.2 (**5.7x**) |

**It is not one table per file.** The model updates thousands of times and
tracks source grain monotonically.

## The cadence gates are not the cause

The analyzer holds the previous model when a fresh fit is within 5%
(`NVEncFilterFilmGrain.cu:1612`), requires a differing fit to persist
`FGS_MODEL_CANDIDATE_FRAMES = 3`, and enforces
`FGS_MODEL_MIN_UPDATE_FRAMES = 24` between updates. Those gates are a plausible
mechanism for a stale model pinned through a rising source.

They are not what happens here. The longest held run is 384 frames, during
which source noise moved 1.33 to 1.36. It held because the content was stable.
No hold in this episode spans a materially rising source.

## What is actually wrong: a compressive strength fit

The heavy sequences are 1,343 frames, **1.59% of the episode**, in three runs:

| start | end | frames | src min-max | amp min-max | held |
| ---: | ---: | ---: | --- | --- | ---: |
| 883 | 896 | 14 | 4.00-4.65 | 59.3 | 100% |
| 1627 | 2805 | 1,179 | 4.42-9.19 | 35.3-76.2 | 96% |
| 84,930 | 85,079 | 150 | 4.84-5.91 | 35.0-58.3 | 95% |

The signalled-to-source ratio falls where grain is heaviest:

| | median signalled/source |
| --- | ---: |
| all frames | **14.5** |
| heavy sequences | **9.6** |

A systematic **34% relative under-signal** on exactly the content that fails.

**This is not a format ceiling.** AV1 scaling points are 8-bit with a maximum of
255, and `scaleShift` stayed at 11 for every frame in the file:

| source noise band | n | src med | amp med | peak point | max point |
| --- | ---: | ---: | ---: | ---: | ---: |
| < 2 | 74,842 | 1.56 | 22.9 | 27 | 95 |
| 2-4 | 8,255 | 2.13 | 31.6 | 39 | 98 |
| 4-6 | 564 | 5.49 | 48.1 | 76 | 112 |
| > 6 | 779 | 6.53 | 66.1 | 98 | 113 |

Peaks reach 113 of 255. There is more than 2x headroom at the heaviest grain in
the episode, so the curve is not clipping. The fit is simply lower than it
should be, which agrees with §3g's own conclusion that this is not an amplitude
ceiling, and now supplies the mechanism.

The same signature appears in `FINDINGS-2026-08-01-RETENTION-DECOMPOSITION.md`:
Cape Fear synthesises at 1.273 with leakage of only 0.149. The strength fit is
content-dependent in a way nothing compensates, in both directions.

## What this does not explain

A 34% under-signal is not a collapse to 0.100. Two candidates remain, and they
are distinguishable:

1. **Downstream of the fit** -- synthesis not delivering the signalled
   amplitude. That would be a real encoder defect.
2. **Measurement.** Korra is animation. Whole-frame HF sigma is dominated by
   line art, which is constant across scenes, so it would compress a 10x grain
   swing into something like the reported 1.7x and crush the ratio precisely in
   the heavy sequences where grain should dominate.

Candidate 2 deserves the weight. That estimator has now been wrong three times
in this same direction in one session: The Shining read 1.154 against a
decomposed 0.950, Drag Race read 3.773 against a median of 0.948, and plain-arm
retention read 0.33-0.97 against a flat-block 0.10-0.64. Animation is its worst
case.

The discriminator is to re-measure the heavy run (frames 1627-2805) with
`flat_retention.py`, whose mask excludes line art. If retention opens toward the
signalled 5.7x it was the ruler; if it stays at 1.7x, synthesis genuinely is not
delivering.

## A separate compounding factor: 59.94 fps

The source is 59.94 fps progressive (`r_frame_rate=19001/317`), 84,440 frames
over 1,424 seconds. Animation authored at 24 or 12 fps carried in a 59.94p
container means frames are duplicated roughly 2.5x. This is the same class as
§2a.

Two consequences for FGS specifically, neither visible to any per-frame
measurement:

- The 8-frame rolling window spans only about three unique frames, so the fit
  has far less independent data than the window size implies.
- The source's grain is **identical** on duplicated frames, while FGS
  synthesises independent grain per output frame. Static grain becomes crawling
  grain. No HF sigma comparison can detect this, because per-frame energy is
  unchanged.

## Method

`model_trace.py <debug.log>`. The encode used the production settings
(`--qvbr 34 --preset quality --tune hq --aq --aq-temporal`, bilateral denoiser)
so the trace describes the shipped configuration.
