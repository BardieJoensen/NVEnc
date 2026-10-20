# R18 resource blocker and exact restart

No candidate meets the user's at-or-below-original bitrate ceiling. R18 has
verified local q4 delivery and legal, decoder-consistent output at
12.6716968Mbps, 30.9530% above E05's 9.6765224Mbps original window. Its two-pass
runtime is214.344583s for336frames. R18 quality and playback remain unassessed.
The strongest previous demonstrated texture preservation remains R15's
190.4115432Mbps (19.6777xoriginal),692.476910s diagnostic; it is not practical.
R16's original-rate arm and R17's fixed-choice q4 diagnostic are valid negatives.

Both runtime child agents, `/root/coefficient_worker` and `/root/method_reviewer`,
returned the same usage-limit failure. The reported reset was
`Oct 27th, 2026 2:36 PM` (timezone not specified by the notification). The parent
did not retry through another model or simulate independent review. This is an
external resource stopping condition. It does not show the codec cannot succeed.

Completed reviewed implementation and parent-inspected outcome evidence:

- Immutable cap-disabled baseline and fresh first-pass statistics controls.
- Real cap1 output, actual remux packet rates and encoding runtime.
- Corrected observer build with exactly neutral bitstream/reconstruction/stats.
- Strict nominal trace admission:339attempts,336accepted pictures,9408selectedSBs
  atq4,428862invoked/1326uninvokedTUs and complete38,535,168-pixel support.
- All336 encoder/dav1d/libaom/NVDEC and native decoder off/on equality.
- Independent packet/header/reference-slot display binding.

Unfinished work is explicitly excluded from those claims:

1. Independent review of `parent/psyex-cap-r18/admit_native.py`, SHA256
   `fc4ff63a76766403ee04ab16d5d212e8a069cfcef00a208ea6ae1c83f9bb32b5`.
   It was not executed. Review actual receipt schemas/outer argv, all336 display
   joins, accepted-generation/source boundaries and exact native q/DQ/EOB/IQM
   ownership. Then execute under the pinned outer wrapper in a fresh directory.
2. Bounded strict-reader, semantic and provenance corruption controls. The
   worker failed before producing a control script. Preserve the original trace;
   each negative must fail the intended check, with a valid positive control.
3. New R18 campaign.py GPU full-reference metrics/tails/CAMBI; exact scored-frame
   validation; five-frame HF+ACF/correlation; full12870frozen tiles, face/edge and
   temporal evidence. Keep the legacy outside mask for comparison and add the
   actual28selected-SB mask. Include comparison with R16 and the preserved R8
   baseline; document all regressions. No such R18 score has been run.
4. Only if preservation passes, test redistribution into99–100% of original
   scored packet rate and examine the entire window for displaced damage. If
   that fails, choose the next discriminator from the measured loss boundary.
   E04, held-out windows, full-episode costs and real playback remain mandatory
   before any production proposal.

Use `trace-index-2.json` SHA256
`b873769031192a25c074843829525f73bc330ff7f47bec20d8a2e17a139b292b`
and `trace2-admission.json` SHA256
`4f430b982b0ac9f473fc1c81764a6ca7fb672fda9ebc4c78757518844b42fe3e`.
The original cap, corrected observer and native decoder have distinct recorded
build identities; retain them. Repeating unchanged completed encodes adds no
information and is unnecessary. [Report](PSYEX_CAP.md),
[hypotheses](HYPOTHESES.md), [ledger](LEDGER.md),
[control manifest](psyex-cap/controls/manifest.json) and
[observation manifest](psyex-cap/observations/manifest.json) are the durable entry
points. Completed GPU metrics and visual artifacts for earlier rounds remain
linked from their reports; no new R18 still or motion acceptance is implied.

Archival and restoration status is recorded in [ARCHIVE.md](ARCHIVE.md). No
production source/binary/configuration, Tdarr, torrent or library change occurred.
