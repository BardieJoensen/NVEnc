# September 14 held repairs and FEL conversion scope

All ten non-FEL held repairs are installed and independently verified. The
finite batch completed at 12:42:53 UTC; Tdarr resumed automatically at 12:49:08
UTC and both GPU workers were observed processing the ordinary backlog.
The repair queue now records **1,880 installed, four FEL holds, zero ready**.
Daniel Sloss's separate timing correction is also installed with rollback.
The completion ledger is
[/opt/docker-apps/logs/fgs-ripple-repair-20260906/held-repairs-review-20260914/implementation](/opt/docker-apps/logs/fgs-ripple-repair-20260906/held-repairs-review-20260914/implementation).
Read `final-verification.json` for installed hashes and validation,
`final-operational-state.json` for restoration, and `reviewed-repairs-run.json`
for each admission and result. This covers these repairs, not whole-library
perceptual clearance.

## What was wrong

The original queue reached 1,870 installed replacements and 14 holds. All 14
retained originals were available on September 14. Ten holds were resolved
through the existing source-repair path after focused validation corrections:

| Files | Evidence and correction |
| --- | --- |
| Six Borgen S2 episodes: 3, 4, 5, 8, 9, 10 | Old AV1 files have misleading average frame-rate metadata and irregular packet timing. The paired-field H.264 sources report 50 fps but sampled decoded pictures are 25 fps. Require complete source picture-count/timestamp measurement, retain the existing progressive-picture check, then validate every replacement packet against the reviewed source clock. Never use this as a general frame-rate bypass. |
| The Bridge S1E4/E10 | Expanded IDET sampling finds eight qualifying progressive passages out of ten in each episode. No passage exceeds the existing 2% woven-frame limit. Unknown/static passages are inconclusive. A file-bound reviewed policy permits these specific sources after a complete 25 fps source-clock check. Other files retain the original gate. |
| Flame and Citron | All 24 stored chapter structures are identical. FFprobe inferred a different final chapter end from the replacement video's end, although that chapter stores no explicit end. On a probe mismatch, compare the actual extracted Matroska chapter tree, including explicit ends, order, titles, languages and identifiers. |
| Scrubs S5E7 | All 471 SubRip cues retain exact start times, durations, text, internal CRLF, indentation and markup. mkvmerge removes one terminal CRLF from each cue (942 bytes). On a stream-hash mismatch, allow only this precise SubRip change, with complete packet inspection and independent hash agreement. Audio and every other subtitle codec still require exact payload hashes. |

The helper is [repair_media_guard.py](../../tools/fgs/repair_media_guard.py),
with [regression tests](test_repair_media_guard.py) and the operational worker
integration patch in `tools/fgs/repair-worker-media.patch` (zero-context patch;
apply with `git apply --unidiff-zero` against the recorded worker base). The deployed helper
copy is `/opt/docker-apps/scripts/fgs_repair_media_guard.py`. Per-file policies
pin library/source signatures and evidence SHA-256; incomplete or changed
evidence cannot authorize an exception. Source originals are never modified.

The new chapter and subtitle paths passed on the retained diagnostic candidates
and on the final installed files. All ten installed videos use production core
`ef5c61fe`, binary SHA-256
`d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b`.
Nine were newly encoded; Scrubs reused an already-qualified encode from that
same build after verifying its source, command and output hashes, then remuxed
and completed full validation. No old-build video was relabelled as current.
The ordinary Tdarr flow, encoder core and its routine validation are unchanged.

All 24 relevant regression tests pass: 13 media-preservation/policy tests,
eight repair alignment tests and three Dolby Vision guard tests. Complete
source decoding measured 698,229 pictures across the eight Borgen/Bridge
episodes, all at 40 ms intervals with no decode errors. Each encoded and final
muxed output matches its complete source clock and frame count. Final full-file
libdav1d decoding completed for all ten outputs (935,911 pictures); both grain
scans and chapter/nonvideo preservation checks passed. Installed SHA-256
hashes were rechecked against receipts, original source identities remained
unchanged, and every prior library version remains available for rollback.

The ten containers total 23,255,999,564 bytes versus 21,228,171,454 bytes for
their immediately preceding library files: +2,027,828,110 bytes (+9.55%). This
is a measured comparison for this selected repair batch, not an estimate for
the rest of the library or automatic retention.

## Daniel Sloss: Hubris timing correction

The separately qualified timing remux is installed. The receipt is
`implementation/daniel-installation.json`; the authoritative pre-install
qualification is `daniel-final-v5-verification.json` in the parent ledger.
Installed SHA-256:
`9df925e2d676b3c03134a3b06ccc5fb9ee0c0317fe4962f0077e4afc36606609`.

It preserves all 120,598 video packets, 241,202 audio packets and 1,352 subtitle
cues, including their complete payload hashes. Audio/subtitle timings and
stream order match exactly. Video now has uniform 40 ms steps, replacing
25,364 duplicate timestamps while preserving its original start and end.
Three decoded 80-frame sequences match in picture order. The deployed cadence
guard passes. The original is retained under
`/media/storage1/tdarr-repair-backups/held-timing-20260914/`.
Tdarr's file watcher detected the installed file and queued it normally.

This was bad timing in the H.264 input, detected before NVEncC started. The
available historical job reports cannot establish whether the release or a
previous stream-copy operation introduced it. The correction does not
re-encode the payload or weaken the cadence guard.

## What the earlier Dolby Vision fix did

[The September 9 readiness work](FINDINGS-2026-09-09-READINESS.md) qualified
Profile 7 MEL metadata normalization for AV1 Profile 10.1. It removed invalid
dual-layer signalling while preserving the supported reshaping/display
metadata. That work explicitly did not reconstruct FEL picture contributions.
The four present FEL holds are Bumblebee, TRON: Legacy, Transformers: Rise of
the Beasts and Transformers: The Last Knight. Their originals remain retained.

It is too broad to say FEL can never be used when creating AV1. A separate
reconstruction stage can combine BL, EL and RPU into a picture before encoding:
[DoViBaker](https://github.com/erazortt/DoViBaker) documents PQ12 reconstruction,
and [felbaker](https://github.com/bbeny123/felbaker) offers a VapourSynth/Linux
implementation. These are candidate components, not qualified dependencies of
our deployment. Dolby describes
[Profile 10](https://professionalsupport.dolby.com/s/article/Introduction-to-Dolby-Vision-Profile-10)
as single-layer 10-bit AV1. Encoding a reconstructed picture into that format
does not carry the original enhancement stream or preserve every 12-bit sample.

Merely [converting RPU metadata](https://github.com/quietvoid/dovi_tool#conversion-modes)
does not perform picture reconstruction. A prospective pipeline needs correct
BL/EL/RPU frame alignment, reconstruction, colour/range conversion and dithering,
then AV1 encoding and metadata adapted to those already-reconstructed pictures.
It must avoid applying reshaping twice. Compare against independently decoded
FEL pictures, check HDR/DV metadata and actual playback, and measure runtime,
memory and output size before allowing a full movie through.

DoViBaker's default reconstruction does not apply display-management trims;
retaining suitable dynamic metadata is a separate integration requirement.
The Linux port also documents arithmetic/colour differences from DoViBaker;
its benchmark claims alone are not fidelity qualification. Use bounded clips
and streaming intermediates, not multi-terabyte raw movie intermediates.
No FEL trial, replacement, new download or optional retention campaign was
started by this repair batch. The existing P7 MEL build admission pin is also
unchanged; this batch contains no MEL source needing that path.

## Completed batch and remaining work

`fgs-held-reviewed-repairs-20260914.service` completed successfully and is
inactive. It admitted only the ten listed files, at most two workers, after
draining current Tdarr jobs and qualifying each reviewed source. Its owned
admission hold was released only after all ten installed; the normal
coordinator reclassified the four FEL inputs as held, then resumed Tdarr under
its existing five-minute idle rule. No repair worker remains active, and the
coordinator no longer owns a Tdarr pause. The live coordinator still preserves
Emby playback yield. The earlier two-file mux starter was superseded before
admission and is inactive.

The primary library CPU audit pass finished at 10:57 UTC (4,896 measured,
264 superseded, zero pending in that manifest). Current-version catch-up and
review remain pending, including these replacements and new ordinary Tdarr
AV1 outputs. Published coverage was refreshed after the repairs. Two recorded
Scrubs measurement errors are unsupported/missing colour metadata, not proven
decode failures; two obsolete movie paths now correspond to upgraded H.264
releases. Diagnostic candidate counts are not confirmed damage or download
lists. See the audit's `acceleration-20260913/completed-pass-20260914/` receipts.

`implementation/reviewed-repairs-run.json` records per-file commands, code
hashes and results. Per-file state under the main repair ledger remains the
installation authority. A held worker exit is not success even when its process
returns zero. Do not rerun this completed batch or repeatedly retry FEL through
the ordinary path. FEL reconstruction needs separate implementation and
qualification; the four retained sources remain available for that work.

The source download/recovery hold, qbitmanager source-retention tags and
manual-start-only retention-trial policy remain in force.
