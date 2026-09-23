# Manual compressed-base model serialization

`model_override_ivf.cpp` writes complete, externally measured grain models into
new AV1 IVF files. It uses the same pinned private FFmpeg n8.0 source/static
libraries as [the isolated seed parser](seed_filter/README.md). It is a manual
research tool, with no production encoder hook or automatic source admission.

Build after creating the private parser build, setting `FGS_FFMPEG` to its
`FFmpeg-140fd653aed8cad774f991ba083e2d01e86420c7` source/build directory:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -I json -I "$FGS_FFMPEG" \
  tests/fgs/model_override_ivf.cpp \
  "$FGS_FFMPEG/libavcodec/libavcodec.a" "$FGS_FFMPEG/libavutil/libavutil.a" \
  -lpthread -lm -lz -latomic -o /path/to/new/model-override-ivf
```

Run `model-override-ivf INPUT.ivf NEW_OUTPUT.ivf MANIFEST.json`. The schema-one
manifest sets `max_packets` (1..1,000,000) and an array `models` (at most 16).
Each model request binds `coded_index`, `expected_apply`, `expected_seed` and
`expected_order_hint`. Coded order differs from displayed order when AV1 hides
and later shows a reference picture. An empty model list supplies a no-op control
and reports coded identities. Missing identities fail at EOF.

An override `model` either contains `apply: false`, or supplies `apply: true`,
`seed`, `ar_shift`, `grain_shift`, `scaling_shift`, integer `overlap`/`restricted`
flags, three `curves` arrays of ordered `[value, strength]` pairs, and three
signed `coefficients` arrays (24 Y, 25 Cb, 25 Cr). It currently supports lag three
and the existing luma-indexed chroma lookup (128/192/256), progressive 4:2:0
8/10-bit streams with a grain-capable sequence header. A legal serialized model
is not proof of picture quality or source-population eligibility.

The tool keeps separate input/output syntax contexts and separate original and
modified reference-grain states. When an unselected coded frame reuses a changed
reference, it writes that frame's original complete model explicitly. A shown
existing picture naturally keeps the model of its selected reference picture.
Layered streams and redundant frame headers remain unsupported. Packets are
limited to 32 MiB and manifests to 64 KiB. Sources are opened read-only, outputs
must be new, and a failed run removes its incomplete output.

D36 qualifies one corrected 10-bit constructive picture: both independent
decoders reproduce all 786,432 oracle samples, with all 16 base pictures and 15
unselected grain pictures unchanged. Reordered 8/10-bit and UHD HDR controls add
1,472 fresh decoded observations, exact sequence/HDR metadata payloads and clocks,
and ten expected failures. A deliberately omitted reference guard changes 15
unselected 8-bit frames and six 10-bit frames; both decoders detect the defect.
Those negative controls establish that reference isolation is actually exercised.
IVF copying may add AV1 temporal delimiters; original packet evidence is reused
only after verifying every other packet byte. This is not Matroska/Dolby Vision
container qualification or an automatic retention release.

The local evidence is `roadmap-r3-model-output-20260923/` under the current
colour-recovery evidence root. Read `comparison.json`, `controls.json` and
`negative-control.json`; source/decoder/model hashes and exact commands are
recorded alongside them. Continue the [retention roadmap](RETENTION-ROADMAP.md).
