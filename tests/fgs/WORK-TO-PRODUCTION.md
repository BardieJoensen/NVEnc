# Source-grain branch: qualified and deployed

The ordinary `cb903a17` correction is qualified and deployed. Four selected
source-backed episode repairs are installed and fully validated; ordinary Tdarr
is resumed. FEL remains disabled, its original HEVC films remain restored and
excluded, and optional automatic-retention studies remain off/manual.

Use the canonical [current operational handoff](/home/bardie/git-repos/NVEnc-fgs-fidelity/tests/fgs/WORK-TO-PRODUCTION.md)
for runtime identity, qualification, repairs, pause ownership, source dependencies
and cleanup. [SOURCE-VARIANCE-20260916.md](SOURCE-VARIANCE-20260916.md) explains
this branch's correction, rejected candidates, measured tradeoffs and test changes.
The live receipt index is [closeout.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/source-variance/training-v7/closeout.json).

Completed cleanup freed 325,922,254,848 allocated bytes. Required originals,
compact regressions, current full qualified trials and unfinished review evidence
remain. Historical raw/timing outputs and retired backups are no longer present;
consult the linked cleanup receipts before attempting a replay.

## Earlier branch handoff, retained for history

The runtime names, paused states and pending work below describe the earlier
snapshot. They do not override the current operational handoff above.

# Source-supported grain correction: current handoff

September 16: isolated core `cb903a17` is being qualified for the excess-grain
correction. Installed ordinary `2fa6cfd0` remains paused and drained; no candidate
has replaced library media. FEL remains disabled. V6 `af37b958` is rejected for
source-detail loss. See [SOURCE-VARIANCE-20260916.md](SOURCE-VARIANCE-20260916.md)
and the canonical current handoff in
`/home/bardie/git-repos/NVEnc-fgs-fidelity/tests/fgs/WORK-TO-PRODUCTION.md`.

The following September 12/9 entries are historical.

# Encoder work through production

September 12 isolated hotfix: ordinary core **273723b7 is deployed**. See
[SOURCE-GUARD-20260912.md](SOURCE-GUARD-20260912.md) for source protection,
qualification, selected repairs, costs and current operations.
[FLICKER-20260912.md](FLICKER-20260912.md) retains the earlier investigation. This
worktree starts at deployed `497caa64`; the historical September 9 status below
does not describe the later fidelity branch. The canonical ongoing handoff is
`/home/bardie/git-repos/NVEnc-fgs-fidelity/tests/fgs/WORK-TO-PRODUCTION.md`.

Status: **in progress**, reconciled 2026-09-09 after the post-encode study.

The goal is to finish the encoder improvements, resolve measured quality,
reliability, speed and storage costs, and integrate the validated result into
Tdarr. The evidence-based library audit and approved repairs continue alongside
that work. A completed experiment is evidence toward this goal; it does not
close the overall task.

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

## Work still open

| Work | Required outcome |
|---|---|
| Production integration | A pinned candidate runtime, fresh encode through the actual media-processing path, deployable configuration, and rollback artifacts |
| Storage policy | An integrated oversized-file decision with measured runtime cost; estimates must not be presented as an exact old-encoder size cap |
| Repeat variability | Establish its picture-quality impact and fix a demonstrated cause or establish a defensible operating policy; matching a few hashes is insufficient |
| Format coverage | Exercise the candidate on available HDR10+, interlace and metadata paths; retain source formats that cannot be preserved |
| Speed and overhead | Measure the final configured pipeline against production and fix demonstrated bottlenecks without discarding fidelity protection |
| Library remediation | Continue the approved repairs and contextual watchability audit, keeping later recovery decisions grounded in severity and recurrence |

The active operational ledger is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/production-readiness-20260909/work-plan.json`.
It must stay open while a critical implementation or acceptance item remains.

## Persistent constraints

The existing ripple protection and repair/audit services stay active. The hold
on new recovery downloads remains in force; a conservative header flag does
not justify a blanket redownload. Oversized or uncertain outputs retain their
input. Exhaustive development audits do not become routine per-file Tdarr
validation by accident. The unrelated FFprobe XML-printer investigation is
documented and deferred.

The current 10% measured-baseline limit is a trial setting. An exact cap needs
a complete matching baseline; sampling cannot remove that requirement. Its
operational cost and behavior must be addressed before treating it as the
normal production policy.

## Evidence already completed

- [Encoder changes and cost study](FINDINGS-2026-09-08-COST.md)
- [Full source metadata, admission and repeat localization](FINDINGS-2026-09-09-TRIALS.md)
- [Post-encode integration and validator timing](FINDINGS-2026-09-09-INTEGRATION.md)

Those reports retain their completed-study status. This broader production
work does not inherit that status.
