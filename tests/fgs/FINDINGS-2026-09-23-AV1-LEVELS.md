# AV1 level signalling and independent decoder compatibility

The bounded September 23 investigation isolates a compatibility failure in the
shared NVIDIA encoding path or its configuration, beyond the retention fork.
It does not establish the precise driver defect or a library damage scope.
Production remains ordinary `cb903a17`; quality settings, validation, retention
and FEL have not changed.

## Reproduction and scope

On RTX 5060 Ti / driver 595.91.07, QVBR 16/20 emits sequence level index 23 and
high tier. It reproduces with the exact deployed `cb903a17` binary, earlier
`b2a6daeb`, the range fix, diagnostic `ecb706d1`, plain NVENC without grain and
FFmpeg's independent `av1_nvenc` implementation. Logged encoder inputs request
auto level (SDK enum 24), separately from target quality. This is not evidence
that the new grain/retention code changed the requested level.

Both generated input at 640x360, 1280x720, 1920x1080 and 3840x2160, and existing
SDR/HDR development originals reproduce QVBR 20 / index 23. On the recorded tiny
controls, QVBR 24/28/30/32 instead signal 31. Q30 at larger sizes signals 8 or 12.
These are tested operating points, not a complete boundary or driver survey.

Index 23 maps to 7.3, but that level has no defined constraints in AV1 v1.0.0
Errata 1; index 31 explicitly means maximum parameters. See
[Annex A.3 of the approved specification](https://aomediacodec.github.io/av1-spec/av1-spec.pdf).
AOM 3.8.2 rejects these level 23 streams; separately pinned AOM 3.14.1 reports
that value 23 is not yet defined. Dav1d 1.4.1 decodes all their displayed frames.
A successful dav1d decode is therefore insufficient interoperability evidence.
This is not a visible-ripple diagnosis.

Preset P1, zero lookahead/B frames, an average bitrate, a 10 Mbit cap, an explicit
buffer, 8-bit input and explicit high tier do not resolve the Q20 finding.
Explicit 4.0/5.1 failed NVENC initialization in the preceding range study.
Constant-QP and bitrate-only controls avoid level 23 but change rate-control
semantics; neither is an equivalent-quality replacement. No silent quality
change or sequence-header rewrite is proposed.

The current Tdarr map requests QVBR 29/30/34/37. Thus the reproduced Q16/20
settings are outside its current map; this does not prove every production
configuration safe. Four existing titles' first sequence headers signal 12 or 31.
Those first-header observations do not replace complete-file qualification.

## Independent checks and diagnostic correction

There are 39 emitted 48-frame controls across 8 finite batches. All 1,872 pictures
decode with dav1d. Seventeen streams also decode with AOM and agree on every
picture and clock. Twenty streams fail AOM on level 23.

Two further Bridge Q30 controls fail AOM despite a defined level 8. Their FFmpeg
output contains malformed timecode metadata, including seconds 63. Forcing
progressive flags does not fix it. Disabling extra SEI forwarding in an isolated
FFmpeg control makes Q30 pass all 48 frames with both decoders; Q20 still fails
on level 23. This isolates another diagnostic-path issue. Disabling all extra
SEI is not a production recommendation or a metadata-preserving solution.
The real NVEncC ordinary comparisons remain their separately qualified evidence.

The failed text-valued tier option is retained as a harness failure; its
corrected numeric replacement reproduces level 23. It is excluded from the39
emitted streams. No failed control was silently relabelled a pass.

## Reusable validation change

`scan_bitstream --defined-levels` now checks every encountered operating point
and sequence header against the approved revision's defined levels. It catches
all 20 level 23 controls. A grain-free concatenated fixture demonstrates rejection
of a later sequence change at packet 49 / 2 seconds. The default report-only mode
still passes the old grain-syntax negative, documenting why grain validation
alone missed this case. The test also covers every five-bit level code, invalid
indices and a valid sequence following an invalid one.

This optional check is cheap header inspection. It does not validate level
bitrate/tile bounds, metadata OBUs (which the existing grain scanner skips),
compressed picture correctness or all players. The two metadata failures above
are deliberate evidence that independent decoding is still required. It has
not been added to routine Tdarr validation. Full CPU checks pass: 185 Python
checks in 26 suites and 29 C++ programs.

## Next action and evidence

Keep the driver/configuration issue recorded for a separate minimal upstream
reproduction. No issue has been sent, driver changed or media rewritten.
Any future workaround must preserve actual coded pictures, grain state, clocks
and container/header consistency and qualify both decoders. Merely changing
quality or relabelling a level is not an established solution.

The evidence root in [the handoff](WORK-TO-PRODUCTION.md) contains
`roadmap-r3-level-signalling-20260923/report.json`, all 8 manifests/commands,
`stream-validation/report.json`, `scanner-regression/report.json`, the pinned
AOM result, the current quality-map identity and all released pause receipts.
No job is scheduled. R3 whole-picture retention selection remains open.
