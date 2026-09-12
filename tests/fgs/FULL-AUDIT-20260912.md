# Full library follow-up audit — September 12

Status: **in progress; qualified finer-source core ef5c61fe deployed and ordinary
repairs resumed**. The audit found and fixed a real small-region source-guard
limit in the preceding deployed encoder. It has not cleared the entire library.
Automatic retention remains deferred and manual-start only.

Start at [WORK-TO-PRODUCTION.md](WORK-TO-PRODUCTION.md), the
[finer-source qualification](FINE-SOURCE-GUARD-20260912.md), and the local
[work ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/work-plan.json).
The [operations index](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/OPERATIONS.md)
and [published coverage](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/published/status.json)
record live jobs, exact versions and remaining work. Local filenames below are
relative to `/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912`.

## Scope and coverage

The explicit snapshot contains **5,578 video files**, including **5,263 AV1**
and 315 other codecs. AV1 payload totals approximately 6.94 TB and 3,189 hours.
All 30 absent paths in the historical 5,293-file syntax inventory were matched
to active Sonarr non-AV1 replacements with record/probe evidence. That older
syntax audit now accounts for 5,259 valid, four invalid and 30 superseded paths.
It is not a temporal or perceptual clearance of the current library.

The current header pass reuses 1,473 exact-version prior scans and reads every
displayed header of the remaining files. It selects up to twelve windows per
file across short and longer grain runs, run boundaries, strength changes while
grain remains enabled, sustained grain and timeline controls. Thirty-four
previous witness anchors in 33 files add targeted coverage. Native libdav1d
measurements cover every pixel and displayed frame of each selected window,
including static reference-display HDR mapping. Retained originals receive
separately aligned native Y/U/V comparisons.

This is full-library header coverage and sampled decoded/source coverage,
**not a source comparison of every pixel of every film**. Partial source matches
cannot clear a window. Original-unavailable, alignment-review, source-error,
changed-file and incomplete states remain explicit. Source statistics cover
complete 16x16 Y / 8x8 U/V blocks; short edge strips are reported as uncovered
by that statistic, although the reference-display inspector covers the image.
A diagnostic threshold never starts a repair or download.

## Completed repairs during this audit

| File | Installed build | Source-backed result |
| --- | --- | --- |
| Regular Show S1E2, Just Set Up the Chairs | 273723b7 | 24 source windows, 16,378-frame full decode, chosen-region recurrence and installed flash/stream checks pass |
| Steven Universe S3E22, Earthlings | ef5c61fe | 24 source windows; 16,536 frames of identified-region checks, old 76 strong source-flat frames become zero |
| Steven Universe S1E23, Monster Buddies | ef5c61fe | 24 source windows; 16,769 frames of identified-region checks, old 207 strong frames become zero |
| Amphibia S1E18, Plantar's Last Stand | ef5c61fe | 23 source windows; 17,193 frames across three identified regions, old 818 strong frames become zero |
| Amphibia S1E11, Sprig Vs. Hop Pop | ef5c61fe | 21 source windows; 17,194 frames across three identified regions, old 874 strong frames become zero |

“Strong” here is the unchanged diagnostic level of more than three native
8-bit-normalized noise levels in a source-flat region. These counts are
spatially bounded recurrence, not seconds of whole-picture damage. Amphibia
S1E18's new maximum in eligible chosen regions is about 1.25 and S1E11's is
about 0.27, so zero strong frames
does not mean zero grain everywhere. Matched source/old/new images were also
reviewed before installation.

`installed-vc1-verification.json`, `strict-installed-steven-verification.json`,
`strict-installed-amphibia18-verification.json` and
`strict-installed-amphibia11-verification.json` verify installed identities,
complete independent decoding, original/superseded hashes, video-packet
identity, synthesis/earlier-flash checks and retained audio/subtitle/chapter/
signalling data. Every old file remains retained. No new source download was
needed. The latter four repeat earlier selections; cumulative
`current-selected-repairs.json/csv` still contains **37 distinct files**, now
+1.620% in complete-container bytes against its recorded earlier baseline.
That history is separate from current audit findings and incomplete coverage.

## Confirmed older-file findings and priority

Full-duration recurrence is complete for the inspected regions in these four
older outputs. It is a lower bound and cannot clear other regions or weaker
noise. They have not been selected for another repair merely from these counts.

| File | Measured recurrence in chosen regions | Disposition |
| --- | --- | --- |
| Batman: The Dark Knight Returns (2013), Deluxe Edition | 63 strong frames / 213,039; three bursts, longest 47 frames (about two seconds) | Lower immediate priority in measured regions; broader review remains |
| South Park S23E7, Board Girls | One strong frame / 32,177 in two regions | Lower immediate priority in measured regions |
| Mousetrap S1E1 | 37 strong frames / 81,411 in two colour regions, longest 10 frames (about 0.42 seconds) | Lower immediate priority in measured regions |
| Amphibia combined S2E18–E19 | 48 strong frames / 32,438 in three regions; 23 short bursts, longest nine frames (about 0.38 seconds) | Lower immediate priority in measured regions |

`additional-source-roi/`, `additional-colour-roi/`, `visual-review/` and
`review-dispositions.json` retain source comparisons, exact coordinates and
all recurrence runs. Mousetrap S1E2/S1E5 also have faint grain in source-clean
black bars during their deliberately textured opening titles. The title artwork
already has strong red/cyan texture in the originals; the large neutral-chroma
area rank must not be read as an equivalent damaged fraction of story footage.
These samples are lower immediate priority and do not clear the rest of either
episode.

Additional source comparisons confirmed conspicuous grain on clean character
artwork in **Amphibia S1E11** near 06:29 and the combined **S2E18–E19** file
near 17:47. The completed `additional-amphibia-source-roi/` job followed three
chosen regions through both files. S1E11 had repeated bursts, including one
lasting about 6.4 seconds; it was qualified and repaired as recorded above.
The combined S2 file has only short bursts in these regions and was not selected
for a repeat repair. Other ranked candidates, including
previously excluded VC-1 footage, remain unreviewed. Read the live ledger and
version-specific decisions before treating any older observation as current.
The [reviewed repair priorities](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/published/repair-priorities.csv)
list installed repairs, remaining reviewed findings and source availability.
They are not an exhaustive affected-file list while the audit is incomplete.

## Four malformed old movies

All four previously recorded syntax defects independently reproduce with
libdav1d. Full-file decode logs and nominal cadence refinement now establish
where decoded gaps occur. Cadence-derived missing intervals are estimates;
these are not source-referenced exact frame-loss counts or TV concealment
measurements. The source files remain unavailable in the tracked seeding/
recovery inventory. No recovery download has started.

| Movie | Full-decode evidence and viewed context | Recovery priority |
| --- | --- | --- |
| The Girl Who Kicked the Hornets Nest (2009), Extended Cut | Six gaps near 25:17 and 29:37, including two about 4.5 seconds; regular story scenes | Recommend source recovery and retranscode in a future approved batch |
| The Girl Who Played with Fire (2009), Extended Cut | Twelve gaps including about 4.24 and 2.24 seconds; viewed examples are story scenes | Recommend source recovery and retranscode in a future approved batch |
| The Shadow's Edge (2025) | Ten gaps near 2:15:49–2:16:00, maximum eight seconds; adjacent viewed footage is outtakes/behind-the-scenes beside credits | Lower story-watchability priority; exact end-material boundary remains unmeasured |
| Saving Private Ryan (1998) | One 0.125-second timestamp gap near 2:49:13, approximately two missing nominal intervals; final DreamWorks logo | Low watchability priority |

`invalid-movie-extent/cadence-status.json` and `movie-visual-context/` retain
complete logs and matched scene evidence. Current payloads total 42.55 GB;
recorded matching source payloads total 129.07 GB. These old-file findings,
37-file repair history and conservative 9.5 TB ripple scope can overlap or use
different baselines. They must not be added into a blanket damaged-file count.

## Audit and encoder hardening

The demonstrated finer-source defect and its deployment qualification are
covered in [FINE-SOURCE-GUARD-20260912.md](FINE-SOURCE-GUARD-20260912.md).
The original periodic change alert remains retained, with all-frame numeric
source review, selected visual checks, a separately named reviewed positive
and a fresh passing regression. Fine original texture can be attenuated at
shared brightness; this tradeoff is documented instead of claiming perfection.

A separate optional motion-denoiser drain issue used a null/empty input to
update thresholds while buffered pictures drained. Fidelity `940d2a07` keeps
the last real input's threshold. Its exact build passes four baseline/candidate
8/10-bit CLI drains with 96 contiguous decoded frames each. This is bounded
drain qualification, not a broadly qualified motion mode. Production uses
bilateral processing; the broader fidelity binary was not deployed.

The source-review tool now separates mean-subtracted grain texture from uniform
code-level shifts. In particular, clipping source superwhite Y=249 toward legal
white can create a large numeric difference while both render white. The old
400,000-pixel / 14-code Regular Show flag is not a validated noise-area estimate.
A whole 16,378-picture VC-1 source-reader control proves hardware/software
picture equality with a +0.042-second software timestamp offset. All 80 prior
exclusions were revisited: 79 new correctly paired windows plus the independently
verified Regular Show pilot. Correct timing resolves eligibility, not fidelity.

Audit commit `e4ed723f` fixes two operational issues. Low evidence-disk space
now checkpoints a paused run and leaves media pending, instead of consuming
thousands of files as failed checks. Sorted timestamp matching inspects nearest
neighbours instead of rescanning the entire source for each output frame.
Twenty-eight CPU tests pass, including partial coverage, wrong cadence,
clipping, finite values, shared matches, low-storage admission/mid-file pauses
and a 213,039-frame variable-cadence case. The real retained Batman timestamps
match in about 0.09 seconds with unchanged pairing; no movie was re-decoded for
that performance check.

Diagnostic commit `708ae7ca` supports explicitly tagged BT.601 PAL/NTSC colour
primaries and corrects floating-point rounding at half-open window endpoints.
The earlier wrapper requested a BT.709 assumption for explicitly tagged SD
video, which the inspector correctly rejected. Separately, the header CSV and
demuxed double could disagree over an excluded endpoint. Neither diagnostic
failure establishes corruption in the media. The old failures remain retained.

Thirty-one Python audit/source tests, eight native CLI tests, and display/spatial
CPU controls pass. Two actual BT.601 windows and their aligned sources pass;
existing SDR/PQ measurements remain byte-identical with unchanged non-timing
metadata. The old inspector fails the new colour and boundary controls.
`audit-tools-v5-qualification.json` pins the diagnostic binary, exact helper
hashes and real/CPU evidence. Among the original snapshot's 155 BT.601-tagged
files, 26 have explicit supported transfer/primaries. The other 129 have missing
colour metadata and remain ineligible for precise reference-display grading;
their tags are not overridden. This is a coverage limit, not a damaged-file count.
No encoder or routine Tdarr validator changed in this diagnostic step.

## Active jobs, storage and required finish

The v3 decoded job was stopped after the application filesystem crossed its
unchanged 6 GiB reserve. Its 72 measured original versions and resource-error
records are preserved. After checking current identities, 69 completed results
were reusable, 5,175 original versions needed further work, and 19 changed
versions received fresh probes and immutable installed receipts. No snapshot
errors occurred. `resume-20260912/` pins that initial continuation.
After qualification of the display/boundary corrections, the v4 consumers were
stopped with all completed and partial evidence retained. The v5 snapshot reuses
86 current completed results, queues 5,160 original versions and freshly pins
17 changed versions, with no snapshot errors. This includes the later S1E11
installation. `resume-v5-20260912/` pins the current finite queues. Reused results
retain their earlier tool identity; they are not relabelled as new measurements.

Completed gate evidence totaling 9,907,127,130 bytes was copied to
`/media/storage1/tdarr-audit-evidence/full-temporal-audit-20260912`, verified file
by file using SHA-256, and linked at its original paths. No qualification bytes
were discarded. New broad decoded evidence also lives on that larger volume.
The relocation receipt is `storage-pause-20260912/evidence-relocation.json`.

The manually started user units are `fgs-full-temporal-audit-20260912`,
`fgs-full-decoded-audit-v5-20260912`, `fgs-catchup-headers-v5-20260912`, and
`fgs-catchup-decoded-v5-20260912`. The focused Amphibia recurrence and earlier
19-version header pass completed. Active jobs use low CPU/I/O priority and
bounded memory. They are finite jobs, with no automatic retention trigger.
The audit-owned repair holds were released; the latest
`final-additional-amphibia-operational-state.json`
records two ordinary ef5 repair workers and preserved playback yield.

Finish the header and decoded/source queues, resolve any actual measurement
errors, review remaining strong/recurrent candidates against matched source
pictures, qualify justified further replacements, and reconcile later file
versions. Publish title-level evidence and watchability priority separately
from raw flags and earlier repair history. New original-source recovery remains
held for evidence, space and batch review. The comprehensive audit remains open.
