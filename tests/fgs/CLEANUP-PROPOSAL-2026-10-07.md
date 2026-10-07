# Cleanup proposal (2026-10-07): nothing has been deleted

FGS work is paused. Every git worktree is clean, and nothing below has been run. Archiving a branch keeps its commits reachable under `refs/archive/<date>/`, so it loses no history. The scratch proposal keeps every source copy, pinned binary, gate input and small receipt, and frees about 230 of 309 GB.

## Branches and worktrees (repo `~/git-repos/NVEnc`)

**Keep:**

| Branch | Worktree | Why |
|---|---|---|
| `fix/fgs-clean-source-20261006` | `NVEnc-fgs-clean-source-20261006` | the release; entry point `tests/fgs/WORK-TO-PRODUCTION.md` |
| `fix/fgs-chroma-codec-flat-20261007` | `NVEnc-fgs-chroma-codec-flat-20261007` | parked codec-flat chroma option |
| `research/fgs-separator-20261007` | `NVEnc-fgs-separator-20261007` | chroma-detail and coarse-band research, separator plan |
| `research/fgs-fidelity-attribution-20261007` | `NVEnc-fgs-fidelity-attribution-20261007` | stage-attribution traces and findings |
| `prod/merge-upstream-9.37-20261004` | `NVEnc-merge937` | source of the rollback binary `c6cbd528`; archive once the rollback window closes |
| `feat/fgs-detail-fidelity-20260908` | `NVEnc-fgs-fidelity` | old research line (216 unmerged commits); holds the old entry point, which now points to the new one |
| `master` | `NVEnc` | upstream tracking, not FGS |

**Fully contained in the release, so archive:**

| Branch | Worktree | Already archived at the same commit |
|---|---|---|
| `fix/fgs-source-variance-20260916` | `NVEnc-fgs-source-variance` | no |
| `qualify/fgs-prod-kernels-20261005` | `NVEnc-fgs-qualified-kernels-20261005` | no |
| `perf/fgs-prod-filter-kernels-20261004` | `NVEnc-fgs-prod-kernels` | no |
| `perf/fgs-prod-bilateral-20261004` | `NVEnc-fgs-prod-bilateral` | no |
| `prod/cb903a17-gmc-fallback` | `NVEnc-prod` | no |
| `fix/fgs-held-amplitude-20260916` | `NVEnc-fgs-amplitude` | yes (`refs/archive/20261002/…`) |
| `fix/fgs-reliability-20260907` | `NVEnc-fgs-hardening` | yes |
| `fix/fgs-ripple-stability-931` | `NVEnc-fgs-ripple-931` | yes (`…/backup/pre-upstream-9.33-20260904`) |
| detached `20e224f4` | `NVEnc-fgs-ripple` | yes (`…/fix/fgs-ripple-stability`) |

**Not contained in the release, but finished or parked: archive too (the archive ref keeps the unmerged commits).** `experiment/fgs-submission-trace-20261005` (`NVEnc-fgs-submission-trace`), `feat/fel-production-20260914` (`NVEnc-fgs-fel`, FEL off), `perf/fgs-filter-pipeline-20260930` (no worktree), `plan/fgs-improvement-20261004` (`NVEnc-fgs-improvement-plan`), `fgs/fft3d-noise-psd` (no worktree). These four are already archived at the same commit: `experiment/fgs-directional-cost-20260908` (`NVEnc-fgs-directional`), `experiment/fgs-input-trace-20260908` (`NVEnc-fgs-trace`), `fix/fgs-rejection-flicker-20260912` (`NVEnc-fgs-flicker`).

Commands, to run after reviewing:

```bash
cd ~/git-repos/NVEnc
D=20261007
archive() {  # branch [worktree]; the worktree removal refuses if it has changes
  git update-ref "refs/archive/$D/$1" "refs/heads/$1" &&
  { [ -z "$2" ] || git worktree remove "$2"; } &&
  git branch -D "$1"
}
W=~/git-repos
archive fix/fgs-source-variance-20260916      $W/NVEnc-fgs-source-variance
archive qualify/fgs-prod-kernels-20261005     $W/NVEnc-fgs-qualified-kernels-20261005
archive perf/fgs-prod-filter-kernels-20261004 $W/NVEnc-fgs-prod-kernels
archive perf/fgs-prod-bilateral-20261004      $W/NVEnc-fgs-prod-bilateral
archive prod/cb903a17-gmc-fallback            $W/NVEnc-prod
archive fix/fgs-held-amplitude-20260916       $W/NVEnc-fgs-amplitude
archive fix/fgs-reliability-20260907          $W/NVEnc-fgs-hardening
archive fix/fgs-ripple-stability-931          $W/NVEnc-fgs-ripple-931
git worktree remove $W/NVEnc-fgs-ripple       # detached, archived 20261002
# finished or parked, not contained in the release
archive experiment/fgs-submission-trace-20261005 $W/NVEnc-fgs-submission-trace
archive feat/fel-production-20260914          $W/NVEnc-fgs-fel
archive perf/fgs-filter-pipeline-20260930
archive plan/fgs-improvement-20261004         $W/NVEnc-fgs-improvement-plan
archive fgs/fft3d-noise-psd
archive experiment/fgs-directional-cost-20260908 $W/NVEnc-fgs-directional
archive experiment/fgs-input-trace-20260908   $W/NVEnc-fgs-trace
archive fix/fgs-rejection-flicker-20260912    $W/NVEnc-fgs-flicker
git worktree prune
git for-each-ref refs/archive/$D               # check
# later, after the rollback window: archive prod/merge-upstream-9.37-20261004 $W/NVEnc-merge937
```

## Scratch under `/tmp/downloads/codex-work/` (309 GB)

**Must stay (about 75 GB plus 4.4 GB of small receipts, and `~/.cache/fgs-gate`, 1.4 GB):**

| What | Where | Size |
|---|---|---|
| Verified source copies (each with a receipt) | `fgs-submission-20261005/heldout-originals` (Insidious, Marshals, Homegrown, Knightfall), `…/heldout-animation-originals` (Toy Story 5), `…/original-fixtures` (Play Dirty), `fgs-improvement-20261004/original-fixtures` (Gentlemen, Lost Tapes, Amphibia, Taxi, Silo), `fgs-fidelity-20261007/originals` (Alien) | 64 GB |
| Known-answer inputs referenced by the trace-identity manifests | `fgs-improvement-20261004/identity-sources` | 3.0 GB |
| Release, rollback and parked-option binaries | `fgs-submission-20261005/bin/nvencc-release-46d6781c`, `fgs-clean-source-20261006/bin/nvencc-prod-c6cbd528`, `fgs-submission-20261005/bin/nvencc-optcand-725585b8` (and `-on`) | 1.2 GB |
| Amplitude negative/reference reports (needed for any candidate history) and the release's own history | `fgs-submission-20261005/amplitude-histories-resumed`, `…/amplitude-final-release-46d6781c` | about 4 GB |
| Gate harness pieces | `fgs-submission-20261005/gate-path-view`, `…/gate-cache` → `fgs-improvement-20261004/gate-cache` → `~/.cache/fgs-gate`; `fgs-clean-source-20261006/pin-e78e97f2` (submodule source for clean clones) | 1.7 GB |
| Release evidence | `fgs-submission-20261005/release-trace-46d6781c`, `…/reports/full-gate-release-46d6781c-0b2db87e`, `…/reports/chroma-detail-*-3d7c5405`, `fgs-clean-source-20261006/release` | 0.4 GB |
| Tools, manifests, notes and every small receipt | `*.py`, `*.json`, `*.md`, `*.log`, `*.sh` in all four directories (`tools/` in each), left in place by the media-only pass below | 4.4 GB |

The gate's labelled negatives are not in scratch: they live in `/media/merged-storage/validation-fixtures/nvenc-fgs/v1/` (including the new `gentlemen-codec-flat-chroma-detail-negative-33m-150s.mkv`) and in `/opt/docker-apps/logs/` (retained encoders). Both must stay.

**Can go (about 230 GB):**

| What | Size |
|---|---|
| Encodes, raw trace dumps and y4m intermediates in `fgs-fidelity-20261007` (traces, held-out, census, guards, side-by-side, separator probes) | 116 GB |
| Gate and measurement report media in `fgs-submission-20261005/reports` (except the release gate) and `fgs-improvement-20261004/reports` | 45 GB |
| Superseded Play Dirty histories (`amplitude-regenerated`, `amplitude-final-{candidate,bundle-e78e97f2,chroma-e65ea00e,optcand-on-*}`) | 12 GB |
| Pinned clones and build trees except `pin-e78e97f2` (`*-pin*` in submission and improvement, `pin-*` and `clean-*` in clean-source and fidelity) | about 30 GB |
| Development and diagnostic binaries (all other `bin/` entries; `fgs-improvement-20261004/bin/nvencc-deployed` duplicates `c6cbd528`) | about 12 GB |
| `task4` and `throughput` media, superseded trace runs and instrumentation dirs | about 12 GB |
| `fgs-fidelity-20261007/ab-set` (a copy is on Nextcloud) | 0.5 GB |

A media-only pass keeps every receipt. Review the list, then swap `-print` for `-delete`:

```bash
cd /tmp/downloads/codex-work
find fgs-fidelity-20261007 fgs-submission-20261005 fgs-improvement-20261004 fgs-clean-source-20261006 \
  \( -path '*/heldout-originals' -o -path '*/heldout-animation-originals' -o -path '*/original-fixtures' \
     -o -path '*/originals' -o -path '*/identity-sources' -o -path '*/pin-e78e97f2' \
     -o -path '*/amplitude-histories-resumed' -o -path '*/amplitude-final-release-46d6781c' \
     -o -path '*/full-gate-release-46d6781c-0b2db87e' -o -path '*/chroma-detail-*-3d7c5405' \
     -o -path '*/release-trace-46d6781c' \) -prune -o \
  -type f \( -name '*.raw' -o -name '*.y4m' -o -name '*.mkv' -o -name '*.yuv' -o -name '*.ivf' -o -name '*.tbl' \) -print
```

Then remove the clone trees and binaries that are not kept, listed by name after a check:

```bash
ls -d fgs-*/{*-pin,*-pin-v2,pin-*,clean-*,harness-*} 2>/dev/null | grep -v pin-e78e97f2
ls fgs-*/bin/ | grep -v -E 'release-46d6781c|prod-c6cbd528|optcand-725585b8'
```
