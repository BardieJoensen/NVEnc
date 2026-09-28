# Source-only stationary and moving component evidence

D82 adds an explicit alternative to D74's component-history diagnostic. A
minimum-error displacement exists even on independent noise; using it without
positive motion evidence unnecessarily rejects stationary structured sources.
The new path chooses stationary or integer translation using source training
pairs 0/1 and 2/3 only. Both pairs must independently support translation before
it is selected. Validation pairs 4/5 and 6/7 can reject that choice but never
select another one. Candidate pixels and other components cannot choose motion.

The diagnostic measures actual visible border rectangles without padding or
wrapping. Insufficient samples or unavailable shifted history remain unknown.
Native luma is not averaged away. Existing anchors, temporal consistency,
source-detail vetoes and numerical bounds remain required. The original D74
entry point and all its recorded results remain unchanged.

## Rejected first version and correction

The initial stationary choice exposed a real ambiguity in the measurement:
slow translation of a smooth noisy surface passed the old consistency checks
while inflating the native luma grain estimate by about 17%. All 16 frozen
8/10-bit controls showed the problem. This was a constructed diagnostic failure,
not a deployed encoder or library defect. Its implementation and results remain
in the local evidence; it was not admitted as a source rule.

Version 2 adds an independent source-model consistency veto. Separate least-
squares lines fit original even frames 0/2/4/6 and odd frames 1/3/5, then predict
frame 7 without including it in either fit. The signed residual cross covariance
must agree with the existing constant-history estimate within 8% of the smaller
positive estimate. This reuses the fixed estimator accuracy budget; it neither
changes the reported target to a more favorable value nor relaxes any old bound.
Disagreement rejects the stationary hypothesis. Agreement alone cannot prove
that arbitrary source content is grain or establish its clean underlying image.

## Qualification and remaining coverage

The fixed study covers 1,344 cases: 28 source families, eight seeds, both native
depths and three components. All 16 slow-motion luma counterexamples now retain
a conflict. Intended stationary luma controls remain usable; persistent-noise,
removed-native-row, scene-change and motion-reversal controls retain their
vetoes or unknown state. Every case without a recorded conflict meets the 8%
known-grain estimator bound in this cohort. No source admission follows.

Independent matrix least-squares solutions agree with all 544 reported control
predictions within 1e-10. All other measurements remain identical to the first
version. The earlier D74 API reproduces all 1,152 original control results and
4,080 original real-region results exactly. Full CPU passes 287 Python tests in
39 suites and 55 C++ programs.

The complete two-frame HDR census covers 16,588,800 native luma samples and all
4,080 regions, including visible borders. Another 1,405 independent least-squares
comparisons agree within 1e-10. The new necessary checks leave 200
and 164 regions without a recorded conflict, covering 9.85% and 8.07% of pixels;
D74 previously covered 5.48% and 4.64%. The first version's larger apparent
coverage is rejected because it misses the slow-motion ambiguity. Original
source identities, clocks, candidate rounding and prior detail vetoes remain.

Every occupied native brightness lookup still contains unsupported pixels.
Consequently these improvements admit no complete grain curve. Whole-picture
source eligibility, joint colour compatibility, automatic runtime and R3–R8
remain open. Do not repeat supported-patch fitting to solve this different
coverage problem. Measure the complementary source hypotheses and their actual
remaining conflicts before another population rule or runtime decision.

This is offline CPU work; it adds no encoder call site, GPU job, service pause
or ordinary validation cost. Production remains ordinary `cb903a17`, retention
and FEL off. Reserved qualification footage is unopened.

Evidence: `roadmap-r3-component-selection-20260928/` in the local
[handoff root](WORK-TO-PRODUCTION.md), starting with `report.json`,
`qualification-report.json`, `qualified-real-report.json`, `full-cpu.json` and
the retained initial reports and `rejected-v1-source/`.
