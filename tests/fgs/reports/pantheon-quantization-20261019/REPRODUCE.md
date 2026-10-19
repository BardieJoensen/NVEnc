# Reproduction and exported-field definitions

Read the video-quality-testing skill and repo instructions, resume coord context,
and check active jobs/mounts/CPU/GPU. Use fresh scratch; never run these scripts
against an evidence archive. Original download paths, source stats, actual PTS,
source packet bytes and previous hash evidence are in `CASE/validity.json`.

## Build and prepare

```bash
cd /home/bardie/git-repos/NVEnc
export PANTHEON_QUANT_DIR=/tmp/downloads/codex-work/pantheon-quantization-reproduction
export PANTHEON_REPORT=$PWD/tests/fgs/reports/pantheon-quantization-20261019
export PANTHEON_CAUSAL=$PWD/tests/fgs/reports/pantheon-causal-20261019
export PANTHEON_OLD=/media/merged-storage/cold-storage/docker-apps/pantheon-independent-investigation
mkdir -p "$PANTHEON_QUANT_DIR/svt-source"
tar -xzf "$PANTHEON_OLD/svt-source.tar.gz" --strip-components=1 -C "$PANTHEON_QUANT_DIR/svt-source"
patch -d "$PANTHEON_QUANT_DIR/svt-source" -p1 < "$PANTHEON_CAUSAL/svt-causal.patch"
patch -d "$PANTHEON_QUANT_DIR/svt-source" -p1 < "$PANTHEON_REPORT/svt-quantization.patch"
cmake -S "$PANTHEON_QUANT_DIR/svt-source" -B "$PANTHEON_QUANT_DIR/svt-build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF
cmake --build "$PANTHEON_QUANT_DIR/svt-build" -j 6
cp "$PANTHEON_QUANT_DIR/svt-source/Bin/Release/SvtAv1EncApp" "$PANTHEON_QUANT_DIR/SvtAv1EncApp-quant"
cc -O2 -Wall -Wextra "$PANTHEON_CAUSAL/apply_grain.c" -o "$PANTHEON_QUANT_DIR/apply_grain" $(pkg-config --cflags --libs dav1d)
uv venv --system-site-packages "$PANTHEON_QUANT_DIR/analysis-venv"
uv pip install --python "$PANTHEON_QUANT_DIR/analysis-venv/bin/python" numpy==2.5.4 scipy==1.18.1 matplotlib==3.11.2 pillow==13.0.0
export PANTHEON_PY=$PANTHEON_QUANT_DIR/analysis-venv/bin/python
"$PANTHEON_PY" "$PANTHEON_REPORT/study.py" e04
"$PANTHEON_PY" "$PANTHEON_REPORT/study.py" e05-1440
"$PANTHEON_PY" "$PANTHEON_REPORT/study.py" e05-1420
"$PANTHEON_PY" "$PANTHEON_REPORT/study.py" e05-1460
```

Use either the patch **or** `instrument.py` after the causal patch, not both.
`audit_artifacts.py` reconstructs all three patches from pristine source and
checks all 12 resulting files against the actual build. `provenance.json` records
binary/patch hashes; `tool-provenance.json` records actual tools.
The archive preserves both `SvtAv1EncApp-quant` and `SvtAv1EncApp-absolute`;
`archived_artifact_copies` maps former build paths to retained copies. The
upstream source is SVT 4.2 commit `9292ec8e32bce26f781f277ec8739b53426c4300`.
This is unrelated to production NVEnc's current repository branch.

`study.py` replays established extraction arrays with a fresh prefix. All 240
new reference frame hashes must equal the previously independently verified
original reference. It also checks unchanged original source size/mtime. No
library transcode is used as a reference. E04 uses 96 preroll + 240 scored frames,
24000/1001 fps; E05 uses 24 fps. Scores and rates exclude the 96 preroll frames.

## Quantization experiments

```bash
"$PANTHEON_PY" "$PANTHEON_REPORT/encode.py" e04 detail baseline
"$PANTHEON_PY" "$PANTHEON_REPORT/encode.py" e05-1440 detail2 baseline
"$PANTHEON_PY" "$PANTHEON_REPORT/stages.py" e04 detail
"$PANTHEON_PY" "$PANTHEON_REPORT/stages.py" e05-1440 detail2
"$PANTHEON_PY" "$PANTHEON_REPORT/validate_recon.py" e04 detail
"$PANTHEON_PY" "$PANTHEON_REPORT/validate_recon.py" e05-1440 detail2
"$PANTHEON_PY" "$PANTHEON_REPORT/encode.py" e04 qp4 4
"$PANTHEON_PY" "$PANTHEON_REPORT/encode.py" e05-1440 qp4 4
"$PANTHEON_PY" "$PANTHEON_REPORT/encode.py" e05-1440 qp4-tx32 4 --max-tx-size 32
"$PANTHEON_PY" "$PANTHEON_REPORT/encode.py" e04 qp8 8
```

Baseline must match the archived **entire IVF byte-for-byte**. Old LP2 runs were
not repeatable; this inherits verified LP1 control, `nice -n 10 taskset -c 0-7`,
preset 4, tune 0, no FGS/FGS denoise, BT.709 limited, and application reconstruction
output enabled in every arm. CQP changes RC to 0 and AQ to 0; all other settings
stay fixed except the explicit E05 TX32 control. CQP includes hierarchical
quantizer variation: ROI qindex spans 4–16 for QP4 and 9–32 for QP8 across frames.
The diagnostic frames realize 16 and 32 respectively. Final block and SB maps
are independently spatially checked for all 240 frames by `maps.py`.

Set `PANTHEON_TRACE_IMAGES_OFF=1` to retain maps without bulky previous stage
images. `encode.py` sets detail POC 230 for E04 or 216 for E05; scored frame is
POC minus 96. Trace directories must be new; old CSVs append. Environment and
command arrays are saved per arm. Failed/canceled attempts are not result arms.

For each completed arm, run `stages.py CASE TAG` and `score.py CASE TAG`.
`score.py` calls the required campaign.py adapter: patched CUDA VMAF/NEG,
PSNR/SSIM/CIEDE, GPU FFVship SSIMULACRA2/Butteraugli, and supplementary CAMBI with
16 CPU threads. It also checks all 240 decoded final pictures against the
application reconstruction, all planes, and records full-window texture,
ACF/correlation, color-conditioned samples and strong-line errors. Baseline
scores are reused only because encoded bytes and reference pixels are identical.
VMAF/NEG p1 excludes frame 0; other summaries include all frames.

## Budget test

```bash
patch -d "$PANTHEON_QUANT_DIR/svt-source" -p1 < "$PANTHEON_REPORT/svt-absolute.patch"
cmake --build "$PANTHEON_QUANT_DIR/svt-build" -j 6
"$PANTHEON_PY" "$PANTHEON_REPORT/absolute.py" e04
"$PANTHEON_PY" "$PANTHEON_REPORT/absolute.py" e05-1440
"$PANTHEON_PY" "$PANTHEON_REPORT/budget.py" e05-1440
"$PANTHEON_PY" "$PANTHEON_REPORT/budget.py" e04
```

The int16 little-endian map is 336×510 raster 64×64 SBs: −1 keeps the normal
value, 16 overrides it absolutely. It covers SBs intersecting the established
rectangle for all input frames, including preroll. E04 target is 512×448,
E05 256×128; this is an optimistic, hand-selected diagnostic allocation, **not a
production texture classifier**. It runs after initial AQ and after recode
resets. Legal delta-q resolution is 1 so later normalization cannot undo it.
VBR still controls all other blocks. Every final target block, every scored
frame, must actually have qindex 16. Logged maps confirm this.

E05 additionally uses global `--max-tx-size 32`; it is a combined intervention,
not allocation-only. Only requested TBR is calibrated, at most six attempts.
Actual rate comes from presentation-ordered video packet sizes over the scored
frames, not requested TBR, QP, output-file size or whole-stream average. Exact
packet lists and mismatch are retained. E05 selects budget1 (+0.1753%); E04
selects none, with budget5 still +5.6754%. E04 budget5 is evaluated as a failed,
**unmatched** attempt; its poor quality makes more bitrate calibration irrelevant
to acceptance. A prematurely launched q32 budget branch was canceled when its
unconstrained ACF result failed. It is not a completed experiment.

Run `controls.py CASE TAG...`, `maps.py`, and `collect.py` after scoring. Spatial
controls cover 15 distributed frames, while full-reference metrics cover all
240. Outside-target statistics exclude the entire SB-aligned allocation area.
The explicit E05 face/line control has semantic meaning only at frame 120.

## Native TU record format and interpretation

Each `.tu` file is keyed by POC and absolute luma TU x/y. Each record has a
32-byte NUL-padded ASCII name, uint32 element count, uint32 element byte size,
then little-endian payload. `*_meta`/`meta` are JSON bytes; samples are uint16,
prediction residual int16, coefficients int32, EOB uint16.

| Field | Exact meaning |
|---|---|
| `input`, `predictor` | Actual final EncDec input and predictor before residual addition; 10-bit samples. Input uses SB-local offset; predictor uses picture coordinates. |
| `prediction_residual` | Signed input minus predictor, verified exactly. |
| `private_forward` | Private DEFAULT_SHAPE forward transform of that residual. On quantizer-run TUs its coded portion equals `actual_forward` exactly. On bypassed TUs it is hypothetical. |
| `actual_forward` | Actual final-coding prequantization coefficients, in SVT's coded coefficient layout. |
| `initial_*` | Actual first FP quantizer output if RDOQ was enabled, otherwise regular B output; qcoeff levels, dqcoeff, EOB and private reconstructed picture. |
| `rdoq_*` | After density gates, any B requantization/fast optimization/full optimize_b; name alone does not identify the path. Parser derives path from recorded fields. |
| `final_*` | After optional coefficient shaving. Shaving is disabled in the diagnostic baseline blocks. |
| `actual_recon` | Actual picture immediately after inverse transform/add/clip, before in-loop filters. Subtract saved predictor for reconstructed residual. |
| `scalar0/1/2_*` | Private regular-B quantization at actual qindex, max(1,qindex−32), and 1; same input/predictor/partition/transform and qmatrix, no RDOQ. This changes quantizer algorithm relative to FP initialization. |
| `unquantized` | Private forward→inverse/add/clip without quantization. It still has integer rounding and AV1 transform support restrictions. |
| `quant_meta` | Effective qindex after frame/delta/segment selection, actual dequant DC/AC table entries, lambda, qmatrix level, transform log scale, initial RDOQ/shaving flags and density thresholds. |
| `meta` | Geometry, block size, TX depth/type, prediction mode, skip-mode/MD-bypass decisions, requested/block/frame/effective qindex, delta-q presence, segment offset, runtime bypass and preset. |

Baseline ROI thresholds are 255/255. EOB density cannot exceed 100%, so all
initial-nonzero FP calls there execute full optimize_b; neither fallback B nor
fast optimization applies. This path determination is derived from logged
values plus the pinned control flow. Parser flags any ambiguous fast path.

Private probes do not preserve an exercised transform on skipped blocks; their
hypothetical data are separated from the quantizer-run-only masked summaries.
Quantizer bypass and final EOB-zero/no-residual are separate maps. Coefficient
nonzero counts, absolute levels and squared magnitudes are **proxies, not bits**.
Actual bit accounting is only stream packet bytes. EOB is last scan position+1,
not nonzero count. Partial-boundary TUs are omitted from contained-TU coefficient
summaries, but pixel summaries cover the entire ROI.

The 64×64 AV1 transform has only a 32×32 coded coefficient region. The pinned
inverse code explicitly zeros the remainder (`inv_transforms.c`,
`svt_av1_inv_txfm2d_add_64x64_c`; `av1_get_max_eob` in `inv_transforms.h`). The
supported max-TX32 option changes legal partition/transform searches; forcing
only a final TU size would be invalid. Integer rounding remains in ≤32 transforms.

## Grain representability and visuals

```bash
"$PANTHEON_PY" "$PANTHEON_REPORT/representability.py"
"$PANTHEON_PY" "$PANTHEON_REPORT/grain_probe.py"
"$PANTHEON_PY" "$PANTHEON_REPORT/grain_visual.py"
"$PANTHEON_PY" "$PANTHEON_REPORT/visualize.py" e04 budget5
"$PANTHEON_PY" "$PANTHEON_REPORT/visualize.py" e05-1440 budget1
"$PANTHEON_PY" "$PANTHEON_REPORT/native_clips.py" e04
"$PANTHEON_PY" "$PANTHEON_REPORT/native_clips.py" e05-1440
"$PANTHEON_PY" "$PANTHEON_REPORT/plots.py"
"$PANTHEON_PY" "$PANTHEON_REPORT/collect.py"
```

This secondary experiment uses the prior fixed **NVENC FGS base**, with decoder
grain disabled, not the SVT arms. Same-frame held-out quiet/stochastic tiles are
screened by original-source gradients, amplitude and temporal behavior. Actual
10-bit base code distributions are checked; the decisive subset has constant
3×3 base neighborhoods at the same code. Overlap bands are excluded. E05 frame72
in the 1460 window uses code72; E04 frame184 uses code102. These evaluation frames
were outside the old estimator's training set. Mean brightness alone is not proof.

`grain_probe.py` compiles a copy of the existing dav1d helper that applies 32
legal deterministic seeds to one unchanged decoded frame. It tests white AR and
prior-interval AR at three constant scales, logs ACF and endpoint occupancy, and
checks base before/after identity. E04's prior-AR vector is zero. Chroma synthesis
is disabled in these probes. The base bitstream is read only; no grain table is
remuxed and **new signaling overhead is unmeasured, not zero**. The probe is an
offline legal-parameter feasibility measurement, not a deployable estimator.

AV1 luma scaling depends on decoded luma. Chroma has its own luma/chroma scaling
combination and luma-grain AR coupling, but those cannot spatially gate luma
noise. Random phase, AR correlation, overlap and clipping can alter finite-ROI
amplitude, so the result is bounded to matched-input neighborhoods and the
measured seed ensembles. Larger E05 scales clip appreciably; do not extrapolate
them as linear amplitude fits. There is no exhaustive proof over all legal AR
parameters/seeds or a whole-shot impossibility claim.

Native FFV1 comparison clips retain 10-bit samples. All four cropped panels are
hash-verified against their corresponding decoded arm for all 240 frames. The
H.264 companions and PNGs are 8-bit previews; metrics use unrendered 10-bit YUV.
Temporal plots are computed evidence, not playback observations. No user player
or display has been tested. Useful results are archived; raw full-length arrays,
build/venv scratch and failed calibration intermediates are reproducible and
retired after hash/measurement retention.
