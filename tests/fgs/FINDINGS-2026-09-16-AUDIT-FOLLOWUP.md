# Approved audit follow-up — September 16

Status: **both approved originals recovered and validating; current-version audit
and source-backed candidate review running.** The comprehensive audit remains
open. Production encoder and routine Tdarr validation are unchanged.

Start with [live progress and job health](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/status.json)
and the [local work record](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/README.md).
The [reconciled starting results](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/result-review-20260916/README.md)
retain confirmed findings, earlier repairs and complete file lists.

## Narrow recovery authorization

The user approved recovery/retranscode of the two extended Girl films with
multi-second story-scene decoding gaps, completing current-version measurements
and reviewing candidates. This is a two-release exception to the general
recovery hold. It does not authorize downloads for the conservative historical
1,981-file/9.5 TB scope merely from flags.

Archived torrents for *The Girl Who Kicked the Hornets Nest* and *The Girl Who
Played with Fire* were verified against their hashes, exact file names and
sizes. Only those two video files were selected: **77,260,158,468 bytes** total.
Incomplete and completed storage use the existing data-drive recovery category.
Both downloads completed; source timing, progressive-segmented-frame checks
and content alignment passed before encoding with ordinary core `ef5c61fe`,
SHA-256 `d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b`.

The worker must still pass complete decoding, grain and retained-track/chapter
checks before installation. Original and superseded files remain retained.
`approved-recovery-plan.json`, `recovery-events.jsonl` and `recovery-started.json`
bind the authorization. `verify_recovered_movies.py` waits for these exact
installations, snapshots their new identities and runs header/decoded/source
checks with prior defective-region anchors. A hold or identity change is not
a successful replacement.

## Current-version measurements

The starting index has 5,483 AV1 files: 4,872 exact versions with completed
reference-display measurements and 611 requiring follow-up. All 611 were
freshly probed with no inventory errors. The immutable new manifest separates
**482 display-eligible files** and **129 SD files lacking colour metadata**.
The initial manifest knew 383 originals. Read-only Sonarr/Radarr import records
and an exact-filename search of retained downloads recovered associations for
**202 more originals**, all passing codec, dimensions, duration and identity
checks. Source availability is now **585 of 611**, with 26 still unmatched.
This is initial correspondence, not proof of matching every scene: each decoded
window must still pass source alignment. See `additional-sources-qualified.json`
and `source-enrichment-summary.json`. The decoder was drained and restarted on
`display-manifest-enriched.json`; its first 21 measurements had unchanged source
bindings and were retained. No source media was redownloaded for this step.

The display queue uses unchanged qualified `tools-v5/` helpers and inspector.
Its two-worker scheduler retains low CPU/I/O priority. It initially hit a race:
the consumer started before the header producer wrote `status.json`. No files
were measured or consumed. The fork now permits bounded startup and publishes
a paused queue for a missing/stalled producer. Eleven scheduler controls pass;
the corrected job and retained failure evidence are in `decoded-restart.json`.
No measurement threshold changed.

The new native-source route checks every selected displayed frame against the
headers, every native Y/U/V sample, unique complete source pairing and the
existing coarse-picture alignment threshold. It separates mean shift from
noise without inventing colour metadata. `native_measured_display_unavailable`
keeps the display-mapping gap explicit. It is not visual clearance. Nine CPU
controls pass, including frame/colour-edge loss, timing mismatch and grain-free
output changes. Scrubs S01E01/E02 qualify all 24 selected windows and 336 frames
against their originals. The 129-file batch uses frozen tools afterward.

Two subsequent Scrubs comparisons exposed a source-seek problem: S02E21 and
S03E19 missed a reference-dependent picture. Decoding S02E21 from the beginning
confirmed that its original picture at 203.245 seconds exists. A one-second
preroll was insufficient; a bounded ten-second decode followed by timestamp
selection restored both failures. The native route retries only this missing-
pair failure, retaining every unique frame, the 2.1 ms tolerance and content
alignment. The default shared decoder command remains unchanged.
Thirteen native-route and fourteen source-review CPU controls pass. Real
qualification covers **30 windows / 419 frames**, restores two failed windows
and reproduces all 28 formerly successful windows exactly. Frozen v2 helpers
and `native-preroll-qualification.json` retain the evidence. A finite retry job
handles further failures after the primary 129-file batch finishes. Earlier
errors remain recorded; they are not evidence of damaged source media.

## Candidate review and source retention

The 515 unreviewed candidates receive up to two high-ranked source/on/off image
witnesses. Extraction completion does not establish damage or warrant repair.
Five PQ/HDR files require appropriate HDR visual mapping separately. A VC-1
image-extraction seek issue was corrected by decoding before the witness and
selecting its timestamp, retaining the 2.1 ms check. The failing Venture witness
now passes; the Rent control produces identical image hashes.

Initial visual comparisons of Venture Bros S06E07, Rent, Adventure Time S10E11
and Samurai Jack S02E12 confirm added coloured grain in source-clean regions.
Three inspected large-area flags concern mostly black surrounds or credits;
Adventure Time includes a clean white story background. These are not evidence
that the ranked fraction of story footage is damaged. The three cartoon files
carry the older `5423d8…` repair build.

Complete-duration checks of the selected regions run with source/on/off
pairing and mandatory numerical witness reproduction. The Adventure Time
check finished: **24 stronger frames across 16,438 displayed pictures**, two
bursts of 15 and nine frames; longest about 0.6 seconds. This supports low
immediate priority in those regions and does not clear other regions or weaker
noise. No additional repair or download was selected from these observations.
Venture Bros S06E07 also finished: six stronger frames across 32,448 pictures,
all in the measured credit-background region. Samurai Jack S02E12 has 27 across
32,899, including one 25-frame burst around 20:04 in the measured black border.
Rent continues. These spatially bounded checks are lower bounds, not proof that
every other part of each film is clear.

An additional luma-focused review avoids black chroma borders dominating the
priority list. Exact source/on/off witnesses show conspicuous added grain in
The Owl House S02E08 around 12:21, plus added grain in clean story regions in
Adventure Time S07E25 and Smiling Friends S01E04. All three installed files carry
the older `5423d8…` build. Full-duration selected-region recurrence and finite
full-source trials of the **unchanged deployed `ef5c61fe` image** have finished.
All three pass their old-witness and new-transition source comparisons. Actual
source/old/current stills show the added clean-region grain removed. In the
poster witness, the current build also retains the deliberate dot pattern more
faithfully than the older repair.

The Owl House S02E08 has 431 stronger frames in 75 measured bursts, longest
70 frames (about 2.9 seconds). The current candidate has **zero** such frames
across all 32,136 pictures in those same four source-qualified regions.
Adventure Time S07E25 has 153 in seven bursts, longest 72 frames (about three
seconds). These two qualify for retained-source repair, conditional on passing
candidate recurrence and all normal worker checks. `story-repair-selection.json`
records the rationale. The finite worker reuses the exact tested videos, retains
old receipts/files and its owned admission hold, and releases that hold after
both installations pass. `story-repair-verification/` then measures the fresh
installed versions. No new downloads or encoder changes are involved.

Smiling Friends S01E04 has 53 stronger frames in six measured bursts, longest
28 frames (about 1.2 seconds); it remains lower priority and is not selected.
Sixteen actual visual witnesses are recorded so far, and nine further selected-
region recurrence checks run serially behind the first luma batch. The rest of
the 515-file candidate queue remains open. These diagnostics do not start the
deferred automatic-retention campaign.

All 907 source paths needed for the queued measurements/review are present.
The 195 mapped torrents have no cleanup exposure under their current groups.
One Hazbin Hotel source lacks a live torrent association; a verified hardlink
outside torrent cleanup roots retains it without copying payload bytes.
See `source-protection-check.json` and `unmapped-source-retention.json`.
The 202 newly found originals map to 34 live torrents. Eleven already had safe
retention; the other **23 now carry the existing audit-hold tag** and verified
unlimited native seeding limits. The total audit-tag count is 345, including
the two recovered films. The qbitmanager configuration was unchanged.
`additional-source-protection-applied.json` records this extension. Release only
owned audit tags after all dependent review/repair work is done; preserve other
holds and let the then-current ordinary seeding policy apply.

Large evidence lives under
`/media/storage1/tdarr-audit-evidence/full-temporal-audit-20260912/followup-20260916`
and is linked from the ledger. Scratch recurrence crops use `/tmp/downloads`
and are removed only after full measurement and witness checks are recorded;
compressed frame metrics remain retained. `resource-adjustment.json` records
reduced auxiliary CPU quotas while the two movie validations run. The display
queue remains two concurrent files within a three-CPU cap during this phase;
measurement settings and normal Tdarr validation are unchanged.

## Required finish

1. Verify both movie installations and the two selected retained-source story
   repairs, including fresh installed-version checks and hold release.
2. Finish the 611-file queues; resolve failures and later changed versions.
   Preserve the native route's display-mapping limitation.
3. Complete contextual candidate review and recurrence, including five HDR
   cases; qualify further repairs only where severity/persistence warrants them.
4. Publish a reconciled library result and release source protection only for
   reviewed batches without outstanding dependent work.

All eleven September 15 ordinary Tdarr error retries succeeded. Four FEL
repairs remain separately held for production/playback qualifications. Optional
retention GPU trials remain manual-start only and were not started here.
