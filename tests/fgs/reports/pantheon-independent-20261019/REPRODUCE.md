# Reproduction and evidence map

Run from `/home/bardie/git-repos/NVEnc`. Read the video-quality-testing skill first and recheck jobs, GPU, CPU and mounts. Inputs come from the earlier report's `inputs.json`, but are checked and hashed here. Use **fresh scratch** under `/tmp/downloads/codex-work/`; set `PANTHEON_INDEPENDENT_DIR` to that directory. The default is the original investigation name, now archived. Do not overwrite the archive or reuse its uncompressed paths. Expected peak for this matrix was about 40 GB; preserve the downloads partition's floor.

Build current independent encoder in scratch, never install it:

```bash
git clone --depth 1 --branch v4.2.0 https://gitlab.com/AOMediaCodec/SVT-AV1.git "$PANTHEON_INDEPENDENT_DIR/svt-source"
cmake -S "$PANTHEON_INDEPENDENT_DIR/svt-source" -B "$PANTHEON_INDEPENDENT_DIR/svt-build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF
cmake --build "$PANTHEON_INDEPENDENT_DIR/svt-build" -j 6
```

Expected source commit `9292ec8e32bce26f781f277ec8739b53426c4300`. The app is `svt-source/Bin/Release/SvtAv1EncApp`. Actual compiled binary SHA, compiler, host and versions are in provenance.json; build logs are archived. The production NVEnc binary is only executed, not modified. Its historical source is inspected with `git show f1327e14:<path>`; do not substitute current master.

The driver always uses `campaign.score()`. Its local adapter accepts decoded lossless intermediates, feeds 10-bit Y4M to patched CUDA VMAF c4a085f6, names both HD models, and requests `psnr_cuda`, `ssim_cuda`, `ciede_cuda`, plus supplementary CPU CAMBI. FFVship in pinned image `sha256:570b739a…b0c16` supplies GPU SSIMULACRA2/Butteraugli. The historical run used eight CAMBI workers to bound CPU contention, a deviation from the skill’s requested 16. The final driver uses 16; a fresh E04 check produced identical per-frame metrics with 16 workers. Exact command arrays and durations are retained in every `*-command.json`, with logs beside them. No CPU equivalents of the required CUDA metrics were used.

The CIEDE feature reports `45 - 20 log10(mean DeltaE)`; exact equality gives positive infinity, serialized by VMAF as null. For raw-clean arms, every such frame is proven byte-identical by frame hash before accepting this condition. No other null/nonfinite feature is accepted. `*-exact-ciede-frames.json` records those exceptions. All metric arms contain 240 frames. P1 in the new report uses interpolated percentile over frames 1–239, while the prior report used an order statistic; small P1 differences do not indicate different decoded pictures.

Representative invocations (the script path prefix is repeated here so commands are directly executable):

```bash
python3 tests/fgs/reports/pantheon-independent-20261019/investigate.py prepare e04
python3 tests/fgs/reports/pantheon-independent-20261019/stages.py e04
python3 tests/fgs/reports/pantheon-independent-20261019/investigate.py encode e04 --kind nv --rate 10.02936
python3 tests/fgs/reports/pantheon-independent-20261019/investigate.py encode e04 --kind nv --rate 20.05872
python3 tests/fgs/reports/pantheon-independent-20261019/investigate.py encode e04 --kind svt42 --rate 10.02936
python3 tests/fgs/reports/pantheon-independent-20261019/e05_stages.py e05-1440
python3 tests/fgs/reports/pantheon-independent-20261019/e05_stages.py e05-1460
python3 tests/fgs/reports/pantheon-independent-20261019/e05_stages.py e05-1420
python3 tests/fgs/reports/pantheon-independent-20261019/decoder_check.py
```

The E04 controls use the same `encode` command with these names/extra arguments:

| kind | `--extra` |
|---|---|
| svt42-ac2 | `--ac-bias 2` |
| svt42-loopoff | `--enable-dlf 0 --enable-cdef 0 --enable-restoration 0` |
| svt42-tfoff | `--enable-tf 0` |
| svt42-vb3 | `--enable-variance-boost 1 --variance-boost-strength 3 --variance-octile 4` |
| nv-uhq | `--tune uhq` |
| nv-uhq-tf0 | `--tune uhq --tf-level 0` |
| nv-sourcegop | `--gop-len 9999 --keyfile PATH` |
| nv-fgs | no extra; production bilateral auto analysis enabled |

Use `--extra='--option value ...'` so argparse handles the leading hyphens. All controls target 10.02936 Mbps, with actual rates calibrated by packet size in the scored window. The source-GOP keyfile in the archive lists input indices 41/89/137/185/233/281/329; frame 0 is also necessarily a keyframe. `rate-allocation.json` preserves the original and challenged encode's presentation-ordered packets and within-shot rates.

The old QVBR22 arm is rescored with `investigate.py score e04 --path /media/merged-storage/cold-storage/docker-apps/pantheon-fix-20261019/q22-plain.mkv --tag old-q22`. Its original encode command is in that older archive and can be replayed with the new verified input. A clean/base/final stage comparison uses `--grain 0` only during **decoding of the same FGS encode**, never labels that as an FGS-disabled encode.

To reproduce the exported-stage equivalence, take the selected E04 FGS trial's exact encoder command, replace its input with `clean.y4m`, remove `--av1-film-grain` and `--film-grain-table-out`, and add `--film-grain-table clean.tbl`. Keep all coding settings/requested bitrate identical. Decode both outputs grain-on/off after frame 96; compare all 240 hashes. Exact replay command, hashes and result are in `e04/external-grain-command.json` and `e04/export-internal-equivalence.json`.

`texture.py CASE TAG DECODED_PATH [--base BASE_PATH]` computes all-frame ROI traces, selected-frame full-picture brightness/chroma bins, spatial ACF, temporal residual correlations, strong gradients and color shifts. `visuals.py CASE TAG...` creates common-timestamp native crops and a three-way synchronized preview (source plus first two tags), plus full-frame PNGs and plots. Pillow, NumPy and Matplotlib are required; Matplotlib was installed only in a scratch uv environment. `summarize.py` writes the compact results and metric table from completed arms; do not point it at an incomplete reproduction and overwrite this committed report.

The independent review found that the initial driver could reuse stale tag-based caches on a changed rerun. The final driver fingerprints encode inputs/binaries/options and decoded/scored dependencies, and refuses stale or unverified caches without deleting evidence. A fresh-score/repeat/changed-input smoke check confirms rejection. **The historical run was a fresh first pass**; selected paths/rates were checked by review and its metrics remain valid. Historical artifacts predate the new cache stamps, so use fresh scratch for reproduction.

Archive map:

- `provenance.json`, `decoder-check.json`, `all-frame-alignment.json`, `grain-switches.json`, `cache-validation.json`: cross-case proofs.
- Each case: `validity.json` (probes/packets/three hash sequences), `conversion-check.json`, `*-selection.json`, command arrays/logs, raw metric JSON, texture JSON, grain tables and selected encodes.
- Each case: `comparison-crops.png`, `comparison-synchronized.mkv`, `texture-temporal.png`, and full-frame stills. Preview is 8-bit conversion; source measurements stay 10-bit. No actual display/playback assessment is implied.
- `svt-source.tar.gz`, compiled `SvtAv1EncApp`, build logs and `scripts/`: preserved build and reproduction material. Intermediate lossless clips, raw/Y4M files, indexes, build objects and scratch environments are reproducible and removed after verification.

The source files, production binary, library files, Tdarr configuration and torrent state were never changed. The archive script checks live references before moving this task's evidence to the established cold-storage root.
