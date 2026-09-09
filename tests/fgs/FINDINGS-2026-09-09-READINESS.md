# Encoder and Tdarr readiness work

Status: **encoder and flow deployed**. The foreground acceptance and rollout
work is complete. Approved library repairs and the watchability audit remain
running in the background; unsupported or unresolved files stay on hold.
This closes the encoder rollout portion of the broader
[work through production](WORK-TO-PRODUCTION.md).

Evidence directory:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/production-readiness-20260909`.
Media and scheduler scratch:
`/tmp/downloads/fgs-production-readiness-20260909`.

## A separate Dolby Vision conversion bug

A retained HEVC source for The Shining supplied a complete 736-frame copied
interval with P7 MEL and HDR10+. Both the production encoder and the earlier
fidelity candidate signaled AV1 profile 10.1 but retained dual-layer P7 RPU
fields. Successful decoding, metadata presence and source/output field equality
did not detect this required normalization step. This is separate from the FGS
ripple; it has not been attributed to the optional retention changes.

Commit `497caa64` retains the actual input profile before adapting the AV1
container record, maps P7 HDR10 compatibility to 10.1 and enables the existing
libdovi conversion for explicit P7-to-10.1 output. It does not reconstruct a FEL.
The pilot preserves sources classified as FEL instead of discarding their
per-pixel enhancement.

The new binary SHA-256 is
`bb7e75cbcb9097f1f1c7ac3347e7193c74caa6c7d57db1c3c77348cc27daf144`.
It was built from a pinned checkout using the previous build image and hashed
dependency artifacts. Runtime dependencies remain those of the production image.

Independent `dovi_tool` mode-2 conversion supplied the expected RPU stream.
Every original RPU was MEL. The reference retained every reshaping curve and
display-metadata block, removed NLQ mapping, disabled residuals and cleared EL
resampling. Both the explicit `10.1` and `copy` candidate modes matched the
independent output metadata on **all 736 frames**. Both preserved all sampled
source frames' HDR10+, mastering display and content-light metadata. Complete
grain-on/off decodes and synthesis scans passed. The historical negative differed
on the Dolby Vision RPU metadata of every frame, with identical stream signaling.

These results cover the complete short interval, not the whole film or all DV
profiles. See `dovi-normalization-reference.json`, `dovi-regression-config.json`
and the scratch `dovi-normalization-regression/report.json`.

## Tdarr integration and routine overhead

The new Dolby Vision guard checks single-layer AV1 signaling and 16 initial
decoded frames. It rejected the observed unconverted MEL output and accepted
known-good SDR and P8-to-P10 output. Measured costs were 0.018 seconds for SDR
and 0.393 seconds for the known-good DV file. FFprobe represents absent NLQ as
`-1` on this runtime; the guard accepts that representation. This is a bounded
normalization check, not complete HDR correspondence.

The generated full review graph, using pinned actual plugin modules with a
fixture dispatcher, passed the 736-frame source in 140.348 seconds. Significant
phases were the existing source detector (44.433 s), encode (21.689 s), source
hash preparation (0.440 s), DV guard (0.433 s) and existing final validator
(72.920 s). The final primary video was 28,807,133 bytes against a 27,803,658-byte
baseline and a 30,584,023-byte trial limit. The existing validator was not
weakened or replaced by the new guard.

The real scheduler then exposed two integration gaps that the dispatcher had
not tested:

- Newly installed local plugins were present on the server but absent after the
  node's plugin download. The candidate runtime now also includes the complete
  local plugin files and their helpers. Deployment must verify both copies.
- Tdarr rejects a flow ending with a working file still in its transcode cache.
  The review terminal now copies the accepted candidate into a dedicated review
  volume, compares complete source/destination hashes, writes a receipt and
  returns the original library object. Normal cache cleanup cannot erase the
  review artifact.

The isolated scheduler uses copied short media, a separate database and internal
Docker network. It has no production media mounts. Its first setup attempt also
confused the persistent node name with a transient runtime ID; that idle stack
was restarted before any encode. Those failed attempts remain recorded.

The latest trial bundle and runtime are recorded in `canary-stack.json`.
The scheduler retry passed all three jobs: two measured candidates were encoded,
validated and copied into the review volume; an unlisted source skipped encoding.
All source hashes were unchanged. All 191 pinned node plugin/helper files matched.
See `canary-result.json` and `canary-runtime-plugin-check.json`.

The staged Shining output has exactly the same complete video payload, codec
private data and stream properties as the fully qualified 736-frame output.
The Bridge output differs slightly between independent NVENC runs and received
fresh complete grain-on/off decodes, both passing all 765 frames. Relative
packet timelines match. Video-only remuxing moved the common origin by -0.125 s
and -0.040 s respectively; this is not an audio-alignment result and does not
relax the existing copy-path timing checks. See `canary-bitstream-comparison.json`.

## Exact size accounting with less unnecessary work

`tdarr_video_bytes.js` measures only primary-video packet bytes. For Matroska
H.264, HEVC and AV1, it disables codec parsers for this byte accounting pass.
Other containers/codecs keep parsers. Timing and decoding checks use their
existing paths. FFmpeg documents that `noparse` requires `nofillin`; neither
option is suitable for the timing checks here.
[FFmpeg format options](https://ffmpeg.org/ffmpeg-formats.html#Format-Options).

All six real-media cases matched the old complete packet counts and video byte
totals. The Gentlemen H.264 source took about 12 seconds with either approach
in an alternating four-run comparison. South Park's final AV1 file improved from
10.986 to 0.700 seconds; the HDR/DV final file from 7.353 to 4.720 seconds. These
are shared-host observations, not universal speed guarantees.

The integrated source-relative size plugin reproduced every previous byte total,
ratio and admission decision for three full titles. Source storage reads can
still dominate: the complete source/output checks took 17.381, 26.676 and
108.430 seconds during that run. It retains the existing 95%/120% rules and the
same retained-audio/subtitle comparison. No audio pruning can conceal video
growth. See `packet-corpus.json` and `source-size-controls.json` under scratch.

## Available cadence path

The Bridge source is coded as interlaced but the actual detector classified the
sampled content as progressive and selected software decoding without a
deinterlacer. A complete copied interval retained all 765 frames at 25 fps.
Production/default and candidate/automatic retention outputs were 5,244,716 and
5,357,671 bytes (+2.154%). Both complete grain-on/off decodes, video properties,
timelines and synthesis scans passed. This exercises flagged-progressive input;
it does not claim coverage of genuine interlaced motion or every VPP filter.

A separate deterministic 12-second test signal has genuine 50-field motion
woven into 300 TFF pictures at 25 fps. The actual detector measured 300 TFF,
zero BFF/progressive pictures and selected software decoding plus RTGMC TFF
without timestamp passthrough. Both old/default and new/automatic modes produced
all 600 progressive frames at 50 fps, with identical decoded timelines and
expected color properties. Every grain-on/off decode and synthesis scan passed.
Output sizes were 21,469,226 and 22,203,586 bytes (+3.42%); encoding took 22.151
and 23.907 seconds on this shared host. This is synthetic cadence coverage,
not a substitute for varied broadcast-content qualification.
See `true-tff-manifest.json`, `true-tff-detector.json` and scratch
`true-tff-comparison/report.json`. The initial harness launch failed before
encoding because its manifest preparation had rejected a stream field-order
label; decoded top-field flags and the detector established the actual order.
The corrected attempt and the failed setup are both retained.

## Repeat variability: bounded operating policy

Three distinct outputs from the previous lifetime trace were compared against
their identical, individually hashed submitted P010 frames. With synthesis off,
mean luma PSNR was 50.0391, 50.0404 and 50.0389 dB. Average distortion barely
changed, but the largest 64x64 regional difference had RMS errors of approximately
2.584, 1.635 and 1.630 code values on an 8-bit scale. The visual comparison and
per-frame measurements are in `repeat-fidelity.json` and
`repeat-fidelity-worst.png`.

This does not establish universally invisible variation or exact encoder
determinism. The cause remains downstream of the verified submitted pixels and
grain models, without identification of a particular NVIDIA component. Do not
disable AQ/lookahead or add synchronization workarounds without evidence of an
improvement. Use full decode/timeline/metadata checks and bounded picture metrics
for independent encodes. Use exact payload hashes when a stream is expected to
be copied unchanged. The diagnostic trace code is not part of the candidate.

The FFprobe XML-printer/AddressSanitizer investigation remains documented and
deferred. Approved library repair and watchability services continue, and the
hold on new recovery downloads remains in force.


## Ordinary rollout acceptance and storage policy

The ordinary flow keeps the existing default `retain=0`, QVBR buckets, sampler,
source-relative 95%/120% thresholds and final validator. It uses the qualified
branch binary, preserves FEL source video, adds the bounded DV guard and uses
the tested packet-byte accounting helper. Optional automatic detail retention
stays in the separate measured-source pilot; its trial 10% old-output cap is
not silently made a whole-library policy. Ordinary jobs acquire neither a
second full encode nor a source hashing pass.

The actual ordinary review flow passed two real intervals and one rejection
control. Bridge retained all 765 frames and produced 5,244,396 bytes; Shining
retained all 736 frames and produced 27,784,955 bytes. Both saved candidates
passed fresh complete grain-on/off decodes and synthesis scans. Relative
packet timelines and video properties match their production-default references.
Shining's parsed DV, HDR10+, mastering-display and content-light metadata match
the independently normalized reference on every frame. This comparison used
JSON metadata output and does not reopen the deferred XML-printer investigation.
The synthetic RTGMC candidate reached 127.25% of its source-relative baseline;
the 95% rule correctly retained the original after encoding all 600 frames.
See `ordinary-canary-result.json`.

The ordinary-flow setup initially assigned the requested flow ID, but Tdarr's
insert API had generated a different document ID. Those three attempts failed
before encoding. The runtime ID was corrected and the complete flow document
was read back before retrying. This does not affect updating the existing
production document by its established ID.

Rollback was rehearsed on the isolated stack: old production image, old flow
body and exact prior plugin archive were restored and verified, then the
candidate was reapplied. Existing 184 plugin/dependency files matched in both
states. The current image also carries all seven new plugin/helper files.
The plugin-archive tests caught and corrected two packaging errors before any
installation: shared ZipInfo offsets and normalization of `./` entry names.

An attempted offline rebuild of the historical dependency-building Dockerfile
failed because its package-install layer was not cached. The final persistent
`Dockerfile.fidelity` reuses the already qualified local production dependency
image, checks the old and new encoder hashes, and copies the new plugins. That
recipe rebuilt successfully without network access, and all encoder/plugin
hashes matched. The historical recipe and old binary remain available.

Prepared artifacts are `ordinary-rollout-v1`, `production-plugin-update-v1`
and `production-files-v2`. The installation-specific `rollout_production.py`
has a read-only `--check` mode and an explicit `--rollback` mode. It preserves
the repair coordinator's existing node pause and worker limits, and touches
only the Tdarr node runtime/build selection, the reviewed flow and its added
plugins. Activation status is recorded separately in
`production-rollout-result.json`; a successful preflight is not activation.

## Live deployment and repair-worker integration

The production node now runs image
`sha256:a7232fd54134b3c54fb4c73ca21df3875f344499a249af1968036d1e5b0a6f19`
with encoder core `497caa64`, binary SHA-256
`bb7e75cbcb9097f1f1c7ac3347e7193c74caa6c7d57db1c3c77348cc27daf144`.
The live flow was read back and all 191 existing/new plugin files were verified.
Its installed export SHA-256 is
`6cebd7cb63d540f61d9c142a9728ed4fbf0edaeaa3312eacae9ae7503126c7fe`.
The original two GPU/two CPU-health worker limits and repair-owned pause were
preserved. Startup's temporary hold setting was restored to its previous value.
Repairs, audit and Emby were not stopped. No library media was replaced by the
deployment, and the hold on new recovery downloads remains in force.

Finishing activation briefly deferred because the post-start process check
still saw an encoder/validator process, despite no assigned worker. Once the
node was quiet, the recorded installation was reverified and finished without
another restart. Both attempts are retained. A read-only rollback preflight
also passed after activation. The persistent build recipe and local encoder
asset were installed; later normal node recreation keeps the selected runtime.

An additional read-only audit found three attempted repair sources with P7:
two MEL encodes still running on the old host binary, and a held FEL source
(Bumblebee) whose archived command also referenced a vanished temporary RPU.
No completed repair in those source-probe records was P7. Only the two unsafe
P7 encode attempts were terminated before installation; both retained their
library file and source. The coordinator and unrelated workers continued.

The separate host repair worker now selects the qualified binary for new jobs,
classifies P7 before encoding, preserves FEL/uncertain input, refuses stale
external-RPU replay, and applies the shared output normalization guard. Its
full P7 MEL fixture completed decoding, validation, mux, backup and atomic
replacement of a disposable test copy. Real FEL and historical bad-RPU controls
were rejected. The new binary uses the coordinator's existing recognized host
path so Emby yielding continues without restarting the repair service. Already
running SDR/P8 workers can finish on the preceding safe encoder.

Two other holds were caused solely by empty track titles becoming omitted tags
during Matroska remuxing. The repair comparison now treats those as equivalent
while preserving all meaningful title/language/disposition/codec/payload checks.
The video-only repair fixture also exposed optional FFmpeg maps falling back
to video when no audio/subtitles existed. It now records an empty nonvideo hash
set and explicitly excludes video from that pass. The initial failure and
successful retry are retained; the completed encode was reused for the retry.

The two interrupted MEL cases and two empty-title cases returned to the normal
repair queue under the corrected worker. Bumblebee remains subject to FEL
preservation. See `repair-p7-protection.json`, `repair-p7-layer-checks.json`,
`repair-guard-negative-results.json`, `repair-worker-trial-state`,
`repair-deployment-v1/deployment.json` and
[repair integration notes](../../tools/fgs/REPAIR-DOVI.md).
