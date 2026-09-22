# R3: coverage, bounded selection and safe model integration

R1 and R2 of the [roadmap](RETENTION-ROADMAP.md) are complete. R3 remains open.
This first R3 stage uses the already source-verified encoder captures; it does
not consume the reserved qualification corpus or change production settings.

## Current implementation: selector and native-base contract

`NVEncFilmGrainRetentionSelect.h` now implements the bounded host policy:
one existing luma proposal, at most five candidates per colour, and one final
compatibility decision. It chooses the first admissible fraction, records all
rejected attempts, and preserves a component when its search is exhausted.
Missing Y/Cb, Y/Cr, Cb/Cr or shared-syntax evidence then preserves the whole
source frame and clears every grain model. Joint failure never starts an
unbounded combination search. Frame, epoch, fraction, model and source-population
identities prevent an older candidate from being substituted.

Candidate checks distinguish unmeasured evidence from measured failure.
The complete native-lookup census includes grain, quiet, rejected and border
populations. Source-selected grain requires independent training/check support
plus native-range, population and reconstructed-source checks. The initial
policy has no qualified recovery model for the other populations: they can
pass only with exactly unchanged native base and zero synthesis. This is a
conservative initial restriction, not a claim that every changed pixel is
damaged. Useful whole-picture recovery still needs the missing population
evidence; a policy that always copies the source has not met the feature goal.

Seventy-two decision/coverage controls pass, including every first-success
location, exhausted searches, unknown checks, one-pixel quiet/border failures,
zero-strength base loss, changed source cohorts and final cross-colour failures.
A CPU replay of 36 actual native component candidates counts 74,649,600 pixel
observations. Independent source-only group counts exactly match the qualified
GPU source gates. With no invented model evidence and zero synthesis, the six
full-source endpoints pass the coverage check and the 30 changed partial bases
are rejected. This is coverage evidence, not six qualified encoder candidates.

`NVEncFilmGrainColourFidelity.h` adds common-coordinate reconstruction checks
for all three component variances, all three colour pairs and 49 Cb/Cr spatial
lags. The input is independently measured total reconstruction, not synthesis
alone or an assumed sum of base and grain variances. Controls detect incorrect
Cb/Cr coupling despite identical per-plane variances and Y/C relationships,
spatial coupling missed by a zero-lag check, quiet-source additions and invalid
or mismatched evidence. Existing aggregate colour moments cannot be subset by
dividing by an other-colour support count: mixed cohorts require recollection
on their actual intersection. All 14 sufficiently populated Cb groups in these
three development pictures are mixed; none supplies a qualified common cohort.

The complete CPU suite passes 185 Python tests in 26 suites plus 21 C++ checks.
The policy and colour helpers have no encoder output call sites.

`NVEncFilmGrainRetentionBlend.cuh` implements separate Y/Cb/Cr native blending
into distinct output storage, using the collector's exact non-fused float32
operations and nearest-even rounding. It preserves the original source and
denoised base so a retry cannot blend an already retained candidate. It rejects
layout, identity, fraction and alias errors; invalid input codes produce a
mandatory error count and cannot mark the output complete. CUDA compilation
passes. **The 31-case GPU/native comparison is prepared but still unrun** because
Emby playback owns the current GPU pause. It must be started explicitly; no
background job waits to launch it.

These are R3 prerequisites. They do not implement the complete fitted model,
native population evidence, scale/gain/DC consistency, actual moving output or
the explicit encoder selection option. R3 remains open, as do R4–R8.

The current ledger is `roadmap-r3-selector-20260922/` under the existing private
evidence root. Read its `report.json` and explicit `run-blend.py --run-manually`
resume command. The earlier `roadmap-r3-20260922/` study remains evidence below.

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
the remaining model/population evidence and integrate the qualified coverage,
source fallback and cross-colour checks before changing output. Preserve the existing detail,
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

The bounded host selector and conservative coverage/fallback path now exist.
The immediate pending check is the standalone native GPU blend, followed by
model/population evidence, consistent gains and runtime integration. Runtime
selection, temporal behaviour, compressed-output quality and quality/size/time
comparisons remain open. Ordinary Tdarr configuration is unchanged; its playback
watchdog owns the current pause. Automatic retention and FEL stay disabled.
No experiment is scheduled or left running.
