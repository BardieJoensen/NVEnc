# FGS encoder: current work and handoff

> **Superseded 2026-10-07.** The current single entry point (release, gate, parked work) is `~/git-repos/NVEnc-fgs-clean-source-20261006/tests/fgs/WORK-TO-PRODUCTION.md` on branch `fix/fgs-clean-source-20261006`. Everything below is history.

Updated September 28, 2026 after D85 qualification. This is the current entry
point; the [archived handoff](WORK-HISTORY-THROUGH-2026-09-28.md) preserves older
checkpoints and the detailed repair/campaign evidence map. Dated findings are
completed study records, not competing queues. Continue through checkpoints.

## Objective and current state

Deliver fast, space-efficient AV1 that preserves source detail and grain on
1080p SDR and UHD HDR, without ripple, flicker, excess grain or banding.
Automatic retention must demonstrate useful picture benefit for its actual
storage and processing cost. Aggregate VMAF or CAMBI scores cannot establish
that by themselves. Lossy encoding is not a pixel-perfect source copy.

| Item | Current state |
| --- | --- |
| Worktree | `/home/bardie/git-repos/NVEnc-fgs-fidelity`, `feat/fgs-detail-fidelity-20260908` |
| Production encoder | Ordinary `cb903a17`; retention and FEL disabled |
| Production binary SHA256 | `06dd65fc00773536f76d09eaf49b1d18032808742e8e13d8037262475c73af7c` |
| Tdarr node image | `nvenc-fidelity/tdarr-node:2.89.01-cb903a17-20260919` |
| Image identity | `sha256:3ed97a8ac3411f32de346b3d6d50e1be98cd4fbb7d306b15098fae46e01fca6e` |
| Latest qualified finite diagnostic | D85 core `dc9498cb`; explicit mechanism only, no automatic source admission |
| Diagnostic binary | `/tmp/downloads/fgs-retention-r1-r2-20260922/build-dc9498cb/nvencc` |
| Diagnostic SHA256 | `f5b3d2099767ac48a1a2989ac8c5494b72c07b3887301115c6ec4fb4e94057df` |
| Roadmap | R1/R2 complete; R3–R8 open |
| Trial state | D85 complete; both owned pauses released, no automatic experiment/restart |
| Tdarr state at closeout | Node `3PtVplgma` unpaused; two GPU transcodes/two CPU healthchecks, other limits zero |

Read actual service/node state and receipts before operational work; this is a
point-in-time record. Production has not been replaced by the experimental
branch. Do not infer permission to deploy from a passing development control.

September 12 application maintenance updated the Tdarr server and node to
2.87.01. The deployed node image is
`nvenc-fidelity/tdarr-node:2.87.01-497caa64-20260912`. It retains the ordinary
`497caa64` encoder, Opus 1.6, all four pinned custom tool binaries, the production
flow and all 25 local plugin files. The repair service and its pause ownership
were preserved. This application update does not qualify an experimental
encoder or start the deferred quality studies. See the
[upgrade and rollback record](/opt/docker-apps/logs/image-upgrades-2026-09-12.md).

## Completed evidence and remaining limits

[D81 source reconstruction](FINDINGS-2026-09-28-LOCAL-SOURCE.md) rejects tile
offsets and ramps that could previously cancel in coarse source-fallback
checks. It passes 278 Python tests / 38 suites and 55 C++ programs, independent
measurements of 661,518,312 samples, 20 native replays and ten actual encoder
jobs. AOM/dav1d agree on 320 decoded observations; ordinary SDR/HDR output stays
exact. Its two expected rejections stop before publishing the offending model.
These constructed counterexamples do not establish new library damage.

[D80 endpoint/recovery qualification](FINDINGS-2026-09-28-CONSTANT-ENDPOINTS.md)
is complete for its declared development controls. The periodic fixture's
intentional grain changes were reviewed against source pictures, causal
controls and exact same-binary repeats. A separately versioned positive records
that decision; original failures, negatives and numerical bounds are retained.
This is not a fresh full-release-gate result or independent unseen qualification.

[D82 source-only stationary/motion selection](FINDINGS-2026-09-28-COMPONENT-SELECTION.md)
adds visible border coverage and rejects a demonstrated slow-motion grain
estimation error. It passes 1,344 known-source controls and the full CPU suite
(287 Python / 39 suites, 55 C++). Necessary source evidence covers about 8–10%
of the two HDR pictures, versus D74's roughly 5%; every occupied brightness
lookup still also includes unsupported pixels. [D83's complementary-hypothesis
union](FINDINGS-2026-09-28-POPULATION-UNION.md) separates only four pixels out of
16.6 million even under optimistic assumptions. Refitting supported patches or
combining these same tests cannot fix that coverage problem.
[D84 compression-only recovery](FINDINGS-2026-09-28-COMPRESSION-RECOVERY.md)
passes two constructed 8-bit windows; both 10-bit windows retain independent
colour rejections. D85 now implements the explicit guarded source-copy/model
diagnostic; 287 Python / 56 C++ tests, GPU copy-proof controls, 160 decoded
observations and the fresh accepted/rejected cases pass. Ordinary SDR/HDR stays
exact. The complete 16-picture control rejects reuse of the frozen model at
picture eight. Next test bounded shape refresh with continuous global seed phase
and independent cross-boundary windows before longer actual encoder trials.
This does not override ordinary fallback or grant real-source/runtime admission.
Source-copy mechanics and reconstruction vetoes are qualified; useful real
automatic partial retention is still open.

The reserved qualification corpus remains unopened. The complete full-movie
amplitude regression is also unavailable: the original Play Dirty REPACK
1080p AMZN H.264-FLUX source and three generated outputs are missing. The outputs
can be rebuilt if that exact original is recovered. The user has been asked
for another source path; no download or substitute source is authorized here.
Missing-input preflight now fails before any GPU work.

## Next work, in order

1. Complete R3's bounded source eligibility, automatic decisions and integrated
   runtime. Derive decisions from actual source/rounded-base/complete-model
   measurements; missing evidence must preserve or reject, not be labelled safe.
   Start with one finite vertical case that can demonstrate useful behaviour.
2. Qualify R4 moving transitions, recovery and source/model/reference state.
   Freeze a useful candidate, then open the reserved corpus for R5 and finish
   all required release checks, including the missing full-history prerequisite.
3. Measure R6 actual video bytes, source detail, grain fidelity and controlled
   speed against ordinary FGS/plain NVENC and selected SVT references. Profile
   only useful qualified behaviour for R7.
4. Present the measured quality/space policy and test R8's actual Tdarr canary,
   bounded failure/oversize handling and rollback before deployment.

Use the [ordered roadmap](RETENTION-ROADMAP.md) and
[decision contract](RETENTION-CONTRACT.md) for exact completion requirements.
A checkpoint or a decision to leave retention off does not mark unfinished
implementation as qualified. Broader encoder research and speculative speed
work can wait. The separate QVBR16/20 undefined-AV1-level finding is recorded in
[its bounded investigation](FINDINGS-2026-09-23-AV1-LEVELS.md); production's
QVBR29/30/34/37 settings are unchanged and no equivalent-quality workaround
has been qualified.

## Local evidence and resumption

Evidence root:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`.

- `README.md`, `handoff.json` and `work-plan.json`: current continuation state.
  The JSON `live` object takes precedence over archived dated entries.
- `evidence-index.json`: hashed point-in-time inventory; its scope and timestamp
  determine freshness. Mutable ledgers can change after the inventory.
- `roadmap-r3-local-source-reconstruction-20260928/report.json`: D81 CPU,
  independent replay, build, GPU comparison, exact hashes and released pause.
- `roadmap-r4-constant-endpoints-20260928/report.json`: D80 declared scope,
  causal controls, source/visual review, repeat evidence and reference decision.
- `roadmap-r3-component-selection-20260928/report.json`: D82 source-only
  selection, rejected first version, independent prediction and complete census.
- `roadmap-r3-population-union-20260928/report.json`: D83 complementary
  hypotheses and complete actual brightness-lookup conflicts.
- `roadmap-r3-compression-recovery-20260928/`: D84 fixed-window feasibility
  and independent source/base/rendered measurements.
- `roadmap-r3-modeled-source-20260928/`: D85 explicit source-copy model path,
  complete report and build/replay/CPU/GPU receipts, retained rejections and
  released pauses.
- `roadmap-r1-r2-20260922/report.json`, `r1-completion.json`, `corpus-report.json`:
  measurement contract/collector and reserved corpus provenance. Do not inspect
  reserved grain results before a useful candidate is frozen.
- `artifact-locations.json` and dated cleanup receipts resolve retired or moved
  artifacts. Historical paths are not proof that bytes remain available.

Tests: [tiers](TIERS.md), [fixture manifest](fixtures.json),
[gate](local_gate.sh), [native engine contract](retention_engine/README.md).
Quality/bytes tools: [tradeoffs](../../tools/fgs/RETENTION-TRADEOFFS.md).
Existing studies: [campaign inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md),
[earlier colour/size work](FINDINGS-2026-09-22-COLOUR-RECOVERY.md).
Keep prior failed results and known-bad regression witnesses.

## Operational and source constraints

- The user permits pausing/unpausing Tdarr for this work. Drain active jobs,
  record pause ownership, respect Emby's independent playback watchdog and
  external maintenance, and restore the current appropriate limits/node state.
  Trials are finite and manually started; do not schedule automatic jobs.
- Heavy qualification stays offline. Do not add development studies, a second
  encode or a new source-hash pass to routine Tdarr validation by accident.
- Put large scratch on `/tmp/downloads`, retained payloads on
  `/media/storage1/tdarr-audit-evidence`, and small ledgers in the log tree.
  Check space first. Remove only completed owned artifacts after dependency
  review; retain required originals, known-bad controls and rollback. Media
  hard links share data: never modify source/fixture media in place.
- Keep FEL encoding disabled. The four FEL films' original HEVC versions were
  restored in Movies and excluded. Consult the current source-protection and
  release ledgers before touching holds, downloads, seeds or library files.
- The earlier repair/audit work is completed. The retired repair coordinator is
  stopped/disabled; do not restart it from an old plan. Library identities and
  current repair decisions come from the latest operational ledger under
  `/opt/docker-apps/logs/fgs-ripple-repair-20260906/`, not historical counts here.
- The 1,981-file/9.5-TB figure was conservative scope, not confirmed visible
  damage. Recovery requires source identity and recurrence/severity evidence;
  no blanket redownload. September 4's import move/copy issue was fixed and is
  not an open encoder task. A previous source search is not proof that no
  original can exist elsewhere.
- The historical 10% measured-baseline cap is a trial storage setting, not a
  retained-residual fraction or production allowance. Ordinary retain=0 and
  existing source-relative savings rules remain. Decide retention cost using
  R6 evidence before R8 policy; never silently trade away quality on oversize.
- FFprobe XML/AddressSanitizer remains documented and deferred at the user's
  request. The qualified JSON metadata path is used; XML work is not a
  prerequisite for retention development.
