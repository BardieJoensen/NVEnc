# Audit of the bilateral source-fit gate, 2026-08-03

Independent check of `FINDINGS-2026-08-03-BILATERAL-SOURCE-QUALITY.md` and the
review package staged by `REVIEW-2026-08-03-BILATERAL-SOURCE.md`.  The reveal
file was not opened.

## Arithmetic reproduces

Every headline figure recomputes from the document's own per-title tables:

| claim | doc | recomputed |
| --- | ---: | ---: |
| lag-1 MAE, production / candidate | 0.2231 / 0.0202 | 0.2228 / 0.0205 |
| lag-2 MAE, production / candidate | 0.3434 / 0.0357 | 0.3437 / 0.0355 |
| played total mean, production / candidate | 0.734 / 0.992 | 0.7342 / 0.9922 |
| played total MAE, production / candidate | 0.266 / 0.028 | 0.2658 / 0.0278 |
| bytes vs plain | 23.06% | 23.0630% |
| bytes vs production | +0.248% | +0.2479% |

Review package: 16 files, 4.7 GiB, and all eight A/B pairs hash differently as
containers.  `The_Shining-A-base` and `-B-base` have byte-identical *file
sizes* (158,278,222), which looks like a duplication error and is not one at
the container level.  See below for what it actually is.

## Closed: the missing banding guard rail

`TESTING-SUITE.md` lists CAMBI as a standing guard rail because banding is
invisible to every other instrument in the base table.  The gate did not run
it, and this is the one change that specifically warrants it:
`kernel_fgs_level_compensate` deliberately adjusts the coded luma base near
black according to the signalled strength LUT, and a near-black level
adjustment on a dark gradient is the classic way to manufacture banding.

CAMBI on the grain-disabled bases, all six films, full clips (lower is better):

| title | production mean | candidate mean | delta | prod max | cand max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Casino | 0.55320 | 0.51612 | -0.03708 | 1.29755 | 1.32161 |
| Interstellar | 0.33178 | 0.33229 | +0.00051 | 1.51216 | 1.53021 |
| Scarface | 0.40449 | 0.40475 | +0.00026 | 1.15878 | 1.17683 |
| Taxi Driver | 0.04006 | 0.03453 | -0.00553 | 0.08220 | 0.06544 |
| The Deer Hunter | 0.08480 | 0.10465 | **+0.01985** | 0.28978 | **0.39368** |
| The Shining | 1.01868 | 1.01868 | 0.00000 | 2.13498 | 2.13498 |
| **mean** | | | **-0.00367** | | |

**The level compensation does not induce banding.**  Corpus mean moves -0.004;
the largest single movement is Deer Hunter at +0.020 from an already-low 0.085.
The Shining carries the highest absolute banding of the six (1.019 mean, 2.135
max) but it is identical in both arms, so it is pre-existing content, not a
consequence of the change.

Deer Hunter is the only title that moves, and it is the same title that
already carries the largest base-fidelity movement (VMAF +0.863,
SSIMULACRA2 -0.740), the worst luma band error (0.375--0.500 at 1.344) and the
worst U over-delivery (1.286).  Four independent measurements converge on one
title.

CAMBI is a CPU feature, so `--threads 16` was passed per the standing rule;
`campaign.py` passes no thread count because it only ever runs CUDA features.

## The Shining base pair is a bit-identical null

The identical CAMBI triple on The Shining is not a coincidence and not a
measurement artifact.  The two arms produce the **same decoded base**:

```text
review package, all frames, luma:  A = B = 85662a16bcd3
review package, all frames, YUV:   A = B = 58c773056de9
quality crop, first 60 frames:     production = candidate = 3201402e0d02
```

Per-title base VMAF confirms it: The Shining reads a delta of exactly `+0.000`
where the other five titles move by -0.005 to +0.863.

Level compensation was a no-op on this title, so the architecture change
altered nothing in its coded base.  Two consequences:

1. **One of the four base pairs in the blind review is the same video twice.**
   Nobody reviewing it has been told.  It is an excellent accidental control --
   a reported difference there calibrates the reviewer -- but if it is left
   undeclared it will instead burn review effort on a pair that cannot differ.
2. For The Shining, every finished-pair difference is caused by the grain layer
   alone, with zero base confound.  That makes it the cleanest controlled
   substrate in the project for the next question.

## The finished-frame gap is not the "presence" effect

The document attributes the finished-frame full-reference loss (mean VMAF
-4.67) to independent grain fields at different pixel positions, and correctly
refuses to read it as worse quality.  The per-title data says the mechanism is
more specific than that.

Grain cost per arm, measured as its own base minus its own finished VMAF, so
each row is internally controlled:

| title | production amplitude | production grain cost | candidate amplitude | candidate grain cost |
| --- | ---: | ---: | ---: | ---: |
| Casino | 0.683 | **+0.281** | 0.955 | -2.825 |
| Interstellar | 0.728 | **+0.014** | 1.060 | -3.972 |
| Scarface | 0.851 | **+1.028** | 0.998 | -3.171 |
| Taxi Driver | 0.684 | -0.214 | 0.992 | -7.298 |
| The Deer Hunter | 0.776 | **+1.079** | 0.968 | -6.962 |
| The Shining | 0.683 | -0.245 | 0.980 | -3.011 |

**Production's grain is free, and on four titles it is a VMAF gain.** The
candidate's grain costs 2.8 to 7.3 points.  Both arms add grain to nearly the
same base, so "grain presence" cannot be the operative variable.

This corrects an overstatement from 2026-08-02.  The earlier "-2.2 to -6.3 on
6 of 6" presence result was measured entirely on source-fit arms, which all
produce coarse grain.  It is a coarse-grain result being reported as a presence
result.  Production's fine, whitened grain (lag-1 0.45 against a source 0.68,
lag-2 negative on four titles) costs VMAF essentially nothing.

The two arms differ in amplitude as well as scale, and amplitude pushes the
same direction, so this is not yet isolated.  Magnitudes on The Shining, where
the base is bit-identical:

- amplitude 0.683 -> 0.980 raises the `1 + a^2` grain-error factor from 1.467
  to 1.960, an increment ratio of about 2.1x;
- the measured VMAF cost ratio is 3.011 / 0.245 = **12.3x**.

The amplitude term accounts for a small part of a much larger effect.  That is
consistent with VMAF penalising coarse grain far harder than fine grain at
comparable energy -- the hypothesis `FINDINGS-2026-08-02-METRIC-SENSITIVITY.md`
explicitly lists as unmeasured and forbids asserting.  It is still not proven
here, because scale and amplitude moved together, and mapping an MSE ratio onto
VMAF is crude.

**The experiment is now cheap.** The Shining supplies a bit-identical base and
two grain models; replaying it with amplitude matched isolates scale exactly.
Until that runs, do not upgrade this to a finding.

## Two claims that outrun their evidence

**Chroma priority.** The document states that the chroma amplitude field is
"an equal-frame diagnostic, not the variance-weighted shipping gate used for
luma", and separately that equal-frame means overweight low-grain frames -- and
then uses those same numbers to name chroma "the most direct analyser-quality
gap" and to order decision item 4.  The chroma *texture* result (U/V lag MAE
improving roughly an order of magnitude) is estimator-independent and solid.
The chroma *amplitude* result is not, and the priority ordering rests on it.
Run the variance-weighted U/V closure first, then rank.

**V did not fail to improve; it inverted.** Reported as MAE 0.129 -> 0.126,
which reads as flat.  The mean moved 0.895 -> 1.120: production under-delivered
V by 0.105, the candidate over-delivers it by 0.120, so mean distance from
target is slightly *worse*.  U improved genuinely (MAE 0.181 -> 0.073) but its
worst title regressed (Deer Hunter 1.139 -> 1.286).  Under- and over-graining
are not perceptually symmetric, and chroma over-delivery is the more visible
failure of the two.

## What holds up well

- Isolation is real: same separator, base scored rather than assumed, the 1.7%
  one-code luma shift disclosed with its mechanism.
- Base-vs-source full-reference metrics are legitimate *here*, unusually. The
  standing rule bans them for separator comparisons because grain removal
  confounds them; both arms share the separator, so that confound cancels. The
  document uses them correctly, though it does not say why it is allowed to.
- The parallel separator lead was rejected on an AUC of 0.63 falling to 0.58 --
  barely above chance -- with no code written. Correct call, correctly recorded.
- The 0.674 timing ratio is explicitly not attributed to source fitting.

## Recommendations

1. Tell the reviewer that The Shining's base pair is identical, or swap in a
   title whose base actually moved.
2. Add Interstellar to the review set: it has the highest whole-title
   over-delivery (1.060) and the thin 1.278 bright band, and it is the title
   that has repeatedly been the outlier.
3. Point the review at bright flat regions as well as dark ones. All three
   flagged band errors are in the brightest populated band (0.375--0.500), while
   both the README and the review doc direct attention to dark regions.
4. Run the amplitude-matched Shining replay before quoting any finished-frame
   full-reference number in either direction.
