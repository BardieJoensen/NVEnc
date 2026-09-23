# Motion evidence with separate frame pairs

The follow-up removes the motion diagnostic's false conflicts on the declared
flat-grain controls while retaining detection of the tested small translations.
It does **not** resolve fast-motion or persistent-grain ambiguity and remains
an offline measurement. No encoder output or source-population rule changed.

## Change

The [first stationarity study](FINDINGS-2026-09-23-STATIONARITY-CONTROLS.md) fit
and assessed small translations on the same noisy samples. Its minimum-error
search could therefore find accidental matches and report independent grain as
motion: 129 of 192 flat-grain component controls had a false motion conflict.

`temporal_motion_holdout_reference.py` now selects a displacement using only
frame pairs 0/1 and 2/3, then evaluates that fixed displacement on pairs 4/5 and
6/7. These pairs share no frames. The validation decision performs no new search,
requires the original 20% improvement/0.04 error floor on both validation pairs,
and preserves negative improvements and undefined-ratio indicators. Training
alone chooses the displacement; changing the validation pictures cannot change
the proposal. The old per-pair measurements remain available as diagnostics.

Disjoint frames do not guarantee statistical independence when the source has
temporally correlated noise. The new helper explicitly leaves population
acceptance and stationarity qualification false. Its four-pixel search is also
insufficient evidence about faster, changing or nontranslational motion.

## Frozen development comparison

The new manifest precedes its results. It reuses the earlier 16 families, 32
seeds and two depths as **development regressions**, not unseen qualification.
The variance, lag, mean and disjoint-history rules are unchanged.

- Flat independent grain: motion false conflicts fall from **129/192 to 0/192**.
- One-pixel translation, four-pixel translation, the moving sinusoid and grain
  combined with one-pixel translation: **192/192** components in each family
  still have motion evidence.
- Fast zero-grain translation: **154/192** components now avoid every conflict.
  Removing spurious matches also removes accidental vetoes on this hard negative;
  absence of motion evidence still cannot imply stationary grain.
- Persistent plus independent grain: **192/192** still avoid conflicts while
  the conditional estimate misses roughly half the known total grain variance.
  The source/detail ambiguity remains unresolved.

All 1,024 synthetic source estimates and ground-truth variances match the prior
study. The same 3,960 HDR development tiles also preserve native source/previous
identity, clocks, moment arrays, R1 populations/support and every non-motion
conflict. Previously rejected regions remain rejected, including the additional
tiles with no remaining diagnostic conflict. Border coverage is unchanged.

Seven additional tests cover exact known translation, training/validation
separation, reversal without refitting, an independent scalar cost oracle,
native-depth equivalence, quiet/undefined denominators and the retained false
motion example. The full CPU suite passes **208 Python tests in 29 suites plus
29 C++ programs**. This CPU-only diagnostic change needs no encoder rebuild.

## Scope and next step

The change makes motion evidence more trustworthy on these controls; it is not
a classifier that can authorize synthesis. Keep the counterexamples and source
fallbacks. A future population rule must protect persistent residual as detail
unless independently established otherwise, and must obtain motion evidence
outside this small tile search before relying on stationary temporal estimates.
Whole-picture model selection and R3–R8 qualification remain open.

The [handoff](WORK-TO-PRODUCTION.md) evidence root contains
`roadmap-r3-motion-holdout-20260923/manifest.json`, `synthetic.json`, `real.json`,
`report.json`, `cpu.json` and `cleanup.json`. No reserved qualification footage
was opened, no worker pause was needed, and no GPU experiment was scheduled.
