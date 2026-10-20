# Hypotheses and decisions

Starting clean master a246c353, coord pantheon-fix r8. User supplied the missing
practicality constraint; investigation resumes under original-rate hard cap.

| Hypothesis | Support | Contradiction / limit | Unknown | Next discriminator |
|---|---|---|---|---|
| Tested search/decision policy wastes texture-preserving bits | Fixed-decision unquantized inverses retain information; broader analysis changes allocation/quality | Lower quantization and4x preservation alone do not prove coding inefficiency; local allocation damages controls | Whole-picture preservation with a distinct search/decision policy at source rate | Inventory prior AV1 settings and independently design one untested contrast |
| More local precision alone solves source budget | Actual q20/q24 selected blocks preserve texture | Verified matched-source arms damage outside detail/face/tails; unselected E05 background fails | A more efficient decision stack or objective | Do not repeat the failed manual ROI strategy |
| Grain synthesis safely replaces the loss | Some prior E05 amplitude recovery | Same-input quiet/textured conflict on tested base; E04 structure not restored | Other legal models/bases with demonstrable representability | No new estimator without a distinct representability discriminator |

- user: Practical repair must be at or below original actual video rate.
- auto: Decisive source-matched calibration interval is99–100%; overshoot is not
  excused by the symmetric1% matching tolerance used in previous experiments.
- auto: Classify all >1x arms as preservation/cost diagnostics only. Their human
  playback is optional scientific evidence, not a blocker for1x machine work.
- auto: Reuse verified prior evidence and fresh scratch; do not rebuild archives.


## Round1: preset policy at the source budget

Primary question: does SVT preset0 improve coding efficiency enough to preserve
both E05 shirt/background at <=original rate without displaced control damage?
All prior SVT arms used preset4/tune0; allocation/filter variations did not test
this alternative search/decision bundle. Choose preset0 once rather than a
sequence of incremental preset trials. It is not exhaustive search (-1 exists).
Keep the same unmodified pinned SVT4.2 binary, one-pass VBR, tune0, lp1, FGS0,
denoise0, default GOP/lookahead/transform policy and exact336-frame10bit input.
Change only preset4→0 and TBR for calibration, aiming99.5% of source packets.
No ROI map, TX32 cap, coefficient retention or new synthesis is used.

Comparator: causal E05 B baseline, same unmodified binary SHA256
5bd538283d52958ffd1756400e4b7b49178bf7895c68904a4670f5ab3a5ba215,
request10053kbps, measured scored-MKV9.6763312Mbps. Reviewer initially cited
NVENC A-base9.648396 incorrectly; parent required correction to exact B artifacts.
Independent re-probe verified336 unique cadence-consistent packets and12,095,414
scored bytes. The IVF contains480 more packet bytes (2/frame), giving9.6767152;
use the established scored-MKV definition consistently and preserve both counts.
The baseline MKV is under source9.6765224 by191.2bps. No baseline rerun is needed
if new full input identity matches archived exact input; otherwise reconcile first.

Acceptance: actual MKV packets99–100% of source and pairwisewithin1%; exact
all336 app/dav1d/NVDEC planes; all240 scored planes match; same source/geometry/color;
unchanged midpoint HF±10% and ACF1<=.05 on both ROIs; source-HF correlation,
all240 temporal traces, frozen12,870tiles/15frames, quiet/edge/face controls,
full GPU campaign/tails/CAMBI and observed wall/runtime. Numeric pass is provisional;
material control regressions reject a repair. Human playback remains required
for any candidate that clears rate and numeric screens.

Interpretation: joint preservation supports a limitation in the preset4 policy
bundle; one-region gain with displaced damage is allocation tradeoff, not repair.
Failure rejects deeper preset0 under this objective only; it neither proves
precision-only causation nor a fundamental AV1/source-rate limit. Next experiment
must follow actual evidence, not another automatic preset sweep.

### Conditional next discriminator, not yet authorized as an encode

Independent pinned-source review found tune0→1 can retain VBR/random access,
unlike tunes2–5 which require CRF. However it changes a bundle: tune0 enables
noise-conditioned temporal-filter adjustment, single-reference mode bias,
interpolation smoothing bias, CDEF/restoration suppression and RDOQ sharpness
that tune1 disables (`Globals/enc_handle.c:3222–3247`), plus keyframe deblock
sharpness (`Codec/deblocking_filter.c:1113–1118`). It is not a pure distortion
formula contrast. Tune4 would additionally force quant matrices, sharpness7 and
variance boost, and its direct SSIM candidate selector is not enabled.

These source findings prevent an incorrectly labeled objective-only experiment.
They do not choose the next arm before Round1's outcome. A tune1 comparison would
test the tune0 policy bundle, not establish which noise heuristic caused a loss.
All source line references are to the archived pinned SVT4.2 tree; no production
source was edited.

### Ancillary reference observation during the slow encode

The original H264 coding state has not been measured in the prior QP comparison.
Parent will export it on the same E05 window to distinguish what quantization
was present in the original compressed representation from the cost of coding
its decoded output again. A read-only packet probe verifies a keyframe exactly
at1436s, the336-frame input start. `original_qp.py` copies that window into fresh
parent-owned scratch, requires all336 decoded planes to equal the existing
fixture, then reuses the validated complete-population H264 QP reader.
No encoder is altered and this copied stream is not a repair candidate.
H264 QP is comparable only within the same codec/bitdepth conventions; skipped
MB values remain decoder state, not proof of residual quantization execution.
This observation cannot by itself prove a coding-efficiency or generation-loss
mechanism, because prediction/transform/filter decisions are not held fixed.

### Rate eligibility correction before seeing quality results

The first preset0 run completed in2740.622s at9.5227592Mbps,98.4110% of source.
It meets the user's hard ceiling but misses the99–100% matched-comparison gate.
The first scorer incorrectly used that matching floor as a prerequisite for
any practical-candidate screen, contradicting this report's stated distinction.
Parent corrected this with an explicit `--under-cap-screen` mode, independently
reviewed before quality results. Default matched mode remains99–100%; the new
mode requires0<actual<=source and all other provenance/decoder/quality checks.
Every assessment/summary records practical and matched eligibility separately,
actual/source and actual/B ratios, and an explicit nonmatched label.

No texture, control, temporal or playback criterion changed. A pass below99%
could establish practical feasibility without preset-only attribution. A failure
rejects that actual arm; it does not establish the effect of preset at equal
rate. Decide calibration versus a different discriminator from the complete
quality result, especially whether the arm is near a screen boundary. Do not
automatically spend another45.7minutes on calibration before this cheap screen.

### Round1 result and decision

Exact all336 app/dav1d/NVDEC samples and all240 scored planes pass. Both midpoint
HF/ACF screens fail on amplitude: shirt0.15720 versus0.61935 source (−74.62%);
background0.92342 versus1.77849 (−48.08%). ACF errors .00103/.04483 pass.
Source correlation, face errors, outside-tile MSE, VMAF/NEG, SSIMULACRA2/tails,
Butteraugli and CAMBI improve descriptively against preset4, despite the
1.5871% lower packet rate. Quiet HF error .08861→.09925 and quiet MSE p95
1.15775→1.20908 worsen; edge HF error is slightly worse. All240 traces corroborate
the amplitude deficit. Parent inspected native stills; no playback occurred.

Independent review accepts the failed practical arm and recommends a distinct
implementation over rate calibration. Parent agrees: these misses are far from
the screen boundary. This is an experiment-selection judgment, **not proof**
that another1.589% source-rate budget cannot matter. The99–100% matched preset
effect is left unresolved; no failed configuration is declared impossible.

### Round2: independent AV1 decision stack

Primary question: can the installed libaom implementation preserve the E05
texture at or below source rate? Exact input and scoring/control gates remain.
One proposed unmodified two-pass arm uses system FFmpeg6.1.1/libaom3.8.2,
10-bit input/coding, good usage, cpu-used4, four threads/row-MT/one tile, SSIM
tune, variance AQ, denoise-noise-level0, alt-ref1, ARNR-strength0, lag25 and
GOP161. ARNR0 is a requested control, not proof that all temporal preprocessing
is absent. No app reconstruction is exposed; require all336 dav1d/native-libaom/
NVDEC samples to agree instead. Actual MKV packets determine rate; aim99.5%.

This is a distinct implementation/objective/allocation/reference/filter bundle,
not an isolated objective or precision ablation. Ten-bit coding is shared with
the SVT path, not a changed confound. A pass supports practical representability
by this stack; a failure rejects only the tested configuration. Worker owns the
new encoder runner and fresh aom run directories; parent owns scoring and Git;
reviewer remains independent. No production or recursive delegation.

- auto: Round2 first run uses8.319776Mbps,85.979% of source,391.026s total.
  Before any quality interpretation, calibrate requested TBR10003→11576 using
  observed packet response to aim99.5%. All settings/input stay fixed and the
  next run has a fresh tag. This resolves large budget underuse, not a quality
  failure. Prior run receipts remain intact.

### Companion fixed-input grain discriminator

Reviewer exploratory read-only calculations suggest preset0 E05-1440 changes
legal-grain input equivalence relative to the old base. Treat stdout numbers as
unverified until parent codifies and preserves the complete selection. Reuse the
frozen causal held-out tiles and original representability selection: quiet versus
flat_texture sourceHF>.4 with baseHF<half source, same frame, base mean distance
<=.5 and exact10bit histogram overlap>=.5. Keep every pair; choose highest overlap
with deterministic coordinate tie break. Within it choose the shared constant3x3
code maximizing the smaller region count, excluding prior2-pixel overlap bands.
Do not select a code for its source amplitude and do not add a minimum-count gate.

Probe only the existing legal white-AR scale16 model and32 fixed seeds, with
native preserved dav1d grain tool on unchanged preset0 IVF. Verify native base
pixels equal the app/dav1d/NVDEC-validated frame, source/selector hashes, exact
masks/counts and base nonmutation. Preserve per-seed conditional output and
isolated-grain HF, full-tile ACF, clipping occupancy, crops and complete selector.
Same-input amplitude differences are a local representability diagnostic, not a
repair or exhaustive AR/scale/seed search. A material position-dependent response
or simultaneous interval satisfaction would weaken/falsify this specific conflict.
A conflict on this new base does not transfer to untested bases or whole-shot
models. CPU work is bounded to8–11 while encoding occupies0–7; no GPU involved.

Companion result: three pairs, selected frame24/code192 (raw10bit,8bit48),
64quiet/37texture pixels. Native base matches all planes;32 nonmutation checks
pass. White16 ensemble conditional HF means .35627/.34820 against source
.09081/.24429; neither region has an interval hit in32seeds. Selected endpoint
occupancy is zero. Independent review validates masks, selection and provenance.
It emphasizes that scale16 overshoots even texture, so zero joint hits alone is
weak evidence; same-input response coupling is the useful observation. Do not
call the frozen flat_texture class proven stochastic grain, or infer exhaustive
legal-model failure. [Bounded result](GRAIN_FIXED_INPUT.md) preserves the limits.
