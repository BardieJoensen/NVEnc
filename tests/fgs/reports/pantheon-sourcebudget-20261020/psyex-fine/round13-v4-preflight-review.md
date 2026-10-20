# R13 v4 preflight review

Disposition: **accepted for the single preregistered qindex-1 diagnostic; no remaining material blocker found.** This is a source review only. I did not execute the experiment or inspect an outcome.

Reviewed frozen inputs:

- `worker/psyex-r13-fine/experiment.py` SHA-256 `dd5dd4ae87a7101be0d580997dd125190f250f2363a0c0b2f894a03482966e11`
- `worker/psyex-r13-fine/run.py` SHA-256 `65384f748006f3c705a67a8c9a6c642156597b0c9c1b8d5623e1a3f61f19aeac`
- `ROUND13_FINE_CONTRACT.md` SHA-256 `4dcd8abfffdc31455f8e020a518b1444bafccfe44b4084b97f78ef4b71dfd302`

The earlier blocking reference-scale error is corrected: `load_luma()` output is used directly for `original` and `coding_input`, while reconstructed native arrays are divided by four exactly once during mosaic assembly. Before any novel-arm metric is emitted, lines 128–133 reproduce R12's fixed-ROI descriptors for original, coding input, raw inverse, baseline FP, and FP-q32 with `1e-12` tolerance. This catches a reference-scale, mapping, or helper drift.

The other prior blockers are resolved. The experiment binds the admitted R11 evidence through the identity stored by R12; reuses R12 baseline/q32 arrays without rerunning those arms; verifies captured baseline q, DQ, and inverse against R11 per TU; enforces gap-free coefficient and pixel offsets plus complete invoked-array lengths; and runs only paired native-C/runtime q1. It changes only FP table rows 0, 1, and 6 and records CPU flags, realized qindex, EOB, per-TU arrays, offsets, and coefficient deltas. Primary distances use the identical invoked mask against both raw inverse and coding input, while full-ROI values remain explicitly secondary and retain predictors for the 720 uninvoked owners.

The runner pins the reviewed experiment, interpreter, R12 result/arrays/build/native library and contract before and after execution; records the literal bounded command; requires both inner and outer completion; and cross-binds the result and q1 array identities. The result scope correctly excludes encode, bitrate, repair, and playback inference.

