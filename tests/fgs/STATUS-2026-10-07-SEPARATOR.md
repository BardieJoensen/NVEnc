# FGS status: separator work, 2026-10-07

Branch `research/fgs-separator-20261007` (worktree `~/git-repos/NVEnc-fgs-separator-20261007`) from the release line `fix/fgs-clean-source-20261006` head `decd1d0e` (runtime `e78e97f2`, release binary `46d6781c`). Scratch: `/tmp/downloads/codex-work/fgs-fidelity-20261007/` (tools in `tools/`, this phase under `sep2/`).

## Where it stands

- Codec-flat chroma option parked on `fix/fgs-chroma-codec-flat-20261007`; the release stays `46d6781c`, no flow change. The blind TV review found duller red lips with the option (chroma base detail loss); details in that branch's `FINDINGS-2026-10-07-CHROMA-OPTION-QUALIFICATION.md`.
- Side-by-side Emby test, its folder and the temporary keep-original allowlist line removed; Emby and Tdarr no longer list it. Nextcloud copy kept.
- Plan (`PLAN-2026-10-07-SEPARATOR.md`), now in this order, stopping after phase 1:
  1. Chroma step: (a) measure the release's structured chroma detail loss (grain off vs the lossless source, most colour-structured tenth of chroma patches, colour amplitude and peak saturation) on held-out live action and on animation; (b) prototype offline a chroma range threshold from the chroma noise model, default mode; (c) report colour detail recovered, chroma grain capture and fixed-QVBR bytes.
  2. Coarse-band phase-1 prototype (offline), as planned.
  3. Gate: add a chroma base-detail check (the 1a measure, release as the floor) to the base-fidelity checks; show it fails the `725585b8` option-on build and passes the release.

- Step 1a done (`FINDINGS-2026-10-07-CHROMA-DETAIL.md`): the release's structured colour loss (0.89-0.995) is almost all in NVENC's coding; the submitted picture keeps 0.995-1.000 in 17 of 19 windows (0.983-0.995 in two). A default-mode chroma threshold fix can recover at most 0-1.7% in two windows. Premise of 1b contradicted: waiting for the user before building the 1b prototype. NVENC chroma QP offset does not help.
- Step 3 done: gate stage `chroma_base_detail` (`3d7c5405`), passes the release, fails `725585b8` option-on, rejects its labelled negative; CPU tests pass.
- Step 2 (coarse-band phase-1 prototype): in progress.

## Decision log

- 2026-10-07 user: Park the codec-flat chroma option and ship `46d6781c`; keep the option code on its branch.
- 2026-10-07 user: Drop the gate mode-awareness and span over-breadth follow-ups; they only mattered for the option.
- 2026-10-07 user: Make the chroma range threshold the first separator step, then the coarse-band phase-1 prototype; stop after phase 1 with both results.
- 2026-10-07 user: Add a chroma base-detail check to the gate's base-fidelity checks.
- 2026-10-07 auto: Branch from the release line rather than the option branch, so the option-only periodic check stays parked with the option.
- 2026-10-07 auto: Split the release's colour loss by stage with default-mode traced encodes (725585b8 option off), because a separator fix can only recover what the separator loses.
- 2026-10-07 stop: The release's structured colour loss is in NVENC's coding, not the chroma threshold (submitted picture 0.995-1.000 in 17 of 19 windows); ask before building the 1b prototype.
- 2026-10-07 auto: Put the chroma base-detail check in its own gate stage on the pinned Gentlemen clip, floor computed from the pinned release positive at run time, the option-on output as labelled negative, margin 0.002 (20x repeat variation).
- 2026-10-07 auto: Cap traced windows at 264 frames, because the submission trace holds at most 2 GiB of 1080p P010 surfaces (about 270 frames).
