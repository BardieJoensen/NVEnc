# Reproduction and provenance

All work is diagnostic. Do not install these binaries or run commands against
library media. Historical command JSON contains the exact measured arguments,
environment, wall time, return code and input/binary hashes. Use a fresh scratch
root when replaying; never overwrite the preserved evidence archive.

## Inputs and environment

`fixtures/{e04,e05-1440}/validity.json` identifies untouched original downloads,
source stat, exact extraction, source packet rates and all240 reference-frame
hashes. `fresh-validation.json` additionally proves newly extracted source/input
identity on all planes, including source raw SHA256 and per-frame MD5. Scored
positions are96:336 of336 frames. E04 is24000/1001fps; E05 is24fps. Both are
1920x1080 BT709 limited-range; the original8-bit samples lift exactly to10bits.

Analysis environment: Python with numpy2.5.4, scipy1.18.1, matplotlib3.11.2 and
pillow13.0.0. CPU encodes are niceness10, affinity0-7; SVT useslp1, x264 four
threads. H264 decoder instrumentation uses two threads. GPU scoring is serialized.
System `/usr/bin/ffmpeg`6.1.1 uses x264 core164 r3108; the separate custom FFmpeg
and decoder-development libraries are fingerprinted in each QP/decoder receipt.
Do not substitute PATH FFmpeg for the explicitly named NVDEC or visualization
binary: the custom build lacks some of those features.

```bash
export PANTHEON_RD_ROOT=/tmp/downloads/codex-work/pantheon-rd-replay
REPORT=/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-rd-20261019
mkdir -p "$PANTHEON_RD_ROOT/parent" "$PANTHEON_RD_ROOT/worker"
python3 -m venv "$PANTHEON_RD_ROOT/analysis-venv"
"$PANTHEON_RD_ROOT/analysis-venv/bin/pip" install numpy==2.5.4 scipy==1.18.1 matplotlib==3.11.2 pillow==13.0.0
PYTHON="$PANTHEON_RD_ROOT/analysis-venv/bin/python"
"$PYTHON" "$REPORT/prepare.py" e04
"$PYTHON" "$REPORT/prepare.py" e05-1440
```

`controls.py` freezes source-only tiles. Preserve the existing frozen-control
JSON when reproducing analyses. The whole-window controls used for real encodes
are the prior quantization archive's12,870 source-defined tiles over15 frames;
their source descriptors are recomputed and required to match exactly.

## SVT instrumentation

Pristine SVT commit: `9292ec8e32bce26f781f277ec8739b53426c4300`.
Pristine tar SHA256:
`753bcc1ba62ca425ad003b22c92609dce9ecbbec2cd572ecf298df9d136d69bc`.
It is preserved in the independent-investigation archive. Starting control
binary is the quantization archive's `SvtAv1EncApp-quant`, SHA256
`f0373fd33170e2409c991cd878f56689ca58b0c44b3dc5a31efd836501dd9fd3`.

Patch order is executable in `audit_patch.py`: pristine source, causal patch,
quantization patch, `instrument.py`/`entropy_probe.c`, `private_fp.py`, absolute-q
patch, then `retain_fp.py`. Build in an isolated directory with CMake Release,
`BUILD_SHARED_LIBS=OFF`, and at most four build jobs. No system installation.

`parent/measured-svt/` preserves the actual final measured binary, exact source
tar and source/binary fingerprints. Its607 source files match the recorded audit.
The final repository reader additionally hardens unknown-record truncated-payload
handling; that final guard was independently exercised by
`validate_probe_reader.py` but was **not rebuilt into the measured real-encode
binary**. Real encodes did not enable the entropy-reader hook. The original
entropy captures independently pass complete expected-record and clone checks.
Use the measured snapshot to reproduce historical binary provenance; use current
code plus identity controls when testing the hardened reader. Do not claim the
two source revisions are identical. The earlier entropy implementation is in
commit67eeff68 and its exact commands/build logs/binary hashes are retained.

`worker/{case}-q32-control/command.json` holds each CQP8/actualq32/TX32 control
command and exact detail/trace environment. Replay it into fresh directories,
remapping only scratch paths. `probe.py` requires complete encoded-stream and
application-reconstruction identity to these controls. `entropy_summary.py`
requires exact key coverage and separates whole-block skip exclusions.
`analyze.py` checks predictor/residual/forward/inverse/TU coverage before texture
analysis. `quantizer_contrast.py` compares FP, regular-B and unquantized inverse
with fixed decisions. `capture_fp.py CASE [8|12]` and `analyze_fp.py` validate
private lower-q FP counterfactuals while requiring the actual stream unchanged.

`real_encode.py CASE TAG REQUEST_KBPS ABSOLUTE_Q` runs the combined real strategy;
use q24 for E04 andq20 for E05. Measured request values are in each command JSON.
`validate_real.py` verifies actual target q, retained coefficient/dequant/EOB
identity and source-defined whole-window controls. `score.py CASE TAG IVF RECON`
uses the established campaign adapter and verifies decoded/application equality.

## Conventional H264 controls

`crosscodec.py CASE TAG REQUEST_KBPS [AQ_STRENGTH] [SUBME] [RATE_MULTIPLE]` runs
two-pass slow/grain on the exact original-derived8-bit input. Every measured
arm retains both pass logs, command JSON, input identity and packet audit. The
grain-tune AQ default is0.5. `subme11` also affects first-pass analysis and QP-RD;
it is not a fixed-QP prediction ablation.

```bash
"$PYTHON" "$REPORT/crosscodec.py" e05-1440 x264-search11-3x1 28322 1.0 11 3
"$PYTHON" "$REPORT/score_crosscodec.py" e05-1440 x264-search11-3x1
"$PYTHON" "$REPORT/export_h264_qp.py" \
  "$PANTHEON_RD_ROOT/parent/crosscodec/e05-1440/x264-search11-3x1/out.mkv" \
  "$PANTHEON_RD_ROOT/parent/h264-qp/search11-3x-validated/blocks.csv"
"$PYTHON" "$REPORT/visuals.py" e05-1440 x264-search11-3x1
"$PYTHON" "$REPORT/summarize.py"
```

Do not assume a replay's requested bitrate meets its target. `packet_window.py`
checks336 unique cadence-consistent presentation positions and sums actual video
packet bytes at96:336. Scoring refuses decisive arms outside1% of their target.
Calibration attempts remain documented but unscored. H264 QP exports require
336x8160 unique macroblocks, complete delayed-frame drain, PTS correspondence,
side-data bounds and input/tool/map hashes. Skipped-block QP is decoder state,
not proof that residual quantization executed. Analyses weight visible MB area,
excluding the padded bottom8rows.

## Metrics and visual evidence

The independent HEVC control uses `crosshevc.py e05-1440 x265-grain-2x1 19938`.
Its measured system libx265 is3.5+1-f0c1022b6, Main10. It uses exact8→10bit
lifted samples, slow/grain, explicit pass1/2 statistics, four pool workers and
two frame threads. The original x0 script is preserved beside its first-run
receipts; strengthened x1 checks exact all336 input equality and stats reuse.
The shared scorer probes codec and uses `hevc_cuvid` with p010le for Main10.
Linked libx265 file SHA256 is
`d36cd663a24eeca90178f95b91513b96ae1d4e3c6cf28557646af5926ef03934`.
Raw `ldd` text contains load addresses, so its text hash is not a stable library
identity; use the saved parsed library path and file SHA.

`score.py` and `score_crosscodec.py` call the prior independent report's
`investigate.py` adapter, which uses `tests/fgs/campaign.py`, patched CUDA VMAF
and GPU FFVship. The campaign commands, executable versions, per-frame JSON,
full pooled metrics and tails are retained in `parent/scores/`. Score references
are hardlinked into that directory so the Docker bind mount sees them. CPU and
NVDEC H264 outputs must match all336 frames/all planes; SVT application output
must match decoded scored samples. Texture files contain all240 frame traces,
not only the five-frame midpoint summaries.

`summarize.py` copies measured values with evidence hashes and generates a
standalone amplitude/ACF plot. `visuals.py` creates native-pixel stills and
lossless synchronized10-bit comparison clips; both panels are validated on
all240 frames. Stills explicitly convert limited BT709 to RGB. These artifacts
do not establish playback observation or perceptual acceptance.


## Provisional 4x candidate and playback

The exact accepted requests are below. Fresh extraction/validation must precede
these commands, and packet calibration remains mandatory on any replay.

```bash
"$PYTHON" "$REPORT/crosscodec.py" e05-1440 x264-search11-4x1 37335 1.0 11 4
"$PYTHON" "$REPORT/score_crosscodec.py" e05-1440 x264-search11-4x1
"$PYTHON" "$REPORT/crosscodec.py" e04 x264-search11-4x1 34531 1.0 11 4
"$PYTHON" "$REPORT/score_crosscodec.py" e04 x264-search11-4x1
"$PYTHON" "$REPORT/block_edges.py" e05-1440 x264-search11-4x1
"$PYTHON" "$REPORT/block_edges.py" e04 x264-search11-4x1
"$PYTHON" "$REPORT/playback.py" e05-1440
"$PYTHON" "$REPORT/playback.py" e04
"$PYTHON" "$REPORT/summarize.py"
```

E05 playback additionally requires the scored3x arm from the earlier example.
Use fresh output directories; scripts reject existing playback directories.
`playback.py` renders deterministic blinded labels, records their key separately,
and verifies every panel on every frame against hash-bound inputs. Native crop
loops are FFV1 references; actual H264 streams plus an original-derived full
reference are retained for real-player checks. Reference hardlinks survive
fixture retirement. Rendering/decoder checks are not observed playback.

`block_edges.py` measures source-compensated grid-gradient excess on the same
12,870 source-defined tiles/15 sampled frames. Its8/16-grid summaries are
additional descriptors, not newly imposed pass/fail thresholds. Boundaries and
interiors have different pixel populations;16-grid interiors include8-grid
boundaries. Use source/control hashes and complete tile rows to reproduce it.

## Preservation and cleanup

[ARTIFACTS.md](ARTIFACTS.md) gives the cold-storage root. `raw-evidence.tar.zst`
contains original detail/trace exports and full H264 macroblock CSVs. Its member
manifest records each SHA and size; `preserve.py pack` independently streams and
verifies every tar member before `retire` removes those raw originals. Extract
only required members into fresh scratch, never modify the archive:

```bash
tar --zstd -tf "$ARCHIVE/raw-evidence.tar.zst"
tar --zstd -xf "$ARCHIVE/raw-evidence.tar.zst" -C "$FRESH_SCRATCH" MEMBER
```

`parent/measured-svt/source.tar.zst` and its actual binary retain historical
provenance. `worker/rejected-source.tar.zst` preserves rejected attempts solely
for audit; do not substitute them for accepted instrumentation. `retirement.json`
lists removed reproducible media/builds/venv. A full manifest covers retained
streams, metric data, logs, scripts, sources and playback packets. Historical
command paths remain original scratch paths; remap them deliberately when
reproducing. Do not rebuild earlier immutable archives or run replay inside them.


After `summarize.py` and `playback.py`, `quiet_tail.py CASE` adds the explicitly
post-hoc maximum quiet-HF-excess stress crop with the same blinded labels.
It binds summary and upstream playback hashes and validates all240/all-plane
panel crops. It must not replace source-selected quiet controls or be described
as a confirmatory sample.
