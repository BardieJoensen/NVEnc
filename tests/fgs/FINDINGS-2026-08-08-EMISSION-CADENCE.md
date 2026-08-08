# The model update cadence is binding on every interval — 2026-08-08

> Research into the second over-synthesis mechanism. No code changed, nothing
> deployed. Measured from grain tables already on disk.

## Correcting the premise

The batch report attributes over-synthesis to "one grain model fitted per file,
applied uniformly". That is not what this encoder does. `modelWindow` defaults
to **8** and `NVEncFilterFilmGrain.cu:2797` trims the history to it, so the fit
is a rolling 8-frame estimate, refreshed continuously.

The problem is not the fit. It is what the fit is allowed to *emit*.

## The emission lock

`NVEncFilterFilmGrain.cu:2986`:

```cpp
if (m_state->pendingStreak >= FGS_MODEL_CANDIDATE_FRAMES      // 3
    && m_state->framesSinceModelUpdate >= FGS_MODEL_MIN_UPDATE_FRAMES) {  // 24
```

A fit that differs by more than the tolerance (`0.05` bilateral, `0.10` motion)
must persist **3 frames** *and* wait until **24 frames** have passed since the
last update. Otherwise the previous model is re-signalled and
`diagnostics.modelHeld` is set.

That exists for a good reason -- requantising every frame makes grain twinkle,
and the comment says so. The question is whether the constant is right.

## It binds on essentially every update

Median frames per interval, from emitted tables:

| title | entries | median frames/interval |
| --- | ---: | ---: |
| Casino | 12 | **25.0** |
| Interstellar | 12 | **25.0** |
| Kiki | 13 | **25.0** |
| Long Halloween | 12 | **25.0** |
| Scarface | 12 | **25.0** |
| The Deer Hunter | 12 | **25.0** |
| The Shining | 12 | **25.0** |
| Taxi Driver | 12 | **26.0** |
| Poppy Hill | 15 | 18.0 |

**Eight of nine sit at 25 -- the 24-frame floor plus one.** These are not
intervals chosen because the grain was stable for a second; they are intervals
truncated by the cadence. The fit wants to move roughly every 8 frames and is
being held to a third of that rate.

Poppy Hill's 18 is consistent: more scene cuts, and a cut calls
`resetTemporalState()` which clears the lock.

## Why this causes over-synthesis specifically

Within a 25-frame interval one model covers content whose true grain varied.
The model is fitted on the *rolling window at the moment it was accepted*, so
wherever the source gets quieter later in the interval, synthesis keeps
delivering the earlier, louder level. Over-synthesis is the asymmetric outcome
because too much grain is visible and too little is not.

Hard cuts escape this -- the SAD detector calls `resetTemporalState()` and the
next model is accepted immediately. What does not escape: dissolves, fades,
lighting changes, and any gradual grain change inside a shot.

## What this does not establish

The correlation is circumstantial. Every interval sitting at the floor proves
the cadence is binding; it does not prove the held models are *wrong* by the
amount the library verifier measured. Establishing that needs per-interval
delivered-vs-source amplitude, which none of the current harnesses produce.

It is also not obviously separable from the selection-bias mechanism. Both
depress the analyser's responsiveness to real grain, one across blocks and one
across time.

## The experiment worth running

`FGS_MODEL_MIN_UPDATE_FRAMES` is a constant. Sweep it (24 -> 12 -> 8, matching
`modelWindow`) and measure:

1. retention on weak-grain titles -- should fall toward 1.0 if this mechanism
   is real;
2. retention on strong-grain titles -- must not move (the same selectivity test
   the ranking change is under);
3. **temporal stability** -- the twinkle the constant exists to prevent. Frame
   to frame variation of delivered grain amplitude within a shot is the
   measurement, and it is the cost side of this trade.
4. table size -- more intervals means more signalling overhead, probably
   negligible but should be checked rather than assumed.

Unlike the ranking change, this one has an explicit known downside, so (3) is
not optional.
