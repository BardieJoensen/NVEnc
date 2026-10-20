# Hypotheses and decisions

- auto2026-10-20R8: independent source review establishes a distinct existing
  texture-sensitive policy reaching coefficient optimization, actual residual
  zero/skip costs and full mode decisions. Freeze the bundle in
  `ROUND8_POLICY_CONTRACT.md`; requested bitrate alone may calibrate.
- auto2026-10-20R8: use bounded per-picture/stage observational counters and
  byte-identical streams to prove runtime delivery. Invocation counts are not
  final pixel ownership. Do not build unnecessary raw pixel traces.
- auto2026-10-20R8: correct documented defaults from source (psy1/noise norm1)
  and private build options from CMake. Independent review accepted the corrected
  runner; unmodified build completed12:51:58UTC without source changes.

Starting clean master a246c353, coord pantheon-fix r8. User supplied the missing
practicality constraint; investigation resumes under original-rate hard cap.

| Hypothesis | Supporting evidence | Contradiction / limit | Still unknown | Cheapest next discriminator |
|---|---|---|---|---|
| Coding-source sample changes cause the severe libaom loss |32 events differ sparsely; removing changes alters stream/reconstruction |Admitted all-original coding inputs still lose84.2%/48.5% midpoint HF at99.47% source rate |Retained analysis and downstream coding/quantization mechanisms |Round6 fixed-TU scalar-quantization versus optimizer/skip observation |
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


### Round5: coding-source pixel neutralization

Primary question: do the measured sparse source-sample changes indirectly cause
material texture loss through reference/coding feedback? Preserve filtering,
GF/TPL/show-existing analysis, public PSNR policy and installed first-pass stats.
Immediately before `av1_encode`, pass a stack copy of `EncodeFrameInput`; the
on arm substitutes the saved original source pointer. No sample-buffer writes.
The same binary's off arm retains selected source, and must exactly reproduce
the admitted installed IVF. Both arms trace selected and effective samples.

Pre-hook order/refresh fields are not yet current. Pair the two stages by unique
(original whole MD5, GF index, update type, parallel level), requiring a dynamic
bijection. Only effective records match the independently parsed bitstream
header population. All336 original frames and every coded event must bind;
all on-arm effective planes must be exact originals, and pre-selected changes
must show a nontrivial intervention. A changed population is allowed and must
be derived afresh. Invalid pairing or bypass coverage stops interpretation.

Fresh tree/build is worker-owned `worker/aom-neutralize-r5b`; parent owns the C
patch, replay and validator; reviewer independently audits implementation,
coverage and outcome. R4 sources/receipts stay immutable. Build/encodes are
bounded to nice10 CPU0–7/four threads, with serialized GPU scoring if needed.
Worker initially omitted two required CMake options; parent required correction
before building. No production changes or recursive delegation are authorized.

First compare exact IVF at unchanged request11671. If identical, reuse quality
and close this sample route for this policy. If changed, enforce actual MKV
source99–100% and pairwise1% before decisive quality comparison; calibrate only
rate if necessary. All frozen texture/control/playback gates remain unchanged.
This is a source-pixel contrast with downstream decision feedback, not fixed
prediction/partition, not all temporal filtering disabled, and not yet a repair.


Round5 preparation correction: first configure failed before compilation because
the prior source-domain manifest excluded upstream `build/cmake` files along
with generated build output. The archive contains1344 regular files; the1294
subset omitted44 build-support files and6 README files. Preserve failed r5;
reconstruct r5b from all archive member paths with no name-based exclusions,
apply the same7 Ubuntu patches and unchanged reviewed intervention. Independent
review audits the50 omitted files against R4 trees. This fixes provenance and
reproduction completeness; it does not alter the measured R4 bitstream evidence.


Round5 result: admitted all-original effective samples for all363 coded events,
selected-stage records unchanged from off; dynamic headers and all336/240 decoder
identities pass. Changed bitstream at9.6256032Mbps (99.4738%source,99.8601%parent).
Midpoint shirt/background HF deficits84.21%/48.54%, ACF errors.07442/.09889 fail.
Full-window controls are mixed; quiet/face improve slightly, overall MSE/tails and
CAMBI worsen. Instrumented replay pass2 costs373.697s; no full-pass runtime claim.
No playback. This rejects measured sample neutralization as a repair for this
policy; it neither makes sparse source changes inert nor excludes retained
analysis influence. Parent inspected the decisive trace and native shirt still.

Next selected question: at fixed final TU/predictor/partition choices, how much
texture is lost in initial scalar quantization versus later coefficient
optimization or skip decisions? Start with observation and scratch inverse
reconstruction only, proving disabled instrumentation bitstream identity. Do not
use public no-trellis as a pure pruning test: it also changes FP→B scalar quant.
`OUTPUT_ENABLED` alone may still include frame-recode attempts; final-bitstream
attempt selection must be audited before implementation. Mark skipped blocks
whose quantization never executes; never read their stale coefficient buffers
as observed quantization. The next contract must settle these coverage issues.


Round6 contract is fixed in AOM_COEFFICIENT_CONTRACT.md. Independent byte-framing
and reference-history binding resolves input216 to the fourth coded OBU in
packet215 (28408B), then show-existing slot7 at display216. The extracted source
frame120 exactly matches input216 whole/per-plane hashes; postloopY is bound to
the admitted decoded display. No codec/metric rerun was needed for this binding.

Two instrumentation drafts were rejected before build. Parent and reviewer
identified zero-seeded inverse, wrong coordinates/stride serialization, unsafe
skip/EOB-zero handling and incomplete final-attempt/provenance checks. Corrections
are engineering validity work, not negative texture results. Parent owns final
C integration in fresh implementation-v3; worker supplied build support; reviewer
checks independently. No Round6 reconstruction evidence is admitted yet.

Round6 outcome: all7,382 records in final generation238 admitted, every visible
pixel covered once, source/predictor/residual exact, final inverse and whole
pre-loop exact, post-loop and packed OBU independently exact. Off and trace IVF
both equal installed R3; reuse complete prior GPU evidence without rerunning.
Observed small-transform raw reconstruction is faithful; shirt initialFPq65
loses most texture, and later processing removes more. Background initial
amplitude survives better but structure is altered; later processing removes
most remaining amplitude. Shirt skip coverage53.12% and reduced64 support17.28%
are separate limitations. Zero frozen quiet tiles exist in this single frame.
No legal alternative encode, bit-cost inference or playback follows.

Parent noticed apparent descriptor mismatch and required a same-frame audit.
R6 frame120 agrees with the old per-frame data; earlier headline summaries average
116,118,120,122,124. Labels are clarified without changing metrics or thresholds.
Unexpected actual qindices led to a second correction: the earlier qmax
inventory and review had read realtime defaults. The applicable non-realtime
branch uses objective delta-Q; the preserved target header proves present1/res2.
No new encode was needed to resolve this.

- auto: Choose one real qmax8 contrast next, retaining request11671 and all
  existing policy including objective delta-Q, with unconstrained measured rate.
  Require actual shirt/background exercised-pixel mean qindex≤40 and at least
  90%≤48, reporting all values above32 and all skipped pixels. This tests material
  precision delivery, not a guaranteed block cap or fixed-decision causality.
  The reviewer instead proposed a≤32 fixed-decision q32/coder study. Preserve it
  as a conditional follow-up: current raw→initial→final evidence already isolates
  local loss, while53.12% skipped plus17.28% reduced64 shirt coverage falls outside
  that proposed study. A real encode also supplies actual packet cost. If delivered
  finer quantization still fails, choose the next discriminator from its observed
  stage/decision changes. A failure at q32 rejects that point, not all precision.

## Round7 completed: actual precision delivered, preservation rejected

Question: does demonstrably finer actual quantization preserve texture before
attempting budget redistribution? The reviewed qmax8 arm delivers shirtq32 and
backgroundq32/36, changes skips/transforms, and costs38.8692416Mbps/441.295s for
336frames. Both private replays match installed output; all336 three-decoder and
all240 score identities pass. Five-frame shirt HF−47.989%/ACFerror.141765 and
background HF−11.071%/ACFerror.037634 fail unchanged gates. Broad GPU/quiet/detail
means improve, but local quiet/texture regressions remain. No playback or repair.

Existing flags7 isolate optimizer-only stage loss (shirtHF.544→.214) without a
new encode. Mixed intra optimizer/dropout shares remain unknown; recapturing them
would not yet select a different action. Accepted negative result, not failure
of all finer precision or a codec limit. See AOM_QMAX.md and bound machine data.

Auto decision: do not redistribute a non-preserving arm or repeat qmax blindly.
Inventory a genuinely different texture-sensitive decision policy, source-first,
against prior tested policies; reviewer independently constrains the next test.

- auto2026-10-20R8: first real two-pass arm requests10000kbps, scores9.3361368Mbps (96.4824% source), full-window9.959614857Mbps,369.290s. Before quality inspection, calibrate request to10313 using observed rate response and99.5% target; fixed policy unchanged.

- R8 calibrated arm: request10313, scored9.6279048Mbps (99.49757%source),
  full336 rate10.25718343Mbps, both passes370.33577s. All336 application/dav1d/
  libaom/NVDEC frames agree exactly with admitted cadence/color. Runtime
  observation and quality remain pending; no preservation inference yet.

- R8 observation admitted: off/on full336 IVF and recon both exact unmodified.
  All336 pictures observed; target216 delivers guarded zero-rate optimizer,
  nonzero spatial/TX psy terms, residual-zero/skip comparisons and HBD/spatial
  candidate selection. Fast hooks inactive; final partition survival unobserved.
  Search-event counts do not establish pixel ownership or separate component
  causality. GPU campaign/full-window quality now running.

- R8 complete, independently reviewed negative. At99.4976%source and370.336s,
  shirt HF−83.02%/ACFerror.08587 and background HF−42.08%/.11624 fail unchanged
  gates. Full controls mixed: broad MSE/CAMBI/temporal descriptors improve, but
  face/edge/quiet and broad ACF errors regress. All336 decoder and240 scored
  samples admitted; all native crop clips exact. Parent inspected stills/plot,
  no playback. Accept this failure; no source-rate or codec impossibility claim.

- auto R9: choose byte-neutral final-block and pre-loop/post-loop observation
  on exact R8. Aggregate search delivery does not prove survival into final
  partitions. Resolve that boundary before another policy or precision arm.
  R3 native one-step margins remain a possible later discriminator; their
  context-dependent sequential costs cannot predict a global optimizer flip.

- R9 scope was narrowed before implementation to packed coding input and
  complete pre/post-loop boundaries. Final-TU state was deferred because MD
  reuse and stale buffers require separate provenance. Reviewed implementation,
  decoder binding, complete510-SB coverage and exact off/on whole336 outputs
  all pass. A Boolean/DPB-slot metadata interpretation error was corrected
  against source and independent review; no trace or quality gate changed.

- R9 admitted, independently reviewed: single-frame shirt HF
  .60632→.44132→.09367→.05454; background1.67639→1.66549→1.28050→.84776.
  Coding loss and filtering both matter; upstream shirt loss is also present.
  Postloop improves MSE and shirt ACF while reducing HF further. All858 frozen
  tiles retained; zero quiet tiles in this frame. Parent inspected rounded luma
  stills only. Exact R8 bytes reuse prior GPU/full-window evidence and rate/cost.
  See PSYEX_BOUNDARIES.md and psyex-boundary-result.json.

- auto R10: choose final committed block/TU ownership and residual-state map
  before another policy arm. The worker's TF-off source audit is preserved:
  it changes reference/analysis behavior as well as samples, and does not
  isolate coding-input→preloop loss. Reviewer requires explicit skip/EOB
  categories, no stale-buffer reads, exact preloop assembly and provenance for
  actual q; unproven q/predictor fields must remain unknown, not inferred.

- R10 completed: reviewed private decoder observation, exact all336 pristine/off/on
  outputs;502events independentlybound, complete9843luma owners and exactR9preloop/
  postloop. EOB-positive covers91.84%shirt/94.84%background; absent-syntax dominance
  rejected. Shirt residual improves MSE without meaningful HF restoration; background
  residual helps substantially, then filters reduce amplitude. All858controls
  retained; noquiet atframe120. Parent viewedstillsonly. No repair/forwardq claim.
  Superres inactive-field guard failure corrected in freshv2, oldfailure preserved.
- auto R11: choose neutral committed encoder coefficient/producer capture before
  another settings arm. Actualprequant/initial/final must join decoderfinalowners;
  MD reuse/bypass requiresproducer lineage, not repeatedcoordinate matching.

- R11 completed and independently reviewed: 2907committed tokens,2187scalarFP
  calls,2151positiveunits, all24shirt positives. Scalar maps rawHFshirt.3930→.0937
  andbackground1.6238→1.2805 while sourcecorrelation/ACF also worsen. Lateroptimizer
  changes0shirt/1background/5face units; noise changesnone. Actualforwardqshirt71,
  bg79–87,face71–115. Noquantizerface34.37% remains distinct. All336bytesexactR8,
  so reuse its rate/GPU/fullwindow evidence; localcounterfactuals have no bitrate.
  Validator's directDQfailure was exact storage-order mismatch; independent source,
  all13scan-families and all2151unit joins establish transpose/effectiveQM correction.
  Sevenmalformedtraces rejected. Parent reviewed native-size luma stills only.
- auto R12: same-q native scalarB contrast with exactFP replay plus a lower-q FP
  precision control, fixedraw/predictor/partition/TX/QM, allinvokedunits retained.
  This separates scalar rule from precision without another policy sweep.
  Require exact q/DQ/EOB/inverse baseline before interpreting counterfactuals.
  A useful diagnostic must still survive realencoderfeedback, packetcost and full
  original-budget controls. No candidate/playback/blocker is established.

- R12 completed and independently reviewed: exact baseline/raw and all B/q32
  C/runtime outputs pass. Same-qB loses amplitude/correlation and worsens MSE;
  accept negative. q32 shirtHF.251 versus.606source, ACFerror.393 fails; background
  HF1.622 versus1.676source and ACF.0322 improve. All720 uninvoked owners retained.
  Independent metrics agree<1e-12; no bitrate/repair/quiet/playback inference.
- auto R13: one nativeFPq1 replay using verified helper, fixed decisions/QM and
  explicit distances to raw. No repeated baseline encode/build or localq sweep.
  Afterwards choose upstream/decision policy from evidence. Contract preserves
  original-rate ceiling and all acceptance gates.

- R13 completed: all2187 q1 C/runtime pairs and inheritedreference parity pass.
  q1 shirtHF.38072,ACFerror.08207 fails versus.60632source. Primaryinvoked MSE
  toraw.02063shirt/.02229background/.02769face; nearraw butnotlossless.
  Independentreconstruction agrees<1e-12. Workerpreparations correctedbefore
  sole2.466528s run; reference-scale oversight explicitlycorrected inreview.
  No encode/rate/fullwindow/quiet/temporal/playback inference.
- auto R14: choose original-visible-source replay through exactnativeforward,
  sameq1/predictor/partition/TX/QM and720unchangedowners. Newforward/newlibrary
  controls require allcapturedcoefficients and R13q1arrays exactlybeforeintervention.
  Sourceonlydistinction comesbefore realTF-off policy (whichalsochangesreferences).

- R14 completed and independently accepted: all captured/new native controls
  exact. Original-source q1 raises shirtHF62.79→86.50%source and ACFerror
  .08207→.04132; raw88.89% still fails amplitude. No legal encode/rate claim.
  Unchanged support and retained64TX remain specific suspects. Full original
  and coding-input references retained; no quiet/playback inference.
- auto R15: choose one actual TF-off plus near-fine public-QP bundle before
  new candidate-RD instrumentation. It measures legal preservation and actual
  cost with changing decisions, addressing a gap local replays cannot close.
  Observe actual target quantizers; fresh two-pass statistics; new decoder,
  color, packet and GPU/full-window validation. Overshoot is diagnostic only;
  practical ceiling remains original rate. No acceptance criterion changes.

- R15 completed and independently accepted as high-rate numerical feasibility:
  exact all336 decoders/off/on encoders, dynamic syntax binding and4809finalTU
  joins pass. All traced pixels use actualq4 and coding input is original.
  Five-frame shirt/background HF errors−3.622%/−1.427%, ACF.02189/.00542 pass;
  all12870 controltile MSEs improve, while41HF/612ACF pairs regress. Quiet
  positiveHF max+.01066; no exhaustive noise or playback acceptance.
  Actual190.4115432Mbps=19.6777xsource,692.476910s across two passes. The practical
  rate ceiling fails. No minimum-rate or codec-limit inference.
  Source/preloop identities and independent raw-surface metrics verified;
  scorer identity-schema failure corrected before any metrics in run1, valid
  run2 retained. Report cross-binding and coefficient-change wording corrected.
- auto R16: choose exact R8 policy with only TFoff at original packet budget,
  no publicQP bounds. Fresh stats, rate-only calibration to99–100%source, all
  unchanged decoder/native/GPU/texture/quiet/fullwindow gates. This fills the
  missing practical comparison before implementing an allocator. Coarseq alone
  cannot select the next mechanism: require sufficient residual support and
  scalar-localized loss for absolutecap; dominantskip/missingsupport selects
  decision tracing. Independent design review accepted that clarification.

- R16 initial rate calibration completed without a quality conclusion:
  requests10313/10070/10014 produced9.8804608/9.70136/9.3933528Mbps.
  First two exceed source; third is under-cap but outside the matched interval.
  All fresh two-pass statistics and packet receipts retained.
- auto R16 calibration refinement: after the contract's three-request
  reassessment, use midpoint requests inside measured bracket10014..10070,
  initially10042, at most three additional requests. Proportional response
  was not locally stable. No encoder policy or acceptance gate changes.
  Parent corrected review's strict-rate condition: endpoint equality is a
  valid quantizer plateau and still narrows the request bracket. Only an
  out-of-range measured response, exhausted integer bracket or trial limit
  requires reassessment. See ROUND16_RATE_REFINEMENT.md.
- auto R16 refinement implementation: reject incomplete ancestry validation
  and old-baseline replay; parent takes implementation ownership and corrects
  both. Independent release and wrapper review pass after exact no-encode
  preview and four-positive/five-negative synthetic controls. Start10042 with
  unchanged TFoff policy and fresh two-pass stats. Frozen refinement-preflight
  package contains scripts, reviews and controls; no quality conclusion yet.
- R16 midpoint10042 reaches9.6698472Mbps (99.9310%source,+0.4356%vsR8),
  372.254131s across two passes. Independent packet sum12,087,309bytes,
  bracket/outer identities/freshstats pass. Stop calibration and select this
  arm for complete observation/quality. All336 independent decoders and syntax
  mapping pass; no texture conclusion is inferred before remaining admission.
- R16 completed: matched9.6698472Mbps,372.254131s; all336 decoder/neutrality,
  2870owner/2130positive joins and observed frame120 original input pass. Shirt/background five-frame
  HF−83.738%/−41.427%, ACF.17584/.11161 fail. SSIMU low tails and some edge/HF
  tails regress despite quiet/CAMBI improvements. Single-frame shirt rawHF.52589
  →scalar/preloop.12740→post.06866 versus.60632source; allshirtpositiveq71,
  lateroptimizerchangesnone. Backgroundq79–87, face33.95%uninvoked remains separate.
  Independent spatial support recomputation passes after parent rejected
  aggregate-only verification. Parser/schema failures retained; no gate changed.
  Native grayscale stills inspected, no playback/candidate/blocker.
- auto R17: one nativeFPq4 replay on newly captured R16 choices, before another
  allocation change. Exact baseline/table/DCdelta/C/runtime/packed64 controls,
  complete arrays and additive support decomposition required. This is a new
  TF-off policy population, not repetition of the old TF-on sweep. A fixed-choice
  failure cannot reject real low-q decision feedback, already material in R15.
  Initial worker drafts rejected for schema, scaling, scalar/final conflation
  and incomplete artifacts before execution. No R17 outcome yet.
