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
| `temporal_drag.py` | joint previous/next projection of base error; their asymmetry detects directional temporal lag while rejecting the labelled symmetric spatial-blur control | asymmetric exposure/state lag, an unmatched timeline, or treating the coefficient as visibility or a literal vector-failure rate |
| Butteraugli max p95 (FFVship) | localized artifacts the pooled metrics average away | absolute value is content-dependent; use the cross-arm gap |
| detail decile: corr / HF kept / RMSE vs source | misplaced vs missing detail (high corr + high RMSE = displacement) | any one of the three alone; they must be read together |
| base vs *denoised source*, same denoiser both sides | picture fidelity with grain cancelled from both sides | denoiser must be identical on both sides or it measures itself |

**Do not use** base-vs-source VMAF/SSIMU2/PSNR to rank separators.  Measured
2026-08-02: the plain encode wins every FR metric on every title while being up
to 2.2x the largest file, so the FR ranking is the exact inverse of the
compression ranking.

Reference values, `FINDINGS-2026-08-02-TEMPORAL-CALIBRATION.md`: bilateral
lag asymmetry 0.00010-0.00036 and motion 0.118-0.141 across three film bases;
the separation survives grain synthesis.  Butteraugli max p95 is 11.18-11.22
for bilateral and 35.3-52.3 for motion.

## Stage 2 -- grain model fidelity (is the signalled grain right?)

| instrument | answers | invalidated by |
| --- | --- | --- |
| `temporal_grain_report.py` | amplitude vs temporal truth, lag-1, lag-2, per luma band, per plane | needs static flat blocks selected from stored native-plane codes and applied unchanged to every arm; reports before `50da8a40` used a gray-converted luma population and are not analyzer-exact |
| `source_fit.py` | offline oracle: what the AR fit should be, with an ideal-clean control | simulation clipping if `--sim-sigma` is left at a saturating value |
| `ar_acf.py` / `cap_table_acf.py` | coefficient-implied autocorrelation of an emitted table | saturating simulation/clipping or too few simulation seeds; the table seed is intentionally irrelevant to this coefficient statistic |
| `amplitude_matched_texture.py` | metric response to fine versus coarse grain with base, seed, luma placement and delivered energy controlled | a single static model does not reproduce rolling per-luma delivery or decide perceptual quality |
| `sourcefit_admission_report.py` | per-table-entry temporal texture evidence, AV1 model fidelity, luma-band coverage and confidence as separate axes | it intentionally emits no routing verdict; a scalar or post-hoc corpus threshold overfits |
| `sourcefit_admission_compare.py` | source-fit versus residual-fit model error after independent film-like evidence is measured | a better source fit is not admission: it wins on all 16 current titles, including every labelled negative |
| `correlation_target_report.py` | shipping all-block correlation, static-block alternatives and temporal grain truth, including fixed luma bands | pooling contaminated blocks by energy is worse than the median; estimator changes require real-film temporal controls |
| temporal-static source AR prototype | whether excluding moving/structured flat blocks improves the emitted source model on real film | the luma-derived subset is not a chroma selector; applying it to U/V tripled six-film V texture error |
| `strength_selection_report.py` + `amplitude_estimator_gate.py` | whether pre/post-encode leak supports a title-independent per-plane transfer across QVBR | predicts the requested target, not the response of the rolling, smoothed, reduced and quantised AV1 curve; it cannot clear an encoder change without the stage-3 replay |

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
That shared mask is valid for comparing played output on fixed picture regions;
it is not evidence that the same subset should train each plane's AR model.
`FINDINGS-2026-08-04-TEMPORAL-SOURCE-OBSERVATIONS.md` measures that distinction:
the temporal subset halves luma texture error but must leave U/V on the full
spatial-flat population.

## Stage 3 -- delivery (does the signalled grain reach the screen?)

| instrument | answers | invalidated by |
| --- | --- | --- |
| `emission_audit.py` | exact normative synthesis vs dav1d, pixel for pixel | using the table's seed: NVENC picks its own, 0 of 42 matched |
| `chroma_emission_audit.py` | exact U/V source, base, target, synthesis and played amplitude per source-luma band | sparse frame pairs can miss table intervals; ratio is undefined at a zero target and misleading near zero energy |
| `chroma_amplitude_compare.py` | control/candidate chroma closure across titles and bands, with ratio and absolute 8-bit sigma error side by side | input reports must use the same frame set, block selector and aggregation; any table/stream or dav1d mismatch invalidates the comparison |
| `delivery_response.py` | whether an analyzer-feasible response summary can replace the exact per-luma oracle | counts/means/histograms lose the spatial clipping term near black; Taxi remains the labelled failure |
| played-total closure | `sqrt(post_base_var + synth_var)` against source truth | needs a grain-disabled *and* grain-enabled decode of the same stream |
| rectification counter | how often `fmax(0, V_source - V_base)` clamps and drags a bin mean down | populations differ between spatial and temporal paths; treat as an upper proxy |

A grain-applying decoder is mandatory.  Use dav1d explicitly
(`-c:v libdav1d`, `-filmgrain 0|1`).  NVDEC is not an integrity validator: on
the known corruption class it reported zero errors where dav1d reported 502.
Even if NVDEC is compared for playback pixels on a known-good stream, it must
never replace dav1d for delivery or safety gates.

Do not make an amplitude shipping decision from the historical six/seven frame
pairs. On 2026-08-04 a 7-pair chroma replay suggested a modest band improvement;
the same six-film A/B over 23 pairs rejected both U and V. Sparse pairs remain
diagnostic. Ratios must also be accompanied by absolute sigma in 8-bit code
values: a nearly grain-free V band produced a 37x ratio error while its absolute
error remained small.

The current delivery-response implementation gate is closed **negative**:
20-bin occupancy predicts 23/26 real-film bands within 5%, but misses Taxi's
darkest band by 27.7%.  A clean-block mean and a full luma histogram still leave
post-correction target errors of -0.070 and -0.060.  Do not turn the exact
multi-seed oracle into an analyzer normalizer; see
`FINDINGS-2026-08-02-DELIVERY-RESPONSE.md`.

## Stage 4 -- compression

Bytes against a **plain encode at the same QVBR**, whole corpus, never a single
title.  Call this same-QVBR, not matched-rate: its purpose is the production
operating-point comparison and the files intentionally differ in size.  Add a
separate matched-bitrate sweep when answering rate-quality questions.  The
plain control is also what exposes metric bias in stages 1 and 2, so it is not
optional.

When a model option unexpectedly changes bytes, use
`sourcefit_transfer_isolation.py`: it encodes the full clean-base x grain-table
factorial and runs complete dav1d validation. This distinguishes changed base
complexity from table/encoder interaction. On Silo it localized the entire
+26.3% source-fit movement to the base, then same-arm repeats and debug traces
identified the original-frame safety fallback after persistent model rejection.

## Stage 5 -- safety and invariance (gates, not diagnostics)

- `fgs_kat.py`: all fixtures, with the flag on **and** off;
- `modelsrc=off` produces a byte-identical table and elementary-stream MD5 to
  the pre-change encoder;
- every paired measurement has the expected frame count, dimensions and
  relative PTS timeline; decoders must exit successfully rather than silently
  truncating at the shorter input;
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
*presence* is -2.2 to -6.3 points on 6 of 6 same-stream pairs.  The attempted
historical amplitude comparison was not isolated and remains withdrawn.  Its
fixed-base/fixed-AR replacement changes only luma scaling values in opposite
directions on two films: VMAF-family means reward less grain in both cases,
even though both candidates move toward their physical target.  Butteraugli is
effectively flat and HDR CVVDP gets slightly worse for both corrections.  None
is a grain-correctness objective.  The fixed-base/fixed-seed replay now closes
the remaining scale question (`FINDINGS-2026-08-03-AMPLITUDE-MATCHED-TEXTURE.md`):
at matched luma energy, coarse source-fit grain loses `0.80--0.84` VMAF at a
production-like amplitude and `1.36--1.48` at a candidate-like amplitude,
while PSNR is essentially flat. VIF/ADM therefore do prefer finer grain at
fixed energy. That is a measured metric bias, not a perceptual ranking.

## The one thing none of the above replaces

A blinded playback A/B.  Every instrument here is statistical; none of them
knows what masking does.  The current set is
`FINDINGS-2026-08-02-MOTION-REVIEW.md`.

## Minimum bar for a shipping candidate

1. stage 5 gates all green;
2. stage 1: the calibrated previous/next temporal statistic and Butteraugli max
   p95 are within reach of the bilateral reference values on the whole corpus;
3. stage 2: amplitude and lag-1/lag-2 close on **both** planes, per luma band,
   not just whole-title;
4. stage 3: emission exact, played total closed, rectification accounted for;
5. stage 4: corpus saving against plain at the production same-QVBR operating
   point, plus a matched-bitrate sweep before making rate-quality claims;
6. guard rails show no new banding or colour drift;
7. the blinded review passes.
8. a general-content gate compares plain, production FGS and the candidate on
   genuinely clean, low-grain digital, animation and hard-edged studio/reality
   material, including the labelled Drag Race and Stormester failures. The
   synthetic `clean` KAT proves zero-grain signalling suppression; it does not
   prove that a separator will leave real clean-looking texture and sharpening
   untouched.

   The first gate is complete and **failed universal promotion**; see
   `FINDINGS-2026-08-03-GENERAL-SOURCEFIT-GATE.md`. Fine/coarse held-out film
   positives and two held-out animation negatives now support the independent
   admission axes, while the source/residual counterfactual proves model-fit
   improvement cannot itself admit content; see
   `FINDINGS-2026-08-04-SOURCEFIT-ADMISSION.md`. Do not convert this still-small
   corpus into fixed routing thresholds.

Whole-title aggregates hide opposite per-title and per-band errors -- this has
already happened twice (the global delivery multiplier, and the luma-occupancy
trap it repeated).  Always decompose before believing a mean.
