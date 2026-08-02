# What full-reference metrics can and cannot see about grain, 2026-08-02

Prompted by a design question: if synthesised grain had the right colour, luma
placement, size and position, would VMAF stop punishing it -- and could VMAF
then be used as the optimisation target?

The answer is measured here rather than argued.  It splits into two questions
that behave completely differently.

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

## Metrics do not see grain *correctness* at all

The sharper test.  Two candidates differ in exactly one thing, leak closure:
same rate, same separator, same selector, same AR coefficients, only the luma
strength curve moves.  Mean synthesis amplitude against source truth goes from
0.893 to 0.959, and corpus bias against the true post-encode target from
-0.069 to -0.004.  This is the largest single fidelity gain of the last two
days.

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

Worse on 3/6 for VMAF and VMAF NEG, 4/6 for PSNR-Y.  **Mean change -0.042 VMAF
with +/-0.9 scatter and no consistent sign.**

The pure-MSE argument predicts a small consistent *decrease* here, since the
only change is more synthetic grain on the picture.  PSNR-Y is directionally
consistent with that (-0.12 dB mean, 4/6 worse) but the effect is far below the
scatter.  The honest reading is not that correct grain scores better or worse.
**It is that the metric cannot see the difference.**

## The decomposition that answers the question

| what changed | VMAF effect | consistency |
| --- | ---: | --- |
| grain present vs absent | -2.2 to -6.3 | 6/6 |
| grain amplitude 0.893 -> 0.959 toward truth | -0.04 mean, +/-0.9 | 3/6 |

The two rows use different setups (1080p crop/HD model versus 4K/4K model), so
this is an order-of-magnitude comparison, not an exact ratio.  It is enough:
VMAF's response to grain *presence* is roughly two orders of magnitude larger
than its response to grain *correctness*, and only the presence term has a
consistent sign.

So a VMAF-driven optimiser does not converge on well-formed grain.  The
correctness signal it would need is buried in its own noise, while the presence
signal dominates every gradient.  It converges on less grain, and at the limit
on no grain.

There is a second-order trap in the same direction.  VMAF's VIF and ADM
features are multiscale, so grain in coarse subbands -- where picture structure
lives -- is penalised harder than fine grain of the same energy.  At fixed
grain energy the metric therefore prefers grain *finer* than the source.  That
is the 2026-07-17 failure exactly: HF 3.67 against a 3.13 source looked like a
win while acf@1 read 0.186 against the source's 0.367.

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

## Artifacts

```text
/media/merged-storage/media/test-encodes/correctness-vmaf-20260802/
```

Pre-closure arm `sourcefit-corpus-20260801/<T>-motion_on.mkv`, post-closure arm
`sourcefit-leakclose-20260802/<T>-q29.mkv`.  The 0.00-0.18% size deltas match
the -0.02% .. +0.17% range recorded in `FINDINGS-2026-08-02-LEAK-CLOSURE.md`,
confirming the arms are the intended pair.
