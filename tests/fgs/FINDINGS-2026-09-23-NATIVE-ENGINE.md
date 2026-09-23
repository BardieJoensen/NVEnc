# Direct fitting and a complete finite sequence engine

D50 measures oriented source/reconstructed-base cross moments and fits the
frozen native luma and colour shapes directly from pixels. D51 joins fitting,
reference synthesis, strength/seed selection, window checks and packet writing
in one process. These remain bounded development diagnostics; source eligibility
and pre-encode retained fractions are still supplied by separate experiments.
Production is ordinary `cb903a17`, retention/FEL off.

`NVEncFilmGrainNativePair.h` measures each `source_i * base_j` on its own shifted
support. This cross matrix is not symmetric. The first eight consecutive
training halves feed the existing PSD, quantization and stability checks; the
independent halves never fit or quantize the shape. Layout/segment/ordinal
changes, invalid moments and incomplete training reject.

The [finite engine](retention_engine/engine.h) buffers at most eight native
source/base pairs, fits once, then performs the qualified batched calibration
and first-training-pass seed policy. Each picture and every eight-picture
window must pass their separate diagnostics. A model becomes available only
when its window passes; the last seven models wait for successful completion.
Known packet identity and model readiness both gate the existing output FIFO.
Failure remains terminal; a compressed partial base is never called source
fallback. The option is not connected to ordinary encoder analysis.

## Recorded checks

- D50: 33 native 8/10-bit pairs and pooled training agree with independent
  NumPy across 618 matrices, including 206 oriented source/base matrices.
  Maximum normalized moment error is `4.473476158868323e-14`. Raw sums use
  the predeclared absolute-plus-relative tolerance, not an absolute-only bound.
- Both 16-picture controls recover all six frozen component shapes exactly.
  Sixteen reversed source/base pairs transpose their cross matrices correctly;
  both reversed training fits reject their invalid missing-energy targets.
- Another 1,250 integer cross sums and their transposes agree with direct
  calculation. Modified check-half values cannot change the fitted model.
  Sequence, count, nonfinite, PSD and stability failures have regressions.
- D51's two complete controls select the same 32 models and produce exactly
  the previously independent AOM/dav1d-qualified AV1 bytes, including reordered
  and hidden pictures. These are reused decoder observations, not fresh decodes.
- Including the separate minimum eight-picture window, 540 fresh calibration
  steps and 54 candidate pictures reproduce the previous oracle results.
  Eleven integration failures reject without writing a successful IVF output:
  incomplete input, duplicate ordinal, changed segment, stalled/sentinel clock,
  native-buffer limit, duplicate/degenerate training seed, packet limit, wrong
  packet clock and reversed source/base.
- Full CPU suite: 214 Python tests in 30 suites plus 43 C++ programs.

On the primary 16-picture controls the first engine run took 3.98 and 3.91 seconds.
Native pair buffering peaked at 25,165,824 bytes; packet buffering peaked at 13
packets because model readiness adds delay beyond reconstruction readiness.
Those byte counts cover the named buffers, not complete process RSS. Temporary
candidate raw files were hashed and removed: 84,934,656 bytes per full engine
qualification run. This CPU reference is not a production throughput result.
The expensive reference synthesis remains explicit diagnostic work, consistent
with the R2 contract; a future production path must earn its speed budget.

Local ledgers: `roadmap-r3-native-fitting-20260923` and
`roadmap-r3-native-engine-20260923`. The engine ledger preserves the initial
build/results under `v1`; the current run also rejects the sentinel timestamp
and records all minimum-window synthesis work in its counts.

Next is the finite live encoder connection using actual NVENC reconstruction
callbacks. Original-source identity must remain explicit and checked. Automatic
pre-encode fraction selection, real whole-picture eligibility/coverage and
R4–R8 are still open; the reserved qualification footage remains unopened.
