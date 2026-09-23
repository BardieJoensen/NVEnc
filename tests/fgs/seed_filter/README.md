# Experimental AV1 seed guard

The native filter changes only the three exceptional AV1 grain seeds: 0,
46372 and 18904 become 1, 46373 and 18905. A CBS parser supplies exact field
locations. The filter edits those bits after the complete packet parses;
it never serializes a replacement header or changes coded video tiles.

Each stream owns its parser and callback. Parser errors leave the caller's packet
unchanged and stop that stream. The native BSF supports an explicit flush/reset;
the simpler C ABI requires closing and reopening a failed stream. Input packets
are bounded to 32 MiB and at most 4,096 edited seed fields. The encoder option
is off by default and requires low-overhead AV1 OBUs with sequence headers.

The C ABI is in `seed-library.cpp`. It copies the compressed input to padded
parser storage, then commits a correction only after a successful one-packet
result. One context is serial; separate contexts can run concurrently. It does
not decode picture pixels or reject all opaque/reserved OBUs; this guard is
not a full bitstream or picture validator. FFmpeg symbols are local to the library, so this
parser does not replace or interpose on the encoder's FFmpeg libraries.

## Manual Linux build

Requires Python 3.12+, a C/C++ toolchain, make, binutils and the verified source
archive below. This builder does not download files or install packages.
Choose a new work directory on storage with adequate free space.

```
FFmpeg n8.0 commit: 140fd653aed8cad774f991ba083e2d01e86420c7
URL: https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/140fd653aed8cad774f991ba083e2d01e86420c7
SHA256: 5c4a9e51e706b8deba835f02ea70e1e1101187f601adae72b36ec2b17b6f15be

python3 tests/fgs/seed_filter/build.py \
  --archive /storage/ffmpeg-n8.0.tar.gz \
  --work-dir /storage/new-seed-parser-build \
  --output /storage/libfgsseed.so

NVEncC --codec av1 --film-grain-seed-guard /storage/libfgsseed.so ...
```

The build verifies the archive, export list and shared-library dependencies,
and records every command and output hash. Existing output paths are rejected.
The private FFmpeg parser remains LGPL 2.1 or later; its source and license are
available through the pinned archive and `COPYING.LGPLv2.1`. Keep that source,
these modifications and the build recipe with any distributed library.

## Qualification scope

The serial IVF experiment in `../seed_patch_ivf.cpp` independently locates
fields via a diagnostic trace. It is a reference tool, not the encoder backend.
The native backend instead uses CBS's per-instance structured callback.

The native filter matches the qualified manual edit byte-for-byte across a
65,536-frame NVENC seed cycle, three 96-frame AOM fixtures containing hidden
and show-existing frames, and real SDR/HDR encoder outputs. Four concurrent
instances preserve packet properties, side data, extradata and shared input
buffers. Malformed packets, partial parsing and explicit reset are tested.
The C ABI also passes with an unrelated FFmpeg already globally loaded.

The seed-cycle correction preserves every base picture and clock; AOM and
dav1d agree on every corrected grain-enabled frame. Only three displayed frames
change. This establishes a narrowly scoped repair mechanism. Actual encoder
integration, broader container/stream checks and deployment remain separate
qualification steps. This folder does not enable production retention or FEL,
schedule jobs, or repair library files.

See [the current findings](../FINDINGS-2026-09-23-SOURCE-PRESERVATION.md) and the
`roadmap-r3-seed-filter-20260923` report in the evidence root from the handoff.
