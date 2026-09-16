# Earlier repairs, source releases and FEL originals

September 16, 2026. The user asked about repairs made before subsequent fixes,
returning held torrents to ordinary handling, and keeping FEL films as originals.
They explicitly selected restoring the original HEVC versions in Movies while
keeping FEL encoding disabled.

## Earlier repair outputs

Reconciled all 1,882 installed repair receipts against current filesystem
identities and the completed audit snapshot:

| Current relationship to the recorded repair | Files |
| --- | ---: |
| Exact installed signature still matches | 1,874 |
| File changed at the same path; its current version was measured | 5 |
| Superseded by a different movie release; replacement was measured | 3 |
| Unresolved missing library file | 0 |

Of the 1,874 exact matches, 1,872 used a build before the latest `2fa6cfd0`
amplitude correction; two used that build. Earlier fixes remain effective for
their recorded defects, but completing the ripple repair does not clear a file
of subsequently discovered grain problems. The diagnostic review queue contains
509 repaired paths and one other file. These are review candidates, not 510
confirmed damaged files. Build age alone is also not a retranscode decision.

Current installed versions remain the review baseline. Check source-supported
visible severity and recurrence, qualify the corrected encoder, then repeat only
justified repairs from originals. The nine selected follow-up repairs remain
installed and postchecked. Their completion does not clear every other episode
inside the same source season pack.

## Torrent handling

Before this change, 345 torrents carried `fgs-audit-hold-20260913`: 341 were idle
seeds and four were uploading. The tag suppresses cleanup and seeding-limit
expiry; it does not suspend uploading. Their 6.84 TB of logical payload is not
a unique disk-space figure or a repair/download requirement.

The dependency review combines the original source inventory, audit manifests,
new source discovery and repair receipts. Only three held torrents had solely
completed selected repairs as library dependencies. Play Dirty remains a source
for the pending encoder regression work, so its hold remains.

The other two are the extended Girl films. Both passed complete repair checks
and fresh installed-version measurements; their actual repair commands do not
enable grain synthesis. Their audit tags were removed, and they returned to
`radarr-longterm`, with normal 30-day total-seeding limits and automatic torrent
management preserved. qBittorrent moved their originals from the temporary
recovery category into `/long-term-seeding/movies`. The installed movies did
not change. Their combined 77.26 GB is eligible for eventual ordinary cleanup;
this action deleted no video payload and did not reset elapsed seeding time.

343 audit tags remain: 340 with unresolved dependent review, one Play Dirty
regression source and two FEL original sources. The other two primary FEL
torrents already have non-cleanup NordicBits rules. Existing cross-seeds and
unrelated tags/policies were left alone. Release more tags only after resolving
all dependent work, including the source's use in pending encoder qualification.

## FEL originals restored

Restored Bumblebee, TRON: Legacy, Transformers: Rise of the Beasts and
Transformers: The Last Knight to their unchanged source HEVC remuxes, including
the original tracks and Dolby metadata. Each library file shares its physical
device/inode with the retained source. No video payload was copied or encoded.
The 249,905,047,569 source bytes were already on disk. Previous AV1 files remain
as 55,505,033,251 bytes of rollback backups outside Movies.

The first physical-backend rename was caught by the merged filesystem's stale
cache and rolled back. The successful installation renamed through mergerfs,
matching the repair worker's established method. Both attempts remain journaled;
the restored files have matching source probes and exactly one physical library
path each. Emby and Radarr refreshed all four and report HEVC with the correct
original sizes. Four scoped Movies-folder exclusions prevent Tdarr processing;
only their stale Tdarr database records were removed, with metadata backups.

The work ledger and four repair states carry an explicit user hold. No FEL
encoder was deployed. Future FEL work requires a new user decision and fresh
library-track qualification against these restored originals.

## Ordinary Tdarr and audit follow-up

At restoration preflight, ordinary Tdarr had resumed despite the existing
fidelity hold. Its cause is not established; the Emby watchdog reported no owned
pause and its log showed no corresponding resume. Admission was paused again.
The two unrelated running jobs, Neagley S01E01 and Reacher S04E08, completed
successfully. The node now has no active workers and remains paused.

After removing the four excluded FEL entries, the current Tdarr index has 5,481
AV1 paths. The two just-completed versions are outside the earlier audit snapshot
and need catch-up measurement. This is separate from its two known native-source
pairing gaps. No automatic-retention campaign was started and no additional
library recovery downloads were selected.

## Evidence and rollback

Source/repair receipts live under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/source-release-review-20260916/`:

- `repair-provenance.json`: every recorded repair, current identity, build and review-queue membership.
- `torrent-dependencies.json`: original 345 held torrents and dependent library keys.
- `release-plan.json`, `release-result.json`: exact two releases, original/current settings and relocated source paths.
- `current-version-catchup.json`: the two new AV1 versions needing measurement.
- `tdarr-pause-reasserted.json`: observed active jobs and pause action.

FEL restoration receipts live under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-production-20260914/original-restore-20260916/`:

- `report.json`: physical inode identity, probes, library signatures and exact backup paths.
- `tdarr-exclusion.json`, `tdarr-records-before.json`: owned exclusions and prior database metadata.
- `emby-after.json`, `radarr-after.json`: application readback.
- `work-plan-before.json`, `*.state-before.json`: prior ledger states.
- `attempt-1-cache-rollback.json`: retained initial rollback evidence.

Do not run restoration scripts again: they intentionally reject an existing
receipt. A future rollback must use its recorded per-file backup and a rename
through mergerfs, retain the HEVC originals, and explicitly reconcile the user's
FEL hold. Do not restore old database records over new versions without review.
