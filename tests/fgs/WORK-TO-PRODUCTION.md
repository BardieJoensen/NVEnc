# Encoder work through production

Status: **encoder rollout complete; approved library work running**, 2026-09-09.

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

## Acceptance and remaining background work

| Work | Required outcome |
|---|---|
| Production integration | Complete: pinned core 497caa64 deployed; real scheduler, staged outputs, live hashes and rollback verified |
| Storage policy | Implemented: ordinary retain=0 and existing savings rules; optional auto retention remains a separate measured-source pilot |
| Repeat variability | Bounded qualification complete; picture impact measured, operating policy recorded, no unsupported deterministic-output claim |
| Format coverage | Available HDR10+/P7 MEL and true-interlace paths pass; FEL/uncertain source video is preserved |
| Speed and overhead | Complete for the configured rollout: tested byte-accounting optimization, bounded DV guard, existing final validator unchanged |
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
limited to the separate measured pilot.

## Evidence already completed

- [Encoder changes and cost study](FINDINGS-2026-09-08-COST.md)
- [Full source metadata, admission and repeat localization](FINDINGS-2026-09-09-TRIALS.md)
- [Post-encode integration and validator timing](FINDINGS-2026-09-09-INTEGRATION.md)
- [DV conversion, size accounting and real scheduler integration](FINDINGS-2026-09-09-READINESS.md)

Those reports retain their completed-study status. This broader production
work does not inherit that status.
