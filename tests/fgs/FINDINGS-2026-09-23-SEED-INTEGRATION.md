# Optional emitted-seed correction: encoder integration

`b2a6daeb` adds an explicit `--film-grain-seed-guard <library>` option. It is
disabled by default and is **not deployed**. Production remains ordinary
`cb903a17`; retention and FEL remain off. This work addresses the three rare
degenerate grain seeds found in the [complete seed-cycle experiment](FINDINGS-2026-09-23-SOURCE-PRESERVATION.md).
It does not complete automatic retention or establish library damage scope.

The encoder corrects only seeds 0, 46372 and 18904, incrementing each by one.
Every other packet bit, coded picture, model parameter, length and timestamp
is preserved. Correction happens on owned CPU packet storage before the quality
decoder and file writer; the NVIDIA driver's buffer is never modified. Both
encoder output paths propagate errors. The legacy path is code-reviewed;
the Linux CLI pipeline is exercised by the trials below.

## Parser isolation and error handling

The [native parser package](seed_filter/README.md) builds a private minimal
FFmpeg n8.0 CBS parser with a per-instance structured callback. It does not use
the serial diagnostic tool's global log callback. Exact field offsets and
values are checked after the entire packet parses, before any edit is committed.
The packet is not reserialized. Parser state is per stream; a failure makes
that context terminal until explicitly reset or reopened.

The library exports five versioned C ABI functions. Its FFmpeg symbols are
hidden, so the newer parser cannot replace the encoder's existing FFmpeg 6
symbols. Qualification loads an unrelated FFmpeg globally first and verifies
that both libraries remain independent. The explicit reproducible builder
pins and checks the official source archive, exports and dependencies; it
refuses to overwrite an existing library and installs nothing system-wide.

Packets are limited to 32 MiB and 4,096 edited seed fields. This parses AV1
headers, not picture pixels; opaque/reserved OBUs are not necessarily errors.
One earlier negative fixture incorrectly assumed eight zero bytes must fail.
That test was corrected to an empty frame-header OBU; its original failed logs
remain preserved. No parser behavior was relaxed to make the test pass.

## Completed comparisons

- The native filter matches the independently qualified manual correction on
  the 65,536-frame NVENC cycle and three 96-frame AOM fixtures. Each AOM fixture
  has 46 hidden and 46 show-existing headers. Actual SDR/HDR packets also match.
  Four concurrent instances preserve input aliases, packet properties, side
  data and extradata; malformed/reset controls pass.
- The encoder loader processes the full cycle identically with both prototype
  and recipe-built libraries. Missing library, ABI, initialization, parser
  failure and reopen behavior are checked.
- Four actual 240-frame SDR/HDR encodes, option off/on, match the qualified
  `696a7b40` controls on 1,920 grain-on/off decoded observations, clocks,
  metadata and grain decisions. On/off compressed video payloads are identical.
- A new full 65,536-frame native encode with the option enabled is byte-identical
  after IVF extraction to the independent seed-only reference. Exactly three
  encoded packets change. That reference has complete grain-off preservation
  and AOM/dav1d grain-on agreement. An additional decode of the new MKV matches
  all 65,536 reference pictures and clock rows.
- Matroska and MP4 controls preserve source audio/subtitle payloads, chapter
  times/titles, file title/comment and language. All off/on packets, clocks
  and tested metadata match; another 808 grain-on/off observations are exact.
- Ten invalid configuration/library/failure requests return nonzero. A forced
  processing failure leaves only a 1,062-byte partial MKV header in scratch;
  no completed file is claimed or installed. The other failures create no file.

The container comparison records existing ordinary-output limits: MP4 track
`name` tags are omitted, and some source audio packet durations are rounded by
the ordinary muxer. Neither changes with this option. No claim is made that
every source container field is preserved byte-for-byte.

The encoder was built with Meson 1.4.2 and verified CUDA header dependencies:

```
encoder b2a6daeb52542a602a49d92747bd0119285324af
SHA256 d779c46b21b74e75c698158531bc605b3c7a067a1c5d591bf31c507ade90f260
parser library SHA256
119674654152b195d5fc74abdfa83b2b3b8a9e50b95d1e9157c49c7b155bf815
```

Finite single-pair SDR/HDR sizes are unchanged and show no observed slowdown;
these short runs do not qualify full-title throughput. Broader release/canary
testing, library visibility/scope and deployment remain separate work. Windows
and the legacy plugin output path have not been runtime-qualified.

## Evidence and operational state

Under the evidence root linked from [the handoff](WORK-TO-PRODUCTION.md), read
`roadmap-r3-seed-filter-20260923/` for native/parser reports and
`roadmap-r3-seed-integration-20260923/report.json` for the encoder qualification,
exact commands, input/output pins and container/failure receipts. The actual
encoder trials check 68,264 decoded observations in total.

Both finite GPU pauses were released; the current two GPU transcodes/two CPU
healthchecks were preserved. All trials were started manually, and none is
scheduled to restart. No library files, production encoder, flow or routine
validation settings were changed. R3–R8 remain open.
