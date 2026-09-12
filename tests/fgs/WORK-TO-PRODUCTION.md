# FGS encoder and library repair: current work and handoff

Status: **qualified finer-source hotfix deployed; ordinary repairs resumed;
full library follow-up audit in progress. Automatic-retention trials remain
deferred and manual-start only.** Updated 2026-09-12.

Production Tdarr and the repair worker now use isolated core `ef5c61fe`, binary
SHA-256 `d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b`.
The exact image is `nvenc-fidelity/tdarr-node:2.87.01-ef5c61fe-20260912`, image ID
`sha256:218540effe6149030631445914c8f35c6e81090326a8e4bbca55d0b57c3f50e4`.
The prior `273723b7` deployment is retained for rollback. The production flow,
25 local plugins, worker limits and routine validation are unchanged; all four
custom runtime tools were verified. Both routine monitors passed for the installed binary, and two
ordinary repair workers were observed after releasing the audit-owned hold.
Pause ownership and Emby playback yield remain in place.

The audit demonstrated a gap in `273723b7`: a small clean source patch inside
a larger textured analysis block could still receive strong grain. The deployed
fix adds finer 16x16 luma / 8x8 colour source evidence while preserving the
existing model-fitting region, ripple/syntax guards and temporal recovery.
It adds no extra pixel reads from GPU global memory, kernel launches or host
synchronization. Both bit depths pass all ten mixed-source controls, including
the four small-region cases that reject the previous deployed build.

[The finer-source qualification](FINE-SOURCE-GUARD-20260912.md) records the
source controls, full-frame periodic review, unchanged quality canary, five
exact-image cases, HDR10 signalling check, installed repairs and limitations.
[The full audit](FULL-AUDIT-20260912.md) records scope, evidence-based repair
priorities, tools and outstanding coverage. The local
[qualification](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/qualification.json),
[rollout](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/rollout-record.json)
and [operational restoration](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/final-additional-amphibia-operational-state.json)
pin the exact tested and installed artifacts.

Five files were repaired from retained originals during this audit: Regular
Show S1E2 with then-current `273723b7`, plus Steven Universe S3E22/S1E23 and
Amphibia S1E18/S1E11 with `ef5c61fe`. The latter four are repeated repairs of existing
selections. The [37 distinct selected-file results](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/current-selected-repairs.csv)
now total +1.620% versus their recorded pre-flicker-repair containers. This
selection history is neither a complete damaged-file count nor whole-file
perceptual clearance. All original and superseded files remain available.

The two Steven source trials add 0.136% and 0.147% video-only bytes versus the
previous `273723b7` trials; single-run encode times rose 0.83% and 0.64%.
The actual installed containers are +13.24 MB and +4.87 MB versus the older
`3778447e` repairs. Amphibia S1E18 grows 40.85 MB (+20.89%) versus its older
repair; S1E11 grows 49.48 MB (+25.96%) versus its earlier partial-fix build.
These comparisons use different baselines and must not be conflated
or extrapolated across the library. Heavy audit tests were not added to Tdarr's
per-file validation.

There is no universal fidelity certificate. Source review shows a fine-texture
tradeoff at shared brightness levels: protecting clean artwork can also reduce
some genuine fine grain elsewhere. The periodic regression was separately
reviewed against all 3,600 source frames; the original change alert, old
positives and failing negatives remain. No numeric detector limit was relaxed.
Lossy base texture, very thin source regions, optional retention cost and actual
Apple TV/Infuse playback remain distinct limitations or deferred work.

The combined fidelity branch includes the new core at `704a8f8f`; its exact
`03eb4796` build compiled and passed the CPU suite. That broader binary is
**not deployed**. Later `e4ed723f` changes only audit tools: low storage now
pauses the finite run without consuming pending files as media errors, and
whole-movie timestamp matching avoids a quadratic scan. Twenty-eight audit CPU
tests and retained real-movie alignment checks pass. Audit-only `708ae7ca`
adds qualified explicit BT.601 mapping and fixes rounded window boundaries.
The active helpers are pinned in `tools-v5/`; 31 Python tests, eight native CLI
tests, display controls and real BT.601/unchanged SDR/PQ comparisons pass.
Missing SD colour metadata remains a coverage limit. The finite v5 continuation
reuses 86 completed results, queues 5,160 original versions and freshly pins 17
replacements. Earlier results remain immutable and keep their method identities.

Read the [active audit ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/work-plan.json)
and [published coverage](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/published/status.json)
for current jobs and timestamps. The original inventory has 5,578 videos,
including 5,263 AV1. The finite catch-up queues cover replacements observed
at their recorded times. Header and sampled decoded/source coverage remain
unfinished. No diagnostic flag authorizes mass downloads.

The earlier [source-guard report](SOURCE-GUARD-20260912.md),
[flicker report](FLICKER-20260912.md) and `grain-recovery-followup-20260912/`
describe their named older builds and dated qualifications. Their 36-file counts
and earlier production pins are historical. The source-recovery download hold
remains in force. No new download or optional retention campaign was started.

This is the canonical entry point for resuming this project. Read the current
state and next steps here before using an older findings report or work ledger.
Older reports describe their named builds and dates; a historical `complete`
status does not close the present goal. Live queues, binaries and file
identities must be checked again when work resumes. No chat history is required
to find the working state, evidence and remaining tasks from this document.

The working checkout is `/home/bardie/git-repos/NVEnc-fgs-fidelity`, branch
`feat/fgs-detail-fidelity-20260908`. Other NVEnc worktrees under `git-repos` are
not necessarily on this branch. The separate deferred-retention preparation ledger is
[/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/work-plan.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/work-plan.json).

The goal is to finish the encoder improvements, resolve measured quality,
reliability, speed and storage costs, and integrate the validated result into
Tdarr. The evidence-based library audit and approved repairs continue alongside
that work. A completed experiment is evidence toward this goal; it does not
close the overall task.

The user's original aim is fast, space-efficient CUDA/NVENC AV1 with grain
preservation comparable in intent to an SVT-AV1 grain workflow, for both UHD/HDR
and ordinary 1080p SDR. Preserving source detail and avoiding ripple, banding,
colour loss and unstable grain matter as much as throughput and size. Higher
average VMAF alone does not justify a storage increase. Demonstrate visible
benefit and compare at similar actual video-byte budgets before choosing an
automatic-retention allowance.

Core `9c1664d4` completes the subsequent local/chroma recovery iteration,
exact-build quality checks, full-source measurements, actual measured and
source-savings Tdarr trials, staged artifact checks and rollback. Automatic
outputs still exceed the unchanged 10% cap on all three full sources, and
the coarse optimization still misses its target. The tested alternative
requires savings versus originals and allows more bytes than the ordinary
encoder. The storage-policy decision follows evidence of visible benefit and
quality per byte against the current production encoder.
The qualification ledger for that optional build
is `/opt/docker-apps/logs/fgs-ripple-repair-20260906/auto-retention-production-20260910/work-plan.json`.

The [repair-period preparation](FINDINGS-2026-09-10-RETENTION-PREPARATION.md)
adds precise fallback diagnostics, prepares skipping unused covariance work,
retains source/output references without copying payloads, and prepares
matched-size comparisons. CPU tests pass. The integrated branch now compiles with the source-guard work. These optional
covariance/model changes still need deferred GPU output-preservation and quality
qualification; compilation does not make them the ordinary production build.

The [September 11 evidence inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md)
recovers the July measurement campaign, Silo retention operating points,
SVT/settings studies, whole-title metrics and additional reference candidates.
Use those records to refine the next comparisons before repeating old sweeps.
Historical scores remain attached to their original runs; newly found media
requires provenance checks before entering the current comparison manifest.

The [CPU model-reuse correction](FINDINGS-2026-09-11-MODEL-HOLD.md) replaces a
sparse brightness-grid comparison that could miss narrow strength-curve
changes. The full CPU suite and an archived Ju-on curve reproduction pass.
The combined branch still needs GPU qualification, including temporal update
stability; this intentional model-decision change is separate from the
covariance optimization's output-preservation checks.

The [joint fallback analysis](FINDINGS-2026-09-11-FALLBACK-PROFILES.md) joins
checks on the same frame across six saved full-episode logs. It distinguishes
overlapping colour/local failures from source preservation after successful
covariance recovery, and selects six short diagnostic targets plus the existing
jacket regression. The report tests pass; new media work remains deferred.

## Build and deployment state

| Revision | Role | State at this handoff |
| --- | --- | --- |
| `e2c3a99d` | First 24-fit recovery hold | Superseded; retained partial-fix baseline and rollback |
| `3778447e` | Prior recovery-ramp hotfix | Superseded ordinary baseline and rollback; residual limits retained in historical reports |
| `273723b7` | Coarse source-quiet and constant-colour protection | Superseded; retained qualified baseline and rollback |
| `ef5c61fe` | Finer independent source protection | Deployed after mixed-source, whole-frame periodic/source review, exact-image, HDR10 and installed-file qualification |
| `e4ed723f` | Audit storage and alignment hardening | 28 CPU tests and full retained-movie timestamp check pass; no encoder change |
| `708ae7ca` | Audit BT.601 and window-boundary corrections | 31 Python tests, eight native CLI controls, display controls and real-file comparisons pass; diagnostic only |
| `497caa64` | Earlier ordinary encoder, `retain=0`, bilateral | Retained comparison/rollback baseline; superseded in production |
| `9c1664d4` | Optional automatic retention | Quality/operational qualification recorded; not broadly enabled; all three complete-source outputs exceed the unchanged 10% trial cap |
| `5450a4fc` | Precise fallback traces and skipping unused covariance work | CPU checks and integrated CUDA compilation passed; separate output-preservation checks deferred |
| `3ac80ceb` | Exact strength-curve comparison for model reuse | Full CPU suite and archived curve reproduction passed; intentional model decisions need GPU/temporal qualification |
| `57c0e8ae` | Joined diagnostic reports and focused target selection | 13 diagnostic and seven tradeoff tests passed; six saved logs reanalyzed; no encoder code changed in this step |

Subsequent documentation commits do not constitute a new encoder qualification.
The preparation ledger records current source hashes and completed CPU commits;
the rollout and qualification records retain the baseline revisions. The two
measured baseline binaries are pinned in
[comparison-manifest.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/comparison-manifest.json):

- Ordinary `497caa64`: SHA-256
  `bb7e75cbcb9097f1f1c7ac3347e7193c74caa6c7d57db1c3c77348cc27daf144`.
  Its retained artifact is `production-readiness-20260909/bin/nvencc-fidelity-497caa64`
  under the repair log root. The host build input now contains `ef5c61fe`;
  do not use that mutable path as the old comparison baseline.
- Optional `9c1664d4`: SHA-256
  `8dff824c8d7360adac294f05e7c6032770f8594cf1c3b63961f50a854e3b0fec`.
  Its retained path is under `auto-retention-production-20260910/bin/` in
  the repair log root.
- Ordinary flow `/opt/docker-apps/configs/tdarr-flow/flows/AV1NVENCflow1.json`:
  SHA-256 `6cebd7cb63d540f61d9c142a9728ed4fbf0edaeaa3312eacae9ae7503126c7fe`,
  verified again on September 12. Hashes are recorded identities, not a promise
  that a future installation is unchanged.

The faster four-thread HDR validator is already deployed. Its 90 checks and
measured sample timing are recorded in the September 10 ledger; this does not
add the expensive development studies to routine Tdarr validation. The repair
coordinator owns the current Tdarr pause. Isolated trial containers are stopped.

The September 12 application upgrade preceded this encoder rollout; its initial
encoder image is historical. The current runtime is pinned above.

## What happens next

**Retention GPU trials are prepared, not running or scheduled to start automatically.**
The user explicitly confirmed manual start only: wait for the repair to finish
and resume the trials when requested. Do not install a timer or trigger that
starts them when the repair completes.
The user's resource decision is to finish the current ripple repair before the
optional retention studies. The later authorization permits focused defect
comparisons and this full audit during the repair; it does not start that
deferred campaign. The
latest observed state still has two active repair workers; use the live status
when resuming, not this count or an old countdown. A failed or stalled service
does not establish repair completion.

1. Read this document and the current preparation ledger. Check the working
   branch/changes, live repair queue, worker state and pause ownership. Preserve
   the running repair/audit work and playback yield. Resolve the resource
   condition before starting the deferred media work.
2. Recheck retained source identities and hashes; build and pin the exact
   candidate binaries in isolated build directories. Use `5450a4fc` separately
   from `3ac80ceb` to distinguish the covariance optimization from intentional
   temporal model changes. The existing comparison manifest still pins
   `497caa64` and `9c1664d4`; preserve those arms and add qualified current
   ordinary `ef5c61fe` explicitly. It must not silently represent a newer build.
3. Start with the six targets in
   [pilot-selection.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/fallback-profiles-20260911/pilot-selection.json)
   plus the existing jacket regression, about 270 seconds of source per arm.
   Verify source-frame alignment and reproduce the historical target with the
   qualified baseline. The initial context is at least ten nominal seconds;
   extend it if a cold excerpt does not reproduce the full-run model state.
4. Use precise source-reason masks and joined checks to identify the useful
   model improvements. South Park's held-colour rejections overlap heavily
   with local mismatch; the HDR episode often preserves source even after a
   successful covariance fit. Legacy logs cannot identify every later reason.
   Improving model coverage must continue to satisfy the picture checks.
5. Qualify actual encoded output with the existing full GPU gate and relevant
   fidelity, local/chroma, temporal, gradient and HDR regressions. Output
   preservation for the speed change and temporal stability for the model-hold
   correction are separate claims. Check labelled negatives as well as passing
   controls. Do not regenerate a positive baseline merely to accept a candidate.
6. Execute the prepared seven-window/70-command quality/size comparison,
   refining operating points until actual video sizes are comparable. Compare
   ordinary FGS, auto and plain AV1; calibrate bounded SVT controls. Pin metric
   definitions, inspect worst scenes, and review grain/detail at playback speed.
   Old campaigns narrow this work; they do not qualify the current build.
7. Measure speed under controlled conditions with pause time accounted for.
   Use the measured quality/byte/time results to resolve retention policy, then
   qualify the chosen build in the isolated real Tdarr flow with staged output
   and rollback checks before production integration. Existing ordinary
   retention and source-savings rules remain the live policy meanwhile.

The overall task remains open while required qualification, retention-cost
resolution or approved library repairs remain outstanding. A clean CPU suite,
completed pilot, or a deployed ordinary encoder is only one part of that goal.

## Where the local state and evidence live

The repair log root is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906`. Paths in this table are
relative to that root unless shown as absolute. These are local records and
private media references; they are not all stored in Git. Additional filenames
in a row share the directory of that row's first path.

| Path | What it answers |
| --- | --- |
| `full-temporal-audit-20260912/work-plan.json`, `OPERATIONS.md`, `published/status.json` | Current full-audit jobs, exact file versions, confirmed findings versus candidate measurements, trial holds and required finish |
| `full-temporal-audit-20260912/inventory.json`, `headers/status.json`, `decoded-v5/status.json`, `resume-v5-20260912/plan.json` | Explicit current-file snapshot, full displayed-header stage and bounded full-image/frame source review |
| `full-temporal-audit-20260912/current-selected-repairs.json`, `installed-vc1-verification.json`, `strict-installed-steven-verification.json`, `strict-installed-amphibia18-verification.json`, `strict-installed-amphibia11-verification.json` | 37-file selection history and all five audit installations, including independent decode, video-packet and retained-stream/source proofs |
| `full-temporal-audit-20260912/qualification.json`, `rollout-record.json`, `final-additional-amphibia-operational-state.json` | Qualified ef5c61fe core, deployed image/runtime identities, monitors and restored repair admission |
| `full-temporal-audit-20260912/resume-v5-20260912/plan.json`, `audit-tools-v5-qualification.json`, `storage-pause-20260912/evidence-relocation.json` | Reused completed evidence, qualified diagnostic corrections, pending checks, replacement catch-up and byte-verified evidence relocation |
| `full-temporal-audit-20260912/published/repair-priorities.csv` | Preliminary human-reviewed repair priorities and source availability, separate from unreviewed diagnostic ranks |
| `retention-prep-20260910/work-plan.json` | Current unfinished encoder objective, constraints, source hashes, completed CPU work and deferred steps |
| `retention-prep-20260910/comparison-manifest.json`, `comparison-plan.json` | Original-source and binary pins, seven quality/size windows and 70 planned commands; none executed by this preparation |
| `retention-prep-20260910/fallback-profiles-20260911/` | Six-log joins, 459,396 decisions, exact diagnostic target profiles, source/log hashes and verification |
| `retention-prep-20260910/model-hold-audit-20260911/` | CPU suite, old-code failing reproduction and archived Ju-on/curve evidence |
| `retention-prep-20260910/existing-log-analysis.json`, `chroma-equivalence.json`, `cpu-suite.json` | Original six-log analysis and prior 40,000-decision colour equivalence/CPU checks |
| `retention-prep-20260910/existing-campaign-inventory-20260911.json` | Older campaign/report inventory and 42 media candidate files; candidates have not been admitted as current references |
| `retention-prep-20260910/reference-retention.json` | The 25 retained artifacts, recorded hashes/identities and hard-link storage accounting |
| `auto-retention-production-20260910/work-plan.json`, `qualified-candidate-9c1664d4.json` | Optional-build quality, full-source costs, actual Tdarr acceptance, unresolved storage cost and pointer to current preparation |
| `auto-retention-production-20260910/foreground-final-state-9c1664d4.json` | Recorded live-state restoration, paused ordinary node and stopped trial containers |
| `production-readiness-20260909/work-plan.json`, `production-rollout-result.json`, `production-rollback-preflight.json` | Ordinary rollout, exact runtime/flow, real scheduler evidence and rollback |
| `status.json`, `progress.md`, `ready-manifest.json` | Current approved repair progress and retained-source work; do not sum unrelated counters into a damage estimate |
| `tdarr-pause-ownership.json`, `source-recovery-hold.json`, `watchability-policy.json` | Pause owner, download hold and recorded review policy |
| `evidence/watchability/`, `reports/watchability-measurements.csv` | Contextual recurrence/severity audit; measurements need their coverage and viewing limits |
| `evidence/grain-syntax/` | Syntax findings, current scans, unresolved entries and repair receipts; syntax accounting is separate from watchability |
| `evidence/jacket-34m05/`, `evidence/movie-extent/`, `evidence/decoded-scenes/` | Original defect and scene/extent review evidence |

Read-only operational checks can start with:

```sh
git -C /home/bardie/git-repos/NVEnc-fgs-fidelity status --short --branch
systemctl --user status fgs-ripple-repair.service fgs-ripple-watchability-audit.service
```

The coordinator and audit scripts are under `/opt/docker-apps/scripts/`:
`fgs-ripple-coordinator.py`, `fgs-ripple-repair.py`, and
`fgs-ripple-watchability-audit.py`. The separate syntax-audit service/timer is
documented in
[the operations guide](/opt/docker-apps/docs/fgs-repair-and-audit.md).
That September 8 guide's encoder revision and numerical counts are historical;
use this handoff and live state for current deployment and queue decisions.

### Retained media, archives and scratch space

The user explicitly requested space care and authorized moving completed work
to cold storage or cleaning it up. Check `/`, `/opt/docker-apps`, `/home` and
`/tmp/downloads` separately; they are different filesystems. Put large new
scratch outputs on `/tmp/downloads`, and retained experiment payloads on
`/media/storage1/tdarr-audit-evidence`. Keep small ledgers and indexes in the
application log tree. Archive completed work after checking active references,
verify copied bytes, and preserve evidence paths and regression controls.
The September 12 cleanup is recorded in
[the storage ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/storage-cleanup-20260912/README.md).
Its receipt identifies original and archive paths, file hashes, metadata and
any ownership changes. Consult it before removing an archive or treating a
relocated artifact's new inode as evidence of changed media content.

- `/media/merged-storage/validation-fixtures/nvenc-fgs/v1` holds the pinned
  source clips and labelled positive/negative controls in
  [FIXTURES.md](FIXTURES.md) and [fixtures.json](fixtures.json).
- `/media/merged-storage/validation-fixtures/nvenc-fgs/retention-20260910`
  and `/tmp/downloads/fgs-retention-prep-20260910/retained` hold the recent
  references. Hard links share data: never modify these media in place. The
  five primary originals keep 15,126,585,999 bytes alive without copying their
  payloads. Unlinking an old name does not release those blocks while another
  link remains. Recorded hashes need rechecking before new experiments.
- `/tmp/downloads/fgs-retention-prep-20260910` holds preparation/reproduction
  scripts. `/tmp/downloads/fgs-auto-retention-production-20260910` holds recent
  full-source outputs and logs. The ledgers bind their exact identities; a
  path's continued existence alone does not establish validity.
- `/media/merged-storage/media/test-encodes` and
  `/tmp/downloads/tdarr-temp` contain older campaign artifacts. Use the
  [campaign inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md) for the Silo,
  SVT, settings, HDR and whole-title reports rather than guessing from filenames.
  Some old sources are missing or have changed at the same path. The
  uncorrected Planet Earth timing sample is excluded.
- Persistent gate tools/builds are under `${FGS_GATE_CACHE:-~/.cache/fgs-gate}`;
  [TIERS.md](TIERS.md) explains exact-commit builds and pinned dependencies.
  Git stores code and findings, not the private media or all raw results.
  Preserve the referenced artifacts when cleaning scratch or test directories.

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
| Production integration | Qualified narrow core ef5c61fe deployed; runtime, source/periodic/HDR10 checks, installed repairs and rollback verified |
| Storage policy | Ordinary retain=0 and existing savings rules; the size-policy decision follows matched-size quality and playback evidence |
| Repeat variability | Bounded qualification complete; picture impact measured, operating policy recorded, no unsupported deterministic-output claim |
| Format coverage | Available HDR10+/P7 MEL and true-interlace paths pass; FEL/uncertain source video is preserved |
| Speed and overhead | Byte-accounting optimization and bounded DV guard retained; four-thread HDR sampling deployed after identical-metadata checks, 90 unit tests and actual-node validation/rollback |
| Further automatic-retention quality | Controlled colour/local-grain faults fixed and full-source/Tdarr acceptance complete; source preservation still costs 20–30% more bytes on measured episodes and leaves about 1% usable synthesis coverage |
| Library remediation | Running in background; repair-worker DV guards and metadata fixes installed, evidence-based later recovery remains under the download hold |

The active operational ledger is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/work-plan.json`.
It distinguishes completed foreground engineering from ongoing background
repairs and explicitly deferred investigations.

## Persistent constraints

The existing ripple protection and repair/audit services stay active. The hold
on new recovery downloads remains in force; a conservative header flag does
not justify a blanket redownload. Oversized or uncertain outputs retain their
input. Exhaustive development audits do not become routine per-file Tdarr
validation by accident. The unrelated FFprobe XML-printer investigation is
documented and deferred.

The user explicitly chose to continue encoder work without the FFprobe
XML/AddressSanitizer investigation. Keep its findings documented; it is not a
prerequisite for the next retention trial. The JSON metadata path and its
qualification are recorded in the later integration/local-recovery reports.

The earlier 1,981-file/9.5-TB figure described a conservative repair scope,
not individually confirmed visible damage. Subsequent title/source identities
and audit coverage matter. Review recurrence, severity and watchability before
new recovery selections; prior source searches do not establish that no
original can exist at another path or later date. The separate September 4
import move-versus-copy/seeding incident was fixed and is not an open encoder
task. Keep those histories distinct when resuming library recovery.

The 10% measured-baseline limit remains a trial setting requiring a complete
matching baseline. The ordinary production flow keeps default retention and
its existing source-relative savings policy, so it gains neither a second
encode nor a source-hash pass. Optional automatic detail retention remains
outside broad production activation. The separate source-savings review
alternative has passed actual accepted/rejected jobs and restoration without
changing the 10% trial rule.

## Evidence and implementation index

Use the relevant report for exact commands, build identities, rejected
prototypes, numerical results and limitations. Dates indicate historical
context, not continuing deployment. In particular, July hypotheses and initial
coarse-grain limits are not conclusions about today's corrected encoder.

| Topic | Entry points |
| --- | --- |
| Tests, coverage and retained controls | [Test README](README.md), [tiers](TIERS.md), [fixtures](FIXTURES.md), [fixture manifest](fixtures.json), [full local gate](local_gate.sh) |
| Grain inspection, HDR/display assumptions and visual review | [Review tools](../../tools/fgs/README.md), [display qualification](FINDINGS-2026-09-07-DISPLAY.md) |
| Original analyzer work and historical limits | [July 17](FINDINGS-2026-07-17.md) |
| Sampling correction, quality/size and texture-substitution history | [July 29 performance](FINDINGS-2026-07-29-PERFORMANCE.md), [July 30 texture](FINDINGS-2026-07-30-TEXTURE.md), [July 31 model statistics](FINDINGS-2026-07-31-MODEL-STATS.md) |
| Recovered historical campaigns | [September 11 inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md), [July campaign plan](/opt/docker-apps/docs/fgs-measurement-campaign.md), [historical open questions](/opt/docker-apps/docs/fgs-open-questions.md) |
| Reliability and source/detail behavior | [September 7 hardening](FINDINGS-2026-09-07-HARDENING.md), [September 8 fidelity](FINDINGS-2026-09-08-FIDELITY.md) |
| Initial retention cost and repeat variability | [Cost](FINDINGS-2026-09-08-COST.md), [repeatability](FINDINGS-2026-09-08-REPEATABILITY.md) |
| Full-source checks, admission, repeats and deferred XML issue | [September 9 trials](FINDINGS-2026-09-09-TRIALS.md) |
| Post-encode assembly and validator time | [Integration](FINDINGS-2026-09-09-INTEGRATION.md) |
| Ordinary production, DV, byte accounting and real scheduler | [Readiness evidence](FINDINGS-2026-09-09-READINESS.md), [rollout/rollback guide](../../tools/fgs/TDARR-ROLLOUT.md), [repair DV handling](../../tools/fgs/REPAIR-DOVI.md) |
| Initial automatic-retention recovery and edge protection | [September 9 auto retention](FINDINGS-2026-09-09-AUTO-RETENTION.md) |
| Colour detail, local grain, gradients, cuts and fades | [September 10 picture](FINDINGS-2026-09-10-PICTURE.md) |
| Current optional recovery, coupled colour, costs and qualification | [Local recovery](FINDINGS-2026-09-10-LOCAL-RECOVERY.md) |
| Measured size limit and separately tested source-savings alternative | [Measured pilot](../../tools/fgs/TDARR-PILOT.md), [source-savings review](../../tools/fgs/TDARR-SOURCE-SAVINGS.md) |
| Retained references, precise traces and prepared comparisons | [Preparation](FINDINGS-2026-09-10-RETENTION-PREPARATION.md), [diagnosis/planning/comparison usage](../../tools/fgs/RETENTION-TRADEOFFS.md) |
| CPU model-reuse correction and archived reproduction | [Model hold](FINDINGS-2026-09-11-MODEL-HOLD.md), [CPU regression](model_hold_test.cpp) |
| Overlapping fallback checks and six diagnostic targets | [Fallback profiles](FINDINGS-2026-09-11-FALLBACK-PROFILES.md), [analyzer](retention_diagnostics.py) |
| Repair/source matching, syntax audit and review limitations | [Operations guide](/opt/docker-apps/docs/fgs-repair-and-audit.md), live state/evidence map above |

Those reports retain their completed-study status. This broader production
work does not inherit that status. When another stage completes, update this
handoff and the current ledger with the exact revision/binary, validation,
remaining work and any deployment change; keep the underlying reports intact.
