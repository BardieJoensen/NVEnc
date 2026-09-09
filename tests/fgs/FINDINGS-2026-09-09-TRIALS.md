# Fidelity trial admission and full HDR follow-up — 2026-09-09

The outstanding paired HDR encodes, complete decodes, metadata comparisons and
size admission are complete. The candidate passes these checks. The work also
localizes the observed repeat variation beyond identical submitted pictures
and exported grain models; it does not establish universal determinism or
remove that variation. Production Tdarr still uses its existing encoder and
flow. These changes and measurements are on the local fidelity branch.

This follows [the cost study](FINDINGS-2026-09-08-COST.md). It tests the same
immutable directional candidate, core `ae50ed9d`, with bilateral
`retain=auto,retain-max=0.1`, against deployed `e778a88b` at default retention.
The new main-branch code in this follow-up concerns trial admission, metadata
verification and avoiding repeated source hashing. Diagnostic encoder changes
remain on a separate experimental branch.

## Completed whole-title results

All outputs below are video-only scratch encodes made with the production video
settings. Each baseline and candidate passes the full synthesis-texture scan,
complete grain-on and grain-off decoding, frame count, timeline and declared
video-property checks. The SDR encoding results come from the preceding study;
their actual artifacts now also pass the new size admission.

| Retained source | Frames | Production-default bytes | Candidate bytes | Extra bytes |
| --- | ---: | ---: | ---: | ---: |
| The Gentlemen S01E01 | 96,671 | 992,177,278 | 1,008,063,141 | +1.60% |
| South Park S23E01 | 32,176 | 268,741,386 | 275,134,375 | +2.38% |
| House of the Dragon S03E08, 4K HDR/DV | 100,851 | 3,189,350,318 | 3,204,249,118 | +0.47% |

The HDR candidate has three strength-fidelity fallback frames and eight
successful fresh-model retries. Neither the low fallback count nor these three
titles predicts every title's byte cost or visual quality.

Three additional 1,080-frame Blade Runner UHD HDR/DV clips start at 00:10:00,
00:58:20 and 01:43:20. Their candidate byte increases are respectively +3.20%,
+8.14% and +3.90%. All six clip outputs pass the same complete decode, synthesis,
timeline and color checks. These roughly 45-second clips cover different
footage but do not establish the complete film's size increase.

## HDR metadata and its limits

`hdr_metadata_trace.py` records metadata on every displayed frame, verifies the
expected source hash and count, and requires a clean, completed decoder run.
It compares timestamps, stream properties, mastering display and content light
metadata, and all parsed Dolby Vision/HDR10+ fields exposed by FFprobe.
Mastering-display values are normalized to AV1's specified fixed-point units
so mandatory format rounding is distinguished from a changed value.

For the full HDR episode, the retained HEVC source, production baseline and
candidate each have 100,851 frames carrying mastering-display, content-light
and parsed Dolby Vision metadata. Both encoded outputs match the source on
every compared frame and stream property: **zero metadata or timing mismatches**.
The source is Dolby Vision profile 8 without an enhancement layer; the AV1
outputs are profile 10 with matching presence and compatibility flags.

Each Blade Runner candidate also matches its corresponding baseline's decoded
HDR/DV metadata on all 1,080 displayed frames. This old/new comparison does not
independently prove the common seek-to-source alignment. The complete episode
provides the direct source comparison.

This evidence covers the tested profile-8-to-profile-10 conversion. It does not
validate Dolby Vision enhancement-layer reconstruction, every Dolby Vision
profile, HDR display rendering, or a real HDR10+ title. The generic parser's
HDR10+ support should not be mistaken for such media-backed coverage.

The local FFprobe build has an XML printing failure when grain application is
disabled and film-grain side data is exported. A synthetic fixture reproduces
the failure; ordinary XML metadata recording and separate grain-off pixel
decodes work. The completed audit uses the working default mode. The separate
printer investigation was stopped, with no system-tool replacement or
FFmpeg patch included in the encoder branch.

## An explicit size decision

`trial_admission.py` requires a completed paired comparison, the explicitly
expected candidate build, unchanged source and output hashes, and successful
full decode, synthesis, timing and video-property checks. It probes the actual
containers and requires exactly one AV1 video stream in each.

The default trial budget is the measured production-default video-only file
size plus 10%, rounded down to a whole byte. This is a selected trial limit,
not a guarantee made by `retain-max` or an enabled production Tdarr policy.

An accepted candidate is copied independently into a fresh staging directory,
checked again and accompanied by a decision receipt. An oversized output
returns `keep_source`, stages no candidate and exits with status 3. It does not
increase QP, suppress fidelity guards, substitute the old baseline, or replace
the library input. A missing or changed artifact prevents admission.

The real fine-detail stress encode grew from 649,737 to 1,337,346 bytes
(+105.83%). Both outputs passed their scans and decodes, but the candidate
exceeded its 714,710-byte budget and was correctly refused. All three complete
titles above are admitted below 10%, including the HDR title's limit of
3,508,285,349 bytes. The source remains in place in both outcomes.

Final HDR admission exposed a helper bug: FFprobe includes `side_data_list`
even when only stream type and codec were selected. Exact dictionary equality
therefore rejected a valid single Dolby Vision video stream. Admission now
checks stream count and the required codec/type fields, allowing associated
metadata. Regression tests accept that real response shape and still reject
audio, subtitles, multiple videos, missing fields and non-AV1 video. The complete
HDR artifact passes the corrected admission.

A hard limit relative to the old encoder needs its complete measured output.
New inputs therefore incur another encode unless a matching pinned baseline
already exists. An estimate from short samples cannot provide this guarantee.
The existing Tdarr source-relative 95%/120% gates have different semantics;
none of the offline staging decisions installs this additional policy there.

## Repeatability localization

The 720-frame Gentlemen reproducer was run in several bounded configurations:

| Isolation | Result |
| --- | --- |
| Production settings, old/candidate ABBA pair | Candidate decoded repeats differ; this baseline pair matches |
| Disable temporal AQ, both AQ modes, or lookahead in separate pairs | The corresponding pairs match; single pairs do not establish causation |
| Four visible encoder-input captures | All submitted pixels and exported models match; one decoded repeat differs |
| Eight initialized, full-pitch input captures before submission and after completion | All input bytes match across runs and stay unchanged through completion; decoded repeats still vary |
| Eight runs retaining host grain-parameter storage for the entire encode | Submitted surfaces and model tables still match; decoded repeat variation persists |
| Eight encodes of the frozen input and fixed grain table | Grain-on and grain-off decoded pictures match across all repeats |
| Eight independent FFmpeg AV1 NVENC encodes of the frozen input | Base decoded pictures match across all repeats |

All completed diagnostic NVEnc outputs pass the full synthesis scan and both
decodes. The independent FFmpeg configuration does not expose exactly the same
lookahead-level control, so it is not a parameter-identical replacement test.

The captures rule out changing analyzed pictures, uninitialized input padding,
early surface reuse and the tested host-parameter-lifetime hypothesis for this
reproducer. They localize the observed divergence to the downstream encoding
path or its interaction with pipeline timing. They do not identify a specific
NVIDIA component or prove an underlying driver defect. Earlier studies also
observed variation in production encodes.

Two differing full-pitch repeats change 718 of 720 decoded base frames. Luma
RMS differences are 0.518 and 0.537 on an 8-bit-equivalent code scale. Maximum
individual luma differences are 105 and 120 native 10-bit steps, respectively.
The small averages do not establish invisibility or harmlessness, and repeat
hash identity is not a perceptual-quality metric. No AQ removal, permanent
synchronization or lifetime workaround is merged merely because a small test
pair happened to become repeatable.

GPU uninitialized-memory checking completed 96 full-HD frames with zero
reported errors. The bounded FGS-kernel race check completed 24 controlled
frames with zero reported hazards, with a deliberate diagnostic control proving
the checker was active. An unrestricted diagnostic produced warnings in
compression-side kernels; causation was not established. A longer heavily
instrumented run was stopped and is explicitly excluded from passing evidence.
These bounded checks are not a proof that every GPU execution is defect-free.

## Cost, scope and provenance

The full HDR baseline and candidate take 2,958.50 and 2,598.72 seconds to encode
on the shared server. Competing GPU workloads differ, so these numbers cannot
support a speedup claim. The four full HDR decode/checksum passes and associated
validation take 3,699.12 seconds with four validation workers. These exhaustive
offline audits do not run on every Tdarr job and add no production validation
time. Repeated scenes from one unchanged source now share one initial SHA-256
read per comparison process, while identity is checked again for every case.

The full CPU suite passes after the final admission correction. The admission
suite includes 13 tests, alongside the metadata and existing encoder regression
tests. No encoder core code changed after the immutable candidate was built.
The completed full HDR result was produced by the earlier pinned harness
version; that exact source snapshot and hash are retained with the evidence.
The source metadata trace likewise retains its original harness hash and
explicit provenance for its later same-source stream-property probe.

Local evidence directory:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/followup-20260908/`.
`evidence-index.json` records completed reports, trace and harness hashes,
admission receipts, diagnostic limitations and the unchanged production hashes.
Scratch artifacts are under `/tmp/downloads/fgs-followup-20260908/`.
No redownload or recovery addition was initiated by this study. The existing
repair and watchability-audit services remain active.

Candidate binary SHA-256:
`12abca76c05f60527fbfe0b66560ed6c7892810e6c9d2e4650953115f4037220`.
Production binary SHA-256:
`5423d8abda1d2c248f25508c311ed4ca0eda08462e1ebc6bce95fba22e830249`.
Production flow SHA-256:
`4f6c33a3516134480f8c7bf48c16cb62d57203ad86861fb3cd9f23dc76580326`.

For the preceding encoder changes and other encoders' influence on model
selection, see the cost study's primary-source references. The AV1 metadata
units used here are specified in the
[AV1 bitstream semantics](https://github.com/AOMediaCodec/av1-spec/blob/master/07.bitstream.semantics.md).
