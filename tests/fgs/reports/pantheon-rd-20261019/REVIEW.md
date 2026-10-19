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
