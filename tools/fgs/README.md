# Decoded film-grain review tools

These read-only tools measure the grain that an AV1 decoder adds to a decoded
base picture. They help locate periodic, directional or unusually strong grain
for visual review. They do not need an original encode and do not judge source
detail, motion quality, or whole-film watchability.

## Build and use

The native tool needs C++17, FFmpeg development libraries and dav1d with
`dav1d_apply_grain` (tested with dav1d 1.4.1). The Python runners use the standard
library and POSIX file locks; Linux is the tested platform.

```sh
g++ -std=c++17 -O3 -Wall -Wextra tools/fgs/grain_inspect.cpp \
    -o /tmp/fgs-grain-inspect \
    $(pkg-config --cflags --libs libavformat libavcodec libavutil dav1d)

# Two seconds, four sampled frames per second, every image pixel per sample.
python3 tools/fgs/review_window.py input.mkv --binary /tmp/fgs-grain-inspect \
    --start 2044 --duration 2 --output-dir /tmp/grain-review

# An explicit SDR scenario for compatible but unspecified colour signalling.
# This assumption is recorded, and cannot override known HDR/BT.2020 metadata.
python3 tools/fgs/review_window.py untagged.mkv --binary /tmp/fgs-grain-inspect \
    --assume-bt709 --output-dir /tmp/grain-review-sdr

# Raw full-image measurements: default is every displayed frame.
/tmp/fgs-grain-inspect --extended --peak-nits 1000 \
    --tiles-csv /tmp/tiles.csv input.mkv /tmp/frames.csv 10 12
```

Open `report.html` for a channel-selectable tile heatmap, location of the local
peak, and area-weighted 95th/99th percentiles. `report.json` also records the
strongest directional result per channel, display assumptions, decoded frame
counts, source identity, binary/wrapper hashes and CSV hashes. The frame and tile
CSVs retain the underlying measurements. A zero score means no measured grain
texture at those samples; it does not establish an undamaged source or encode.

Use `--sample-period 0` to measure every displayed frame in the requested window.
Seeking still decodes from a preceding random-access point; a short window does
not guarantee a fixed runtime. The wrapper has a 300-second default timeout.
It reuses only a completed, matching request with intact artifacts, rejects a
source/binary changed during analysis, and locks the output directory against a
second writer. Interrupted attempts never become completed reports.

For a finite batch, create a manifest and run:

```json
{
  "schema": "fgs_review_batch_v1",
  "cases": [
    {
      "name": "pq-scene-1000",
      "file": "pq-scene.mkv",
      "role": "Same scene at a 1000-nit reference peak",
      "start": 10,
      "duration": 2,
      "sample_period": 0.25,
      "peak_nits": 1000
    }
  ]
}
```

```sh
python3 tools/fgs/review_batch.py manifest.json --binary /tmp/fgs-grain-inspect \
    --output-dir /tmp/grain-batch
```

Paths are relative to the manifest. Optional `sha256` pins a retained fixture;
`assume_bt709`, `sdr_white_nits`, `stream_index` and `timeout` match the window
runner options. Unknown options and duplicate/unsafe case names are rejected.
The batch writes `index.html` and `status.json`, continues to report individual
errors, and exits nonzero if any window failed. Repeating the command resumes
completed windows after checking their identities. Batch completion is an
execution status, not a quality classification.

## Reference-display and spatial method

`--extended` decodes with grain disabled and uses `dav1d_apply_grain` on that same
picture. This avoids comparing two independently scheduled decoder outputs.
Measurements use the grain-on minus grain-off display residual, subtracting each
tile's mean. The four channels are perceptual luminance, red, green and blue.

The image is partitioned into native-resolution 48-pixel tiles. A final strip
smaller than eight pixels joins the preceding tile. Every image pixel belongs
to exactly one tile, including edges and letterbox bars. No spatial downscaling
is used. A frame retains the strongest local result and area-weighted score
percentiles, so a small damaged region or opposing directions cannot disappear
in a global average.

For each tile the tool computes RMS and twelve signed autocorrelations at
`(1,0), (0,1), (1,1), (-1,1), (2,0), (0,2), (2,2), (-2,2), (3,0), (0,3),
(3,3), (-3,3)`. The texture score is `RMS * max(abs(correlation))`. The additional
directional score is `RMS * max(abs(correlation_a - correlation_b))`, comparing
horizontal/vertical and diagonal/antidiagonal directions at equal distances.
It helps distinguish directional structure from isotropic coarse grain; a
symmetric grid can evade that distinction. Neither score has a universal
watchability threshold. `--correlations` records the complete correlation
vector of the strongest texture tile per frame/channel.

Display mapping follows these explicit scenarios:

| Input | Reference mapping |
| --- | --- |
| SDR BT.709 or BT.2020 NCL | Gamma 2.4; 100-nit white by default |
| PQ BT.2020 NCL | Absolute BT.2100 EOTF, clipped to the chosen display peak |
| HLG BT.2020 NCL | Inverse OETF and luminance-coupled OOTF/system gamma at the chosen peak |

PQ/HLG use a 1000-nit peak by default. All scenarios use zero display black.
The mapping uses bilinear chroma reconstruction, respects AV1 chroma siting,
and explicitly assumes centered siting when it is unspecified. Component range,
8/10/12-bit depth and I400/I420/I422/I444 layouts are handled. Conflicting or
unsupported colour metadata is rejected; it is never silently mapped as SDR.
Multiple video streams require `--stream-index`, and attached pictures are
excluded from automatic selection. Midstream geometry/colour changes, absent
or non-increasing timestamps, empty windows and write failures are errors.

Absolute luminance is mapped through PU21 `banding_glare`. The transfer functions
and HLG luminance coupling follow [ITU-R BT.2100-3](https://www.itu.int/rec/R-REC-BT.2100-3-202502-I/en).
The PU21 equation and parameters are adapted from the authors'
[reference implementation](https://github.com/gfxdisp/pu21/blob/main/matlab/pu21_encoder.m),
with its [BSD 3-Clause notice](LICENSE-PU21.txt) retained. The
[PU21 paper](https://www.cl.cam.ac.uk/~rkm38/pdfs/mantiuk2021_PU21.pdf) describes
the luminance encoding; it does not validate this tool's ripple scores as a
perceptual quality metric.

Clipping is counted separately for base and grained pictures. Real televisions
apply different tone mapping, gamut mapping, scaling, sharpness and viewing
conditions. This tool does not render Dolby Vision/HDR10+ dynamic metadata or
model those display operations. PQ highlight clipping can suppress measured
grain, and HLG results change with display peak. Do not compare different
display settings as if they were interchangeable.

## Compatibility, costs and checks

Without `--extended`, the original nine-patch SDR method and compact CSV remain
available. Its clipped RGB8 scores have different units and coverage; old
baselines must not be applied to full-image PU21 results. It rejects HDR/BT.2020
and layouts other than I420. See [calibration findings](../../tests/fgs/FINDINGS-2026-09-07-DISPLAY.md).

Native completion JSON uses `complete` for end-of-stream draining and
`interval_complete` for finishing either the requested window or the stream.
Both report actual counts and decoded timestamps; neither proves the media
file was originally complete. An error may leave partial CSV files. Prefer the
wrapper when resumability and completion checks are needed.

This is a background/release diagnostic. Full-image pixel work is intentionally
outside normal per-file Tdarr validation. LUTs avoid per-pixel PQ/SDR powers;
their measured error against analytic mapping is below 0.004 PU21 units on the
current numeric controls. Full-image review still costs more than nine patches.

```sh
bash tests/fgs/run_cpu_tests.sh
FGS_INSPECT_BINARY=/tmp/fgs-grain-inspect python3 tests/fgs/test_grain_inspect.py
```

The CLI tests additionally need an FFmpeg build with software AV1/H.264 encoders.
Controls cover PQ reference points, HLG colour coupling, LUT precision, ranges,
odd dimensions and borders, localized alternating-line patterns, metadata
rejection, stream selection, sampled completion, artifact corruption, concurrent
writers and changed source fixtures.
