# FEL reconstruction trial, September 14, 2026

Status: **bounded reconstruction trial and FGS transition diagnosis complete;
15 valid diagnostic outputs. No production FEL integration or library
replacement.** Read the linked live ledger before resuming work.

The four held originals can be reconstructed through a bounded CPU pipeline and
fed to the deployed FGS encoder. This is actual BL + EL + RPU picture
reconstruction, separate from the earlier MEL metadata conversion. These
video-only diagnostic outputs contain untrimmed PQ/HDR pictures and mastering
display metadata; they do **not** contain a Dolby Vision RPU or constitute a
qualified Profile 10 deliverable.

The live ledger is
[/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-reconstruction-trial-20260914](/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-reconstruction-trial-20260914).
Its `scratch` link locates all local media, dependency builds and logs.
[The dated harness](fel-trial-20260914/README.md) records the actual scripts and
reproduction dependencies. It is not installed into Tdarr or started by CI.

## Scope and reconstruction controls

Two requested six-second windows per original, at 20% and 63% of duration.
Stream-copy begins at a preceding random-access point; **the requested seek
positions are not exact scene timestamps**. All findings use decoded clip frame
indices. Sources are pinned by device, inode, size and nanosecond modification
time in `work-plan.json`; prepared components have SHA-256 identities in
`clip-preparation.json` and each clip's `preparation.json`.

All eight clips have matching BL/EL/RPU counts and matching 24000/1001 fps
BL/EL clocks. Every one of 1,305 clip frames reconstructs and carries decoded
RPU data. This checks these demultiplexed pairs; it does not replace a general
per-POC alignment validator for arbitrary discs or edited sources.

The default graph follows FelBaker's external Spline16 path: upscale the EL,
reconstruct 12-bit YUV, resample chroma, and convert using the RPU matrix to
untrimmed PQ RGB48. The AV1 input then converts explicitly to limited-range
BT.2020/PQ 10-bit 4:2:0 with error-diffusion dithering and left chroma siting.
The source BL is top-left; this is a real resampling conversion, with matching
output signalling. No display-specific Dolby trims are baked into the picture.

Three picture controls are distinct:

- Full FEL reconstruction.
- The same RPU mapping/colour conversion with the EL residual disabled in a
  separately named diagnostic plugin. This isolates the residual; it is not
  an ordinary Profile 7-to-8 metadata conversion.
- The original HDR10 base layer, using its standard colour conversion.

The residual changes the measured picture in every sampled window. Numbers
below are mean absolute differences in untrimmed PQ RGB16 code values
(0–65535), sampling every fourth pixel in each direction on every frame.
**They are differences, not perceptual quality scores or improvement percentages.**

| Movie | Window | Frames | FEL vs same mapping without residual | FEL vs HDR10 BL |
|---|---:|---:|---:|---:|
| Transformers: The Last Knight | 20% | 168 | 62.44 | 945.08 |
| Transformers: The Last Knight | 63% | 170 | 111.96 | 467.13 |
| Transformers: Rise of the Beasts | 20% | 165 | 45.10 | 45.02 |
| Transformers: Rise of the Beasts | 63% | 154 | 25.91 | 25.81 |
| TRON Legacy | 20% | 153 | 109.40 | 108.25 |
| TRON Legacy | 63% | 168 | 101.62 | 100.58 |
| Bumblebee | 20% | 158 | 184.80 | 622.18 |
| Bumblebee | 63% | 169 | 714.54 | 798.29 |

Larger BL-versus-reconstruction differences include RPU reshaping and colour
conversion, not just the enhancement residual. The strongest-frame stills
show subtle texture/tonal changes in the inspected passages; a fixed SDR
preview cannot establish their value on the user's HDR display. Retained
`comparison.png`, native RGB arrays, `encoded-comparison.png` and
`encoded-native-centre-crop.png` allow further review without selecting new
sources. The preview uses fixed 100-nit Reinhard followed by BT.709/sRGB,
without Dolby display management.

## Encode controls and measured cost

All encodes use the unchanged production image/core `ef5c61fe`, binary SHA
`d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b`.
Initial trials encode the 20% window of each movie with full reconstruction,
without residual, and from the original HDR10 BL: 12 outputs. A thirteenth
repeats The Last Knight's full reconstruction from the exact saved Y4M input.

Shared settings are AV1 10-bit, QVBR 29, 50,000 kb/s maximum, quality/HQ,
lookahead 32/level 3, spatial/temporal AQ and the deployed bilateral automatic
FGS mode. These are same-setting comparisons, **not matched-size encodes or
whole-movie storage estimates**. Actual video packet bytes:

| Movie | HDR10 BL | Mapping without residual | Full FEL | FEL vs BL |
|---|---:|---:|---:|---:|
| Transformers: The Last Knight | 7,001,691 | 7,231,165 | 7,218,871 | +3.10% |
| Transformers: Rise of the Beasts | 12,135,419 | 12,095,893 | 11,611,022 | -4.32% |
| TRON Legacy | 17,960,175 | 17,977,421 | 17,984,862 | +0.14% |
| Bumblebee | 7,792,010 | 7,357,966 | 5,890,851 | -24.40% |

Full reconstructed streaming trials took about 12–15 seconds for approximately
6.4–7.0 seconds of picture with four CPU cores assigned to reconstruction.
The Last Knight repeat took 15.126 seconds streamed versus 7.824 seconds from
saved Y4M, and produced **identical AV1 video payload bytes**. This isolates a
real pipeline cost, but includes container startup, pipeline filling, file I/O,
reference tee and polling overhead. It is not a calibrated full-film ETA.

The first four direct-BL controls incorrectly inherited the raw HEVC demuxer's
25 fps default. The timestamp gate rejected them. All four were superseded
with explicit verified 24000/1001 input clocks; old results remain in
`baseline-trials-invalid-clock.json` and are excluded from conclusions. Corrected
BL controls ran serially alongside ordinary workers, so their timing is not
used as an isolated speed baseline. No library/container input clock was changed.

## Validation and limits

The 13 valid outputs pass full libdav1d decoding, 2,100 displayed frame checks,
packet timestamps within the existing one-millisecond Matroska rounding bound,
codec/bit-depth/range/colour/chroma signalling, and the unchanged strict grain
syntax/model-stability scanner. Source mastering-display fields match within
one AV1 field quantization unit. Whole-source MaxCLL/FALL are not asserted as
new measurements of reconstructed excerpts.

PQ-domain decoded-grain PSNR against each output's own input is retained, along
with per-frame errors. It measures code error, not HDR perceptual quality,
Dolby rendering, banding clearance or a cross-input improvement score. The
frame counts and actual clocks are checked before index-aligned PSNR, avoiding
false metric shifts caused by rounded Matroska timestamps.

Dependencies and reference controls:

- FelBaker `cae66302433578ec62afa8c5c5809e93d0405b2f`, its pinned libdovi
  submodule, VapourSynth R73 and FFMS2 are isolated from production.
- All three published FelBaker expected checksums pass unchanged.
- A separately compiled compatibility variant matches the published 150-frame
  original DoViBaker checksum. This is one upstream reference fixture, not an
  independently decoded golden reference for all four movies.
- The final cache-bounded external graph matches the published 100-frame
  checksum; removing RPU data correctly raises a failure.
- Initial upstream and multi-graph processes exceeded the 6 GiB trial cap.
  Explicit two-frame node caches, four VS threads and two outstanding requests
  resolve this without changing expected pictures. The completed every-frame
  comparison peaks at about 4 GiB process RSS.
- The isolated FFMS2 build returned an empty-frame error when reading AV1
  outputs. HEVC BL/EL reconstruction was unaffected. Output validation/stills
  use explicitly selected host libdav1d instead; FFMS2 AV1 reading is unqualified.

`runtime-provenance.json`, variant source patches/build commands, test logs,
component hashes and the unmodified expected checksums are preserved locally.
The host follow-up runtime reproduces the container's native reference still
exactly; the additional diagnostic producer also reproduces the entire
recorded Beasts Y4M reference SHA.

## Temporal follow-up: cause established, production quality still conditional

The separate full-image HDR grain inspection covers all 644 frames in the four
fully reconstructed encoded windows. The Last Knight and Bumblebee signal
grain continuously. TRON starts without grain for 30 frames and then enables
it. Beasts signals grain for frames 0–29, disables it for 30–53, resumes for
54–99, disables it for 100–153, and resumes for 154–164.

Beasts' ordinary BL and no-residual controls also disable grain at 100–153,
but lack the initial 0–29 grain segment. Source inspection confirms a picture
cut at 27, **not at 30**, and a cut at 100. Source high-pass texture does not
collapse at 30. The exact deployed-encoder diagnostic reproduction establishes:

- Frames 27–29 retain the previous model; the spatial scene detector does not
  reset at the source cut (`reset=0`, `held=1`). This is a concrete scene
  adaptation limitation, not whole-library clearance.
- Frame 30 explicitly rejects the new fitted model (`rejected=1`). The existing
  protective path copies the reconstructed source into the coded picture.
- Frames 31–53 retain source during the existing 24-frame recovery requirement.
  Frame 54 resumes synthesis at gain 1/16, then ramps over 16 frames with
  corresponding source blending. This is a deliberate fallback/recovery, not
  an accidental reference to a grain-free AV1 frame.
- The logging-enabled encode produces **exactly the original AV1 payload**.
  A separate same-QVBR encode without FGS passes complete decoding, clocks,
  colour, mastering metadata and no-grain checks. Both add 330 validated
  output frames to the initial 2,100 (15 valid outputs in total).

Native source/output comparisons cover all 165 Beasts frames at 50 fixed
64x64 luma patches, with normal libdav1d, grain-disabled libdav1d and the
separate no-FGS encode. At frames 29→30, aggregate high-pass RMS is
2.279→2.487 in the source, 1.412→1.760 in the normal FGS output, and
0.926→1.723 in the no-FGS encode (10-bit PQ luma codes). Synthesized grain
switching off therefore does **not** erase all picture texture. Both encoded
controls also show the subsequent texture variation. These sparse code-domain
observations are not a subjective HDR playback verdict or proof that every
remaining temporal change is harmless.

The no-FGS control uses 12,347,452 video bytes versus 11,611,022 with FGS:
**+6.343% in this one passage**. PQ-domain average PSNR is 48.403 versus
47.836 dB against the same reconstructed input; this is not a perceptual
improvement percentage and does not justify a universal policy. Keep it as
an alternate quality/control path for later FEL trials; ordinary Tdarr FGS
settings and all model rejection/source safeguards remain unchanged.

Evidence: `beasts-grain-followup.json`, `beasts-fgs-diagnostics.json`,
`beasts-followup-validation.json`, `beasts-followup-hdr-validation.json`,
`beasts-texture-comparison.json`, `beasts-grain-transition-controls.json`,
`decoded-grain-observation.json` and `scratch/results/beasts-source-transition.json`.
The manually owned admission pause was restored at 15:10:35 UTC; running Tdarr
jobs were allowed to finish. No repair or playback work was interrupted.

## Remaining production gates

1. Qualify source-cut adaptation and actual display texture for reconstructed
   input, using the diagnosed Beasts sequence and its no-FGS alternative. The
   missed cut at 27 is a specific future regression case; improve it without
   weakening unsafe-model or clean-source protection.
2. Independently check layer/RPU alignment and reconstruction against a suitable
   reference over representative full sequences, including cuts/highlights.
3. Implement and qualify the metadata transformation for an already reconstructed
   standard PQ picture. Do not attach old reshaping/EL metadata unchanged and
   risk applying it twice. Qualify Dolby metadata/profile/container signalling
   separately from the HDR diagnostic picture.
4. Test the intended playback path and bit-depth/chroma tradeoffs; only then
   consider a full-movie trial with complete track/timing checks and rollback.

The four retained originals and their repair holds remain. There have been no
FEL library installations, source releases or new downloads. The deployed
encoder, ordinary Tdarr flow and validation policy are unchanged. Temporary
raw references/stills from the completed initial trials reclaimed
36,453,897,276 bytes after hash verification, including the regenerated
follow-up reference. Their source clips, generation commands, hashes and
comparison artifacts remain. All 6,601 retained evidence files/links
(2,762,893,661 regular-file bytes) were copied to
`/media/storage1/tdarr-audit-evidence/fel-reconstruction-trial-20260914` with
source/destination hashes and symlink targets verified. Both earlier path
links remain valid. See `evidence-relocation.json` and
`final-operational-state.json`; root retains about 50 GiB free.

Primary implementation references:
[FelBaker](https://github.com/bbeny123/felbaker),
[DoViBaker](https://github.com/erazortt/DoViBaker),
[dovi_tool conversion modes](https://github.com/quietvoid/dovi_tool#conversion-modes),
and [Dolby's Profile 10 overview](https://professionalsupport.dolby.com/s/article/Introduction-to-Dolby-Vision-Profile-10).
