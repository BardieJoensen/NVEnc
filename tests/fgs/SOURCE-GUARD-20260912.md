# Source-quiet grain protection, September 12

Status: **ordinary core `273723b7` deployed**, selected Lost Tapes repair verified
and ordinary repair resumed, 2026-09-12 17:14 UTC. The broader fidelity branch
is separate and its retention campaign remains deferred. Read the live receipts
when resuming; this is a recorded snapshot.

The recovery hold and ramp in `3778447e` removed the strongest reported flashes,
but longer weak pulses remained on clean Lost Tapes artwork. An 8-bit trial also
failed. Noisy background samples can train a brightness-dependent grain model
that is unsuitable for clean foreground pixels at the same brightness. This
spatial problem supplements the temporal restart problem; the header-versus-plan
checks did not establish AV1 reference-state corruption.

The new guard checks original-source luma and colour blocks independently of
grain-model training. It bounds synthesis over each conflicting brightness
range and retains the corresponding original residual in all planes. It
includes valid partial edge blocks. Exactly constant source colour over active
luma is protected even outside recovery, covering neutral opening lettering
over a textured background. Constraints have their own hold and gradual release;
the unscaled model cache and existing unsafe-model rejection remain independent.

The AV1 strength curve is bounded at every fixed-point lookup entry. CPU checks
include 600 randomized envelopes at both AV1 point-count limits. Six mixed-source
cases cover interior artwork, partial bottom edges and constant colour over
textured luma, each at 8 and 10 bits. They require genuine background synthesis
to remain; turning off grain everywhere cannot pass. Raw-filter and conventional
AV1 controls distinguish invented synthesis from ordinary compression error.

The ordinary QVBR/profile and Tdarr validation flow are unchanged. These expanded
developer tests do not run for every library transcode.

## Evidence and decisions

The durable local root is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/grain-recovery-followup-20260912/`.
Media references and machine-specific receipts are local, not public test media.

| Record relative to that root | Purpose |
| --- | --- |
| `INVESTIGATION.md` | Causal investigation, rejected prototypes, source and codec controls |
| `build.json`, `runtime-build.json`, `runtime-label-verification.json` | Exact ordinary core, binary, image and labels |
| `constant-full-gate/` | Full original run, including the intentional periodic baseline failure; never relabeled |
| `constant/initial-trials-status.json` | Real-source and mixed-source regressions, old failing controls |
| `constant/native-headers/summary.json` | Complete displayed headers for Lost Tapes and selected excerpts |
| `constant/transition-review/report.json` | All 38 Lost Tapes transitions; 1,156 aligned frames, 16 neighbours on each side |
| `constant/full-opening-regression/report.json` | Sixteen native-colour title frames; source SD 0, old 4.828, candidate 0.170 |
| `constant/source-window-review.json`, `constant/visual-review.json` | Source-aligned residual windows and reviewed pictures |
| `constant/weak-source-review.json` | Smiling Friends and Steven Universe residuals; no additional full replacement selected from these windows |
| `constant-periodic-source-review.json` | All 3,600 Gentlemen source frames; unchanged grain schedule, improved mean source error |
| `constant-periodic-critical-scenes.json`, `constant-periodic-visual-review.json` | Original jacket/ripple assertions and worst-frame still review |
| `periodic-baseline-receipt.json` | Separately retained source-reviewed positive; old positives and negatives retained |
| `periodic-repeat-measurements.json`, `periodic-repeat-source-review/` | Same-build low-amplitude repeatability investigation |
| `constant-container-smoke.json` | Five real-source checks in the exact final labelled Tdarr image |
| `constant-periodic-final/reports/report.json` | Fresh complete long regression with the reviewed reference and corrected eligibility |
| `constant/performance/summary.json` | ABBA old/new timing and video-container sizes on two sources |
| `qualification.json`, `rollout-record.json` | Final evidence disposition and actual deployment; absent/incomplete means pending |
| `current-selected-repairs.json`, `current-selected-repairs.csv` | Consolidated 36-file list with unchanged-identity verification receipts; latest aggregate +0.791% |
| `repair-selection.json`, `remediation-verification.json` | Source-justified selection and independently verified installed result |
| `OPERATIONS.md`, `work-plan.json` | Current services, pause ownership, runtime monitoring, next work |

Whole-file review found important counterexamples that the initial excerpts
missed. The first whole-frame fallback was too costly. A narrower colour policy
then degraded encoded luma on the original Taxi canary despite identical raw
luma, because colour restoration changed bit allocation. That prototype was
rejected. The current ordinary candidate keeps the original canary result.
A subsequent full-file review found the opening-title colour gap; that earlier
candidate was also rejected before deployment. Their outputs and failures remain.

## Repeatability of the periodic measurement

The intentional source-guard change was reviewed against all 3,600 source frames
before pinning a separate positive. A same-binary repeat then differed in the
normalized red/blue correlation vector on frame 214, where all sampled patch
amplitudes were below 0.066 of an 8-bit display code. Normalized covariance can
vary strongly when a quantized residual is almost zero.

The detector now records such changes without failing solely on their normalized
direction while both encodes' strongest patch RMS is within the existing 0.15
absolute amplitude margin. This is an explicit change to correlation eligibility,
not a claim that the original failed run passed. Amplitude, scheduling, temporal,
source-patch and ripple limits remain unchanged. The strongest patch in either
encode determines eligibility, preventing a localized or disappearing pattern
from being hidden by mean amplitude. Regression tests retain those counterexamples,
and the real damaged mesh must still fail. This fixture-specific repeatability
margin is not a universal visibility or HDR threshold.

## Scope and remaining limits

The current Lost Tapes transition review measures peak added grain in checked
source-flat full blocks of 0.259/0.237/0.218 native 8-bit-equivalent Y/U/V codes.
The earlier seven-frame artwork pulse falls from patch SD 1.77 to 0.068 against
source SD 0.21. These measurements support the known repair; they do not certify
every frame of every title or every player's display behavior.

Ordinary lossy AV1 can still attenuate fine grain and leave compression texture.
The guard uses statistical source blocks and a global brightness curve. Very
thin partial strips remain outside its block evidence. Persistent weak, nonzero
chroma-only retention outside recovery remains optional automatic-retention
policy, not a default promise to reproduce every source texture. Server-side
independent decoding and still review do not constitute Apple TV playback testing.

The historical 5,293-file inventory has not received whole-file source-referenced
temporal clearance. Header flags and one sampled scene do not authorize mass
downloads. The prior 36 selected repairs and their source decisions remain in
`../amphibia-flicker-fix-20260912/`; follow-up replacement is separately recorded.

The broader automatic-retention quality/size campaign remains deferred and
manual-start only. Preserve the historical `497caa64`, `3778447e` and optional
`9c1664d4` measurements. Add the qualified current ordinary build as a separate
baseline when that campaign resumes; never relabel historical results.

The installed Lost Tapes file is 14.627% larger (+32.822 MB) than the
previous repair. ABBA tests show no measured slowdown on the two sampled sources;
video-container growth is 20.95% for Lost Tapes and 3.56% for Gentlemen. These
are case-specific measurements, not a library estimate. See OPERATIONS.md.
