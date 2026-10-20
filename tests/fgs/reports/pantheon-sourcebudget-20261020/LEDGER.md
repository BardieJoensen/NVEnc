# Hypotheses and decisions

Starting clean master a246c353, coord pantheon-fix r8. User supplied the missing
practicality constraint; investigation resumes under original-rate hard cap.

| Hypothesis | Supporting evidence | Contradiction / limit | Still unknown | Cheapest next discriminator |
|---|---|---|---|---|
| Material source preprocessing causes libaom texture loss | Byte-neutral trace finds 32 sparsely changed coded events, max two 10-bit levels | Prescribed midpoint input is exactly unchanged; most events are identical | Indirect sensitivity through reference or coding decisions | Round5 all-event coding-source sample neutralization, preserving preprocessing analysis |
| SSIM's extra variance weighting causes the severe loss | It changes block rate prices; removing it improves face/edges | Matched PSNR still loses 84%/49% of shirt/background HF and fails ACF | Interactions with other policies | Direct removal failed; do not repeat this contrast |
| More local quantization precision solves the original-rate budget | Fixed-decision inverses retain information; verified lower quantization and 4x coding preserve target texture | Matched-budget precision arms damage other regions; broader controls remain necessary | A policy that preserves texture without displaced damage | Resolve source-boundary uncertainty before another allocation policy |
| A slower or independent decision stack suffices | Preset0 and libaom improve several broad controls | Tested preset0, SSIM and PSNR arms all fail texture; preset0 was under-cap, not matched | Untested search/allocation strategies and interactions | Use measured mechanism to choose the next arm, not a settings sweep |
| Legal grain safely replaces lost texture | Some E05 amplitude recovery; decoded bases can improve | Tested same-input quiet/texture conflict and E04 structure failure | Other legal models/bases with demonstrated representability | No estimator until a distinct representability discriminator is justified |

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

Round2 result: calibrated9.6243504Mbps (99.4608%source),389.179s. All3decoder
and scored-sample checks pass. Shirt/background HF deficits84.37%/50.81% and
ACF errors .10866/.12137 fail. Broad tile controls, SSIMULACRA2 mean, Butteraugli
and CAMBI improve versus SVT-B, but face MSE/gradient error and VMAF/NEG regress.
Independent review accepts this actual failed policy and rejects global superiority.
No motion playback. See RESULTS.md and aom-result.json for full scope/evidence.

Round3 primary question: is libaom's SSIM tune policy responsible for the remaining
texture suppression relative to its PSNR tune policy at the same source budget?
Change only public tune=ssim→psnr and TBR calibration; retain exact input, binary,
two-pass good/cpu-used4, variance AQ, worker/GOP/reference/ARNR/color settings.
Require source99–100% and pairwise1%, all existing gates and direct pairing with
aom-1x1 for controls, traces and tails. This is an encoder decision-policy
contrast, not a fixed-predictor scalar-distortion or pure-quantizer ablation.
No model fit or threshold change. A persistent severe deficit rejects this
specific SSIM-policy explanation, not other encoder strategies or AV1.

Round3 source audit sharpens the hypothesis before results: libaom3.8.2's tune
switch does not change the default in-block PSNR distortion metric. SSIM adds
source-variance-derived, geometrically normalized block RDMULT factors after
variance-AQ/delta-Q setup; PSNR omits that additional weighting. The audited direct
PSNR/SSIM branches do not switch filter/reference/ARNR tools. Downstream decisions
can still change. Thus test the extra source-variance rate-price weighting, not
“SSIM versus PSNR distortion.” Pinned upstream source and installed Ubuntu patch
scope are preserved. Exact first-pass statistics equality is now required; no
firstpass tune branch exists. Compare actual rates, not identical requested TBR.

- auto: First PSNR arm atrequest11576 completed391.557s, actual9.5041536Mbps,
  98.22% of source and98.75% of matched SSIM. Before any quality inspection,
  calibrate only TBR to11727 (observed response,99.5% aim). Preserve the first
  arm. Unlike the earlier practical preset0 screen, this round's primary policy
  contrast specifically requires matched rates, so calibration is necessary.

- auto: Request11727 yielded9.7005904Mbps,100.249% of source. Reject before
  quality inspection; do not excuse the overshoot with the1% matching tolerance.
  Interpolate the observed11576/11727 bracket to request11671, targeting99.5%.
  This run yielded9.639088Mbps,99.613% of source and100.153% of SSIM.
  Both rate gates pass. All three PSNR runs have identical pass1 statistics
  and unchanged input hashes; only the matched final run receives quality scoring.


Round3 result: all identity and rate gates pass. At 9.639088 Mbps, PSNR removes
SSIM's additional variance weighting but leaves shirt/background amplitude
errors −84.080%/−48.869% and ACF errors 0.113094/0.106166. Face/edges improve;
quiet and flat-texture controls regress, and 54.5% of tiles worsen in MSE.
Independent review accepts the failed policy and the mixed full-reference/tail/
banding results. Parent inspected the native shirt still and full traces.
No playback was observed. This weakens the extra-SSIM-weighting explanation for
the severe suppression under these controls; it does not isolate quantization
or exclude other policies and interactions.

Next question selected: whether the coding source itself differs materially
from original input before prediction/quantization. Requested ARNR strength zero
is insufficient proof either way: the filter path is reachable, but its integer
weights can round the change away. Trace actual samples before another settings
trial. The private build must preserve output before its evidence is admitted.


## Round4 contract: original samples versus coding-source samples

Hypothesis: material temporal preprocessing suppresses texture before libaom
performs coding decisions, despite ARNR strength zero. Supporting evidence is
only source-path reachability; integer weight truncation may make that path
pixel-identical. Round3's similar severe deficit under both tune policies leaves
this distinct mechanism unresolved. The cheapest decisive observation is an
all-plane sample trace at the coding-source boundary, not another settings arm.

Worker owns `worker/aom-source-trace-preflight/`: fresh copies of pinned upstream
and Ubuntu patches, bounded four-job private builds, instrumentation patch,
commands/toolchain/config manifests and later isolated runs. No install or edits
to production, prior archives or the reviewer's audited source. Reviewer owns
`reviewer/round4-coverage/` and independently parses actual AV1 frame headers.
Parent owns contract, integration, analysis and the Git index. No recursion.

Hook immediately before the SSIM scaling branch in `encoder.c`, after early
show-existing and dropped-frame returns. Compare visible cropped Y/U/V samples
of `cpi->source` and `cpi->unfiltered_source`, with raw little-endian 10-bit
whole-frame and per-plane MD5, unequal-sample counts and maximum deltas. Bind
unfiltered hashes to the 336 unique validated original frame hashes. Record
geometry/bit depth, source-pointer equality and frame/update/GF/order/parallel
metadata. Use stack-local state and one bounded atomic write to an inherited
append descriptor; no shared counters, encoder-state changes or silent I/O loss.

Before full encodes, review patch/build manifests. Then require exact elementary
stream equality between private pristine and traced builds on the frozen PSNR
pass2 command/stats. Compare the private pristine stream with the installed
admitted output; if unequal, trace findings apply only to the private build until
resolved. Record source and stats before/after, actual loaded library and complete
commands. Instrumented runtime is diagnostic overhead, not candidate speed.

Independent bitstream coverage already shows 490 frame headers in 336 packets:
363 coded frames (154 hidden, 209 shown) and 127 show-existing headers. Require
exact coded-event multiset equality using source index, frame type/show/showable,
order hint and refresh flags after documented implicit-header normalization.
The source-index map uses exact input hashes; displayed packet count is not
an instrumentation completeness check. Parallel emission order may differ.

An identity trace rejects material source preprocessing on the observed path.
A nonidentity trace localizes changes but does not alone prove harmful texture
loss or that disabling preprocessing repairs the window. Inspect changed samples
and quantify amplitude/structure before choosing an intervention. Every candidate
still faces the original packet-rate ceiling and unchanged quality gates.


Round4 result: admitted installed/pristine/traced IVF identity; all 336 original
whole/plane bindings and all 363 independent coded-event keys pass. There are
32 changed events, 26 hidden and six shown keyframes, with maximum delta two
10-bit levels. Across coded-event samples, changed Y/U/V fractions are 0.01019% /
0.01850% / 0.01765%. Input 216 (scored midpoint 120) and input 120 are exactly
unchanged. Direct preprocessing loss at the prescribed midpoint is excluded.
Do not infer all TF-related decisions are inert: altered references and earlier
analysis remain possible pathways. Independent outcome review accepts this scope.

- auto: Select one all-event source-sample neutralization next. Keep the actual
  preprocessing calculations but hand original samples to coding; no ROI-selected
  patch or sample-outcome-dependent selection. This is cheaper and more causal
  than another settings switch or deeper coefficient export. A byte-identical
  result ends this measured-sample mechanism without rescoring. If bytes change,
  validate achieved input replacement and actual packet rate before quality work.
  Worker coefficient-path inventory is preserved as a conditional later tool,
  not an automatically authorized optimization sweep.
