# What full-reference metrics can and cannot see about grain, 2026-08-02

> **Audit correction, 2026-08-02:** the grain-present versus grain-absent
> result remains valid because each pair is decoded from the same stream.  The
> pre/post leak-closure comparison did **not** isolate grain correctness as
> claimed.  Its grain-disabled bases differ, and its emitted AR sequence also
> changes.  Retain that table only as an end-to-end comparison of two
> candidates; withdraw the causal conclusion and the "two orders of magnitude"
> estimate until a fixed-base, fixed-AR, fixed-seed replay is run.

Prompted by a design question: if synthesised grain had the right colour, luma
placement, size and position, would VMAF stop punishing it -- and could VMAF
then be used as the optimisation target?

The position and grain-presence parts are measured here.  The attempted
grain-correctness arm is retained as a failed experiment so its confounds are
not repeated.

## Position is not a fixable parameter

For source grain `g` and synthetic grain `g'` at relative amplitude `a`,
positionally independent by construction:

```text
E[(g - g')^2] = sigma^2 * (1 + a^2)
```

minimised at `a = 0`, for every value of texture, colour and luma placement.
Grain that is perfect in every respect except position still costs `2*sigma^2`,
3 dB worse than sending no grain at all.

Position cannot be corrected inside AV1 FGS because it is exactly what was
discarded to save the bits.  The bitstream carries AR coefficients, a scaling
curve and a seed; the seed does not encode source grain positions, and
`FINDINGS-2026-08-02-QVBR-EMISSION.md` found NVENC picks its own seed with
0 of 42 matching the analyser's table.  Transmitting grain position would be
transmitting the grain.

## Metrics see grain *presence* strongly

Grain-disabled base against grain-enabled finished, same stream, same arm,
1080p centre crop, HD models (from `FINDINGS-2026-08-02-MOTION-METRICS.md`):

| title / arm | base | finished | delta |
| --- | ---: | ---: | ---: |
| The Shining bilateral | 93.38 | 90.72 | -2.65 |
| The Shining motion | 82.09 | 79.93 | -2.16 |
| The Deer Hunter bilateral | 76.42 | 70.12 | -6.30 |
| The Deer Hunter motion | 62.80 | 59.76 | -3.04 |
| Scarface bilateral | 80.06 | 77.16 | -2.90 |
| Scarface motion | 76.36 | 74.04 | -2.32 |

Six of six.  Enabling the best grain the project has produced -- source-fit,
correct lag-1/lag-2, leak-closed amplitude -- costs 2 to 6 VMAF points every
time.

## The attempted grain-correctness comparison is not isolated

The intended test compared the pre/post leak-closure candidates at the same
QVBR, separator and selector.  Mean synthesis amplitude against source truth
moves from 0.893 to 0.959, and corpus bias against the true post-encode target
from -0.069 to -0.004.

The isolation premise is false.  An audit of the emitted side data finds
different AR entries and update intervals on every title.  A direct
grain-disabled decode also differs; for Taxi Driver:

```text
pre  SHA-256 7f7f1a3369ff58eecac67780215871ffc0caf1792930244b3ff5bc3ded3d529f
post SHA-256 552c926dbecc45e009ee06a68efdac72f91c0c19580550334678737c448b6617
```

The bitstream seed sequence is identical, which removes one possible
confound, but it is not enough.  The comparison mixes luma strength, AR-model
and coded-base changes.

Scored at native 4K against the lossless originals, 4K models, dav1d decode:

| title | synth pre | synth post | VMAF pre | VMAF post | dVMAF | dNEG | dPSNR-Y | dSSIM | dbytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Casino | 0.889 | 0.959 | 87.899 | 88.157 | +0.258 | +0.308 | +0.178 | +0.00205 | +0.05% |
| Interstellar | 0.914 | 0.993 | 86.648 | 87.513 | +0.865 | +1.037 | +0.536 | +0.00405 | +0.05% |
| Scarface | 0.956 | 1.001 | 87.169 | 86.895 | -0.274 | -0.320 | -0.340 | -0.00067 | +0.18% |
| Taxi Driver | 0.874 | 0.956 | 82.492 | 81.696 | -0.796 | -0.895 | -0.551 | -0.00274 | +0.09% |
| The Deer Hunter | 0.835 | 0.902 | 78.395 | 78.067 | -0.328 | -0.395 | -0.284 | -0.00171 | +0.15% |
| The Shining | 0.892 | 0.942 | 86.035 | 86.056 | +0.021 | +0.040 | -0.259 | +0.00011 | +0.00% |
| **mean** | | | | | **-0.042** | **-0.038** | **-0.120** | **+0.0002** | |

Worse on 3/6 for VMAF and VMAF NEG, 4/6 for PSNR-Y.  The observed end-to-end
change has signed mean -0.042 VMAF, mean absolute change 0.424, RMS change
0.521, and a -0.796 .. +0.865 range.

The pure-MSE argument would predict a small consistent decrease if amplitude
were the only change.  Because it was not, neither PSNR-Y's -0.12 dB mean nor
the VMAF scatter can be assigned to grain correctness.  The honest reading is
that this run does not answer the intended question.

## The decomposition that answers the question

| what changed | VMAF effect | consistency |
| --- | ---: | --- |
| grain present vs absent | -2.2 to -6.3 | 6/6 |
| two non-isolated candidates whose mean amplitude is 0.893 -> 0.959 | -0.042 signed mean; 0.424 mean absolute | 3/6 |

The two rows use different setups (1080p crop/HD model versus 4K/4K model), and
the second row is not isolated.  Even as descriptive arithmetic, comparing the
2.2--6.3 presence effect with the 0.424 mean-absolute / 0.521 RMS candidate
change gives roughly 4--15x, not two orders of magnitude.  Only the first row
supports a causal finding: VMAF consistently penalises adding an independent
grain realisation.

The valid presence result is already enough to reject VMAF as the sole grain
objective: an optimiser can improve its score by removing independent grain.
This experiment does not quantify VMAF's sensitivity to amplitude correctness;
that requires the controlled replay below.

A plausible second-order trap remains unmeasured.  VMAF's VIF and ADM features
are multiscale, so they may penalise coarse grain differently from fine grain
at equal energy.  The 2026-07-17 HF 3.67 / acf@1 0.186 result establishes that
the old retention statistic preferred excess fine energy over the source's
coarser texture; it was not a controlled VMAF fine-versus-coarse experiment.
Do not state that VMAF prefers finer grain until that experiment exists.

## What the instinct gets right

Luma and chroma placement are genuinely optimisable and are *not* subject to
the position argument.  Grain in a sky that had none is a bias error: wrong to
the metric and wrong to the eye, in the same direction.  The per-luma band
closure work is the right treatment, and chroma at 0.891 mean amplitude is the
open case.  This is the one region where a metric and perception agree.

## Recommended use of FR metrics here

- **Not as an objective.**  The distributional targets already in place are
  correct: amplitude ratio to temporal truth, lag-1/lag-2 against source, and
  per-luma band closure.
- **As a guard rail** for failures grain statistics are blind to: banding,
  colour drift, blocking, and the separator damage in
  `FINDINGS-2026-08-02-MOTION-METRICS.md`.
- **For an honest FR number**, score the base against a *denoised source* using
  the same denoiser on both sides.  Grain cancels from both, and what is left
  is picture fidelity with no retention bias.  The ideal-clean machinery in
  `source_fit.py` already supports this.
- **Untested and worth one run:** CVVDP models visual masking, and grain masks
  itself perceptually.  It is available in FFVship and has never been run on
  this project.  It is the one metric that might respond to grain correctness
  rather than grain quantity.

## Required rerun

Use one grain-disabled base and synthesize two lossless outputs while holding
the following byte- or pixel-identical:

- decoded base pixels and frame timeline;
- AR coefficients and every non-luma-scaling parameter;
- per-frame normative seed;
- luma scaling-point locations, unless location is the variable explicitly
  being tested.

Change only the luma scaling values, verify those invariants automatically,
then score VMAF/VMAF NEG, PSNR, SSIM, SSIMULACRA2, Butteraugli and exploratory
CVVDP.  `metric_sensitivity.py` now refuses to score a pair that fails the
fixed-base/non-scaling-field checks; the historical arms fail by design.

## Artifacts

```text
/media/merged-storage/media/test-encodes/correctness-vmaf-20260802/
```

Pre-closure arm `sourcefit-corpus-20260801/<T>-motion_on.mkv`, post-closure arm
`sourcefit-leakclose-20260802/<T>-q29.mkv`.  The 0.00-0.18% size deltas match
the -0.02% .. +0.17% range recorded in `FINDINGS-2026-08-02-LEAK-CLOSURE.md`,
confirming the arms are the intended pair.
The size agreement does not establish metric isolation; that claim is
superseded by the decoded-base and side-data audit above.
