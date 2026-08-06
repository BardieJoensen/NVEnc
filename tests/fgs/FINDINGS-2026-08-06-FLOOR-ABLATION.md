# The floor model is wrong — 2026-08-06

> Executes `PLAN-2026-08-06-FLOOR-ABLATION.md` and lands on its pass condition
> 3. Diagnosis only; no default changed, `modelsrc` still default-off.

`FINDINGS-2026-08-06-FLOOR-LOCATION.md` named the flat-block selection floor at
`:2425` as the leading cause of the one-defect relationship — low-signal
over-delivery of `1.47`--`5.18x`, log-log slope `-0.414`. **That conclusion is
retracted.** The floor does not bind at its production value and cannot be the
cause.

## The ablation

`NVENC_FGS_TEST_MIN_NOISE=<select>[,<denoise>]` (commit `3bfdcfe9`) moves the
two floors independently. Four arms, five titles, QVBR 25, `modelsrc=on`:

| title | band | control | select 0.05 | denoise 0.05 | both 0.05 |
| --- | --- | ---: | ---: | ---: | ---: |
| Long Halloween | low | 0.01982 | 0.01982 | 0.01982 | 0.01982 |
| Poppy Hill | low | 0.02356 | 0.02356 | 0.02356 | 0.02356 |
| Kiki | low | 0.04152 | 0.04152 | 0.04152 | 0.04152 |
| The Deer Hunter | high | 0.04497 | 0.04497 | 0.04497 | 0.04497 |
| Taxi Driver | high | 0.01705 | 0.01705 | 0.01705 | 0.01705 |

A tenfold reduction of both floors changes the emitted curve by **nothing**, on
every title and all three planes, to five decimal places.

Inertness verified: with the variable absent the new binary reproduces the
pre-hook `denoise=auto` curve RMS exactly on 3/3 titles, and `3bfdcfe9` is the
only FGS-touching commit between the two builds.

## The knob is live — proven, not assumed

A dead knob and a non-binding floor produce identical null results, so the
override was pushed until it broke something. Selection floor against admitted
flat blocks, Long Halloween, 2040 blocks:

| select | flat blocks | curve RMS |
| ---: | ---: | ---: |
| 0.05 | **208** | 0.01982 |
| 0.5 (production) | **208** | 0.01982 |
| 1.0 | 206 | — |
| 2.0 | 206 | 0.01623 |
| 4.0 | 17 | — |
| 8.0 | **0** — model never forms | encode produces no table |

**`0.05` and `0.5` admit the same 208 blocks.** Not one block in a grain-free
animation title lies below sigma 2.0 on 10-bit. The floor sits underneath the
entire population, so lowering it admits nothing and raising it is the only
direction with an effect.

## The censoring mechanism is real, just inactive

At `select = 2.0` the two bands move in opposite directions:

- Long Halloween (low signal) `0.01982` → `0.01623`, down;
- The Deer Hunter (high signal) `0.04497` → `0.05582`, **up**.

That is the censored-sample bias made visible: discarding the quietest blocks
leaves a grainier surviving sample and inflates the estimate. The mechanism
proposed in `FLOOR-LOCATION` exists and behaves as predicted — it simply does
not operate at `minNoiseLevel = 0.5`, because nothing is below it.

## What this costs and what it buys

Pass condition 3 was written as "record that and stop", and it applies. Both
floors are exonerated: the denoise clamp by its `~1.1x` per fourfold
sensitivity, the selection floor by not binding at all. **The defect lives in
the estimator** — in what the analyser does with the blocks it admits, not in
which blocks it admits.

That has a consequence the plan anticipated: six estimator rejections were each
fitted to one symptom of what is now known to be one relationship, and none of
them can be excused as "the floor was interfering". They need re-reading as
attempts on the actual defect.

It also removes a hypothesis that would have been expensive to be wrong about
later. Lowering `minNoiseLevel` in production would have changed nothing
whatsoever, and the counter-test built to catch it reintroducing codec-noise
fitting never had anything to catch.

## Methodological finding: never compare grain tables by hash

The arms initially appeared to differ, and did not. **The encoder is
nondeterministic at the byte level**: six identical runs of the same binary,
same input, same settings produced **two distinct table hashes** — and one of
them was byte-identical to the `D-both` table, which is what first looked like a
floor effect.

The fitted curve is not affected. Across those same six runs the curve RMS was
identical to five decimals, `sd = 0.00000`:

| instrument | six identical runs |
| --- | --- |
| table md5 | 2 distinct values |
| curve RMS | 1 value, sd `0.00000` |

The nondeterminism is in table *structure* — interval boundaries and entry
layout — not in fitted amplitude. So `md5` is an invalid instrument for
comparing arms and every prior curve-RMS result stands, including the denoise
sweep in `FLOOR-LOCATION`, which was briefly in doubt when the nondeterminism
surfaced.

## Limits

Five titles, one QVBR, emitted curve rather than delivered amplitude. The
emitted curve is the correct instrument for locating an analyser-side floor and
is not a quality claim; it overstates delivered strength roughly twofold. Stage
2 of the plan — the eight-cell delivered-amplitude corpus and the codec-noise
harm axis — is **not run**, because it was conditional on stage 1 moving and
stage 1 did not move.

The block-admission table is from one title. The claim it supports is narrow
and directly measured: at production settings the floor excludes nothing.
