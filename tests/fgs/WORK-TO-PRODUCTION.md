# Encoder work through production

Status: **ordinary encoder and faster HDR validation deployed; retention
diagnostics and comparison preparation complete on CPU; heavy quality/size
experiments deferred until the running repair finishes**, 2026-09-10.

The goal is to finish the encoder improvements, resolve measured quality,
reliability, speed and storage costs, and integrate the validated result into
Tdarr. The evidence-based library audit and approved repairs continue alongside
that work. A completed experiment is evidence toward this goal; it does not
close the overall task.

Core `9c1664d4` completes the subsequent local/chroma recovery iteration,
exact-build quality checks, full-source measurements, actual measured and
source-savings Tdarr trials, staged artifact checks and rollback. Automatic
outputs still exceed the unchanged 10% cap on all three full sources, and
the coarse optimization still misses its target. The tested alternative
requires savings versus originals and allows more bytes than the ordinary
encoder. The storage-policy decision follows evidence of visible benefit and
quality per byte against the current production encoder.
The active ledger for that work
is `/opt/docker-apps/logs/fgs-ripple-repair-20260906/auto-retention-production-20260910/work-plan.json`.

The [repair-period preparation](FINDINGS-2026-09-10-RETENTION-PREPARATION.md)
adds precise fallback diagnostics, prepares skipping unused covariance work,
retains source/output references without copying payloads, and prepares
matched-size comparisons. CPU tests pass. The CUDA changes still need GPU
compilation and qualification; they are not a new production build.

The [September 11 evidence inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md)
recovers the July measurement campaign, Silo retention operating points,
SVT/settings studies, whole-title metrics and additional reference candidates.
Use those records to refine the next comparisons before repeating old sweeps.
Historical scores remain attached to their original runs; newly found media
requires provenance checks before entering the current comparison manifest.

## Quality requirements for further encoder work

The user's priority is source-picture fidelity and prevention of artifacts,
including ripple and banding, alongside speed and storage efficiency. Evaluate
quality independently: a size or speed improvement does not qualify a change
that introduces artifacts or fails the agreed source-detail checks. Compare
against both the source and the qualified encoder, and retain rejected
examples as regression controls.

The September 10 automatic-retention iteration addresses these questions:

- Smooth gradients, near-black detail and fades in SDR, PQ and HLG now have
  source-labelled, per-frame grain-on/off checks. No new gradient regression
  was found. SDR CAMBI evidence also records existing source/base contours;
  the results do not establish freedom from banding on arbitrary footage.
- Confirmed colour-only detail loss is fixed with independent colour noise
  and direction measurements in bilateral auto, plus restoration of source
  colour components that have no synthesized grain. Clean, noisy, asymmetric
  and moving-colour controls compare with ordinary compression at the same QP.
- Confirmed local grain overshoot is caught by finer independent source
  evidence, including quiet and weak regions excluded from coefficient
  fitting. Cuts and fades check source-fallback entry and recovery. Existing
  sharp-curve, woven-texture, synthesis and jacket regressions remain required.

The [picture findings](FINDINGS-2026-09-10-PICTURE.md) retain the demonstrated
failures, rejected prototypes, decoded comparisons, storage costs and final
qualification. Subsequent local recovery adds independent colour checks and
constrained spatial covariance fitting. Unsupported, coupled or insufficient
evidence preserves source picture before encoding. The existing model checks
still apply. These controlled optional-mode faults
do not establish additional damaged library titles or justify new downloads.

Aggregate quality scores alone do not qualify a candidate. Future local
retention changes must preserve grain balance across regions and time.
Output-preserving speed changes require decoded-pixel comparisons; the
saturated-edge shortcut has those comparisons and a separate bounded timing
study. These results complete this development iteration, not a promise of
lossless encoding or complete perceptual coverage.

The expensive qualification work stays in offline development and bounded
pilots; the existing routine Tdarr validation budget remains unchanged.

The [local recovery findings](FINDINGS-2026-09-10-LOCAL-RECOVERY.md) record the
subsequent source-population, correlated-energy and component-restoration
work, its cost measurements, rejected prototypes, completed acceptance and
the remaining storage-policy and grain-model limits.

## Established

- The intermittent ripple originated in the transcode. The corrected encoder
  is deployed in Tdarr and the repair workers.
- The fidelity branch contains the optional detail-preservation, current-model
  recovery and directional-filter changes. Controlled cases, real footage,
  full episodes, decoded HDR metadata and post-encode media assembly have
  completed their documented checks.
- The offline measured-baseline admission rejects oversized candidates while
  preserving the source. This admission is not yet an active Tdarr policy.
- The exact source/bitstream/track checks and the limitations of sampled or
  conservative measurements are recorded in the linked findings.

## Acceptance and remaining background work

| Work | Required outcome |
|---|---|
| Production integration | Complete: pinned core 497caa64 deployed; real scheduler, staged outputs, live hashes and rollback verified |
| Storage policy | Ordinary retain=0 and existing savings rules; the size-policy decision follows matched-size quality and playback evidence |
| Repeat variability | Bounded qualification complete; picture impact measured, operating policy recorded, no unsupported deterministic-output claim |
| Format coverage | Available HDR10+/P7 MEL and true-interlace paths pass; FEL/uncertain source video is preserved |
| Speed and overhead | Byte-accounting optimization and bounded DV guard retained; four-thread HDR sampling deployed after identical-metadata checks, 90 unit tests and actual-node validation/rollback |
| Further automatic-retention quality | Controlled colour/local-grain faults fixed and full-source/Tdarr acceptance complete; source preservation still costs 20–30% more bytes on measured episodes and leaves about 1% usable synthesis coverage |
| Library remediation | Running in background; repair-worker DV guards and metadata fixes installed, evidence-based later recovery remains under the download hold |

The active operational ledger is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/production-readiness-20260909/work-plan.json`.
It distinguishes completed foreground engineering from ongoing background
repairs and explicitly deferred investigations.

## Persistent constraints

The existing ripple protection and repair/audit services stay active. The hold
on new recovery downloads remains in force; a conservative header flag does
not justify a blanket redownload. Oversized or uncertain outputs retain their
input. Exhaustive development audits do not become routine per-file Tdarr
validation by accident. The unrelated FFprobe XML-printer investigation is
documented and deferred.

The 10% measured-baseline limit remains a trial setting requiring a complete
matching baseline. The ordinary production flow keeps default retention and
its existing source-relative savings policy, so it gains neither a second
encode nor a source-hash pass. Optional automatic detail retention remains
outside broad production activation. The separate source-savings review
alternative has passed actual accepted/rejected jobs and restoration without
changing the 10% trial rule.

## Evidence already completed

- [Encoder changes and cost study](FINDINGS-2026-09-08-COST.md)
- [Full source metadata, admission and repeat localization](FINDINGS-2026-09-09-TRIALS.md)
- [Post-encode integration and validator timing](FINDINGS-2026-09-09-INTEGRATION.md)
- [DV conversion, size accounting and real scheduler integration](FINDINGS-2026-09-09-READINESS.md)
- [Qualified automatic-retention recovery and edge protection](FINDINGS-2026-09-09-AUTO-RETENTION.md)
- [Colour detail, local grain, gradients and transition qualification](FINDINGS-2026-09-10-PICTURE.md)

Those reports retain their completed-study status. This broader production
work does not inherit that status.
