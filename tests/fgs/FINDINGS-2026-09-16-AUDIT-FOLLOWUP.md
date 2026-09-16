# Approved audit follow-up — September 16

Status: **both approved films and two retained-source episode repairs installed
and postchecked; current-version audit and source-backed review running.**
A further Gentlemen S01E01 replacement is passing normal installation gates.
The comprehensive audit remains open. Production encoder and routine Tdarr
validation are unchanged.

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

Both films passed complete decoding, grain and retained-track/chapter checks
and are installed. Original and superseded files remain retained.
`approved-recovery-plan.json`, `recovery-events.jsonl` and `recovery-started.json`
bind the authorization. `recovered-movies/status.json` records successful fresh
installed-version measurements, including the old defective-region anchors.
All 261,705 / 263,190 displayed headers are covered. Neither new film carries
synthetic grain; the nine decoded/control/anchor windows report grain absent.
This is not a whole-film source-fidelity comparison. The new containers are
14.65 / 16.03 GB, +15.15% / +12.69% versus the prior broken containers.
`four-repairs-completed.json` binds exact identities, backups and preservation
proof for these films and the two episodes below.

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
handles further failures after the primary 129-file batch finishes. The primary
native pass is finished; the qualified retry leaves 127 exact versions measured
and two source-pairing gaps open. Scrubs S05E02 has a source packet at 2.252 s
that two independent software decoder versions omit, even starting at the
beginning. Scrubs S07E11 independently shows the same behavior at 1.418 s in both decoder
versions, also starting from the beginning. These stay
failed source comparisons; timestamps and required frame coverage were not
relaxed. Read `native-retry/source-clock-review/`,
`native-retry/source-clock-review-s07e11/` and the native reports.

All **611 header scans now pass**. A temporary audit cgroup freeze used to
prioritize installation I/O allowed wall-clock deadlines to expire in two header
scans, two display/source checks, one native check and one still extraction.
These are operational interruptions, not media defects. Every cgroup was thawed;
`pause-timeout-recovery.json` retains the incident and prevention rule: use
graceful active-file drain/checkpoints for future pauses. The two header retries,
native timeout retry and image retry pass. The finite `decoded-retry/` waits for
the primary display pass, then retries failed measurements and any timed-out
source subchecks, including files otherwise labelled measured. Original failure
evidence remains. No measurement threshold changed.

## Candidate review and source retention

The 515 unreviewed candidates receive up to two high-ranked source/on/off image
witnesses. Extraction completion does not establish damage or warrant repair.
All 510 SDR image sets are now staged after the one operational retry. Five
PQ/HDR witnesses were separately extracted and reviewed with explicit fixed
BT.2020/PQ-to-BT.709/sRGB mapping. Their source-quiet peaks lie in black bars;
no conspicuous story defect was demonstrated in those mapped stills. Static
1000-nit-to-100-nit diagnostic mapping is not Dolby Vision or HDR playback
qualification, and a single witness does not clear a film. A VC-1
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
seconds); its candidate has zero across all 16,570 pictures in those selected
regions. Both repairs passed the normal full worker checks and are installed.
Their fresh installed-version header and 13-window audits also pass. Exact
old receipts/files remain; the owned admission hold was released and ordinary
Tdarr resumed. `story-repair-selection.json`, `story-repairs/` and
`story-repair-verification/` retain the proof. The containers grow 40.53 MB
(14.36%) and 5.12 MB (1.88%). No new downloads or encoder changes were involved.

Smiling Friends S01E04 has 53 stronger frames in six measured bursts, longest
28 frames (about 1.2 seconds); it remains lower priority and is not selected.
Twenty-seven distinct files have actual visual observations recorded, including
the five HDR cases and six additional full-image-ranked witnesses. Nine further
selected-region recurrence checks run serially behind the first luma batch.
Early results include Steven Universe S02E27 (670 stronger frames / 16,667,
longest 84) and Regular Show S02E06 (1,055 / 16,319, longest 112). These warrant
current-build qualification before another repair selection. Both exact-image
trials now pass their 24 old/new source windows. Their full-duration selected-
region checks fall from 670 and 1,055 stronger frames to zero, with unique
timestamp/source identity checks unchanged. Actual full-resolution comparisons
show clean character artwork restored while retaining the intentionally textured
backgrounds. `next-story-repair-selection.json` records the evidence-based
retained-source repeat repairs; `next-story-repairs/` and
`next-story-repair-verification/` record successful normal installation and new-version checks. Steven Universe
passes 12 installed source windows and grows 13.66 MB (4.13%); Regular Show
passes 13 installed windows (12 source-compared, one without synthesized grain)
and grows 29.63 MB (13.39%). All seven selected replacements now have completed
worker and fresh post-install evidence in `seven-repairs-completed.json`. The
owned admission hold was released; originals and backups remain. No new downloads or encoder changes are involved. The rest of the
candidate review remains open. These diagnostics do not start the deferred
automatic-retention campaign.

## Complementary whole-image review

The Gentlemen S01E01 exposed a review-priority limitation: its native quiet-
source flag covered only 256 pixels, yet a source/on/off witness at 38:45 shows
conspicuous crosshatched grain across much of the picture. Quiet-source fraction
is a locator, not an estimate of visible screen area or severity. The existing
full-image measurements did record the high amplitude; the initial ordering
underweighted them. `whole-image-review-priorities.json` / `.csv` now provide
a separate ordering by full-image amplitude, with temporal changes,
directionality, source correspondence and display mapping retained. They reuse
qualified measurements, check current identities, and do not classify every
grain-bearing file as damaged. Review SDR and PQ mappings separately.

Six diverse source-backed witnesses illustrate why scene review still matters:
Play Dirty has heavy added grain over a city shot; Futurama S10E04 spills its
intentional television static onto the clean surrounding wall/casing; Cunk on
Life roughens a painted illustration. Their recurrence remains to be established.
Alice in Borderland, Cyberpunk and Venture Bros witnesses already contain
intentional screen/glitch/grain effects; large amplitude alone does not justify
repair. `whole-image-review/visual-decisions.json` records those distinctions.
All six exact library versions use older `5423d8` or `bb7e75` encoders.

The Gentlemen trial uses the unchanged deployed `ef5c61fe` image and retained
original. It passes all 13 prior and 12 new source windows. Five source/old/current
visual comparisons show the severe 38:45 overlay removed and the logo improved;
weaker added-grain differences remain in the truck/building scenes. This is an
improvement, not whole-episode perceptual identity. `gentlemen-repair-selection.json`
selects this repeat repair with normal full decoding, grain, timing and retained-
track gates. `gentlemen-repair/` and `gentlemen-repair-verification/` track the
installation and fresh measurements. Installation is now complete: strict
full decoding, grain/timing gates, retained-track hashes and chapters all pass.
The exact new version `f79ea0116639339d` passes 15 installed-version windows
(13 source-compared and two without synthesized grain), including the earlier
34:05 anchor. The container grows from 1,455,838,076 to 1,579,046,118 bytes
(+123.21 MB / 8.46%). Backups and original remain; the owned hold was released.

The severe Play Dirty city witness is receiving a separate full-source trial
with the unchanged deployed image. This is a stress case for the complementary
review: the old source-qualified window has no source-quiet luma patch, so that
criterion alone cannot approve fidelity. `city-trial/`, `city-qualification/`
and `next-trial-visuals/31f295cbb640d53811d6/` retain the trial and comparison.
Candidate scene review and recurrence must precede any movie repair selection.

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
reduced auxiliary CPU quotas during movie validation. After the four completed
installations, `resource-adjustment-after-repairs.json` restores the display
queue's original six-CPU allowance, retaining two concurrent files and low
CPU/I/O priority. Measurement settings and normal Tdarr validation are unchanged.
The finite `reconciliation/` waits for the follow-up scans and qualified retries,
then publishes current identities, source-comparison gaps and the remaining
review backlog. Its completion never means whole-library perceptual clearance.

## Required finish

1. All seven selected repairs are installed and postchecked. Their admission
   holds were released, but the later Play Dirty deployed-build failure has a
   separate active hold. Isolate and qualify a correction before resuming encoding.
2. Finish the 611-file queues; resolve failures and later changed versions.
   Preserve the native route's display-mapping limitation.
3. Complete contextual candidate review and recurrence using both source-quiet
   and full-image priorities; qualify further repairs where severity/persistence
   warrants them. The five mapped HDR stills retain their playback limitation.
4. Publish a reconciled library result and release source protection only for
   reviewed batches without outstanding dependent work.

All eleven September 15 ordinary Tdarr error retries succeeded. Four FEL
repairs remain separately held for production/playback qualifications. Optional
retention GPU trials remain manual-start only and were not started here.

## Current deployed-build failure: Play Dirty

The full-source trial **fails actual visual qualification**. The exact deployed
image retains severe source-absent grain across the city at 856.375 s and strong
added grain over the later dialogue witness at 5727.625 s. This is not an
installation candidate. `next-trial-visuals/31f295cbb640d53811d6/visual-qualification.json`
and `city-more-witnesses/` retain the images. The 24 sampled source-alignment/
quiet-region checks pass, illustrating their documented limited scope: the
city window has no quiet luma evidence. Passing those checks alone does not
establish full-picture fidelity.

`city-reproducer/` records a bounded 30-second default-mode encode in the exact
production image, with debug model traces. Around 856.375 s the source estimate
is much lower than the held grain curve still being emitted. This is a lead,
not a completed root-cause finding. Independently paired native source/on/off
decodes find median source 16x16 sigma 8.69 versus synthesized-grain sigma 26.13
(native code values normalized to eight bits); 4,034 of 6,000 blocks exceed
source sigma by both 1.5x and one code value. Source variance includes real
structure, so this is strong excess evidence, not a qualified new detector.

`city-fidelity-hold-before.json` and `city-fidelity-hold.json` record the
operational pause. There were zero active Tdarr workers. The idle repair
coordinator was stopped, Tdarr remains paused, and a separately owned
`worker-admission-hold.json` blocks new repairs. Read-only audit jobs and source
protection continue. No production binary changed, no Play Dirty replacement
was installed and no optional-retention campaign was started. Resume only after
a qualified correction or explicitly reviewed operational decision.
