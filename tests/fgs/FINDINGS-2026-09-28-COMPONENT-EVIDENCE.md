# Native component evidence after source-preserved colour

D74 separates the native luma motion hypothesis from copied colour. It improves
structured-source measurements but does not solve whole-picture eligibility.
No source/detail/joint admission bits or R1 thresholds change.

The offline diagnostic independently registers one component using the same
source-only training pairs, native refinement and separate validation pairs as
D67. It retains every native Y pixel, including alternating-line structure.
Odd luma translations are representable without assuming a chroma displacement.
Missing overlap, anchors or validation remains unknown. The old three-component
registration/covariance implementation remains unchanged; independent component
motion cannot prove a joint colour relationship.

The frozen known-source study covers 1,152 component cases across 24 families,
eight seeds and both depths. All 112 native Y cases with static/spatial/moving
independent grain, including differing or flat colour and odd Y motion, meet
the 8% estimator-accuracy bound and recorded consistency/detail checks. All 64
grain-free translation/weak-texture Y cases estimate exactly zero noise. Temporal
correlation, scene changes, reversal and missing overlap retain their conflicts
or unknown state. All 16 persistent-plus-independent and 16 removed-native-row
cases retain a detail veto. Flat independent noise without a structure anchor
remains outside this structured-source hypothesis; no success is inferred.

Every region and border in the two existing UHD HDR development frames is
included: 4,080 regions and 16,588,800 native Y samples. Registration support
increases from 56/127 joint regions to 411/486 native Y regions. After all new
and earlier necessary vetoes, 111/94 regions remain without a recorded conflict,
covering 5.48%/4.64% of pixels. This is provisional evidence, not qualification.
Every occupied candidate lookup code (499/513 codes) still also contains
unsupported pixels. Even the optimistic native-code separation therefore cannot
enable a whole-picture grain curve. The roughly 46-second offline census is not
a production throughput measurement.

Full CPU checks pass 267 Python tests in 37 suites plus 53 C++ programs. Original
histories, clocks and candidate rounding match their previous independent pins.
Production, reserved footage and media remain unchanged; this study needs no GPU
or service pause. Further source work must account for unsupported regions, not
repeat the same patch fits or treat these necessary checks as sufficient proof.
Full-resolution and temporal qualification of the new copied-colour mechanism
also remains useful independently of source classification.

Evidence: `roadmap-r3-component-evidence-20260928/` in the handoff's local root:
`plan.json`, `study-manifest.json`, `synthetic-report.json`, `real-report.json`,
per-frame candidate lookup coverage, `full-cpu.json` and `report.json`.
