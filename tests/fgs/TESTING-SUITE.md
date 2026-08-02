# The FGS test suite: what to run together, and what each thing can prove

No single measurement can rank an FGS encode.  The pipeline has five stages
that fail independently, and the metrics that see one stage are actively
misleading about another.  This is the standing list of what to run, what each
instrument answers, and what invalidates it.

Rule of thumb: **every stage needs an instrument that is not confounded by the
stage before it.**

## Stage 1 -- separator damage (is the picture intact?)

The base is what the viewer actually sees under the grain.  Grain removal and
picture damage look identical to any whole-frame quality metric, so this stage
must not be judged by VMAF or SSIMU2 against the source.

| instrument | answers | invalidated by |
| --- | --- | --- |
| `temporal_drag.py` | ghosting/disocclusion: fraction of frame n-1 bled into the base | nothing known; box-size sweep is the built-in control |
| Butteraugli max p95 (FFVship) | localized artifacts the pooled metrics average away | absolute value is content-dependent; use the cross-arm gap |
| detail decile: corr / HF kept / RMSE vs source | misplaced vs missing detail (high corr + high RMSE = displacement) | any one of the three alone; they must be read together |
| base vs *denoised source*, same denoiser both sides | picture fidelity with grain cancelled from both sides | denoiser must be identical on both sides or it measures itself |

**Do not use** base-vs-source VMAF/SSIMU2/PSNR to rank separators.  Measured
2026-08-02: the plain encode wins every FR metric on every title while being up
to 2.2x the largest file, so the FR ranking is the exact inverse of the
compression ranking.

Reference values, `FINDINGS-2026-08-02-MOTION-METRICS.md`: bilateral drag beta
0.002-0.025 and Butteraugli max p95 11.18-11.22 across three films; motion
0.141-0.169 and 35.3-52.3.

## Stage 2 -- grain model fidelity (is the signalled grain right?)

| instrument | answers | invalidated by |
| --- | --- | --- |
| `temporal_grain_report.py` | amplitude vs temporal truth, lag-1, lag-2, per luma band, per plane | needs static flat blocks selected from the *source* and applied unchanged to every arm |
| `source_fit.py` | offline oracle: what the AR fit should be, with an ideal-clean control | simulation clipping if `--sim-sigma` is left at a saturating value |
| `ar_acf.py` / `cap_table_acf.py` | implied autocorrelation of an emitted table | table seed is not the bitstream seed -- see stage 3 |

Amplitude and texture must be reported **separately**.  HF sigma alone cannot
tell correct grain from correctly-sized grain: 2026-07-17 measured HF 3.67
against a 3.13 source (looked like a win) while acf@1 was 0.186 against 0.367
-- right energy, half the grain size.

`flat_retention.py` is **known-confounded** for this purpose: it high-passes,
and coarse grain carries less energy above the cutoff than fine grain of the
same total sigma, which is exactly the variable under test.  Use total
detrended flat-block sigma instead.

Chroma is measured by the same tool with the luma-derived mask mapped to 4:2:0
blocks, so both planes select the same picture content.  Chroma currently sits
at 0.891 mean amplitude against luma's 0.959 and is the open modelling gap.

## Stage 3 -- delivery (does the signalled grain reach the screen?)

| instrument | answers | invalidated by |
| --- | --- | --- |
| `emission_audit.py` | exact normative synthesis vs dav1d, pixel for pixel | using the table's seed: NVENC picks its own, 0 of 42 matched |
| played-total closure | `sqrt(post_base_var + synth_var)` against source truth | needs a grain-disabled *and* grain-enabled decode of the same stream |
| rectification counter | how often `fmax(0, V_source - V_base)` clamps and drags a bin mean down | populations differ between spatial and temporal paths; treat as an upper proxy |

A grain-applying decoder is mandatory: dav1d (`-c:v libdav1d`, `-filmgrain 0|1`)
or NVDEC, validated bit-exact against each other.

## Stage 4 -- compression

Bytes against a **plain encode at the same QVBR**, whole corpus, never a single
title.  The plain control is also what exposes metric bias in stages 1 and 2,
so it is not optional.

## Stage 5 -- safety and invariance (gates, not diagnostics)

- `fgs_kat.py`: all fixtures, with the flag on **and** off;
- `modelsrc=off` produces a byte-identical table and elementary-stream MD5 to
  the pre-change encoder;
- complete `libdav1d -xerror` decode of every candidate stream;
- the CPU test suite;
- the labelled-negative fixture is still rejected and the shipping model still
  accepted.

These say a candidate is safe to keep testing.  They never say it is shippable.

## Guard rails -- run them, don't optimise them

VMAF / VMAF NEG / PSNR / SSIM / CIEDE2000 (all CUDA paths, `--gpumask 0`),
SSIMULACRA2, and CAMBI for banding.  These catch failures the grain statistics
are structurally blind to: banding in the denoised base, colour drift, blocking,
and gross regressions.

They must not be the objective.  Measured 2026-08-02
(`FINDINGS-2026-08-02-METRIC-SENSITIVITY.md`): VMAF's response to grain
*presence* is 2.2-6.3 points on 6 of 6 pairs, while its response to a 0.893 ->
0.959 amplitude *correctness* improvement is -0.04 mean with +/-0.9 scatter and
no consistent sign.  The metric cannot see the thing being optimised, and its
multiscale VIF/ADM features additionally prefer grain finer than the source.

## The one thing none of the above replaces

A blinded playback A/B.  Every instrument here is statistical; none of them
knows what masking does.  The current set is
`FINDINGS-2026-08-02-MOTION-REVIEW.md`.

## Minimum bar for a shipping candidate

1. stage 5 gates all green;
2. stage 1: drag beta and Butteraugli max p95 within reach of the bilateral
   reference values, on the whole corpus;
3. stage 2: amplitude and lag-1/lag-2 close on **both** planes, per luma band,
   not just whole-title;
4. stage 3: emission exact, played total closed, rectification accounted for;
5. stage 4: corpus saving against plain at matched rate;
6. guard rails show no new banding or colour drift;
7. the blinded review passes.

Whole-title aggregates hide opposite per-title and per-band errors -- this has
already happened twice (the global delivery multiplier, and the luma-occupancy
trap it repeated).  Always decompose before believing a mean.
