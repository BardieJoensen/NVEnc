# FEL reconstruction: production qualification in progress

Updated September 16, 2026. **The complete Beasts candidate passed automated
qualification with current-library tracks. The user reports no visible mistakes
in the playback clips, but saw only a UHD label; actual HDR output remains
unconfirmed. No FEL replacement is installed, and other production gates remain
open. All four originals remain held.** The authoritative automated result is the corrected
[full-library receipt](/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-production-20260914/full-library-qualification.json).
The earlier frozen canary's TrueHD timing failure remains separate historical
evidence; the corrected validation reused its completed video.

The full candidate has 182,867 pictures and passed strict libdav1d decoding,
all RPU/static-HDR checks, chapter and retained-payload checks, and exact native
TrueHD clock preservation. Both complete source-layer decodes passed. The
staged library mux is 11,533,838,971 bytes, versus 10,342,050,816 bytes for the
current library file and 66,993,725,383 bytes for the original remux. Its video
container is 8,420,626,323 bytes. These are different source/fidelity baselines;
full-file size is not a matched-quality comparison.

The two precisely aligned reference windows finished at average PQ-code PSNR
48.423216 and 51.125299 dB (164 and 100 pictures). These measurements do not
establish whole-film visual equivalence or correct physical Dolby playback.
Complete Bumblebee preparation also passed, with 163,840 frames; its full
reconstruction/encode is not yet qualified. The September 16 Apple TV/Infuse
review covers the short clips, with actual HDR output still unconfirmed.
All finite September 14 units have finished, and their Tdarr pause was
restored. September 15 ordinary Tdarr retries are a separate task.

The canonical project entry point remains
[WORK-TO-PRODUCTION.md](/home/bardie/git-repos/NVEnc-fgs-fidelity/tests/fgs/WORK-TO-PRODUCTION.md).
The [earlier reconstruction report](/home/bardie/git-repos/NVEnc-fgs-fidelity/tests/fgs/FEL-RECONSTRUCTION-20260914.md)
records the dependency builds, original reference fixtures and the first
diagnostic windows. Its claims and limitations belong to that earlier run.

## Exact artifacts and scope

The focused checkout is `/home/bardie/git-repos/NVEnc-fgs-fel`, branch
`feat/fel-production-20260914`. It starts from deployed `ef5c61fe` and excludes
the deferred automatic-retention changes. Nothing starts that campaign.

| Artifact | Identity |
| --- | --- |
| Candidate encoder core | `a72f589ea2fab66da2f1d3515e5d3189326d7089` |
| Candidate binary SHA-256 | `19869914b1f0081b3d4b8326f0e9f1802f8ca4ca77a06fe2d37b70accfb0a788` |
| Candidate encoder container base | `sha256:218540effe6149030631445914c8f35c6e81090326a8e4bbca55d0b57c3f50e4` |
| Active full-canary reconstruction runtime, v2 | `sha256:5f604f00fa9ed29b530cdfa0c6629e894aac73c1996a77ae80f27eabea2e0404` |
| Subsequently qualified runtime, v3 | `sha256:56d34f39bda207ea97f08195e1bd3df25e897f3b8709d9b5ed16a66f5d8215bd` |
| Full-canary host harness | `11c4fcb52c7cfa569676e9ca02d7e95015aa6b31`, frozen in `scratch/pinned-canary-v2` |
| Subsequent source-continuity guard | `9851de57`; independently applied to the complete prepared source |
| Current-library validation harness | `86fbcc2f`, frozen in `scratch/pinned-library-v3`; includes explicit native TrueHD clocks |
| Ordinary production encoder | `ef5c61fe`, SHA-256 `d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b` |

This FEL work did not change the production node image, ordinary flow or
plugins. The separate September 15 subtitle metadata correction changed two
Tdarr plugins; see the canonical handoff for that deployment. The candidate binary is bind-mounted into disposable trial
containers. The FEL runtime is a separate image and has not been installed into
the Tdarr node. Its receipt identifies every packaged file and the base image.
It packages the previously built dependencies; it is not a new from-source build.
Runtime v3 also requires arithmetic and source-continuity evidence at the graph
entry point. Both rejection controls pass. Its complete-source 164-picture
Beasts window is byte-identical to the matching reconstructed reference prefix.
The initial hash comparison mistakenly retained `XLENGTH=165` in that prefix's
Y4M header. Correcting only the length field produces the exact streamed hash;
no picture bytes or acceptance limits changed. The initial failure is retained.

The only original titles in scope are Bumblebee (2018), TRON: Legacy (2010),
Transformers: Rise of the Beasts (2023), and Transformers: The Last Knight
(2017). Source identities and retained paths are in the
[work ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-production-20260914/work-plan.json).
No downloads, source releases or library replacements are part of this canary.

## Implemented behavior

The prepared-input path requires progressive 3840x2160 ten-bit 4:2:0 BL,
1920x1080 ten-bit EL, supported P7 FEL metadata, limited-range BT.2020/PQ and
the qualified chroma positions. It verifies every original video timestamp,
BL/EL picture order, all RPUs, dependency hashes and source identities.
Nonzero video starts, incompatible mapping forms and unsupported frame layouts
remain explicit holds.

The bounded VapourSynth graph reconstructs YUV12 from BL, EL and RPU, converts
through RGB48, then explicitly produces limited-range BT.2020/PQ YUV420P10 with
left chroma and error-diffusion quantization. The output is an untrimmed PQ
picture. This ten-bit AV1 delivery path is not lossless twelve-bit preservation.
Dolby display trims are retained in metadata rather than applied to these pixels.
The method follows the pinned [FelBaker implementation](https://github.com/bbeny123/felbaker/tree/cae66302433578ec62afa8c5c5809e93d0405b2f).

The metadata preparation uses the pinned dovi_tool editor with `mode=2` and
`remove_mapping=true`. It deliberately retains the active area and bars.
Every resulting RPU must have the exact expected identity mapping and normalized
PQ matrices. All other display metadata, including trims and scene flags, must
match the source. Only a verified single-layer RPU reaches AV1 Profile 10.1.
The matching [upstream editor example](https://github.com/quietvoid/dovi_tool/blob/82384bc7652c6f88cb63f7f11e0315b624003fc3/assets/editor_examples/fel_to_p81_encode.json)
also enables cropping; that option is not appropriate for this unchanged geometry.

Source RPU scene boundaries can now be passed through
`--film-grain-scene-cuts`. The schedule declares the exact number of input
frames and strictly increasing frame indexes. Missing, repeated, reordered,
truncated or excess input fails. Boundaries reset the statistical grain history;
they do not force keyframes, enable retention or bypass source-quiet protection,
model rejection, the recovery hold or recovery ramp. No schedule means the
ordinary path is unchanged.

A real error-propagation problem was found by the excess-input test: the encoder
logged a filter failure during final draining but could return success. Commits
`d4024d5b` and `a72f589e` latch failed schedule correspondence and preserve fatal
filter/writer errors through the final drain. Truncated and excess input now
return failure. The original failing evidence is retained.

The two-process supervisor checks both producer and encoder exits, cancels both
sides on failure or timeout, and monitors the scratch reserve. Raw pictures
travel through a FIFO, not a raw movie file or Docker's log stream. Containers
use immutable images, read-only dependencies, private writable scratch and
explicit CPU/memory limits. The site controller restores its Tdarr pause in
normal cleanup and through a systemd `ExecStopPost` cleanup.

## Evidence completed

- Eight constructed diagnostic sequences contain 1,252 decoded frames. All
  eight AV1 candidates pass complete strict libdav1d decoding, ten-bit PQ colour
  signalling, picture counts, clocks, grain syntax/stability and decoded HDR
  metadata checks. The full CPU suite and targeted process/packet-timing tests pass.
- Complete Dolby RPUs are recovered from the AV1 metadata OBUs and compared byte
  for byte with the prepared RPUs. This verifies trims that FFprobe's JSON does
  not expose. The static HDR checker also records every CLL/MDCV payload.
- The separate Python integer reference matches 338,040 sampled YUV codes and
  676,080 sampled RGB codes across those sequences, with zero mismatches.
  Removing the residual changes 211,065 tested samples. Decoder and resampler
  are shared, so this is not a Dolby-certified independent end-to-end decoder.
- All parameters in the eight samples and all 182,867 complete-film RPUs pass
  conservative native arithmetic bounds. Polynomial intermediate products, MMR
  sums, residual lookup storage and RGB matrix sums are covered before rendering.
- The packaged graph reproduces the earlier Beasts Y4M byte for byte. Its
  deliberate EL/RPU mismatch fails at frame zero. The direct FIFO pipeline also
  reproduces the qualified AV1 payload exactly and rejects both mismatched RPU
  input and a producer that ends one frame early.
- Eight every-frame decoded grain observations are complete. These distinguish
  actual synthesized grain from coded texture. On/off runs are observations,
  not automatic damage verdicts.

Beasts' first window illustrates the scene-boundary correction. The earlier
ordinary path carried the previous grain model across the source cut at frame
27, then rejected the model at frame 30. The new schedule resets at frame 27.
Recovery remains gradual; the diagnostic window still includes deliberate
grain-off intervals. Sparse texture measurements show that fine detail can
still be lost by lossy coding. Neither the boundary correction nor average
PSNR proves perfect texture preservation.

| Beasts first window, same QVBR 29 settings | Video packet bytes | PQ PSNR average |
| --- | ---: | ---: |
| Unchanged ordinary path | 11,611,022 | 47.836228 dB |
| Scene schedule, plain PQ | 11,941,782 | 48.130553 dB |
| Scene schedule plus Dolby metadata | 11,973,792 | 48.130553 dB |

The ordinary candidate payload is byte-identical to the deployed encoder's
earlier trial. After removing metadata OBUs, the two scheduled variants also
have identical encoded picture payloads. The scheduled video costs about 2.85%
more in this one excerpt; this is not a matched-size comparison, a perceptual
improvement percentage or a whole-film size estimate.

### Corrections to the excerpt methodology

The old second Beasts window began at a CRA with preceding RASL pictures. The
stricter preparation rejected it; a new excerpt starts at the following complete
IDR. Its 101 pictures replace the older 154-picture diagnostic sequence.

Later comparison against the full source found non-contiguous terminal pictures
in six stream-copy excerpts. Equal BL/EL counts do not catch that condition.
Eight terminal pictures across the set are outside the contiguous source
prefixes. The original 1,252-picture runs remain valid constructed-input
experiments; **the source-contiguous prefixes total 1,244 pictures**. Playback
copies use those prefixes and have been revalidated after threefold looping.
Earlier untrimmed playback receipts remain under their superseded names.

The source checker now rejects missing or duplicate POCs inside closed IDR
groups, including these truncated tails. POC wrapping inside an IDR group is
outside this qualified path. The complete Beasts source passes all 182,867
pictures across 2,941 groups, with no gaps. No source or library media was
changed by this harness correction.

### Correct mastering metadata

Bumblebee and The Last Knight carry 4,000-nit Dolby authoring metadata while
their HDR10 base layers describe 1,000 nits. The reconstructed candidates use
the Dolby authoring luminance and preserve the source mastering chromaticities.
Known CLL/FALL values are retained. These are authoring values, not measurements
of the new lossy encodes. The earlier all-1,000-nit clips remain picture
diagnostics but are not qualified fallback-mastering examples for those titles.

## Complete-film trial design and results

The manual, finite canary uses the complete Beasts original. Preparation has
verified every source timestamp, all metadata, layer order, arithmetic ranges
and complete picture continuity. The graph verifies the exact display-order
RPU attached to every decoded EL picture during reconstruction.

The producer is capped at four CPUs/6 GiB, the encoder at two CPUs/4 GiB,
and each independent CPU validation unit at two CPUs/3 GiB. Swap is disabled
for these limits. Active ordinary Tdarr jobs may finish alongside startup when
at least 8 GiB of GPU memory is free; new Tdarr admission was paused until
the canary encode ended. Emby playback pauses both canary containers. Measurements
from overlap periods are not isolated throughput benchmarks.

| User unit | Purpose |
| --- | --- |
| `fgs-fel-full-canary-20260914` | Direct pipeline controls, full encode, pause restoration, staged mux and validation |
| `fgs-fel-source-decode-20260914` | Independent strict decoding of both complete HEVC source layers |
| `fgs-fel-full-comparison-20260914` | Wait for this encode, then compare two precisely matched source windows |
| `fgs-fel-full-library-20260914` | Qualify the completed encode with the current library's tracks and native TrueHD clocks |
| `fgs-fel-bumblebee-prepare-20260914` | Prepare and verify the next complete retained source, without a GPU encode |

These are manually started transient units, with deadlines and no restart or
boot schedule. They do not start unrelated trials. The full canary restores
Tdarr before its subsequent CPU mux/decode validation. A failure leaves media
staged and the original holds intact.

The initial staged container retained the original source's audio, subtitles,
attachments and chapters; its older TrueHD timing check rejected that mux. Validation checks retained payloads, all retained
packet timestamps, exact encoded-video payload preservation during muxing,
complete Dolby/static HDR data, the full video clock and strict decoded count.
It also waits for the separate source-layer decode evidence. This canary uses
the original's tracks for qualification; a later library repair must preserve
the current library's chosen tracks and metadata through the existing repair
installation/rollback path.

The reusable validator now accepts an explicit current-library path and expected
identity for that subsequent staged mux. It requires the complete library video
clock to match the reconstruction clock, applies the existing source-content
alignment checks and rechecks both file identities. Negative controls reject
missing/extra pictures, timestamp offsets and changed cadence. The original
canary remained frozen on its earlier harness. The subsequent corrected
full-library qualification passed without installing anything. The separately bounded
`fgs-fel-library-handoff-20260914` unit records the four current track inventories
and the complete Beasts library alignment in `library-handoff.json`.
That preflight is now complete. All four library copies have different track
selections from their originals; all retain Opus and TrueHD, with fewer embedded
subtitles. Beasts' complete 182,867-picture library clock matches its original,
and the two source-content witnesses pass. The library mux must retain those
current selections.

### TrueHD timing preservation

The end-to-end library fixture exposed a separate mux issue: MKVToolNix 82's
TrueHD packetizer recalculates audio timestamps. In the controlled fixture,
1,369 of 8,220 TrueHD packet starts moved by 1 ms despite identical audio bytes.
Disabling lacing and changing the container time scale did not preserve them.

The new staged path exports the original native Matroska TrueHD frame starts
and supplies them explicitly when muxing. The packet validator verifies every
known FFprobe PTS against that native clock. If FFprobe omits an access unit's
PTS, only its actual stored frame start may fill the omission. Frame counts,
packet durations and codec trimming remain checked. The extra inferred end
line written by mkvextract is not an audio frame; this was verified against
the [82.0 source](https://mkvtoolnix.download/sources/mkvtoolnix-82.0.tar.xz).
No timing tolerance was widened.

The repeated fixture passes complete video/HDR/RPU decoding and preservation
of real Opus/TrueHD audio, interleaved SubRip with whitespace, an attachment and
chapters. A deliberate 100 ms TrueHD offset retains the audio bytes but fails
the timing comparison; a mismatched native-clock proof also fails. An initial
negative fixture accidentally changed track order and is retained separately.

The original full canary was frozen on its earlier validator and rejected
this strict TrueHD check as anticipated. The separate `qualify_full_library.py` unit reuses only
its completed, hash-verified encoded video and performs the corrected full
validation with current library tracks. It pins the helper scripts, binaries
and host media tools. It neither installs a replacement nor releases sources.

The two source comparison windows begin at original pictures 36,554 and
115,251, with 164 and 100 contiguous reference pictures. Exact RPU sequence
matching establishes their source locations. Both comparisons are complete in `full-reference-comparison.json`. The raw
reference Y4Ms can be archived with their receipts after dependent jobs finish.

## Remaining release gates

1. Review completed Beasts speed, size and measured texture results. Its full
   encode, independent source decodes and corrected final mux checks passed.
   The two reference windows do not cover every scene in the film.
2. Verify actual HDR output on the user's Apple TV/Infuse path. On September 16
   the user reported that the FEL clips looked good, with no mistakes noticed,
   but only UHD was indicated, without HDR or Dolby Vision. This is a positive
   visual observation; it establishes neither HDR10 output nor an SDR failure.
   Match Dynamic Range was not reported, and the TV has no Dolby Vision support.
   At the user's request, all eight temporary `FEL Test 20260914` Movies folders
   and their owned Tdarr exclusion were removed; Emby's index was verified clear.
   The hash-verified original review clips remain in
   `/media/merged-storage/media/test-encodes/FEL-production-20260914`.
   They are silent, lossy candidates repeated three times, using the verified
   contiguous source prefixes. Exact feedback and cleanup evidence:
   [cleanup receipt](/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-production-20260914/emby-playback-pack-20260916/cleanup-20260916.json).
3. Actual Dolby Vision playback remains unqualified on other hardware. It
   cannot be checked on this TV and is separate from the intended HDR10
   fallback-path approval; do not ask the user to verify a Dolby output badge.
   Dolby's [April 16, 2026 Profile 10 article](https://professionalsupport.dolby.com/s/article/Introduction-to-Dolby-Vision-Profile-10)
   states that tvOS did not support Profile 10 at publication. Firecore's
   [settings documentation](https://support.firecore.com/hc/en-us/articles/360015608854-Settings-Overview)
   describes its Dolby toggle as applying to Profile 8. HDR10 fallback playback
   does not establish that the preserved Dolby trims are being applied. A TV
   badge alone also cannot establish that with forced output modes enabled.
4. Integrate a qualified FEL result with the existing library-track preservation,
   source-hold, install and rollback journal. Complete the other three sources'
   full preparation and qualification before releasing their holds.

The normal non-FEL flow should continue using its fast path. This CPU FEL
reconstruction is a special path with a measurable throughput cost. GPU FEL
reconstruction, broader input families and optional retention are separate work;
they are not silently enabled by this change. The FFprobe XML/ASAN investigation
remains documented and deferred; these checks use JSON and elementary streams.

## Evidence and cleanup map

The ledger is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-production-20260914`.
Its `scratch` link points to `/tmp/downloads/fgs-fel-production-20260914`.
All paths below are relative to that ledger unless marked `scratch`.

| Evidence | Location |
| --- | --- |
| Build, initial failures, final candidate | `build.json`, `build-command.json`, `build*.log` |
| CPU qualification | `cpu-qualified.log`, `cpu-check.log`, targeted test records |
| Eight encodes and strict checks | `clip-encodes.json`, `validation-clips.json` |
| Scene and fatal-error controls | `beasts-scene-v2-trials.json`, `validation-beasts.json` |
| Whole RPU/static HDR verification | `static-hdr-roundtrip.json`, `roundtrip-parser-controls.json` |
| Arithmetic checks and source continuity | `parameter-bounds.json`, `contract-revalidation.json`, `picture-continuity.json` |
| Scalar reconstruction reference | `scratch/arithmetic-reference/*/result.json` |
| Runtime packages and controls | `runtime-build-v2.log`, `runtime-qualification.json`, `runtime-qualification-v3.json`, `runtime-v3-prefix-header-correction.json`, `scratch/runtime-context-v*/fel/runtime-receipt.json` |
| Full source preparation | `scratch/full-beasts/preparation.json` and `metadata/` |
| Initial complete-film job (older timing check rejected mux) | `full-canary.json`, `run_full_canary.py`, `canary-harness-pin-v2.json` |
| Full source and decoded output checks | `full-source-decode.json`, `scratch/full-library-v3/validation/validation.json` (passed) |
| Source-matched full encode measurements | `full-reference-comparison.json`, `post_full_alignment.py` |
| Comparison seek controls | `comparison-seek-controls.json`: all four known frame starts pass |
| Current library track inventory/alignment | `library-handoff.json`, `scratch/library-handoff/` |
| Current library mux and exact TrueHD controls | `staged-library-fixture-v2.json`, `truehd-clock-negative-controls.json`; original failures and alternative mux controls remain separate |
| Full current-library qualification | `full-library-qualification.json`, `qualify_full_library.py`, `library-harness-pin-v3.json` |
| Next complete-source preparation | `bumblebee-preparation.json`, `scratch/full-bumblebee/preparation.json` |
| Broader branch integration | `branch-integration.json`, `main-cpu.log`, `main-build.json`; compiled `296993f9` remains undeployed |
| Every-frame grain and sparse texture | `decoded-grain-observation.json`, `beasts-texture-comparison.json` |
| Validated playback copies | `playback-pack.json`; earlier receipts keep their superseded names |
| User playback review and Movies cleanup | `emby-playback-pack-20260916/cleanup-20260916.json`: visually clean clips; UHD label only, HDR output unconfirmed; original clips retained |

Keep full-source components, indexes and the pinned canary tools while the units
are active. Never move an active FIFO or backing directory. Archive completed
evidence with hash verification on cold storage, then remove regenerable raw
references/build copies only after their dependent checks finish. No cleanup
here authorizes deleting retained originals or releasing seeding holds.
