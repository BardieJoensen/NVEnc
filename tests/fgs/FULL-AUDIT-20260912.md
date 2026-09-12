# Full library follow-up audit — September 12

Status: **in progress**. The deployed ordinary encoder remains `273723b7`.
This is a new, explicitly authorized audit after the focused source-guard
qualification. It does not reopen or automatically start the deferred retention
campaign, and it does not declare the remaining library clean or damaged.

The live [work ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/work-plan.json)
and [operations/evidence index](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/OPERATIONS.md)
are the resumption points. Earlier focused qualification remains in
[SOURCE-GUARD-20260912.md](SOURCE-GUARD-20260912.md).

## Current scope and method

The September 12 snapshot contains **5,578 current library video files**:
5,263 AV1 and 315 other codecs. The AV1 files total approximately 6.94 TB and
3,189 hours. The historical 5,293-path AV1 inventory has 30 absent paths;
Sonarr episode/file records and fresh probes identify their active non-AV1
replacements. Those are retired old paths, not historical syntax passes.

The new header pass reuses 1,473 prior matching file-version scans and reads the
remaining AV1 files. It profiles every displayed header, including longer grain
runs and scaling changes while grain stays enabled. Each file receives up to
12 explicit windows covering short/long runs, boundaries, amplitude changes,
sustained grain and timeline controls. Native libdav1d measurements cover every
pixel and displayed frame of those windows, including reference-display HDR
mapping. Retained originals receive separately aligned Y/U/V source comparisons.

This is whole-library header coverage plus bounded decoded/source coverage,
**not a source comparison of every pixel of every movie**. Header completion,
decoded-window completion and visual/source decisions have separate states.
Originals that cannot be located, unsupported comparisons, changed files and
errors remain explicit. No threshold starts a download or replacement.

## Findings established so far

- Four previously recorded old movie syntax failures independently reproduce
  with libdav1d: **Saving Private Ryan**, **The Girl Who Kicked the Hornets Nest
  (Extended Cut)**, **The Girl Who Played with Fire (Extended Cut)** and
  **The Shadows Edge**. Their current files total 42.55 GB; recorded matching
  source payloads total 129.07 GB. No retained originals were located by the
  tracked recovery inventory/name search. Full decoder error/recurrence checks
  are running. These are old-file findings, not failures of the deployed build.
- The 20 unresolved missing-path errors in the syntax audit were matched to
  active Sonarr non-AV1 replacements and retired with pinned evidence. That
  audit now accounts for its complete scope: 5,259 valid, four invalid, 30
  superseded paths. Conclusive syntax coverage is not picture clearance.
- A whole **Regular Show S1E2** source-reader control covers all 16,378 displayed
  pictures. Software and hardware VC-1 decoding produce identical picture
  sequences, but software timestamps are one frame later. The current repaired
  output follows hardware timing, within 1 ms, and retains the full picture
  sequence. Its downscaled same-frame source RMS is 0.517 on average, maximum
  0.817; shifting the actual pictures makes the comparison much worse. Prior
  exact-timestamp comparisons mistakenly paired adjacent source pictures.
  All 80 prior exclusions have now been revisited: 79 new source comparisons
  plus the separately verified repaired pilot witness. Every new window aligns
  with the explicit +0.042-second source-reader offset; maximum coarse-picture
  RMS is 1.094. This resolves the timing exclusion, not picture-quality findings.
- Corrected source statistics and visual review confirm recurring added luma
  and colour noise in the older **Regular Show S1E2**. The unchanged current
  encoder was compared in 12 old witness windows and 12 additional current-run
  windows. The strong active-region noise is removed. A full 16,378-frame
  independent decode, synthesis scans, installed-window checks, video-packet
  identity and audio/metadata preservation passed before/after installation.
  The complete file grew from 196,271,655 to 229,472,648 bytes (+16.916%), still
  83.677% smaller than the retained original. Both old library versions remain.
  The [installation proof](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/installed-vc1-verification.json)
  and [37-file cumulative selection history](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/current-selected-repairs.csv)
  retain exact identities. A historical selected repair is not whole-file
  perceptual clearance: the expanded audit has found additional scenes in two
  previously selected Steven Universe files, described below.
- The first expanded source screen exposed a measurement pitfall: uniform
  clipping of superwhite Y=249 to legal white can create a large uncentred
  difference while both pictures render white. The new source tool separates
  mean-subtracted grain texture from mean code-level shifts and reports active
  levels versus endpoints separately. The preliminary 400,000-pixel / 14-code
  Regular Show flag is **not a validated grain-area/severity estimate**.
  The original diagnostic records are retained; corrected measurements and
  visual/recurrence review determine any repair selection.

The known old Lost Tapes opening-colour defect remains a real method control:
old quiet-colour peak differences around 5.84/6.21 code levels become exactly
zero U/V synthesis in the installed source-guard version. An unchanged luma
endpoint residual was located in a source-black patch and is kept distinct
from that colour defect. Source noise, decoder clipping and lossy base texture
must not be conflated.

Two earlier `3778447e` repairs, **Steven Universe S3E22 (Earthlings)** and
**S1E23 (Monster Buddies)**, have additional visibly confirmed source-grain
mismatches outside their earlier reviewed witnesses. Full-duration measurements
of the specifically reviewed 16x16 luma regions reproduce the original native
window values. Earthlings has 76 source-flat frames above the diagnostic
three-code noise level across 25 small runs. Monster Buddies has 207 such frames,
including continuous runs lasting about 2.2 and 6.2 seconds. These are spatially
bounded recurrence measurements, not whole-picture damaged durations or a
universal visibility threshold. Current-build full-source comparisons remove
most of the strong affected area but retain small source-quiet patches with
excess grain. They have **not** been installed. No download is needed. See the
live ledger and `roi-recurrence/`.

The remaining current-build case is independently reproduced at Monster
Buddies 01:47.441: a 16x16 source patch has standard deviation 0.25, while its
containing 32x32 block has detrended deviation 5.294. The deployed guard sees
the larger textured block and misses that quiet subregion; decoded grain in
the small patch reaches approximately 10.7 code levels. The affected area is
much smaller than in the prior encode, but this is a demonstrated limit of
the current source guard. Finer independent source protection is being
implemented and qualified. Repair admissions remain held for this focused
encoder correction, not for the long CPU-only library pass. Source measurements
and exact decoded levels are retained in `small-region-investigation/`.

Code review also found an optional motion-denoiser drain issue: threshold
updates consulted a null/empty input picture rather than keeping the last real
input's threshold while buffered pictures drained. Fidelity commit `940d2a07`
guards that update. Its exact build passes four actual baseline/candidate
8/10-bit CLI drains with 96 contiguous independently decoded frames each.
Finite source statistics are checked in the revised fixture. The initial
narrow fixture's unused empty-band statistics and results remain historical.
This is bounded drain validation, not broad motion-mode quality qualification;
the live bilateral encoder has not changed.

The full old Shadows Edge decode finishes with libdav1d errors and displayed
gaps, including an approximately eight-second gap. The four-film extent job
retains the full logs; error log positions identify the preceding successful
picture, not an exact failing-packet timestamp. Original downloads remain held.

## Runtime boundaries

The audit uses separate manually started jobs, low CPU/I/O priority, bounded
memory, pinned tools and versioned reports. Normal Tdarr validation is unchanged.
Ordinary repairs may be drained briefly for a source-referenced current-build
trial, as authorized by the user. The first VC-1 trial hold was released and
two ordinary workers were observed again. A second bounded hold may cover the
two Steven Universe comparisons. Any admission hold owned by this audit
must be released after that work. Read the live ledger before assuming a hold
is present or absent.

The existing source-recovery download hold remains in force. Source-free flags
do not authorize redownloading the conservative 9.5 TB scope. The automatic
retention campaign remains deferred and manual-start only. No encoder or flow
deployment is part of the audit unless a newly demonstrated defect requires
a separately qualified fix.

## Tools and remaining work

New reusable tools are `tools/fgs/library_audit.py`,
`decoded_library_audit.py` and `source_plane_review.py`. CPU regressions cover
header continuity, normalized scaling, longer pulses, colour-only changes,
decoded spatial/timestamp completeness, source alignment, grain versus uniform
clipping, and source-textured controls. Real-file controls include SDR, PQ HDR,
the corrected VC-1 alignment and retained bad/repaired colour examples. Twenty
CPU tests pass. The stricter source-coverage helper refuses a partially matched
window instead of accepting any three matches. All 253 previously completed
source windows already had twelve complete pairs; the earlier artifacts remain
at their original paths. The active decoded run uses `tools-v3/` and
`decoded-v3/`, with exact pins and the restart receipt in
`complete-source-coverage-upgrade.json`.

Finish the version-bound header and expanded decoded/source passes; review
strong, recurrent candidates in actual matched pictures; qualify the current
encoder against any justified additional repair; reconcile files changed while
the ordinary repair ran; and publish the affected/title list with evidence,
recurrence, source availability and a concrete repair plan. Keep pending,
reviewed and confirmed files distinct. The comprehensive audit remains open.
