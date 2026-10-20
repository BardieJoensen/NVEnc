# R14 preflight review

Disposition: **native intervention and provenance are sound; one small result-schema correction is required before execution.** No R14 experiment was run for this review.

Reviewed frozen artifacts:

- contract `0674ce053b27410e5bf184e861a7f88c77b902374984531089787d530e62106d`
- `native.c` `41a9173ac13d4ff5d1d7155a9d02759f2276a9549ce518ca869c1f421d0aa1ef`
- `build.py` `cf38f56ae68dfcc669c3e37e1836e1073d4923b9ab5c3483a4811515760c0148`
- completed build receipt `8ddbfd8c092185ff99181c68dd88cc25ff0cbec9af569cfae3a0b7d2fb202825`
- private library `2d8a97ac78e7ec6986fb1d05ba2766dd28ed0cca6010ff17245195294af4f08a`
- `experiment.py` `226c23bff712e47f044f6ca6931f1cc555196de2be016065bcddfeeeff340904`
- outer `run.py` `d78ea2f9030ea1fd1243a277af822cca604aa1b4cfc2ff09e9974b43647dc2c1`

## Required correction

`experiment.py:124` reports every stage's full and split support against the original, but reports coding-input distance only on invoked pixels. The contract requires the original and coding-input references separately, including skipped support and the full ROI. Before execution, add:

- a full-ROI coding-input-referenced descriptor (or at minimum full-ROI coding-input pixel distance), and
- `uninvoked_to_coding_input` beside `uninvoked_to_original`.

This does not change the intervention or thresholds. It prevents source-processing error from being conflated with the unchanged-predictor error in the 720 uninvoked owners. The existing `invoked_to_coding_input` should remain.

## Native route and controls

The forward wrapper follows `av1_estimate_transform_default` in the pinned R11 source:

- 8×8, 16×16, 8×16, and 16×8 use their initialized RTCD functions, with the corresponding C function for the direct control;
- 16×32 and 32×16 use RTCD only for DCT_DCT/IDTX and C for the other types;
- 32×32 uses C for the six one-dimensional transform types and RTCD otherwise; and
- 64×64 requires DCT_DCT and applies the matching in-place `handle_transform64x64` packing before returning the 1,024 adjusted coefficients.

The wrapper copies all inputs into private aligned storage, constrains 10-bit residual range and admitted geometry, and compares direct C with initialized runtime output and energy. The compile log's `-Wmisleading-indentation` warnings come from macro formatting; the generated `if/else; break` control flow is correct. Rebuilding solely for those warnings is unnecessary.

The experiment performs all 2,187 captured-source controls before substituting any original sample. It requires captured visible source identity to the admitted R9 coding input, exact native forward coefficients and raw inverse against R11, and q1 q/DQ/EOB/inverse from the new library against every R13 array. This makes the new forward wrapper, 64×64 packing, CPU dispatch, and reused quantizer/inverse fail closed before novel measurements.

For the intervention, only visible rows are replaced with exact native-10-bit original samples; padded rows remain byte-identical to the capture. The predictor, TX, scan, QM/IQM, and q1 rows stay fixed. Direct C/runtime equality is required for every new forward, quantizer, and inverse call. The 720 uninvoked owners retain their predictors, and new arrays preserve source, raw coefficients/inverse, q/DQ/inverse, EOB, token and gap-free coefficient/pixel offsets.

## Provenance and scope

The build reuses the exact completed R11 object population read-only, binds the 1,790-file source manifest and every linked object before/after, and writes a fresh private library. The experiment pins R11 admission, R12 helper, R13 result/arrays, metric helpers, source planes, build, library, and contract before/after. The outer runner records the literal `nice`/`taskset 8-11` command, pins its tools and current artifacts, and cross-binds inner result/arrays/script/library/build/contract.

The stated interpretation is appropriate: this is a local fixed-predictor/partition/TX source-sample counterfactual. It cannot establish encoder feedback, entropy cost, a valid bitstream, source-budget feasibility, full-window behavior, or playback.

