# Independent review and corrections

A separate read-only reviewer used the runtime's real agent tools. It reviewed
contracts, source patches, frozen controls, raw TU/entropy exports, validation
receipts and real-encode metrics before receiving the parent's conclusions.
No child delegated further. The parent owns all conclusions and Git integration.

## Rejected worker instrumentation

The first implementation did not produce usable entropy evidence. Its final-TU
state transport crossed translation-unit/thread boundaries unsafely; copying a
writer buffer while retaining shared ownership could mutate the real coder; one
prefix comparison was tautological; and its first VBR trace realized q77 while
its selection expected q32. Requested settings did not establish intervention.
Those outputs are recorded as failed attempts, not pooled with valid results.
The parent explained each defect, requested focused corrections, then replaced
that instrumentation in a separate scratch source tree. The worker subsequently
executed the parent's bounded, validated controls and real arms.

## Accepted instrumentation, with scoped findings

- The entropy wrapper now owns a full private writer buffer, rebased pointers,
  buffer-owner object, CDF and entropy scratch. An identical-vector clone must
  equal the real call's coder state, emitted byte prefix, CDF and returned level.
  Both entire IVF streams and application reconstructions equal their controls.
- Summaries initially lacked a complete eligible-population audit. The correction
  derives exact keys from independent final-block/entropy traces:4,750 E04 and
  6,389 E05 TUs. Six/21 whole-block skipped TUs are explicitly excluded. Their
  revival cannot be priced by an isolated coefficient writer call.
- A wording error called already-divided values eighth-bits. They are **bits,
  with1/8-bit precision** (`tell_frac/8`). No numerical results changed.
- Reader hardening now rejects missing required EOB records, partial trailing
  headers and truncated unknown payloads. The last needed checked reads because
  `fseek` past EOF succeeds. The actual C reader passes one complete export and
  rejects all three corruptions. Separately validated complete measured exports
  protect the earlier results; parser revisions are not encode interventions.
- Pre-reset exercised transform type is retained for a zero-EOB TU revival.
  Bypassed blocks remain unchanged in counterfactual composites and are reported
  separately. No hypothetical transform is called exercised evidence.

## Private lower-q and real retention review

The reviewer found no implementation defect in the private FP contrasts. Current
q FP exactly equals actual initial coefficients/dequant/EOB/reconstruction;
input, predictor, residual, exercised transform and actual reconstruction match
controls. Full streams/reconstructions remain unchanged. E04 q24 and E05 q20 pass
the established whole-ROI screens. **E05 q20 transformed-only neighborhoods have
HF+10.71%**, just outside10%; retain this limitation rather than selecting only
the favorable whole-ROI result. The quiet E05 frame starts atq27, so minus12 is
q15 there; it is not an independent absolute-q20 validation.

Real-arm legality and selection were checked. The SB map is applied before mode
decision, and reapplied before recode, so q changes search/partition/transform/
predictor choices. Final FP retention then changes reconstruction and reference
feedback. Real results are a **combined absolute-q allocation + global TX32 +
final coefficient-retention strategy**, not a retention-only ablation. Every
selected block over240 frames realizes q20/q24. All logged retained coefficient/
dequant hashes and EOBs match, sampled TU arrays match exactly, and all240 decoded
planes equal application reconstruction.

E04 purple and E05 shirt pass five-frame screens at high rate. The E05 map only
selects the shirt; its background fails badly. Quiet-region ACF error slightly
worsens in the E05 high-rate arm despite broader improvements. These are manual
selected-region preservation results, not full-picture or practical repairs.
Rates refer to original packet budgets; the comparison baseline is diagnostic
SVT at source budget, not a production/library encode. No motion playback was
observed. Native still inspection is reported separately.

## Cross-codec review

A prior-evidence inventory found only source-budget, single-pass E04 x264 grain
controls, with no E05 or2x result. The new two-pass arm is distinct and remains a
feasibility test, not a claim about AV1's limits. Review caught two rate-contract
gaps before interpretation: container start offsets can decouple absolute PTS
rounding from decoded frame positions, and a nominal2x request does not ensure
2x actual packets. Accounting now validates336 cadence-consistent sorted PTS,
selects presentation positions96:336, records2x source target/error and requires
within1% before decisive scoring. A separate audit proves identical selected
packets for all six earlier real SVT arms (firstPTS0); their rates do not change.

E05 input's all336 lifted8bit hashes equal the SVT10bit input. CPU and NVDEC
candidate decoding match all336 frames/all planes. Completion initially failed
because PATH selected a custom FFmpeg without cuvid, then because a command Path
was not JSON serializable; both are corrected with explicit system NVDEC FFmpeg
and string command arguments. Neither failure is a decoder mismatch or a metric
failure. The durable final decoder receipt is required before claiming success.

## H264 allocation and analysis-depth review

The first reader omitted two delayed output frames. A later count-only receipt
still did not implement requested error/coverage/resource checks; the parent
rejected it, rewrote the reader/wrapper, and the reviewer accepted the final
implementation. It has checked input/side-data bounds/geometry, two decoder
threads, fail-on-unexpected send EAGAIN, complete flush-to-EOF, fresh outputs and
streaming exact336x8160 grid/PTS checks. The compact maps and inputs are hashed.
No causal claim uses the incomplete exports. An executor also prematurely
reported a still-running two-pass encode as failed; parent inspection of both
completed returncodes and final receipts corrected that reporting error.

AQ0.5/1/2 comparisons each meet the common2x target and pairwise1% rate gates.
Complete source-defined controls, decoders, QP maps, PTS and coding-type schedules
validate. Area-weighted ROI-minus-outside contrasts prove exercised allocation;
whole-frame QP also changes, so this remains a calibrated AQ/search intervention.
AQ2 sharply increases edge/face error while quiet-region error improves. Its
shirt amplitude passes but spatial structure fails; do not select amplitude
alone or describe the tradeoff as uniform degradation. No further AQ escalation
is justified by these results.

The reviewer checked [x264 help](https://github.com/mirror/x264/blob/master/x264.c),
[analysis source](https://github.com/mirror/x264/blob/master/encoder/analyse.c),
[motion-estimation tables](https://github.com/mirror/x264/blob/master/encoder/me.c)
and [FFmpeg's wrapper](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/libx264.c).
Subme11 includes QP-RD/mode refinement, deblock-aware RDO and disabled early
termination; it is not simply more subpixel iterations or fixed-QP prediction.
Explicit x264 params override fast-first-pass defaults too, so changed first-pass
statistics are part of the intervention. Pass2 options differ only subme8→11;
required trellis2/AQ>0 are logged. Keep this two-pass analysis-depth scope explicit.

R8 result review accepted packet/input/decoder/whole-control evidence and its
failure of the shirt screen. It also required removal of "without further
spatial reallocation" from the initial question: fixed AQ strength does not
hold MB quantizers fixed when QP-RD is enabled. The exported R8 map is retained;
no unmeasured fixed-allocation claim remains. Quiet HF error slightly worsens
despite otherwise broad control improvements, and midpoint background temporal
correlation moves slightly away from source. Both limitations are retained.

R9 independent review found no provenance defect and accepted the negative
joint-screen result: at calibrated3x rate, shirt amplitude passes but ACF error
0.05736 fails. Raising rate improves many metrics but does not monotonically
improve every structure statistic. The initial+1.416% calibration arm remains
unscored. No threshold was rounded or relaxed.

The reviewer recommended a single x265 feasibility control before another x264
rate increase. [x2653.5 documentation](https://x265.readthedocs.io/_/downloads/en/release_3.5/pdf/)
and its [grain-tune table](https://x265.readthedocs.io/en/stable/presets.html)
describe a bundled policy: AQ/cutree/SAO disabled, high psy-RD/RDOQ, constrained
QP variation and grain-oriented rate control. That makes it an independent
feasibility test, not a codec-only or quantizer-only contrast. Original samples
remain identical; coding at10bits adds no source precision. Multipass stats
reuse, effective options, exact input identity and Main10 CPU/NVDEC agreement
are required explicitly. Review of the first worker script caught count-only
input validation and absent stats assertions; the running script was preserved
unchanged to keep its receipt hash honest, and supplemental checks were required
before accepting the run.

R10 final review accepted exact Main10 input/CPU/NVDEC, source/ref, campaign and
packet receipts. The shirt's failed amplitude/ACF screens override its high
VMAF and zero full-reference CAMBI. Flat-texture structure and temporal outliers
remain; no codec-wide conclusion follows. The meaningful library identity is
the linked libx265 file SHA, not raw `ldd` stdout whose load addresses vary.

R11 closes the two-pass analysis interaction check: both3x arms fail shirt ACF
at almost the same error. The3x rates differ only0.026%. R9 generally has better
whole-window and temporal errors, while R11 midpoint amplitude is closer.
Actual first-pass options are subme2 versus9 (plus chroma QP offset), and second
pass8 versus11. Claims remain about the complete two-pass user-setting effect.

R12 review accepted the deblock-off intervention and negative result. Pass1's
effective option is in generated `pass-0.log`, not the null-output console log;
pass2 reports it directly. The worker initially relied on argv for pass1, which
was insufficient. Both effective headers now have an inspectable audit, the
executed runner is preserved, and future runs assert the realized flag.
Disabling the filter worsens shirt ACF and increases source-compensated8-grid
mean excess0.28467→0.39555 (+39%). Whole-window and temporal structure are mostly
slightly worse. The reviewer accepted the grid math after requiring exact
source fingerprint, original-control identity and12,870tile/15frame coverage.
This diagnostic is not a new acceptance gate;16-grid interiors include8-grid
boundaries. Feedback/mode changes prevent fixed-decision filter attribution.

Evidence-retirement review required two corrections before deletion: bind the
raw-member manifest to its verified archive hash and reject escaping paths;
also independently stream/check all607 measured-source tar members and the
actual measured binary hash. Both are implemented and the source/binary check
has passed. No retirement starts until jobs/mounts/schedules/worktrees are clear.


R13 independent review accepts the E05 4x numerical screen, including full240
traces: shirt HF error mean/p95/max2.252/5.069/6.833%, ACF0.01207/0.03379/0.06602.
Background HF2.291/4.683/9.895%, ACF0.01136/0.03051/0.05428. Shirt temporal error
maximum0.07978 improves from3x0.22043. Quiet HF/ACF errors slightly worsen versus
3x; this limits any claim of uniform improvement. No source-clean threshold was
relaxed and no new threshold was invented. Tested3x failure and4x success do not
locate a monotonic minimum rate.

R14 independent review finds no blocking validity defect and accepts E04 as a
numerically qualified playback candidate. All240 purple HF error mean/p95/max
2.656/4.653/6.548%; ACF0.01069/0.02778/0.04285; temporal error0.00483/0.01639/0.02557.
Source correlation mean0.8666/minimum0.6998 and sampled strong-edge ratio mean
0.9630/minimum0.9322 support broad preservation with remaining error. Quiet
ACF absolute error0.08656 and signed HF excess0.01721 remain perceptual concerns;
small CAMBI values cannot settle them. Known-fixture transfer is not held-out
validation. The reviewer found no further machine diagnostic necessary before
human playback; actual player/display and practicality remain unresolved.

Playback artifact review caught a provenance gap: a decoder-success boolean
alone did not prove that the currently rendered scored file was the validated
one. The smallest correction binds each decoded file SHA to score identity and
all240 plane hashes to decoder hashes[96:336], binds full streams to receipts,
and binds reference hashes to fresh original validation. The second correction
adds both E05 3x and4x actual full streams, so the requested normal-distance
comparison is possible. Hardlink identity/link count is recorded before source
retirement. Both cases then pass all240/all-plane native panel validation. The
independent reviewer rechecked corrections and found no remaining concrete bug.
The reviewer and parent have not observed motion playback.


The reviewer recommended supplementary quiet-tail contexts because the largest
measured overshoots were outside the preselected quiet crops. `quiet_tail.py`
keeps those unbiased controls and adds only an explicitly outcome-selected
stress diagnostic, with frozen-control provenance, summary fingerprint, exact
tile/frame/time and the same blind mapping. It introduces no new gate. Native
panels validate all240 frames/all planes. Full-reference supplemental receipts
also bind retained source336 bytes to the all336 exact-input validation.

Final quiet-tail review accepted selection, clamping, timestamps, upstream
binding and exact panels. Supplemental `viewer-key-binding.json` fingerprints
the unchanged key and both validation receipts, closing the archival key-binding
omission without rerendering unchanged clips.
