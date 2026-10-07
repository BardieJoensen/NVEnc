# FGS status: separator work, 2026-10-07

Branch `research/fgs-separator-20261007` (worktree `~/git-repos/NVEnc-fgs-separator-20261007`) from the release line `fix/fgs-clean-source-20261006` head `decd1d0e` (runtime `e78e97f2`, release binary `46d6781c`). Scratch: `/tmp/downloads/codex-work/fgs-fidelity-20261007/` (tools in `tools/`, this phase under `sep2/`).

## Where it stands

- Codec-flat chroma option parked on `fix/fgs-chroma-codec-flat-20261007`; the release stays `46d6781c`, no flow change. The blind TV review found duller red lips with the option (chroma base detail loss); details in that branch's `FINDINGS-2026-10-07-CHROMA-OPTION-QUALIFICATION.md`.
- Side-by-side Emby test, its folder and the temporary keep-original allowlist line removed; Emby and Tdarr no longer list it. Nextcloud copy kept.
- Plan (`PLAN-2026-10-07-SEPARATOR.md`), now in this order, stopping after phase 1:
  1. Chroma step: (a) measure the release's structured chroma detail loss (grain off vs the lossless source, most colour-structured tenth of chroma patches, colour amplitude and peak saturation) on held-out live action and on animation; (b) prototype offline a chroma range threshold from the chroma noise model, default mode; (c) report colour detail recovered, chroma grain capture and fixed-QVBR bytes.
  2. Coarse-band phase-1 prototype (offline), as planned.
  3. Gate: add a chroma base-detail check (the 1a measure, release as the floor) to the base-fidelity checks; show it fails the `725585b8` option-on build and passes the release.

## Decision log

- 2026-10-07 user: Park the codec-flat chroma option and ship `46d6781c`; keep the option code on its branch.
- 2026-10-07 user: Drop the gate mode-awareness and span over-breadth follow-ups; they only mattered for the option.
- 2026-10-07 user: Make the chroma range threshold the first separator step, then the coarse-band phase-1 prototype; stop after phase 1 with both results.
- 2026-10-07 user: Add a chroma base-detail check to the gate's base-fidelity checks.
- 2026-10-07 auto: Branch from the release line rather than the option branch, so the option-only periodic check stays parked with the option.
