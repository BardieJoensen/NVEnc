# Upstream 9.38 merge into the FGS release line, 2026-10-08

Branch `prod/merge-upstream-9.38-20261008`: merge commit f1327e14 = FGS release line
`fix/fgs-clean-source-20261006` (7bdabca9; runtime e78e97f2, release binary 46d6781c) + rigaya
master ce3890cc (tag 9.38, 11 commits after 0b433672). No textual conflicts.

Upstream content: seek/seekto/trim fixes, mpegts seek, KFM progressive output and raw SAR, SSIM > 1.0 on
odd sizes, Linux IO-stats log, docs, and a flush fix (`NVEncCore::Encode`): a task error during flush
now aborts instead of finishing with lost frames. It fires only on errors other than
`RGY_ERR_MORE_DATA`/`RGY_ERR_MORE_BITSTREAM`; the FGS terminal filter's drain path returns
`RGY_ERR_NONE`/`RGY_ERR_MORE_DATA`, so normal drains are unaffected. The MPEG-4 GMC software-decode
fallback in `rgy_input_avcodec.cpp` is unchanged by the merge.

## Build

Pinned clone, gate recipe (`nvenc-fgs-build:cuda13.3-deps`, `-Denable_vmaf=disabled
-Denable_libvship=disabled`): NVEnc 9.38 (r4412), sha256
`b30612f9e8b4b8f20e900a5cec0a64fa77e931b17f39ec83da4163057fce30db`.

## Qualification

- `tests/fgs/run_cpu_tests.sh`: 119 Python tests and all C++ programs pass.
- `local_gate.sh --quick --candidate-nvencc`: 5 passed, 0 failed (incl. lookahead picture order,
  timestamps and drain tails).
- Flow paths (exact flow arguments, binary mounted in the release image; WEB-DL h264 avhw, DV P8 HEVC
  2160p with `--dolby-vision-rpu copy`, HDR10+ with `--dhdr10-info copy`, AVC Blu-ray remux with
  TrueHD/AC3/PGS on avsw and avhw, the remux through `--vpp-rtgmc`, XviD AVI): every packet of every
  stream identical to release 46d6781c on six paths; the avhw remux's video produced the release's
  state in 4 of 5 runs and one other state once, the known two-state variability on that path
  (recorded for d32b6270 on 2026-10-04). Audio, subtitles and stream metadata identical on all paths;
  DV on 326/326 and HDR10+ on 259/259 frames; full libdav1d decodes clean.
- In its own image (`nvenc-fidelity/tdarr-node:2.94.02-f1327e14-20261008`, layered on the 46d6781c
  image because the original base image was deleted from the host on 2026-10-08): WEB-DL, DV and HDR10+
  files byte-identical (all streams) to the release's.

Receipt: `/opt/docker-apps/logs/nvencc-merge-9.38-20261008` (build log, CPU tests, gate log, path
comparison). Not deployed by this work.
