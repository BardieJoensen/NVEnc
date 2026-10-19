# Reproduction and evidence definitions

Read the video-quality-testing skill and check jobs/mounts/CPU/GPU before work. The prior archive is immutable. Use fresh scratch, never point these scripts at either archive. Historical command paths are retained verbatim as evidence; substitute the new scratch root when replaying them.

```bash
cd /home/bardie/git-repos/NVEnc
export PANTHEON_INDEPENDENT_DIR=/tmp/downloads/codex-work/pantheon-causal-reproduction
export PANTHEON_REPORT=/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-causal-20261019
export PANTHEON_OLD=/media/merged-storage/cold-storage/docker-apps/pantheon-independent-investigation
export PANTHEON_EVIDENCE=/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019
mkdir -p "$PANTHEON_INDEPENDENT_DIR/svt-source"
tar -xzf "$PANTHEON_OLD/svt-source.tar.gz" --strip-components=1 -C "$PANTHEON_INDEPENDENT_DIR/svt-source"
cmake -S "$PANTHEON_INDEPENDENT_DIR/svt-source" -B "$PANTHEON_INDEPENDENT_DIR/svt-build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF
cmake --build "$PANTHEON_INDEPENDENT_DIR/svt-build" -j 6
cp "$PANTHEON_INDEPENDENT_DIR/svt-source/Bin/Release/SvtAv1EncApp" "$PANTHEON_INDEPENDENT_DIR/SvtAv1EncApp-unmodified"
patch -d "$PANTHEON_INDEPENDENT_DIR/svt-source" -p1 < "$PANTHEON_REPORT/svt-causal.patch"
cmake --build "$PANTHEON_INDEPENDENT_DIR/svt-build" -j 6
cp "$PANTHEON_INDEPENDENT_DIR/svt-source/Bin/Release/SvtAv1EncApp" "$PANTHEON_INDEPENDENT_DIR/SvtAv1EncApp-instrumented"
cc -O2 -Wall -Wextra "$PANTHEON_REPORT/apply_grain.c" -o "$PANTHEON_INDEPENDENT_DIR/apply_grain" $(pkg-config --cflags --libs dav1d)
uv venv --system-site-packages "$PANTHEON_INDEPENDENT_DIR/analysis-venv"
uv pip install --python "$PANTHEON_INDEPENDENT_DIR/analysis-venv/bin/python" scipy matplotlib
export PANTHEON_PY="$PANTHEON_INDEPENDENT_DIR/analysis-venv/bin/python"
```

The combined patch was dry-run checked, applied to pristine files, and all nine resulting files matched the actual build source byte-for-byte. It is disabled without its environment variables. Do not also apply `instrument_svt.py`/`apply_allocation.py` after the combined patch: those are the historical construction scripts. They expect fresh source/backups. Nothing is installed. Binary/build/source hashes are in provenance.json; GCC 13/Release/static was used.

Prepare each case using the established harness, then create raw source/Y4M and copy the selected fixed A picture from the old archive:

```bash
"$PANTHEON_PY" - <<'PY'
import os,sys,pathlib,json,shutil
sys.path.insert(0,os.environ['PANTHEON_REPORT'])
import grain_model as g
x=g.x;old=pathlib.Path(os.environ['PANTHEON_OLD'])
tags={'e04':'nv-fgs-10.0294','e05-1440':'nv-fgs-9.67652','e05-1420':'nv-fgs-9.00141','e05-1460':'nv-fgs-7.77255'}
for case,tag in tags.items():
    d=x.prepare(case)
    x.run(['ffmpeg','-v','error','-threads','4','-i',d/'ref.mkv','-pix_fmt','yuv420p10le','-f','rawvideo',d/'source.yuv'],d,'source-raw')
    x.run(['ffmpeg','-v','error','-threads','4','-i',d/'input.mkv','-pix_fmt','yuv420p10le','-strict','-1','-f','yuv4mpegpipe',d/'input10.y4m'],d,'input-y4m')
    selected=pathlib.Path(json.loads((old/case/(tag+'-selection.json')).read_text())['selected']).name
    shutil.copy2(old/case/selected,d/'fixed-picture.mkv')
    x.run(['ffmpeg','-v','error','-i',d/'fixed-picture.mkv','-c','copy',d/'fixed-picture.ivf'],d,'fixed-ivf')
    for mode,name in [(0,'base'),(1,'existing')]:
        x.decode(d/'fixed-picture.mkv',d/(name+'-decoded.mkv'),96,mode)
        x.run([x.ROOT/'apply_grain',d/'fixed-picture.ivf',d/(name+'.yuv'),mode,96,240],d,name+'-native')
PY
```

Before accepting new results, compare raw native base/existing samples against the corresponding FFmpeg renders, all three planes/all 240 frames, and assert helper logs `base_before_after_exact=240`. Fresh `validity.json` verifies the source, packet PTS, independent extraction hashes and rates. Native decoder agreement is not inferred from matching thumbnails.

For each `CASE` among e04, e05-1440, e05-1420, e05-1460:

```bash
export CASE=e05-1440
"$PANTHEON_PY" "$PANTHEON_REPORT/grain_model.py" collect "$CASE"
"$PANTHEON_PY" "$PANTHEON_REPORT/grain_model.py" fit "$CASE"
"$PANTHEON_INDEPENDENT_DIR/apply_grain" "$PANTHEON_INDEPENDENT_DIR/$CASE/fixed-picture.ivf" "$PANTHEON_INDEPENDENT_DIR/$CASE/calibration.yuv" 2 96 240 "$PANTHEON_INDEPENDENT_DIR/$CASE/calibration-model.txt"
"$PANTHEON_PY" "$PANTHEON_REPORT/grain_model.py" calibrate "$CASE"
"$PANTHEON_INDEPENDENT_DIR/apply_grain" "$PANTHEON_INDEPENDENT_DIR/$CASE/fixed-picture.ivf" "$PANTHEON_INDEPENDENT_DIR/$CASE/model.yuv" 2 96 240 "$PANTHEON_INDEPENDENT_DIR/$CASE/model.txt"
"$PANTHEON_PY" "$PANTHEON_REPORT/evaluate_a.py" "$CASE"
```

After all four, run `chroma_controls.py`, `temporal_audit.py`, and `quiet_crop.py`. A visuals use the previous report's `visuals.main(CASE, ['a-existing','a-model','a-base'])`; rename its comparison/temporal/visuals outputs with the `a-` prefix. Native AV1 AR uses lag3, Q7 coefficients, scaling_shift10, overlap, restricted clipping, independent deterministic seeds, independent chroma lookup and zero chroma/luma AR coupling. Parameter files retain every frame. Source/base PSD subtraction is a modeling assumption, not unique identification of authentic grain. All original-source compression artifacts remain part of the requested reference.

For B, replay the archived baseline and trace command arrays for the two primary cases after replacing the historical scratch prefix with the new root. Baseline command files are `e04/b-baseline-command.json` and `e05-1440/b-baseline-try2-command.json`; trace commands are `CASE/b-trace-command.json`. Baseline requests are 10172/10053 kbps. Common argv:

```text
nice -n 10 taskset -c 0-7 SvtAv1EncApp -i input10.y4m -b OUTPUT.ivf
--preset 4 --tune 0 --rc 1 --tbr REQUEST --lp 1
--film-grain 0 --film-grain-denoise 0 --color-range 0
--color-primaries 1 --transfer-characteristics 1 --matrix-coefficients 1
--progress 0 -o OUTPUT-recon.yuv
```

Use the unmodified binary for baseline, the patched binary for trace, no allocation env in either. For tracing set `PANTHEON_TRACE_DIR=CASE/trace` to a newly created empty directory and leave `PANTHEON_TRACE_IMAGES_OFF` unset. Keep `-o` enabled in both arms so nonreference frames receive the same reconstruction/filter path. Remux IVF to MKV with FFmpeg streamcopy, retaining IVF for exact comparisons. Never reuse a nonempty trace directory: CSVs append. Run through `investigate.run(argv,d,tag)` to save command arrays/durations/logs, including `b-trace-command.json` used by `run_allocation.py`.

Require identical complete baseline/trace IVF. Compare app recon frames 96:336 to independent decoded samples. On the historical E04 run the coefficient-hook correction was a separate byte-identical encode (`b-coeff.ivf`, `coeff-trace/`); current patch emits those coefficients during the main trace. `stage_analysis.py` selects the validated separate directory when present, asserts 240 coefficient files, and is baseline-only.

```bash
"$PANTHEON_PY" "$PANTHEON_REPORT/stage_analysis.py" "$CASE"
"$PANTHEON_PY" "$PANTHEON_REPORT/allocation_map.py" "$CASE"
"$PANTHEON_PY" "$PANTHEON_REPORT/run_allocation.py" "$CASE"
```

For E05 name/copy the chosen baseline reconstruction `b-baseline-recon.yuv`, or retain its `b-baseline-selection.json` with `tag` pointing to the chosen trial. `allocation_map.py` expects that baseline. The map is 336×17×30 signed int8; each entry is 0 or −12. Hooks apply it after initial AQ and after recode resets, before legal delta-q normalization; it is not applied twice to a cumulative qindex. `PANTHEON_ALLOCATION_MAP` selects it; `PANTHEON_TRACE_IMAGES_OFF=1` leaves CSVs without bulky pictures. Calibrate only TBR, measure actual MKV video packets within 1% afterward. Historical selected requests: E04=10037, E05=10247 kbps. E05 required five proportional/bracket attempts, not five quality settings. Final trial argv and env records are archived. Use fresh scratch/tags after any binary/input/map change; the allocation calibration-resume path is for unchanged experiments only.

Score baseline with `investigate.score(CASE, d/'b-trace.mkv', 'b-base', grain=0)` and run the prior `texture.analyze` on that decoded arm. Then `evaluate_b.py CASE` scores the intervention and generates spatial controls/visuals. `stage_audit.py CASE` preserves all-stage hashes/differences and spatially verified qindex maps. `collect_results.py` rebuilds report tables (it writes this report directory). No GPU metric is replaced by a CPU equivalent. CAMBI is supplementary; source/reference files and all result identities are retained. Frame0 is excluded only from VMAF/NEG p1; all other summaries use all 240.

CSV fields, without headers:

| File | Ordered fields |
|---|---|
| `sb-POC-a0-o0.csv` | SB index, origin x/y, SB size, actual SB qindex, frame base_q_idx, final block count |
| `blocks-POC-a0-o0.csv` | SB index, SB origin x/y, leaf origin x/y, width/height, block qindex, SB qindex, skip_coeff, skip_mode |
| `luma_txs-POC-a0-o0.csv` | transform origin x/y, transform width/height, block qindex, EOB, nonzero final quantized levels, sum absolute quantized levels, SB index |

POC is display picture_number; scored frame=POC−96. All captured frames are a0/o0. Qindex is AV1's quantization index, not application QP. EOB is last scan position plus one, not count of nonzeros. Magnitudes/counts are measured at final entropy input, but are **not entropy-coded bits**. Fully contained transform ROI summaries omit crossing transforms and skip-only blocks. No prediction image/prequantized coefficient export was implemented; that causal partition remains unresolved.

Raw stage images are planar 10-bit 4:2:0 little-endian. `original` is before TF; `tf` is after TF's final rendezvous on the frames using that path; `coding_input` is enhanced_pic after TF; `pre_sb_dlf` is a mosaic of freshly reconstructed SBs before their deblock call; `post_dlf` precedes CDEF; `final` follows restoration. Full hashes allow stage identity audit even after reproducible raw frames are retired. Selected diagnostic raw stages and all CSVs are retained. No synthetic arm rewrites encoded picture data. New AV1 signaling bytes remain unknown, not zero.

Reproduction peak was 82 GB, below the 100 GB task budget. At completion, raw source/decoder/Y4M/calibration arrays, build directories, analysis venv and duplicate renders are reproducible and removed; selected encodes, synthesis previews/models, stage samples/hashes, CSVs, commands, metrics and tool binaries are archived. Do not delete the original downloads or either evidence archive.

Native synthesis uses the public [dav1d API](https://videolan.videolan.me/dav1d/dav1d_8h.html), with decoder grain disabled and `dav1d_apply_grain` applied to a borrowed picture plus an isolated frame-header copy. Pixel identity was measured independently; API documentation alone is not the validation.
