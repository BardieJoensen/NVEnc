# Exact constant copied chroma in the finite retention fitter

September 27, 2026 — D68 implementation and mechanism qualification; complete
encoder qualification is in progress. R3–R8 remain open. Production stays
ordinary `cb903a17`, retention and FEL off.

The finite fitter previously required nonzero source variance and partial
retention in all three components. Even an explicitly source-preserved colour
plane forced the schedule to preserve the entire frame. A constant copied plane
can instead use a present zero-strength curve with neutral AR coefficients,
provided its pixels and the restricted-range clamp are proved safe.

The new diagnostic options pair `pre_encode_copied_chroma` in the finite plan
with `copied_chroma_mask` in the native engine (2=Cb, 4=Cr, 6=both; default 0).
Y remains partial. The selected colour must have the same exact constant code
in the original, actual pre-encode candidate, reconstruction and synthesized
output, across the complete modeled segment. The code must be in 16–240 scaled
to native depth. An extra capture checks the actual GPU candidate before NVENC
submission; its proof travels with the immutable original source. Libraries must
explicitly confirm this option so an older ABI-compatible build cannot ignore it.

This path does not fit a singular colour regression or divide by zero. It
requires exact zero rows/cross terms and exact native global/fold means for
copied components, while retaining the existing bounds for all active variables.
A changed pixel, missing proof, clamp, source-preservation override or changed
constant rejects the diagnostic. A failed partial encode cannot be relabelled
as source fallback after compression. The automatic selector still treats
unsupported mixed components conservatively; these explicit trials grant no
source classification or perceptual approval.

Completed mechanism evidence:

- 54 native CPU controls at both depths, including padded and ragged geometry;
  944 counted pixel/moment vetoes plus plan, calibration and source association
  checks. Existing strict failures remain failures.
- 72 GPU layout/capture controls; 393,120 exact copied samples and 864 expected
  rejections. These were small transfer checks, not encoding/timing trials.
- 18 sixteen-frame CPU synthesis cases: Cb, Cr or both copied, at low/mid/high
  native colour codes. Independent NumPy checks agree on all 291 attempted
  candidate comparisons and 162 sliding windows. All 50,724,864 copied samples
  are exact. The other components reuse recorded NVENC reconstructions; this
  constructed CPU fixture does not claim a fresh encoded reconstruction.
- Ten earlier all-active/source-segment library replays preserve all 160 models,
  decisions, readiness and complete packet bytes, including 1080p and UHD.
- Full CPU suite: 259 Python tests in 36 suites and 52 C++ programs pass.

The first independent checker stopped on its own nested-JSON comparison type
error after the native case completed. The checker was corrected and resumed
against the same native result and raw witnesses. No encoder, model or numerical
bound was changed for that correction. All generated synthesis witnesses were
retired only after their measurements and hashes were recorded (457,703,424
bytes). Inputs, recipes and current binaries remain available off the root disk.

Next: build the actual encoder, exercise fresh NVENC/source/model/copy association,
independently decode grain-on/off outputs, and compare ordinary SDR/HDR controls.
Only then close this mechanism stage. Broader real-source classification and
bounded automatic integration remain open; the reserved corpus is unopened.

Local evidence is in `roadmap-r3-constant-chroma-20260927/` under the evidence
root linked by [the current handoff](WORK-TO-PRODUCTION.md). Read `plan.json`,
`model-plan.json`, `model-report.json`, `library-v9-report.json`,
`gpu-layout-report.json`, `full-cpu.json` and the active stage `report.json`.
