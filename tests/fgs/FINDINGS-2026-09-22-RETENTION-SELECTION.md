# R3: coverage feasibility and safe model reuse

R1 and R2 of the [roadmap](RETENTION-ROADMAP.md) are complete. R3 remains open.
This first R3 stage uses the already source-verified encoder captures; it does
not consume the reserved qualification corpus or change production settings.

## Whole-picture coverage remains a real implementation requirement

The qualified collector measures six native rounded colour-retention fractions
(0, 0.1, 0.25, 0.5, 0.75, 1) on each of three Shining development frames, with
luma retention fixed at 0.1. Source-selection decisions remain identical across
candidates. Both colour components and every occupied native lookup range are
included. Training and independent check groups each require 16 blocks.

At 25% colour retention, valid Cb missing-noise groups account for 12.5%, 55.4%
and 62.7% of lookup pixels in those three pictures. None of their Cr groups has
sufficient qualifying support. Those percentages identify ranges with supported
moment targets; they do not qualify every pixel in those ranges or a complete
synthesis model. Many base pixels still change outside supported ranges, even
at 75% retention. Setting the corresponding synthesis curve to zero cannot by
itself approve the altered base.

This is insufficient evidence for automatic colour recovery, not evidence that
the source or installed library is damaged. The earlier successful source-patch
prototype therefore cannot simply become a whole-picture policy. Implement
population-aware coverage, explicit source fallback and cross-colour checks
before allowing the selector to change output. Preserve the existing detail,
quiet-region and amplitude guards. No acceptance threshold was relaxed.

## Grain-scale changes must invalidate model reuse

Commit `2000f767` fixes a prerequisite for the future nonzero-grain-scale model.
`film_grain_params_close` previously compared strength curves and AR coefficients
without checking `grainScaleShift`. Otherwise identical parameters could therefore
reuse an older template even when its innovation power changed substantially.

The regression uses the independently AOM-verified native template generator.
Changing the shift from zero to one produces a measured power ratio of 0.250109;
the old comparator incorrectly accepts reuse and fails this negative. The
correction requires a fresh model across scale changes, including nominal curve
compensation because finite clipping and rounding can also change the shape.
Same-shift reuse still passes for shifts 0–3, as do the existing 6,000 independent
brightness-grid comparisons and jitter/equivalent-curve controls.

The full CPU suite passes: 185 Python tests in 26 suites and 19 C++ checks.
Ordinary automatic fitting uses shift zero. This result does not establish a
new defect in the deployed encoder or another library repair requirement. It
also does not enable scale one: gain/DC limits, curves, component blending and
actual moving-output qualification still need the complete R3/R4 integration.
The last fully compared diagnostic encoder binary remains `da9ce557`.

## Evidence and next action

The private `colour-recovery-20260922/roadmap-r3-20260922/` ledger contains:

- `manifest.json`, `preparation.json`: finite candidates and native input hashes.
- `coverage.json`, `groups-*.json`: all ranges, both components and measured moments.
- `grain-shift-negative.json`, `cpu.json`: retained failing comparator and passing suite.
- `report.json`: completed stage scope, evidence hashes and remaining work.
- `archive.json`: verified lossless archive of completed per-tile measurements.
- `r3-frame*-pause.json`: released GPU pauses with unchanged worker limits.

The next implementation is the bounded selector's coverage/fallback path,
followed by consistent model gains and per-component native blending. Runtime
selection, temporal behaviour, compressed-output quality and quality/size/time
comparisons remain open. Ordinary Tdarr is unpaused; automatic retention and
FEL stay disabled. No experiment is scheduled or left running.
